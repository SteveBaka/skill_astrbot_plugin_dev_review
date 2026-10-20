"""Unit tests for runtime.tools_smoke — case generation and verdict logic."""

from __future__ import annotations

import json

import pytest
from runtime.tools_smoke import (
    astrbot_smoke_suite,
    build_smoke_cases,
    judge_case,
)

COMPONENTS = [
    {"type": "command", "name": "ttsinfo", "command": "ttsinfo", "has_admin": False},
    {"type": "command", "name": "mimo_say", "command": "mimo_say", "has_admin": False},
    {"type": "command", "name": "ttsraw", "command": "ttsraw", "has_admin": True},
    {"type": "command", "name": "voice", "command": "voice", "has_admin": True},
    {"type": "hook", "name": "on_decorating_result"},
    {"type": "page", "name": "studio"},
]


class TestBuildCases:
    def test_admin_skipped_by_default(self):
        cases = build_smoke_cases(COMPONENTS)
        names = [c["name"] for c in cases]
        assert "ttsraw" not in names and "voice" not in names
        assert "ttsinfo" in names and "mimo_say" in names

    def test_admin_included_on_request(self):
        names = [c["name"] for c in build_smoke_cases(COMPONENTS, include_admin=True)]
        assert "ttsraw" in names

    def test_info_like_commands_first(self):
        cases = build_smoke_cases(COMPONENTS)
        assert cases[0]["name"] == "ttsinfo"

    def test_hook_generates_one_probe(self):
        kinds = [c["kind"] for c in build_smoke_cases(COMPONENTS)]
        assert kinds.count("hook") == 1

    def test_page_ignored(self):
        assert all(c["kind"] != "page" for c in build_smoke_cases(COMPONENTS))

    def test_max_cases_cap(self):
        many = [
            {"type": "command", "name": f"c{i}", "command": f"c{i}", "has_admin": False}
            for i in range(20)
        ]
        assert len(build_smoke_cases(many, max_cases=5)) == 5

    def test_command_message_format(self):
        case = build_smoke_cases(COMPONENTS)[0]
        assert case["message"] == "/ttsinfo"

    def test_llm_tool_soft_case(self):
        cases = build_smoke_cases([{"type": "llm_tool", "name": "t"}])
        assert cases and cases[0]["kind"] == "llm_tool"

    def test_empty_components(self):
        assert build_smoke_cases([]) == []
        assert build_smoke_cases([{"type": "page", "name": "p"}]) == []

    def test_dedup(self):
        dup = [
            {"type": "command", "name": "a", "command": "a", "has_admin": False},
            {"type": "command", "name": "a", "command": "a", "has_admin": False},
        ]
        assert len(build_smoke_cases(dup)) == 1

    def test_curated_example_plugin(self):
        cases = build_smoke_cases(
            [{"type": "command", "command": "weather", "has_admin": False}],
            plugin_id="astrbot_plugin_weather_tool",
        )
        names = [c["name"] for c in cases]
        assert "weather_usage" in names
        assert "weather_beijing" in names
        # curated first
        assert cases[0]["require_markers"] is True


class TestJudgeCase:
    def _probe(self, ok=True, plains=None, records=None, errors=None):
        return {
            "ok": ok,
            "elapsed_ms": 100,
            "summary": {
                "plain_texts": plains or [],
                "records": records or [],
                "attachments": [],
                "errors": errors or [],
            },
        }

    def test_pass(self):
        v = judge_case(self._probe(ok=True, plains=["hi"]), "command")
        assert v["verdict"] == "pass"

    def test_sse_error(self):
        v = judge_case(self._probe(ok=False, errors=["boom"]), "command")
        assert v["verdict"] == "error"
        assert v["sse_errors"] == ["boom"]

    def test_no_content(self):
        v = judge_case(self._probe(ok=False), "command")
        assert v["verdict"] == "no_content"

    def test_llm_tool_soft_pass(self):
        v = judge_case(self._probe(ok=False, plains=["no tool needed"]), "llm_tool")
        assert v["verdict"] == "soft_pass"

    def test_platform_llm_auth_not_pass(self):
        plain = (
            "LLM 响应错误: All chat models failed: AuthenticationError: "
            "Error code: 401 - OAuth access token has expired"
        )
        v = judge_case(self._probe(ok=True, plains=[plain]), "command")
        assert v["verdict"] == "platform_error"

    def test_markers_hit_reported_when_markers_given(self):
        # regression: markers_hit must be computed even without require_markers
        v = judge_case(
            self._probe(ok=True, plains=["⭐"]),
            "example",
            markers=("correct", "base class"),
        )
        assert v["markers_hit"] is False
        # but without require_markers, judge alone does NOT fail it (suite soft-downgrades)

    def test_handler_exception_not_pass(self):
        plain = (
            "在调用插件 astrbot_plugin_daily_report 的处理函数 list_jobs 时出现异常："
            "'coroutine' object is not iterable"
        )
        v = judge_case(self._probe(ok=True, plains=[plain]), "command")
        assert v["verdict"] == "handler_error"

    def test_markers_required(self):
        v = judge_case(
            self._probe(ok=True, plains=["Welcome to the quiz!"]),
            "example",
            markers=("welcome", "question"),
            require_markers=True,
        )
        assert v["verdict"] == "pass"
        v2 = judge_case(
            self._probe(ok=True, plains=["嗯？什么意思"]),
            "example",
            markers=("welcome", "question"),
            require_markers=True,
        )
        assert v2["verdict"] == "content_mismatch"

    def test_chitchat_command_mismatch(self):
        v = judge_case(
            self._probe(ok=True, plains=["不太清楚你说的 toggle_hook 是指什么"]),
            "command",
        )
        assert v["verdict"] == "content_mismatch"

    def test_content_truncated(self):
        v = judge_case(self._probe(ok=True, plains=["x" * 500]), "command")
        assert len(v["content"]["plain"][0]) == 120


class TestSuiteGates:
    def test_plugin_id_required(self):
        r = json.loads(astrbot_smoke_suite(""))
        assert r["error_kind"] == "bad_request"

    def test_confirm_required(self):
        r = json.loads(astrbot_smoke_suite("astrbot_plugin_x"))
        assert r["error_kind"] == "confirm_required"

    def test_env_allows(self, monkeypatch):
        monkeypatch.setenv("ASTRBOT_ALLOW_CHAT_PROBE", "true")
        r = json.loads(astrbot_smoke_suite("astrbot_plugin_x"))
        assert r.get("error_kind") != "confirm_required"


class TestNoContentAll:
    def test_all_no_content_hints_provider(self, monkeypatch):
        """Pure LLM message returns nothing → no_content_all (provider issue, not key)."""
        monkeypatch.setenv("ASTRBOT_ALLOW_CHAT_PROBE", "true")

        class _R:
            def __init__(self, data=None, ok=True, error=None, error_kind=None):
                self.data = data
                self.ok = ok
                self.error = error
                self.error_kind = error_kind

        class _FakeClient:
            def get(self, path, **kw):
                if "failed" in path:
                    return _R(data={"status": "ok", "data": {}})
                return _R(
                    data={
                        "status": "ok",
                        "data": {
                            "name": "astrbot_plugin_x",
                            "version": "0.1.0",
                            "activated": True,
                            "components": [
                                {
                                    "type": "command",
                                    "command": "hi",
                                    "name": "hi",
                                    "description": "x",
                                    "has_admin": False,
                                }
                            ],
                        },
                    }
                )

        monkeypatch.setattr("runtime.tools_smoke.AstrBotClient", lambda *a, **k: _FakeClient())

        def fake_probe(message, **kw):
            # empty SSE: ok but zero output (no plain, no error event)
            return json.dumps(
                {
                    "ok": False,
                    "elapsed_ms": 10,
                    "summary": {"plain_texts": [], "records": [], "attachments": [], "errors": []},
                }
            )

        monkeypatch.setattr("runtime.tools_smoke.astrbot_chat_probe", fake_probe)
        r = json.loads(
            astrbot_smoke_suite("astrbot_plugin_x", confirm=True, username="u", max_cases=3)
        )
        assert r["ok"] is False
        assert r["error_kind"] == "no_content_all"
        assert r["summary"]["no_content"] >= 1
        assert "provider" in r["next_step"].lower()
        assert "NOT an API-key" in r["next_step"]


# ── auto-cleanup (self-cleaning smoke cycles) ──────────────────


class TestSmokeAutoCleanup:
    """A smoke run must leave no leftovers; deletion still respects mutations."""

    def test_cleanup_skipped_when_mutations_disabled(self, monkeypatch):
        from runtime import tools_smoke

        monkeypatch.delenv("ASTRBOT_ALLOW_MUTATIONS", raising=False)
        out: dict = {}
        tools_smoke._finish_smoke_cleanup(out, "someone", True)
        assert out["cleanup"]["attempted"] is False
        assert out["cleanup"]["skipped"] == "mutations_disabled"
        # the hint must tell the operator how to enable it
        assert "ASTRBOT_ALLOW_MUTATIONS" in out["cleanup"]["hint"]

    def test_cleanup_can_be_disabled_per_call(self, monkeypatch):
        from runtime import tools_smoke

        monkeypatch.setenv("ASTRBOT_ALLOW_MUTATIONS", "true")
        out: dict = {}
        tools_smoke._finish_smoke_cleanup(out, "someone", False)
        assert "cleanup" not in out

    def test_cleanup_requires_an_owner(self, monkeypatch):
        from runtime import tools_smoke

        monkeypatch.setenv("ASTRBOT_ALLOW_MUTATIONS", "true")
        monkeypatch.delenv("ASTRBOT_CHAT_USERNAME", raising=False)
        out: dict = {}
        tools_smoke._finish_smoke_cleanup(out, "", True)
        assert out["cleanup"]["attempted"] is False
        assert "username" in out["cleanup"]["error"]

    def test_owner_resolved_from_env(self, monkeypatch):
        """Env fallback keeps automation working without passing username each time."""
        from runtime import tools_smoke

        monkeypatch.setenv("ASTRBOT_ALLOW_MUTATIONS", "true")
        monkeypatch.setenv("ASTRBOT_CHAT_USERNAME", "env-owner")
        captured = {}

        def fake_cleanup(client, owner, **kw):
            captured["owner"] = owner
            return {"attempted": True, "cleaned": True, "targets": []}

        monkeypatch.setattr("runtime.tools_chat.cleanup_smoke_workspace", fake_cleanup)
        out: dict = {}
        tools_smoke._finish_smoke_cleanup(out, "", True)
        assert captured["owner"] == "env-owner"
        assert out["cleanup"]["cleaned"] is True


class TestWorkspaceCleanup:
    """cleanup_smoke_workspace drains both current and stale smoke artifacts."""

    @pytest.fixture
    def env(self, monkeypatch):
        monkeypatch.setenv("ASTRBOT_BASE_URL", "http://astrbot.test:6185")

    def test_discovers_stale_and_current(self, env, monkeypatch):
        import httpx
        from runtime.client import AstrBotClient
        from runtime.config import load_config
        from runtime.tools_chat import cleanup_smoke_workspace

        capture: list = []

        def handler(request: httpx.Request):
            capture.append((request.method, request.url.path))
            if request.method == "GET" and request.url.path == "/api/v1/chat/sessions":
                return httpx.Response(
                    200,
                    json={
                        "status": "ok",
                        "data": {
                            "sessions": [
                                {"session_id": "mcp-smoke-a", "platform_id": "webchat"},
                                {"session_id": "mcp-smoke-stale", "platform_id": "webchat"},
                                {"session_id": "chat-123", "platform_id": "webchat"},
                            ]
                        },
                    },
                )
            if request.url.path == "/api/v1/conversations":
                return httpx.Response(
                    200,
                    json={"status": "ok", "data": {"conversations": [], "pagination": {"page": 1, "total_pages": 1}}},
                )
            return httpx.Response(200, json={"status": "error", "message": "Permission denied"})

        client = AstrBotClient(load_config())

        def patched(method, path, *, params=None, json_body=None, timeout=None,
                    max_total_seconds=None):
            transport = httpx.MockTransport(handler)
            with httpx.Client(transport=transport) as hc:
                resp = hc.request(method.upper(), client._url(path), params=params, json=json_body)
            return client._from_response(resp)

        client.request = patched  # type: ignore[method-assign]
        rep = cleanup_smoke_workspace(client, "owner-x", extra_session_ids=["mcp-smoke-a"])

        # both the fresh session and the stale one are targets; real chat is not
        assert "mcp-smoke-a" in rep["targets"]
        assert "mcp-smoke-stale" in rep["targets"]
        assert "chat-123" not in rep["targets"]
        assert rep["stale_discovered"] == ["mcp-smoke-stale"]

    def test_no_leftovers_is_clean(self, env, monkeypatch):
        import httpx
        from runtime.client import AstrBotClient
        from runtime.config import load_config
        from runtime.tools_chat import cleanup_smoke_workspace

        client = AstrBotClient(load_config())

        def patched(method, path, *, params=None, json_body=None, timeout=None,
                    max_total_seconds=None):
            def handler(request):
                if request.url.path == "/api/v1/chat/sessions":
                    return httpx.Response(200, json={"status": "ok", "data": {"sessions": []}})
                return httpx.Response(200, json={"status": "ok", "data": {"conversations": [], "pagination": {"page": 1, "total_pages": 1}}})

            transport = httpx.MockTransport(handler)
            with httpx.Client(transport=transport) as hc:
                resp = hc.request(method.upper(), client._url(path), params=params, json=json_body)
            return client._from_response(resp)

        client.request = patched  # type: ignore[method-assign]
        rep = cleanup_smoke_workspace(client, "owner-x")
        assert rep["attempted"] is False
        assert rep["cleaned"] is True
        assert "No smoke leftovers" in rep["note"]


class TestExtraMessagesQuota:
    """User-supplied cases must survive max_cases truncation."""

    def _run(self, monkeypatch, *, extra: str, max_cases: int):
        from runtime import tools_smoke

        class _Fake:
            def request(self, *a, **k):
                class R:
                    ok = True
                    status_code = 200
                    data = {
                        "data": {
                            "components": [
                                {"type": "command", "name": n, "command": n, "has_admin": False}
                                for n in ("a", "b", "c", "d", "e")
                            ],
                            "activated": True,
                            "name": "astrbot_plugin_t",
                            "version": "1.0",
                        }
                    }
                    error = None
                    error_kind = None
                    url = ""
                    elapsed_ms = 1.0

                return R()

            def get(self, *a, **k):
                return self.request()

        monkeypatch.setattr("runtime.tools_smoke.AstrBotClient", lambda *a, **k: _Fake())
        monkeypatch.setenv("ASTRBOT_ALLOW_CHAT_PROBE", "true")
        monkeypatch.setenv("ASTRBOT_ALLOW_MUTATIONS", "false")

        def fake_probe(message, **kw):
            return json.dumps(
                {
                    "ok": True,
                    "summary": {"plain_texts": ["ok"], "errors": [], "records": [], "attachments": []},
                }
            )

        monkeypatch.setattr("runtime.tools_smoke.astrbot_chat_probe", fake_probe)
        raw = tools_smoke.astrbot_smoke_suite(
            "astrbot_plugin_t",
            confirm=True,
            username="u",
            max_cases=max_cases,
            extra_messages=extra,
            auto_cleanup=False,
        )
        return json.loads(raw)

    def test_custom_case_is_not_dropped(self, monkeypatch):
        r = self._run(monkeypatch, extra="自定义用例", max_cases=4)
        planned = r["pipeline"]["cases_planned"]
        assert len(planned) == 4
        kinds = [c["kind"] for c in planned]
        assert "custom" in kinds, f"custom case dropped: {kinds}"
        assert planned[-1]["message"] == "自定义用例"

    def test_multiple_custom_cases_keep_quota(self, monkeypatch):
        r = self._run(monkeypatch, extra="one||two", max_cases=3)
        planned = r["pipeline"]["cases_planned"]
        customs = [c for c in planned if c["kind"] == "custom"]
        assert len(customs) == 2, planned
        assert len(planned) == 3
