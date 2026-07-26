"""Unit tests for runtime.client — auth headers, error classification, SSE body.

All HTTP via httpx.MockTransport; no real AstrBot required.
"""
from __future__ import annotations

import httpx

from runtime.client import (
    AstrBotClient,
    _build_headers,
    _classify_httpx_error,
    encode_plugin_id,
)
from runtime.config import RuntimeConfig


def _cfg(**over) -> RuntimeConfig:
    base = dict(
        base_url="http://astrbot.test:6185",
        token="",
        auth_mode="api_key",
        timeout=5.0,
        allow_mutations=False,
        allow_chat_probe=False,
        chat_username="",
        chat_config_name="plugin_dev_skill",
    )
    base.update(over)
    return RuntimeConfig(**base)


class TestAuthHeaders:
    def test_no_token_no_auth_headers(self):
        h = _build_headers(_cfg())
        assert "X-API-Key" not in h and "Authorization" not in h

    def test_api_key_default(self):
        h = _build_headers(_cfg(token="tok"))
        assert h["X-API-Key"] == "tok"
        assert "Authorization" not in h

    def test_bearer(self):
        h = _build_headers(_cfg(token="tok", auth_mode="bearer"))
        assert h["Authorization"] == "Bearer tok"
        assert "X-API-Key" not in h

    def test_auto_sends_both(self):
        h = _build_headers(_cfg(token="tok", auth_mode="auto"))
        assert h["X-API-Key"] == "tok"
        assert h["Authorization"] == "Bearer tok"


class TestErrorClassification:
    def test_kinds(self):
        assert _classify_httpx_error(httpx.ConnectTimeout("t"))[0] == "timeout"
        assert _classify_httpx_error(httpx.ConnectError("c"))[0] == "connect"
        assert _classify_httpx_error(ValueError("x"))[0] == "unknown"

    def test_message_never_contains_token(self):
        # invariant: token must not leak through error text
        kind, msg = _classify_httpx_error(httpx.ConnectError("boom"))
        assert "abk_" not in msg


class TestNotConfigured:
    def test_disabled_returns_not_configured_without_network(self):
        client = AstrBotClient(_cfg(base_url=""))
        r = client.get("/api/v1/plugins")
        assert not r.ok
        assert r.error_kind == "not_configured"


def _response_client(resp: httpx.Response) -> AstrBotClient:
    client = AstrBotClient(_cfg())

    def patched_request(method, path, *, params=None, json_body=None, timeout=None):
        transport = httpx.MockTransport(lambda req: resp)
        with httpx.Client(transport=transport) as hc:
            real = hc.request(method.upper(), client._url(path))
        return client._from_response(real)

    client.request = patched_request  # type: ignore[method-assign]
    return client


class TestFromResponse:
    def test_json_ok(self):
        c = _response_client(httpx.Response(200, json={"status": "ok", "data": {}}))
        r = c.get("/api/v1/plugins")
        assert r.ok and r.data["status"] == "ok"

    def test_auth_401_403(self):
        for code in (401, 403):
            c = _response_client(httpx.Response(code, json={}))
            r = c.get("/x")
            assert not r.ok and r.error_kind == "auth"

    def test_http_500(self):
        c = _response_client(httpx.Response(500, text="boom"))
        r = c.get("/x")
        assert not r.ok and r.error_kind == "http_status"

    def test_sse_body_wrapped(self):
        c = _response_client(httpx.Response(200, text='data: {"type": "end"}\n\n'))
        r = c.get("/api/v1/chat")
        assert r.ok
        assert r.data["_sse"] is True
        assert "data:" in r.data["_raw_text"]

    def test_non_json_body_kept_truncated(self):
        c = _response_client(httpx.Response(200, text="<html>hi</html>"))
        r = c.get("/x")
        assert r.ok
        assert r.data["_raw_text"].startswith("<html>")


class TestEncodePluginId:
    def test_plain_and_special(self):
        assert encode_plugin_id("astrbot_plugin_x") == "astrbot_plugin_x"
        assert encode_plugin_id("a/b c") == "a%2Fb%20c"
        assert encode_plugin_id("  x  ") == "x"
        assert encode_plugin_id("") == ""
