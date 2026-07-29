"""Unit tests for runtime.tools_smoke — case generation and verdict logic."""
from __future__ import annotations

import json

from runtime.tools_smoke import astrbot_smoke_suite, build_smoke_cases, judge_case

# component fixtures mirroring GET /plugins/{id} output (mimo_tts shape)
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
        assert cases[0]["name"] == "ttsinfo"  # info-like prioritized

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
        # tool not invoked but LLM replied → soft signal, not failure
        v = judge_case(self._probe(ok=False, plains=["no tool needed"]), "llm_tool")
        assert v["verdict"] == "soft_pass"

    def test_platform_llm_auth_not_pass(self):
        # Regression: chat_probe ok=true on "LLM 响应错误" must NOT be smoke pass
        plain = (
            "LLM 响应错误: All chat models failed: AuthenticationError: "
            "Error code: 401 - OAuth access token has expired"
        )
        v = judge_case(self._probe(ok=True, plains=[plain]), "command")
        assert v["verdict"] == "platform_error"

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
        # passes gate; fails later on not_configured (no BASE_URL in tests)
        r = json.loads(astrbot_smoke_suite("astrbot_plugin_x"))
        assert r.get("error_kind") != "confirm_required"
