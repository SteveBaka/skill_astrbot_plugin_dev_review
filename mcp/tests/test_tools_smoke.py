"""Unit tests for runtime.tools_smoke — case generation and verdict logic."""
from __future__ import annotations

import json

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
