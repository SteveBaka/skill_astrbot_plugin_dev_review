# [RUNTIME P1] MCP-client relay to astrbot_plugin_mcp_logs_bridge (SSE logs).
"""
Fetches AstrBot runtime logs **via MCP** from the plugin-hosted SSE server.

Why a relay:
  - The public OpenAPI has NO API-key-accessible log endpoint (dashboard
    /logs/history + /logs/live need the `system` scope, not grantable to keys).
  - astrbot_plugin_mcp_logs_bridge hosts an MCP SSE server inside the AstrBot
    process and reads the shared in-process LogBroker (same source as the
    Dashboard /logs/history).
  - These tools act as an MCP **client** (mcp.client.sse.sse_client), connect to
    the plugin SSE endpoint, and relay tool results back synchronously.

ENABLEMENT (strict):
  The feature is **disabled unless ASTRBOT_LOG_MCP_URL is explicitly set** on the
  MCP host. When unset, the relay tools are NOT registered (see
  runtime/register.py) and `_log_mcp_url()` returns "" — no connection attempt.

Env (MCP host):
  ASTRBOT_LOG_MCP_URL     REQUIRED to enable. SSE endpoint of the plugin, e.g.
                          http://<astrbot>:6185/api/v1/plugins/extensions/
                          astrbot_plugin_mcp_logs_bridge/sse
  ASTRBOT_LOG_MCP_TOKEN   Optional shared secret; sent as `X-MCP-Token`. The
                          plugin only accepts requests carrying the SAME value
                          (from its `auth_token` config or the ASTRBOT_LOG_MCP_TOKEN
                          env inside AstrBot). Set it on BOTH sides to avoid
                          accidentally talking to the wrong bridge.
  ASTRBOT_TOKEN           Optional AstrBot API key; sent as X-API-Key (plugin
                          scope) when set.
  ASTRBOT_LOG_MCP_TIMEOUT  seconds, default 15 (SSE read timeout inside a call).

Privacy: tools return log text only (no configs/secrets); the relay is read-only.
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List

from .config import load_config

TOKEN_HEADER = "X-MCP-Token"


def _log_mcp_url() -> str:
    """SSE endpoint. Empty string → feature disabled (do not connect)."""
    return (os.environ.get("ASTRBOT_LOG_MCP_URL") or "").strip()


def _not_configured() -> Dict[str, Any]:
    return {
        "ok": False,
        "error_kind": "not_configured",
        "hint": (
            "Set ASTRBOT_LOG_MCP_URL to the plugin SSE endpoint "
            "(http://<astrbot>:6185/api/v1/plugins/extensions/"
            "astrbot_plugin_mcp_logs_bridge/sse), install + enable "
            "astrbot_plugin_mcp_logs_bridge on AstrBot, then restart the MCP "
            "server. If the plugin requires a shared token, also set "
            "ASTRBOT_LOG_MCP_TOKEN on the MCP host (must equal the plugin's "
            "auth_token / ASTRBOT_LOG_MCP_TOKEN inside AstrBot)."
        ),
    }


def _auth_headers() -> Dict[str, str]:
    """Headers sent to the plugin: X-API-Key (optional) + X-MCP-Token (shared)."""
    headers: Dict[str, str] = {}
    cfg = load_config()
    if cfg.token:
        headers["X-API-Key"] = cfg.token
    token = (os.environ.get("ASTRBOT_LOG_MCP_TOKEN") or "").strip()
    if token:
        headers[TOKEN_HEADER] = token
    return headers


def _extract_text(content: Any) -> List[str]:
    """Flatten CallToolResult.content into TextContent texts."""
    out: List[str] = []
    if not isinstance(content, (list, tuple)):
        return out
    for block in content:
        if block is None:
            continue
        kind = getattr(block, "type", None) or ""
        if kind == "text":
            out.append(getattr(block, "text", "") or "")
    return out


async def _call_plugin_tool(tool_name: str, args: Dict[str, Any]) -> Dict[str, Any]:
    """Open an SSE session to the plugin and call one MCP tool synchronously."""
    url = _log_mcp_url()
    if not url:
        return _not_configured()

    headers = _auth_headers()
    timeout = float(os.environ.get("ASTRBOT_LOG_MCP_TIMEOUT", "15") or 15)
    if timeout <= 0:
        timeout = 15

    try:
        from mcp import ClientSession
        from mcp.client.sse import sse_client
    except Exception as exc:  # pragma: no cover — env missing mcp client
        return {
            "ok": False,
            "error_kind": "missing_dependency",
            "error": f"mcp client not importable on MCP host: {exc}",
            "hint": "Install mcp>=1.8.0 in the MCP server venv.",
        }

    try:
        async with sse_client(url, headers=headers, timeout=timeout) as (
            read_stream,
            write_stream,
        ):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                result = await session.call_tool(tool_name, args)
                texts = _extract_text(result.content)
                payload = None
                if texts:
                    try:
                        payload = json.loads(texts[0])
                    except Exception:
                        payload = texts[0]
                return {
                    "ok": not getattr(result, "isError", False),
                    "tool": tool_name,
                    "content": texts,
                    "payload": payload,
                    "error": None,
                }
    except Exception as exc:
        return {
            "ok": False,
            "error_kind": "mcp_call_error",
            "tool": tool_name,
            "error": str(exc),
            "hint": (
                "Check ASTRBOT_LOG_MCP_URL reachability, that the plugin is "
                "enabled, that ASTRBOT_TOKEN has plugin scope, and that "
                "ASTRBOT_LOG_MCP_TOKEN matches the plugin's auth_token."
            ),
        }


async def astrbot_logs_history(
    limit: int = 100, level: str = "", keyword: str = "", category: str = ""
) -> str:
    """[RUNTIME P1] Recent AstrBot logs via MCP (plugin log bridge, read-only).

    Reads the in-process LogBroker cache (last 500 entries, same source as
    Dashboard /logs/history) through astrbot_plugin_mcp_logs_bridge over MCP.
    Filters: level (INFO/WARNING/ERROR/...), keyword (substring), category.

    ENABLED ONLY when ASTRBOT_LOG_MCP_URL is set (relay tools are not registered
    otherwise). If the plugin requires a shared token, set ASTRBOT_LOG_MCP_TOKEN
    on the MCP host (sent as X-MCP-Token; must equal the plugin's auth_token).
    """
    args: Dict[str, Any] = {"limit": limit}
    if level:
        args["level"] = level
    if keyword:
        args["keyword"] = keyword
    if category:
        args["category"] = category
    return json.dumps(await _call_plugin_tool("logs_history", args), ensure_ascii=False, indent=2)


async def astrbot_logs_tail(lines: int = 50, level: str = "") -> str:
    """[RUNTIME P1] Tail last N AstrBot log lines via MCP (read-only).

    Prefers the in-process LogBroker cache; falls back to the log file when the
    plugin resolves it. Enabled only when ASTRBOT_LOG_MCP_URL is set.
    """
    args: Dict[str, Any] = {"lines": lines}
    if level:
        args["level"] = level
    return json.dumps(await _call_plugin_tool("logs_tail", args), ensure_ascii=False, indent=2)


async def astrbot_logs_search(keyword: str, level: str = "", limit: int = 100) -> str:
    """[RUNTIME P1] Search recent AstrBot logs for a keyword via MCP (read-only).

    Case-insensitive substring search over the in-process LogBroker cache through
    astrbot_plugin_mcp_logs_bridge. Enabled only when ASTRBOT_LOG_MCP_URL is set.
    """
    args: Dict[str, Any] = {"keyword": keyword, "limit": limit}
    if level:
        args["level"] = level
    return json.dumps(await _call_plugin_tool("logs_search", args), ensure_ascii=False, indent=2)
