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
        assert _is_webchat_session({"session_id": "webchat:FriendMessage:webchat!user!326b11bd"})
        assert _is_webchat_session({"umo": "webchat:FriendMessage:webchat!u!x"})
        assert _is_webchat_session({"id": "webchat!u!x"})

    def test_other_platforms_rejected(self):
        # PRIVACY: real conversations must never be classified as webchat
        assert not _is_webchat_session({"platform_id": "aiocqhttp"})
        assert not _is_webchat_session({"platform_id": "telegram"})
        assert not _is_webchat_session({"session_id": "aiocqhttp:FriendMessage:12345"})
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
        s = summarize_chat_events([{"type": "plain", "data": "x" * 2000}], text_limit=100)
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
        r = json.loads(tools_chat.astrbot_chat_sessions_cleanup("id1", confirm_cleanup=True))
        assert r["error_kind"] == "bad_request"

    def test_no_ids_no_flag_rejected(self, monkeypatch):
        monkeypatch.setenv("ASTRBOT_ALLOW_MUTATIONS", "true")
        r = json.loads(
            tools_chat.astrbot_chat_sessions_cleanup("", username="u", confirm_cleanup=True)
        )
        assert r["error_kind"] == "bad_request"


# ── session policy (Plan B fixed smoke session) ────────────────


def _mock_client(handler) -> AstrBotClient:
    """AstrBotClient whose httpx calls hit a MockTransport."""
    client = AstrBotClient(load_config())

    def patched_request(
        method,
        path,
        *,
        params=None,
        json_body=None,
        timeout=None,
        max_total_seconds=None,
    ):
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

        monkeypatch.setattr(tools_chat, "AstrBotClient", lambda cfg=None: _mock_client(handler))
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

        monkeypatch.setattr(tools_chat, "AstrBotClient", lambda cfg=None: _mock_client(handler))
        json.loads(tools_chat.astrbot_chat_probe("hi", confirm_probe=True))
        assert captured["body"]["session_id"] == "custom-smoke"

    def test_random_session_id_arg_ignored(self, env, monkeypatch):
        # Anti-spam: per-call random ids must NOT create new WebChat rows
        captured = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["body"] = json.loads(request.content.decode())
            return httpx.Response(
                200,
                text='data: {"type": "plain", "data": "ok"}\n\ndata: {"type": "end"}\n\n',
            )

        monkeypatch.setattr(tools_chat, "AstrBotClient", lambda cfg=None: _mock_client(handler))
        r = json.loads(
            tools_chat.astrbot_chat_probe(
                "hi",
                confirm_probe=True,
                session_id="mcp-smoke-types-type2-deadbeef",
            )
        )
        assert captured["body"]["session_id"] == "mcp-smoke-tester"
        assert r["request"].get("session_id_arg_ignored") is True

    def test_http200_error_envelope_detected(self, env, monkeypatch):
        # AstrBot returns HTTP 200 + {"status": "error"} — must NOT count as ok
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"status": "error", "message": "Missing key: username"})

        monkeypatch.setattr(tools_chat, "AstrBotClient", lambda cfg=None: _mock_client(handler))
        r = json.loads(tools_chat.astrbot_chat_probe("hi", confirm_probe=True))
        assert r["ok"] is False
        assert r["error_kind"] == "chat_api_error"


# ── cleanup ownership (owner == API-key identity ⇒ auto-deletable) ──────────


class TestCleanupOwnership:
    """AstrBot deletes a session only when creator == auth identity.

    An API-key caller's identity is "api_key:<key_id>", so a smoke session is
    auto-deletable only when the probe created it under exactly that owner.
    These tests pin that contract and the report we emit for each case.
    """

    @pytest.fixture
    def env(self, monkeypatch):
        monkeypatch.setenv("ASTRBOT_BASE_URL", "http://astrbot.test:6185")
        monkeypatch.setenv("ASTRBOT_ALLOW_CHAT_PROBE", "true")
        monkeypatch.delenv("ASTRBOT_CHAT_USERNAME", raising=False)
        monkeypatch.delenv("ASTRBOT_CHAT_SMOKE_SESSION_ID", raising=False)

    @staticmethod
    def _install(monkeypatch, calls, listed_ids, sid):
        def handler(request: httpx.Request) -> httpx.Response:
            calls.append(request.method)
            if request.method == "GET":
                sessions = [
                    {"session_id": i, "platform_id": "webchat"} for i in listed_ids
                ]
                return httpx.Response(
                    200,
                    json={
                        "status": "ok",
                        "data": {
                            "sessions": sessions,
                            "page": 1,
                            "page_size": 50,
                            "total": len(sessions),
                        },
                    },
                )
            return httpx.Response(
                200,
                text=(
                    f'data: {{"type": "session_id", "data": "{sid}"}}\n\n'
                    'data: {"type": "plain", "data": "ok"}\n\n'
                    'data: {"type": "end"}\n\n'
                ),
            )

        monkeypatch.setattr(
            tools_chat, "AstrBotClient", lambda cfg=None: _mock_client(handler)
        )

    def test_key_owner_is_auto_deletable(self, env, monkeypatch):
        calls: list[str] = []
        sid = "mcp-smoke-api_key-key123"
        # owner == this key's identity ⇒ the session is listed under it ⇒ delete ok
        self._install(monkeypatch, calls, [sid], sid)
        r = json.loads(
            tools_chat.astrbot_chat_probe(
                "hi", confirm_probe=True, username="api_key:key123"
            )
        )
        assert r["ok"] is True
        assert r["cleanup"]["mode"] == "auto"
        assert r["cleanup"]["owner_is_api_key_identity"] is True
        assert r["cleanup"]["session_listed_under_owner"] is True
        assert "astrbot_chat_sessions_cleanup can delete it" in r["session_policy"]
        assert "GET" in calls  # ownership actually verified, not assumed

    def test_key_owner_not_listed_falls_back_to_manual(self, env, monkeypatch):
        calls: list[str] = []
        sid = "mcp-smoke-api_key-wrongkey"
        # probe succeeds, but the session is not under this owner → warn loudly
        self._install(monkeypatch, calls, [], sid)
        r = json.loads(
            tools_chat.astrbot_chat_probe(
                "hi", confirm_probe=True, username="api_key:wrongkey"
            )
        )
        assert r["ok"] is True
        assert r["cleanup"]["mode"] == "manual"
        assert r["cleanup"]["session_listed_under_owner"] is False
        assert "NOT listed under this owner" in r["cleanup"]["reason"]

    def test_plain_username_stays_manual_without_extra_call(self, env, monkeypatch):
        calls: list[str] = []
        sid = "mcp-smoke-tester"
        self._install(monkeypatch, calls, [sid], sid)
        r = json.loads(
            tools_chat.astrbot_chat_probe(
                "hi", confirm_probe=True, username="tester"
            )
        )
        assert r["cleanup"]["mode"] == "manual"
        assert r["cleanup"]["owner_is_api_key_identity"] is False
        assert calls == ["POST"]  # no verification round-trip on the default path

    def test_key_owner_session_id_has_no_colon(self, env, monkeypatch):
        captured = {}

        def handler(request: httpx.Request) -> httpx.Response:
            if request.method == "GET":
                return httpx.Response(
                    200, json={"status": "ok", "data": {"sessions": []}}
                )
            captured["body"] = json.loads(request.content.decode())
            return httpx.Response(
                200,
                text='data: {"type": "plain", "data": "ok"}\n\ndata: {"type": "end"}\n\n',
            )

        monkeypatch.setattr(
            tools_chat, "AstrBotClient", lambda cfg=None: _mock_client(handler)
        )
        json.loads(
            tools_chat.astrbot_chat_probe(
                "hi", confirm_probe=True, username="api_key:abc:def"
            )
        )
        assert captured["body"]["session_id"] == "mcp-smoke-api_key-abc-def"
        assert ":" not in captured["body"]["session_id"].removeprefix("mcp-smoke-")
        assert captured["body"]["username"] == "api_key:abc:def"


class TestSmokeDeadline:
    """The probe must always return inside a typical MCP client window."""

    def test_default_cap_is_client_safe(self, monkeypatch):
        monkeypatch.delenv("ASTRBOT_CHAT_SMOKE_DEADLINE", raising=False)
        # default request timeout is >=60s, but the cap must stay under a 30s window
        assert tools_chat._smoke_deadline(60) == 25.0
        assert tools_chat._smoke_deadline(10) == 25.0  # 10+15=25 → still capped at 25

    def test_small_request_timeout_is_not_raised(self, monkeypatch):
        monkeypatch.delenv("ASTRBOT_CHAT_SMOKE_DEADLINE", raising=False)
        assert tools_chat._smoke_deadline(2) == 17.0

    def test_env_can_widen_the_window(self, monkeypatch):
        monkeypatch.setenv("ASTRBOT_CHAT_SMOKE_DEADLINE", "120")
        assert tools_chat._smoke_deadline(60) == 75.0  # 60+15, under the 120 window

    def test_env_zero_disables_the_client_window_cap(self, monkeypatch):
        monkeypatch.setenv("ASTRBOT_CHAT_SMOKE_DEADLINE", "0")
        assert tools_chat._smoke_deadline(60) == 75.0

    def test_bad_env_falls_back_to_default(self, monkeypatch):
        monkeypatch.setenv("ASTRBOT_CHAT_SMOKE_DEADLINE", "not-a-number")
        assert tools_chat._smoke_deadline(60) == 25.0


class TestConversationFallback:
    """Creator gate blocks session DELETE; `data` scope still removes the conversation.

    The endpoint takes a conversation **cid** (uuid), not a session id — passing a
    session id matches zero rows yet still returns 200, which produced a false
    success in an earlier revision. These tests pin the GET-cid → DELETE → verify
    sequence so that mistake cannot come back.
    """

    SID = "mcp-smoke-x"
    CID = "11111111-2222-3333-4444-555555555555"
    UMO = f"webchat:FriendMessage:webchat!skill-smoke!{SID}"

    @pytest.fixture
    def env(self, monkeypatch):
        monkeypatch.setenv("ASTRBOT_BASE_URL", "http://astrbot.test:6185")
        monkeypatch.setenv("ASTRBOT_ALLOW_MUTATIONS", "true")

    @classmethod
    def _install(cls, monkeypatch, capture, *, vanish_after_delete=True):
        state = {"deleted": False}

        def handler(request: httpx.Request) -> httpx.Response:
            path = request.url.path
            capture.append((request.method, path, dict(request.url.params)))
            if request.method == "GET" and path == "/api/v1/chat/sessions":
                return httpx.Response(
                    200,
                    json={
                        "status": "ok",
                        "data": {"sessions": [{"session_id": cls.SID, "platform_id": "webchat"}]},
                    },
                )
            if path.endswith("/batch-delete"):
                return httpx.Response(200, json={"status": "ok"})  # claims ok, deletes nothing
            if path.startswith("/api/v1/chat/sessions/"):
                return httpx.Response(200, json={"status": "error", "message": "Permission denied"})
            if path == "/api/v1/conversations" and request.method == "GET":
                rows = []
                if not (state["deleted"] and vanish_after_delete):
                    rows = [{"cid": cls.CID, "user_id": cls.UMO, "platform_id": "webchat"}]
                return httpx.Response(
                    200,
                    json={
                        "status": "ok",
                        "data": {
                            "conversations": rows,
                            "pagination": {"page": 1, "total_pages": 1},
                        },
                    },
                )
            if path.startswith("/api/v1/conversations/") and request.method == "DELETE":
                state["deleted"] = True
                return httpx.Response(200, json={"status": "ok"})
            return httpx.Response(404, json={"status": "error", "message": "unexpected"})

        monkeypatch.setattr(tools_chat, "AstrBotClient", lambda cfg=None: _mock_client(handler))

    def test_looks_up_cid_then_deletes_and_verifies(self, env, monkeypatch):
        capture: list = []
        self._install(monkeypatch, capture)
        r = json.loads(
            tools_chat.astrbot_chat_sessions_cleanup(
                self.SID, username="skill-smoke", confirm_cleanup=True
            )
        )
        assert r["ok"] is True
        assert r["conversation_fallback"]["deleted"] is True
        assert r["conversation_fallback"]["deleted_ids"] == [self.SID]
        assert r.get("session_row_retained") is True
        # ok=true must not also carry a failure field
        assert "error_kind" not in r and "error" not in r

        # the DELETE must target the real cid, not the session id
        deletes = [c for c in capture if c[0] == "DELETE" and "/conversations/" in c[1]]
        assert deletes, "conversation DELETE was never sent"
        assert deletes[0][1].endswith(self.CID)
        assert self.SID not in deletes[0][1]
        assert deletes[0][2].get("user_id") == self.UMO
        # and a verification GET must follow the DELETE
        assert len([c for c in capture if c[1] == "/api/v1/conversations"]) >= 2

    def test_verification_catches_a_silent_no_op(self, env, monkeypatch):
        capture: list = []
        # DELETE returns ok but the row keeps coming back → must NOT claim success
        self._install(monkeypatch, capture, vanish_after_delete=False)
        r = json.loads(
            tools_chat.astrbot_chat_sessions_cleanup(
                self.SID, username="skill-smoke", confirm_cleanup=True
            )
        )
        assert r["ok"] is False
        assert r["conversation_fallback"]["deleted"] is False
        assert any(f.get("stage") == "verify" for f in r["conversation_fallback"]["failures"])

    def test_non_smoke_ids_are_never_sent(self, env, monkeypatch):
        capture: list = []
        self._install(monkeypatch, capture)
        res = tools_chat._delete_smoke_conversations(
            _mock_client(lambda r: httpx.Response(200, json={"status": "ok"})),
            "someone",
            ["real-user-conversation-1234"],
        )
        assert res["deleted"] is False
        assert res["refused_non_smoke_ids"] == ["real-user-conversation-1234"]
        assert not [c for c in capture if "/conversations/" in c[1]]

    def test_other_owner_sessions_are_ignored(self, env, monkeypatch):
        capture: list = []

        def handler(request: httpx.Request) -> httpx.Response:
            capture.append((request.method, request.url.path, dict(request.url.params)))
            return httpx.Response(
                200,
                json={
                    "status": "ok",
                    "data": {
                        "conversations": [
                            {
                                "cid": self.CID,
                                "user_id": "webchat:FriendMessage:webchat!other!mcp-smoke-x",
                                "platform_id": "webchat",
                            }
                        ],
                        "pagination": {"page": 1, "total_pages": 1},
                    },
                },
            )

        res = tools_chat._delete_smoke_conversations(
            _mock_client(handler), "skill-smoke", [self.SID]
        )
        assert res["deleted"] is False
        assert not [c for c in capture if c[0] == "DELETE"]


class TestCleanupIdempotency:
    """Running cleanup twice must read as "already clean", not "delete failed"."""

    SID = "mcp-smoke-y"

    @pytest.fixture
    def env(self, monkeypatch):
        monkeypatch.setenv("ASTRBOT_BASE_URL", "http://astrbot.test:6185")
        monkeypatch.setenv("ASTRBOT_ALLOW_MUTATIONS", "true")

    def _install(self, monkeypatch, *, conversation_present: bool):
        def handler(request: httpx.Request) -> httpx.Response:
            path = request.url.path
            if request.method == "GET" and path == "/api/v1/chat/sessions":
                return httpx.Response(
                    200,
                    json={
                        "status": "ok",
                        "data": {"sessions": [{"session_id": self.SID, "platform_id": "webchat"}]},
                    },
                )
            if path.endswith("/batch-delete"):
                return httpx.Response(200, json={"status": "ok"})
            if path.startswith("/api/v1/chat/sessions/"):
                return httpx.Response(200, json={"status": "error", "message": "Permission denied"})
            if path == "/api/v1/conversations":
                rows = (
                    [
                        {
                            "cid": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
                            "user_id": f"webchat:FriendMessage:webchat!skill-smoke!{self.SID}",
                            "platform_id": "webchat",
                        }
                    ]
                    if conversation_present
                    else []
                )
                return httpx.Response(
                    200,
                    json={
                        "status": "ok",
                        "data": {"conversations": rows, "pagination": {"page": 1, "total_pages": 1}},
                    },
                )
            return httpx.Response(200, json={"status": "ok"})

        monkeypatch.setattr(tools_chat, "AstrBotClient", lambda cfg=None: _mock_client(handler))

    def test_second_run_reports_already_clean(self, env, monkeypatch):
        self._install(monkeypatch, conversation_present=False)
        r = json.loads(
            tools_chat.astrbot_chat_sessions_cleanup(
                self.SID, username="skill-smoke", confirm_cleanup=True
            )
        )
        assert r["ok"] is True
        assert r["conversation_fallback"]["already_absent"] is True
        # must not masquerade as a permission/delete failure
        assert "error_kind" not in r
        assert "already cleaned" in r["note"]
        assert r["session_row_retained"] is True

    def test_first_run_still_reports_deletion(self, env, monkeypatch):
        # the row must disappear between the pre-check and the post-check
        state = {"listed": 0}

        def handler(request: httpx.Request) -> httpx.Response:
            path = request.url.path
            if request.method == "GET" and path == "/api/v1/chat/sessions":
                return httpx.Response(
                    200,
                    json={
                        "status": "ok",
                        "data": {"sessions": [{"session_id": self.SID, "platform_id": "webchat"}]},
                    },
                )
            if path.endswith("/batch-delete"):
                return httpx.Response(200, json={"status": "ok"})
            if path.startswith("/api/v1/chat/sessions/"):
                return httpx.Response(200, json={"status": "error", "message": "Permission denied"})
            if path == "/api/v1/conversations":
                state["listed"] += 1
                rows = []
                if state["listed"] == 1:  # first look still has it
                    rows = [
                        {
                            "cid": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
                            "user_id": f"webchat:FriendMessage:webchat!skill-smoke!{self.SID}",
                            "platform_id": "webchat",
                        }
                    ]
                return httpx.Response(
                    200,
                    json={
                        "status": "ok",
                        "data": {"conversations": rows, "pagination": {"page": 1, "total_pages": 1}},
                    },
                )
            return httpx.Response(200, json={"status": "ok"})

        monkeypatch.setattr(tools_chat, "AstrBotClient", lambda cfg=None: _mock_client(handler))
        r = json.loads(
            tools_chat.astrbot_chat_sessions_cleanup(
                self.SID, username="skill-smoke", confirm_cleanup=True
            )
        )
        assert r["ok"] is True
        assert r["conversation_fallback"]["deleted"] is True
        assert r["conversation_fallback"]["already_absent"] is False


class TestReasoningSeparation:
    """Model reasoning must not be mistaken for plugin output.

    Live 4.29.0 run: `/mimo_say` and `/sing` were judged `pass` although the handlers
    never ran — the only "content" was the model's `🤔 思考:` reasoning. That is a false
    pass on a smoke suite, so reasoning is now bucketed separately and cannot inflate
    `has_content`.
    """

    def test_detects_reasoning_markers(self):
        assert tools_chat.is_reasoning_text("🤔 思考: The user typed mimo_say")
        assert tools_chat.is_reasoning_text("思考: 让我看看")
        assert tools_chat.is_reasoning_text("Thinking: let me check")

    def test_plugin_output_is_not_reasoning(self):
        assert not tools_chat.is_reasoning_text("🤔 表情包管理器 v2.4.5")
        assert not tools_chat.is_reasoning_text("MiMO TTS v2.4.5 功能信息")
        assert not tools_chat.is_reasoning_text("")
        assert not tools_chat.is_reasoning_text("思考题：这是插件正文")

    def test_summary_buckets_reasoning_apart(self):
        events = [
            {"type": "session_id", "data": "mcp-smoke-x"},
            {"type": "plain", "data": "🤔 思考: The user typed ttsinfo"},
            {"type": "plain", "data": "MiMO TTS v2.4.5"},
            {"type": "end"},
        ]
        s = tools_chat.summarize_chat_events(events)
        assert s["reasoning"] == ["🤔 思考: The user typed ttsinfo"]
        assert s["plain_texts"] == ["MiMO TTS v2.4.5"]

    def test_judge_flags_reasoning_only_as_mismatch(self):
        from runtime.tools_smoke import judge_case

        probe = {
            "ok": True,
            "summary": {
                "plain_texts": [],
                "reasoning": ["🤔 思考: The user typed sing - likely the /sing command"],
                "records": [],
                "attachments": [],
                "errors": [],
            },
        }
        v = judge_case(probe, "command")
        assert v["verdict"] == "content_mismatch"
        assert "reasoning_only_no_plugin_output" in v["sse_errors"]

    def test_judge_still_passes_real_output(self):
        from runtime.tools_smoke import judge_case

        probe = {
            "ok": True,
            "summary": {
                "plain_texts": ["MiMO TTS v2.4.5 — 20 种情感"],
                "reasoning": ["🤔 思考: 用户想看版本"],
                "records": [],
                "attachments": [],
                "errors": [],
            },
        }
        assert judge_case(probe, "command")["verdict"] == "pass"


class TestAdminOwnerHint:
    """Sending as an admin id needs the chat:admin sub-scope; make that diagnosable."""

    @pytest.fixture
    def env(self, monkeypatch):
        monkeypatch.setenv("ASTRBOT_BASE_URL", "http://astrbot.test:6185")
        monkeypatch.setenv("ASTRBOT_ALLOW_CHAT_PROBE", "true")

    def test_admin_reserved_error_gets_actionable_hint(self, env, monkeypatch):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json={
                    "status": "error",
                    "message": "username is reserved for an AstrBot administrator",
                },
            )

        monkeypatch.setattr(tools_chat, "AstrBotClient", lambda cfg=None: _mock_client(handler))
        r = json.loads(
            tools_chat.astrbot_chat_probe(
                "hi", confirm_probe=True, username="admin_user"
            )
        )
        assert r["ok"] is False
        assert r["error_kind"] == "admin_username_needs_chat_admin"
        assert "chat:admin" in r["hint"]
        # must offer the non-admin fallback so the agent is not stuck
        assert "non-admin" in r["hint"] or "plain" in r["hint"]
