"""Unit tests for runtime.tools_chat — SSE parsing, scope gate, session policy.

HTTP layer is exercised with httpx.MockTransport (no real AstrBot needed).
"""
from __future__ import annotations

import json

import httpx
import pytest

from runtime import tools_chat
from runtime.client import AstrBotClient
from runtime.config import load_config
from runtime.tools_chat import (
    _is_webchat_session,
    parse_sse_events,
    summarize_chat_events,
)

# ── webchat hard-scope filter (privacy invariant) ──────────────


class TestWebchatScopeFilter:
    def test_platform_id_webchat(self):
        assert _is_webchat_session({"platform_id": "webchat"})
        assert _is_webchat_session({"platform_id": " WebChat "})

    def test_umo_string_forms(self):
        assert _is_webchat_session(
            {"session_id": "webchat:FriendMessage:webchat!user!326b11bd"}
        )
        assert _is_webchat_session({"umo": "webchat:FriendMessage:webchat!u!x"})
        assert _is_webchat_session({"id": "webchat!u!x"})

    def test_other_platforms_rejected(self):
        # PRIVACY: real conversations must never be classified as webchat
        assert not _is_webchat_session({"platform_id": "aiocqhttp"})
        assert not _is_webchat_session({"platform_id": "telegram"})
        assert not _is_webchat_session(
            {"session_id": "aiocqhttp:FriendMessage:12345"}
        )
        assert not _is_webchat_session({"session_id": "326b11bd-3337-49f5"})
        assert not _is_webchat_session({})


# ── SSE parsing ────────────────────────────────────────────────


class TestParseSse:
    def test_multi_event_stream(self):
        raw = (
            'data: {"type": "session_id", "data": "mcp-smoke-u"}\n\n'
            'data: {"type": "plain", "data": "pong"}\n\n'
            'data: {"type": "end"}\n\n'
        )
        events = parse_sse_events(raw)
        assert [e["type"] for e in events] == ["session_id", "plain", "end"]

    def test_crlf_and_empty(self):
        assert parse_sse_events("") == []
        events = parse_sse_events('data: {"type": "end"}\r\n\r\n')
        assert events == [{"type": "end"}]

    def test_unparseable_payload_kept_truncated(self):
        events = parse_sse_events("data: not-json\n\n")
        assert events[0]["type"] == "_unparsed"

    def test_bare_json_block(self):
        events = parse_sse_events('{"type": "plain", "data": "x"}')
        assert events[0]["type"] == "plain"


class TestSummarize:
    def test_full_flow_summary(self):
        events = [
            {"type": "session_id", "data": "mcp-smoke-u"},
            {"type": "user_message_saved"},
            {"type": "plain", "data": "hello"},
            {"type": "record", "data": "[RECORD]x.wav"},
            {"type": "attachment_saved", "data": {"id": "a1", "type": "record"}},
            {"type": "end"},
        ]
        s = summarize_chat_events(events)
        assert s["session_id"] == "mcp-smoke-u"
        assert s["plain_texts"] == ["hello"]
        assert s["records"] == ["[RECORD]x.wav"]
        assert len(s["attachments"]) == 1
        assert s["ended"] is True
        assert s["errors"] == []

    def test_plain_truncated(self):
        s = summarize_chat_events(
            [{"type": "plain", "data": "x" * 2000}], text_limit=100
        )
        assert len(s["plain_texts"][0]) == 101  # 100 + ellipsis

    def test_error_events_collected(self):
        s = summarize_chat_events([{"type": "error", "data": "boom"}])
        assert s["errors"] == ["boom"]


# ── probe gates (no network unless allowed + configured) ──────


class TestProbeGates:
    def test_blocked_without_confirm(self):
        r = json.loads(tools_chat.astrbot_chat_probe("hi"))
        assert r["error_kind"] == "chat_probe_disabled"

    def test_env_allow_bypasses_confirm(self, monkeypatch):
        monkeypatch.setenv("ASTRBOT_ALLOW_CHAT_PROBE", "true")
        # passes gate, then fails on missing message/username — not on gate
        r = json.loads(tools_chat.astrbot_chat_probe("hi"))
        assert r["error_kind"] == "bad_request"  # username missing

    def test_empty_message_rejected(self):
        r = json.loads(tools_chat.astrbot_chat_probe("   ", confirm_probe=True))
        assert r["error_kind"] == "bad_request"

    def test_username_required(self):
        r = json.loads(tools_chat.astrbot_chat_probe("hi", confirm_probe=True))
        assert r["error_kind"] == "bad_request"
        assert "username" in r["error"]


class TestCleanupGates:
    def test_mutations_gate_first(self):
        r = json.loads(tools_chat.astrbot_chat_sessions_cleanup("id1", username="u"))
        assert r["error_kind"] == "mutations_disabled"

    def test_confirm_required(self, monkeypatch):
        monkeypatch.setenv("ASTRBOT_ALLOW_MUTATIONS", "true")
        r = json.loads(tools_chat.astrbot_chat_sessions_cleanup("id1", username="u"))
        assert r["error_kind"] == "confirm_required"

    def test_username_required(self, monkeypatch):
        monkeypatch.setenv("ASTRBOT_ALLOW_MUTATIONS", "true")
        r = json.loads(
            tools_chat.astrbot_chat_sessions_cleanup("id1", confirm_cleanup=True)
        )
        assert r["error_kind"] == "bad_request"

    def test_no_ids_no_flag_rejected(self, monkeypatch):
        monkeypatch.setenv("ASTRBOT_ALLOW_MUTATIONS", "true")
        r = json.loads(
            tools_chat.astrbot_chat_sessions_cleanup(
                "", username="u", confirm_cleanup=True
            )
        )
        assert r["error_kind"] == "bad_request"


# ── session policy (Plan B fixed smoke session) ────────────────


def _mock_client(handler) -> AstrBotClient:
    """AstrBotClient whose httpx calls hit a MockTransport."""
    client = AstrBotClient(load_config())

    def patched_request(method, path, *, params=None, json_body=None, timeout=None):
        transport = httpx.MockTransport(handler)
        url = client._url(path)
        with httpx.Client(transport=transport) as hc:
            resp = hc.request(method.upper(), url, params=params, json=json_body)
        return client._from_response(resp)

    client.request = patched_request  # type: ignore[method-assign]
    return client


class TestSessionPolicy:
    @pytest.fixture
    def env(self, monkeypatch):
        monkeypatch.setenv("ASTRBOT_BASE_URL", "http://astrbot.test:6185")
        monkeypatch.setenv("ASTRBOT_ALLOW_CHAT_PROBE", "true")
        monkeypatch.setenv("ASTRBOT_CHAT_USERNAME", "tester")

    def test_default_fixed_session_id(self, env, monkeypatch):
        captured = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["body"] = json.loads(request.content.decode())
            sse = (
                'data: {"type": "session_id", "data": "mcp-smoke-tester"}\n\n'
                'data: {"type": "plain", "data": "ok"}\n\ndata: {"type": "end"}\n\n'
            )
            return httpx.Response(200, text=sse)

        monkeypatch.setattr(
            tools_chat, "AstrBotClient", lambda cfg=None: _mock_client(handler)
        )
        r = json.loads(tools_chat.astrbot_chat_probe("hi", confirm_probe=True))
        assert captured["body"]["session_id"] == "mcp-smoke-tester"
        assert captured["body"]["username"] == "tester"
        assert captured["body"]["config_name"] == "plugin_dev_skill"
        assert r["ok"] is True
        assert "mcp-smoke-tester" in r["session_policy"]

    def test_env_override_session_id(self, env, monkeypatch):
        monkeypatch.setenv("ASTRBOT_CHAT_SMOKE_SESSION_ID", "custom-smoke")
        captured = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["body"] = json.loads(request.content.decode())
            return httpx.Response(200, text='data: {"type": "end"}\n\n')

        monkeypatch.setattr(
            tools_chat, "AstrBotClient", lambda cfg=None: _mock_client(handler)
        )
        json.loads(tools_chat.astrbot_chat_probe("hi", confirm_probe=True))
        assert captured["body"]["session_id"] == "custom-smoke"

    def test_arg_beats_env(self, env, monkeypatch):
        monkeypatch.setenv("ASTRBOT_CHAT_SMOKE_SESSION_ID", "from-env")
        captured = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["body"] = json.loads(request.content.decode())
            return httpx.Response(200, text='data: {"type": "end"}\n\n')

        monkeypatch.setattr(
            tools_chat, "AstrBotClient", lambda cfg=None: _mock_client(handler)
        )
        json.loads(
            tools_chat.astrbot_chat_probe(
                "hi", confirm_probe=True, session_id="from-arg"
            )
        )
        assert captured["body"]["session_id"] == "from-arg"

    def test_http200_error_envelope_detected(self, env, monkeypatch):
        # AstrBot returns HTTP 200 + {"status": "error"} — must NOT count as ok
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200, json={"status": "error", "message": "Missing key: username"}
            )

        monkeypatch.setattr(
            tools_chat, "AstrBotClient", lambda cfg=None: _mock_client(handler)
        )
        r = json.loads(tools_chat.astrbot_chat_probe("hi", confirm_probe=True))
        assert r["ok"] is False
        assert r["error_kind"] == "chat_api_error"
