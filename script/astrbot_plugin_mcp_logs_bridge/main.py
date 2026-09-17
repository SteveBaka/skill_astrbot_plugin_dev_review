from __future__ import annotations

import asyncio
import gzip
import hmac
import json
import os
import re
import uuid

import anyio
from astrbot.api import logger
from astrbot.api.star import Context, Star
from astrbot.api.web import (
    error_response,
    json_response,
    stream_response,
)
from astrbot.api.web import (
    request as web_request,
)
from mcp.server.lowlevel import Server as McpLowLevelServer
from mcp.shared.message import SessionMessage
from mcp.types import JSONRPCMessage, TextContent, Tool

PLUGIN_NAME = "astrbot_plugin_mcp_logs_bridge"
PLUGIN_VERSION = "0.1.5"
TOKEN_HEADER = "X-MCP-Token"
_TS_RE = re.compile(r"(\d{4}-\d{2}-\d{2})[ T](\d{2}:\d{2}:\d{2})")


class MCPLogsBridge(Star):
    """在 AstrBot 进程内宿主一个 MCP SSE 服务器，同步暴露运行日志。

    数据源优先使用进程内共享的 LogBroker（log_cache 最近 500 条，含
    level/time/data/category），与 Dashboard `/logs/history` 同源。logs_tail /
    logs_search 支持 source="file" 强制读取落盘日志文件（默认
    <data>/logs/astrbot.log，可用插件配置 log_file_path 覆盖）及其同目录轮转
    归档（astrbot.log*，含 .gz），用于捞取超出缓存窗口的多日历史日志；
    logs_search 在 file 源下还支持 since/until 时间范围过滤（按日志行
    '[YYYY-MM-DD HH:MM:SS]' 前缀）。

    安全：除 AstrBot 插件扩展路由自身的 plugin 域 API Key 鉴权外，本插件
    额外支持**双向共享令牌**认证。令牌取值优先级：
      1. 插件配置 `auth_token`（_conf_schema.json）
      2. AstrBot 进程环境变量 `ASTRBOT_LOG_MCP_TOKEN`
    客户端（MCP 宿主机）必须在请求头携带 `X-MCP-Token: <相同令牌>`，否则
    SSE / messages 端点一律返回 401。两者皆未配置时跳过令牌校验（此时仍受
    plugin 域 API Key 保护，但不推荐仅依赖它）。
    """

    def __init__(self, context: Context, config: dict | None = None):
        super().__init__(context)
        self.config = config or {}
        self._broker = None
        self._sessions = {}
        self._mcp = self._build_mcp_server()

        if not self.config.get("enable_bridge", True):
            logger.warning("MCP Logs Bridge 已按配置 enable_bridge=false 关闭，未注册 SSE 端点")
            return
        context.register_web_api(
            f"/{PLUGIN_NAME}/sse",
            self._handle_sse,
            ["GET"],
            "MCP SSE log stream",
        )
        context.register_web_api(
            f"/{PLUGIN_NAME}/messages",
            self._handle_message,
            ["POST"],
            "MCP JSON-RPC message endpoint",
        )

    def _resolve_token(self) -> str:
        """共享令牌：配置 auth_token 优先，其次 AstrBot 进程环境变量。"""
        configured = str((self.config or {}).get("auth_token") or "").strip()
        if configured:
            return configured
        return (os.environ.get("ASTRBOT_LOG_MCP_TOKEN") or "").strip()

    def _check_token(self) -> str | None:
        """校验 X-MCP-Token。无令牌配置 → 跳过；缺失/不匹配 → 返回 401 文案。"""
        expected = self._resolve_token()
        if not expected:
            return None
        provided = (web_request.headers.get(TOKEN_HEADER) or "").strip()
        if provided and hmac.compare_digest(provided, expected):
            return None
        return f"missing or invalid {TOKEN_HEADER}"

    async def initialize(self):
        logger.info(
            "MCP Logs Bridge 已加载，SSE 端点: /api/v1/plugins/extensions/%s/sse",
            PLUGIN_NAME,
        )

    async def terminate(self):
        for writer in self._sessions.values():
            await writer.aclose()
        self._sessions.clear()

    # ── data source ────────────────────────────────────────────

    def _resolve_broker(self):
        if self._broker is not None:
            return self._broker
        try:
            pr = web_request._get_current()
            lifecycle = pr._request.app.state.core_lifecycle
            broker = getattr(lifecycle, "log_broker", None)
            if broker is not None:
                self._broker = broker
                return broker
        except Exception:
            pass
        try:
            from astrbot.core import LogManager

            broker = getattr(LogManager, "_log_broker", None)
            if broker is not None:
                self._broker = broker
                return broker
        except Exception:
            pass
        return None

    def _default_log_path(self):
        try:
            from astrbot.core.utils.astrbot_path import get_astrbot_data_path

            return os.path.join(get_astrbot_data_path(), "logs", "astrbot.log")
        except Exception:
            return ""

    def _resolve_log_path(self) -> str:
        """与 AstrBot 本体 log_file_path 语义一致（log.py:_resolve_log_path）。

        空 → <data>/logs/astrbot.log；绝对路径 → 原样；相对路径 → <data>/<path>。
        """
        configured = str((self.config or {}).get("log_file_path") or "").strip()
        if not configured:
            return self._default_log_path()
        if os.path.isabs(configured):
            return configured
        try:
            from astrbot.core.utils.astrbot_path import get_astrbot_data_path

            return os.path.join(get_astrbot_data_path(), configured)
        except Exception:
            return configured

    def _read_file_lines(self, path: str) -> list[str]:
        """读取单个日志文件全部行；.gz 自动解压；不可读返回空。"""
        try:
            opener = gzip.open if path.endswith(".gz") else open
            with opener(path, "rt", encoding="utf-8", errors="ignore") as f:
                return f.readlines()
        except OSError:
            return []

    def _log_file_candidates(self) -> list[str]:
        """日志文件候选列表（含轮转），按新→旧排序。

        当前文件优先；轮转文件取同目录 `astrbot.log*`（覆盖 RotatingFileHandler
        的 .1/.2 与 TimedRotatingFileHandler 的 .2026-08-28 后缀及 .gz 压缩），
        按修改时间降序。"""
        base = self._resolve_log_path()
        if not base:
            return []
        import glob as _glob

        seen: set[str] = set()
        candidates: list[str] = []
        for p in [base, *_glob.glob(base + "*")]:
            rp = os.path.realpath(p)
            if rp in seen or not os.path.isfile(rp):
                continue
            seen.add(rp)
            candidates.append(rp)
        candidates[1:] = sorted(candidates[1:], key=lambda p: os.path.getmtime(p), reverse=True)
        return candidates

    def _read_file_tail(self, lines: int) -> list[str]:
        """跨当前文件与轮转文件取最后 N 行（按时间正序）。"""
        remaining = max(1, lines)
        chunks: list[list[str]] = []  # 旧 → 新组装
        for path in self._log_file_candidates():
            if remaining <= 0:
                break
            file_lines = self._read_file_lines(path)
            if not file_lines:
                continue
            take = file_lines[-remaining:]
            chunks.insert(0, take)
            remaining -= len(take)
        return [ln for chunk in chunks for ln in chunk]

    # ── MCP server ─────────────────────────────────────────────

    def _build_mcp_server(self):
        server = McpLowLevelServer(PLUGIN_NAME, version=PLUGIN_VERSION)

        @server.list_tools()
        async def list_tools():
            return [
                Tool(
                    name="logs_history",
                    description=(
                        "Synchronously return recent AstrBot runtime logs. "
                        "Reads the in-process LogBroker cache (last 500 entries), "
                        "same source as the Dashboard /logs/history. "
                        "Returns newest-first. Filters: level (INFO/WARNING/ERROR/...), "
                        "keyword (substring in the log text), category."
                    ),
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "limit": {
                                "type": "integer",
                                "description": "max entries",
                                "default": 100,
                            },
                            "level": {
                                "type": "string",
                                "description": "exact level, case-insensitive",
                                "default": "",
                            },
                            "keyword": {
                                "type": "string",
                                "description": "substring in log text",
                                "default": "",
                            },
                            "category": {
                                "type": "string",
                                "description": "log category",
                                "default": "",
                            },
                        },
                    },
                ),
                Tool(
                    name="logs_tail",
                    description=(
                        "Tail the last N log lines. source=auto (default): LogBroker "
                        "cache (last 500 entries); source=file: read the log file "
                        "(<data>/logs/astrbot.log, or plugin config log_file_path) "
                        "and its rotated archives (astrbot.log*) when the current "
                        "file has fewer lines — use it for entries older than the "
                        "cache. level filter is case-insensitive."
                    ),
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "lines": {
                                "type": "integer",
                                "description": "number of lines",
                                "default": 50,
                            },
                            "level": {
                                "type": "string",
                                "description": "exact level, case-insensitive",
                                "default": "",
                            },
                            "source": {
                                "type": "string",
                                "description": '"auto" (default, cache first) or "file" (force log file)',
                                "default": "auto",
                            },
                        },
                    },
                ),
                Tool(
                    name="logs_search",
                    description=(
                        "Search logs for a keyword (case-insensitive), optional level "
                        "filter. source=auto (default): in-process LogBroker cache "
                        "(last 500 entries). source=file: line-by-line search of the "
                        "log file (<data>/logs/astrbot.log, or plugin config "
                        "log_file_path) AND its rotated archives (astrbot.log*, "
                        ".gz supported), newest file first — use it for multi-day "
                        "history beyond the cache; optional since/until filter on "
                        "the '[YYYY-MM-DD HH:MM:SS]' timestamp prefix ('YYYY-MM-DD' "
                        "or 'YYYY-MM-DD HH:MM:SS', inclusive). Returns newest-first "
                        "matching lines up to limit."
                    ),
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "keyword": {
                                "type": "string",
                                "description": "required substring to match",
                            },
                            "level": {
                                "type": "string",
                                "description": "exact level, case-insensitive",
                                "default": "",
                            },
                            "limit": {
                                "type": "integer",
                                "description": "max entries",
                                "default": 100,
                            },
                            "source": {
                                "type": "string",
                                "description": '"auto" (default, cache) or "file" (search log file)',
                                "default": "auto",
                            },
                            "since": {
                                "type": "string",
                                "description": "inclusive start time, 'YYYY-MM-DD' or 'YYYY-MM-DD HH:MM:SS' (file source)",
                                "default": "",
                            },
                            "until": {
                                "type": "string",
                                "description": "inclusive end time, 'YYYY-MM-DD' or 'YYYY-MM-DD HH:MM:SS' (file source)",
                                "default": "",
                            },
                        },
                        "required": ["keyword"],
                    },
                ),
            ]

        @server.call_tool()
        async def call_tool(name: str, arguments: dict):
            if name == "logs_history":
                result = self._tool_history(arguments)
            elif name == "logs_tail":
                result = self._tool_tail(arguments)
            elif name == "logs_search":
                result = self._tool_search(arguments)
            else:
                result = {"error": f"unknown tool: {name}"}
            return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False, indent=2))]

        return server

    # ── tool implementations ────────────────────────────────────

    def _iter_cache(self):
        broker = self._resolve_broker()
        if broker is None:
            return []
        try:
            return list(broker.log_cache)
        except Exception:
            return []

    def _filter(self, entries, level="", keyword="", category=""):
        level = (level or "").strip().upper()
        keyword = (keyword or "").strip().lower()
        category = (category or "").strip()
        out = []
        for e in reversed(entries):
            if level and str(e.get("level", "")).upper() != level:
                continue
            if keyword and keyword not in str(e.get("data", "")).lower():
                continue
            if category and str(e.get("category", "")) != category:
                continue
            out.append(e)
        return out

    def _tool_history(self, arguments):
        limit = int(arguments.get("limit") or self.config.get("history_limit") or 100)
        entries = self._filter(
            self._iter_cache(),
            level=arguments.get("level", ""),
            keyword=arguments.get("keyword", ""),
            category=arguments.get("category", ""),
        )
        return {
            "logs": entries[:limit],
            "total": len(entries[:limit]),
            "source": "broker",
        }

    def _tool_tail(self, arguments):
        lines = int(arguments.get("lines") or 50)
        level = (arguments.get("level", "") or "").strip().upper()
        source = (arguments.get("source", "") or "auto").strip().lower()
        if source != "file" and self._resolve_broker() is not None:
            entries = self._filter(self._iter_cache(), level=level)
            return {"lines": entries[:lines], "source": "broker"}
        raw = self._read_file_tail(lines)
        if level:
            raw = [ln for ln in raw if self._level_tag_in_line(level, ln.upper())]
        return {"lines": [ln.rstrip("\n") for ln in raw[-lines:]], "source": "file"}

    @staticmethod
    def _normalize_time_bound(value: str, end: bool) -> str:
        """'YYYY-MM-DD' → 当日 00:00:00 / 23:59:59；完整时间原样返回；非法返回 ''。

        返回值与日志时间戳同为 'YYYY-MM-DD HH:MM:SS' 字符串，可直接按字典序比较。
        """
        value = (value or "").strip()
        m = _TS_RE.search(value)
        if m:
            return f"{m.group(1)} {m.group(2)}"
        m = re.fullmatch(r"(\d{4}-\d{2}-\d{2})", value)
        if m:
            return f"{m.group(1)} {'23:59:59' if end else '00:00:00'}"
        return ""

    def _in_time_range(self, text: str, since: str, until: str) -> bool:
        """按日志文本中的时间戳做 inclusive 范围过滤；无时间戳的行在启用过滤时剔除。"""
        if not since and not until:
            return True
        m = _TS_RE.search(text)
        if not m:
            return False
        ts = f"{m.group(1)} {m.group(2)}"
        if since and ts < since:
            return False
        if until and ts > until:
            return False
        return True

    _LEVEL_ABBREV = {
        "DEBUG": "DBUG",
        "ERROR": "ERRO",
        "WARNING": "WARN",
        "CRITICAL": "CRIT",
    }

    @classmethod
    def _level_tag_in_line(cls, level: str, line_upper: str) -> bool:
        """文件行级别匹配：AstrBot 落盘标签是缩写（[ERRO]/[DBUG]/[WARN]），
        同时兼容完整写法（[ERROR]/[DEBUG]/[WARNING]）。"""
        abbrev = cls._LEVEL_ABBREV.get(level, level[:4])
        return f"[{level}]" in line_upper or f"[{abbrev}]" in line_upper

    def _search_file(
        self, keyword: str, level: str, since: str, until: str, limit: int
    ) -> list[str]:
        """跨当前文件与轮转文件逐行扫描，返回最新 limit 条命中（最新在前）。

        文件按新→旧遍历（跨文件正确排序）；文件内按行序升序扫描后反转。
        凑满 limit 即提前停止，避免为截断结果而扫描更老的归档。"""
        limit = max(1, limit)
        matched: list[str] = []
        keyword = keyword.lower()
        for path in self._log_file_candidates():
            try:
                opener = gzip.open if path.endswith(".gz") else open
                file_hits: list[str] = []
                with opener(path, "rt", encoding="utf-8", errors="ignore") as f:
                    for ln in f:
                        if keyword and keyword not in ln.lower():
                            continue
                        if level and not self._level_tag_in_line(level, ln.upper()):
                            continue
                        if not self._in_time_range(ln, since, until):
                            continue
                        file_hits.append(ln.rstrip("\n"))
            except OSError:
                continue
            for ln in reversed(file_hits):
                matched.append(ln)
                if len(matched) >= limit:
                    return matched
        return matched

    def _tool_search(self, arguments):
        keyword = (arguments.get("keyword", "") or "").strip()
        level = (arguments.get("level", "") or "").strip().upper()
        limit = int(arguments.get("limit") or self.config.get("search_limit") or 100)
        source = (arguments.get("source", "") or "auto").strip().lower()
        since = self._normalize_time_bound(arguments.get("since", ""), end=False)
        until = self._normalize_time_bound(arguments.get("until", ""), end=True)
        if source == "file" or (since or until):
            # 时间过滤需要逐行时间戳，仅文件源可靠提供；指定 since/until 即隐含 file 源
            logs = self._search_file(keyword, level, since, until, limit)
            return {
                "keyword": keyword,
                "logs": logs,
                "total": len(logs),
                "source": "file",
            }
        entries = self._filter(
            self._iter_cache(),
            level=level,
            keyword=keyword,
        )
        return {
            "keyword": keyword,
            "logs": entries[:limit],
            "total": len(entries[:limit]),
            "source": "broker",
        }

    # ── SSE transport bridge ────────────────────────────────────

    async def _handle_sse(self, **path_values):
        token_error = self._check_token()
        if token_error:
            return error_response(token_error, status_code=401)
        self._resolve_broker()
        request_path = web_request.path or ""
        messages_url = request_path.rsplit("/sse", 1)[0] + "/messages"
        session_id = uuid.uuid4()

        read_writer, read_reader = anyio.create_memory_object_stream(0)
        write_writer, write_reader = anyio.create_memory_object_stream(0)
        self._sessions[session_id] = read_writer

        init_opts = self._mcp.create_initialization_options()

        async def run_server():
            try:
                await self._mcp.run(read_reader, write_writer, init_opts)
            except Exception as exc:
                logger.error("MCP logs bridge server error: %s", exc)
            finally:
                await read_reader.aclose()
                await write_writer.aclose()

        task = asyncio.create_task(run_server())

        async def sse_gen():
            try:
                yield f"event: endpoint\ndata: {messages_url}?session_id={session_id.hex}\n\n"
                async with write_reader:
                    async for msg in write_reader:
                        payload = msg.message.model_dump_json(by_alias=True, exclude_none=True)
                        yield f"event: message\ndata: {payload}\n\n"
            finally:
                self._sessions.pop(session_id, None)
                await read_writer.aclose()
                task.cancel()

        return stream_response(
            sse_gen(),
            content_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
        )

    async def _handle_message(self, **path_values):
        token_error = self._check_token()
        if token_error:
            return error_response(token_error, status_code=401)
        q = web_request.query
        session_id_str = q.get("session_id") or q.get("sessionId")
        if not session_id_str:
            return error_response("session_id is required", status_code=400)
        try:
            session_id = uuid.UUID(hex=session_id_str)
        except ValueError:
            return error_response("invalid session_id", status_code=400)
        writer = self._sessions.get(session_id)
        if writer is None:
            return error_response("session not found", status_code=404)
        body = await web_request.body()
        try:
            message = JSONRPCMessage.model_validate_json(body)
        except Exception as exc:
            return error_response(f"invalid JSON-RPC: {exc}", status_code=400)
        await writer.send(SessionMessage(message))
        return json_response({"status": "accepted"}, status_code=202)
