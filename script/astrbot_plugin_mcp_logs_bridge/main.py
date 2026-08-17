import asyncio
import hmac
import json
import os
import uuid

import anyio
from astrbot.api import logger
from astrbot.api.star import Context, Star
from astrbot.api.web import (
    error_response,
    json_response,
    request as web_request,
    stream_response,
)
from mcp.server.lowlevel import Server as McpLowLevelServer
from mcp.shared.message import SessionMessage
from mcp.types import JSONRPCMessage, TextContent, Tool

PLUGIN_NAME = "astrbot_plugin_mcp_logs_bridge"
TOKEN_HEADER = "X-MCP-Token"


class MCPLogsBridge(Star):
    """在 AstrBot 进程内宿主一个 MCP SSE 服务器，同步暴露运行日志。

    数据源优先使用进程内共享的 LogBroker（log_cache 最近 500 条，含
    level/time/data/category），与 Dashboard `/logs/history` 同源；不可用时
    回退读取日志文件尾部。

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
        logger.info("MCP Logs Bridge 已加载，SSE 端点: /api/v1/plugins/extensions/%s/sse", PLUGIN_NAME)

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

    def _read_file_tail(self, lines: int) -> list[str]:
        path = self._resolve_log_path()
        if not path or not os.path.isfile(path):
            return []
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                return f.readlines()[-lines:]
        except OSError:
            return []

    # ── MCP server ─────────────────────────────────────────────

    def _build_mcp_server(self):
        server = McpLowLevelServer(PLUGIN_NAME, version="0.1.0")

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
                            "limit": {"type": "integer", "description": "max entries", "default": 100},
                            "level": {"type": "string", "description": "exact level, case-insensitive", "default": ""},
                            "keyword": {"type": "string", "description": "substring in log text", "default": ""},
                            "category": {"type": "string", "description": "log category", "default": ""},
                        },
                    },
                ),
                Tool(
                    name="logs_tail",
                    description=(
                        "Tail the last N log lines. Prefers LogBroker cache; falls back "
                        "to reading the log file (<data>/logs/astrbot.log) when file "
                        "logging is enabled. level filter is case-insensitive."
                    ),
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "lines": {"type": "integer", "description": "number of lines", "default": 50},
                            "level": {"type": "string", "description": "exact level, case-insensitive", "default": ""},
                        },
                    },
                ),
                Tool(
                    name="logs_search",
                    description=(
                        "Search recent logs for a keyword (case-insensitive) within the "
                        "in-process LogBroker cache, optional level filter. Returns "
                        "newest-first matching entries."
                    ),
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "keyword": {"type": "string", "description": "required substring to match"},
                            "level": {"type": "string", "description": "exact level, case-insensitive", "default": ""},
                            "limit": {"type": "integer", "description": "max entries", "default": 100},
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
        return {"logs": entries[:limit], "total": len(entries[:limit]), "source": "broker"}

    def _tool_tail(self, arguments):
        lines = int(arguments.get("lines") or 50)
        level = (arguments.get("level", "") or "").strip().upper()
        if self._resolve_broker() is not None:
            entries = self._filter(self._iter_cache(), level=level)
            return {"lines": entries[:lines], "source": "broker"}
        raw = self._read_file_tail(lines)
        if level:
            raw = [ln for ln in raw if f"[{level}]" in ln.upper()]
        return {"lines": [ln.rstrip("\n") for ln in raw[-lines:]], "source": "file"}

    def _tool_search(self, arguments):
        keyword = (arguments.get("keyword", "") or "").strip()
        limit = int(arguments.get("limit") or self.config.get("search_limit") or 100)
        entries = self._filter(
            self._iter_cache(),
            level=arguments.get("level", ""),
            keyword=keyword,
        )
        return {"keyword": keyword, "logs": entries[:limit], "total": len(entries[:limit]), "source": "broker"}

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
