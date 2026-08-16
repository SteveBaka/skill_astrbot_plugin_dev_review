"""Unit tests for runtime.tools_logs — strict enablement gate + auth headers.

The MCP-client relay itself is exercised end-to-end in an integration test
(hosts the plugin SSE server on FastAPI and connects via mcp client); here we
cover the pure logic that does not need a live AstrBot.
"""
from __future__ import annotations

import asyncio
import json
import types

from runtime import tools_logs


class TestEnablementGate:
    def test_no_url_disabled(self, monkeypatch):
        monkeypatch.delenv("ASTRBOT_LOG_MCP_URL", raising=False)
        monkeypatch.delenv("ASTRBOT_BASE_URL", raising=False)
        assert tools_logs._log_mcp_url() == ""

    def test_base_url_alone_does_not_enable(self, monkeypatch):
        # Security: the feature is DISABLED unless ASTRBOT_LOG_MCP_URL is set.
        # ASTRBOT_BASE_URL must NOT implicitly enable the log bridge.
        monkeypatch.delenv("ASTRBOT_LOG_MCP_URL", raising=False)
        monkeypatch.setenv("ASTRBOT_BASE_URL", "http://127.0.0.1:6185")
        assert tools_logs._log_mcp_url() == ""

    def test_env_url_enables(self, monkeypatch):
        monkeypatch.setenv("ASTRBOT_LOG_MCP_URL", "http://x:1/custom/sse")
        monkeypatch.setenv("ASTRBOT_BASE_URL", "http://ignored:9999")
        assert tools_logs._log_mcp_url() == "http://x:1/custom/sse"


class TestAuthHeaders:
    def test_no_token_no_api_key(self, monkeypatch):
        monkeypatch.delenv("ASTRBOT_LOG_MCP_TOKEN", raising=False)
        monkeypatch.delenv("ASTRBOT_TOKEN", raising=False)
        assert tools_logs._auth_headers() == {}

    def test_api_key_only(self, monkeypatch):
        monkeypatch.delenv("ASTRBOT_LOG_MCP_TOKEN", raising=False)
        monkeypatch.setenv("ASTRBOT_TOKEN", "api-key-123")
        assert tools_logs._auth_headers() == {"X-API-Key": "api-key-123"}

    def test_shared_token_sent(self, monkeypatch):
        monkeypatch.delenv("ASTRBOT_TOKEN", raising=False)
        monkeypatch.setenv("ASTRBOT_LOG_MCP_TOKEN", "s3cret")
        assert tools_logs._auth_headers() == {"X-MCP-Token": "s3cret"}

    def test_both_headers(self, monkeypatch):
        monkeypatch.setenv("ASTRBOT_TOKEN", "api-key-123")
        monkeypatch.setenv("ASTRBOT_LOG_MCP_TOKEN", "s3cret")
        assert tools_logs._auth_headers() == {
            "X-API-Key": "api-key-123",
            "X-MCP-Token": "s3cret",
        }


class TestExtractText:
    def test_text_blocks(self):
        blocks = [types.SimpleNamespace(type="text", text="hello")]
        assert tools_logs._extract_text(blocks) == ["hello"]

    def test_mixed_and_empty(self):
        blocks = [
            types.SimpleNamespace(type="text", text="a"),
            types.SimpleNamespace(type="image", text=""),
            None,
        ]
        assert tools_logs._extract_text(blocks) == ["a"]

    def test_non_list(self):
        assert tools_logs._extract_text("nope") == []
        assert tools_logs._extract_text(None) == []


class TestRelayToolsReturnJson:
    def test_not_configured_payload(self, monkeypatch):
        monkeypatch.delenv("ASTRBOT_LOG_MCP_URL", raising=False)
        monkeypatch.delenv("ASTRBOT_BASE_URL", raising=False)
        out = json.loads(asyncio.run(tools_logs.astrbot_logs_history(limit=5)))
        assert out["ok"] is False
        assert out["error_kind"] == "not_configured"

    def test_search_not_configured(self, monkeypatch):
        monkeypatch.delenv("ASTRBOT_LOG_MCP_URL", raising=False)
        monkeypatch.delenv("ASTRBOT_BASE_URL", raising=False)
        out = json.loads(asyncio.run(tools_logs.astrbot_logs_search("boom")))
        assert out["error_kind"] == "not_configured"

    def test_search_not_configured_even_with_base_url(self, monkeypatch):
        # base_url alone must NOT enable the log bridge
        monkeypatch.delenv("ASTRBOT_LOG_MCP_URL", raising=False)
        monkeypatch.setenv("ASTRBOT_BASE_URL", "http://127.0.0.1:6185")
        out = json.loads(asyncio.run(tools_logs.astrbot_logs_search("boom")))
        assert out["error_kind"] == "not_configured"
