"""Tests for runtime.register — log bridge tools only register when enabled.

Security invariant: when ASTRBOT_LOG_MCP_URL is unset on the MCP host, the
astrbot_logs_* relay tools MUST NOT be registered (feature disabled; no
connection attempts). When it is set, they MUST be present.
"""
from __future__ import annotations

from runtime import register


class _FakeMCP:
    """Minimal FastMCP stand-in capturing tool names from the @mcp.tool() decorator."""

    def __init__(self) -> None:
        self.tools: dict[str, object] = {}

    def tool(self):
        def decorator(func):
            self.tools[func.__name__] = func
            return func

        return decorator


LOG_TOOL_NAMES = ("astrbot_logs_history", "astrbot_logs_tail", "astrbot_logs_search")


def test_log_tools_not_registered_without_url(monkeypatch):
    monkeypatch.delenv("ASTRBOT_LOG_MCP_URL", raising=False)
    monkeypatch.delenv("ASTRBOT_BASE_URL", raising=False)
    mcp = _FakeMCP()
    register.register_runtime_tools(mcp)
    for name in LOG_TOOL_NAMES:
        assert name not in mcp.tools, f"{name} must be DISABLED without ASTRBOT_LOG_MCP_URL"


def test_log_tools_not_registered_with_base_url_only(monkeypatch):
    # base_url alone must not implicitly enable the log bridge
    monkeypatch.delenv("ASTRBOT_LOG_MCP_URL", raising=False)
    monkeypatch.setenv("ASTRBOT_BASE_URL", "http://127.0.0.1:6185")
    mcp = _FakeMCP()
    register.register_runtime_tools(mcp)
    for name in LOG_TOOL_NAMES:
        assert name not in mcp.tools


def test_log_tools_registered_with_url(monkeypatch):
    monkeypatch.setenv("ASTRBOT_LOG_MCP_URL", "http://127.0.0.1:6185/.../sse")
    mcp = _FakeMCP()
    register.register_runtime_tools(mcp)
    for name in LOG_TOOL_NAMES:
        assert name in mcp.tools, f"{name} must be registered when ASTRBOT_LOG_MCP_URL is set"


def test_non_log_tools_always_registered(monkeypatch):
    monkeypatch.delenv("ASTRBOT_LOG_MCP_URL", raising=False)
    mcp = _FakeMCP()
    register.register_runtime_tools(mcp)
    assert "astrbot_plugin_list" in mcp.tools
    assert "astrbot_runtime_info" in mcp.tools
