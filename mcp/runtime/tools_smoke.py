# [RUNTIME P3+] smoke_suite: status → auto test-case generation → probes → report.
"""
Composite smoke test for an installed plugin, codifying the manual loop proven
on astrbot_plugin_mimo_tts (2026-07): failed-check → derive cases from plugin
components → chat_probe each → aggregate verdict.

Case derivation (from GET /plugins/{id} components):
  - command  → "/<command>" (+ optional sample arg text)
  - command_group → "/<group>" (help view)
  - hook (on_decorating_result / on_llm_*) → one natural-language message
  - llm_tool → one natural message nudging tool use (LLM may still skip it)

Known skill example plugins (plugin-types/*) get extra curated cases and
content markers so LLM chit-chat is not counted as command success.

Safety / privacy — same posture as chat_probe:
  - Needs confirm=true (or ASTRBOT_ALLOW_CHAT_PROBE) + chat-scoped key
  - All messages land in the ONE fixed smoke session (mcp-smoke-<username>)
  - Output truncated summaries only; no transcripts stored
  - max_cases hard cap; admin-only commands skipped by default
"""

from __future__ import annotations

import json
import os
import re
import time
from typing import Any, Dict, List, Optional, Sequence, Tuple

from .client import AstrBotClient, encode_plugin_id
from .failure_analysis import analyze_failed_payload
from .tools_chat import astrbot_chat_probe

DEFAULT_MAX_CASES = 8
HOOK_PROBE_MESSAGE = "请用一句话回复：现在是插件冒烟测试"

# Curated extras for skill example plugins (message, optional markers for match).
# Markers empty → only platform/handler checks apply for that message.
_EXAMPLE_CASES: Dict[str, List[Tuple[str, str, Sequence[str]]]] = {
    # (case_name, message, success_markers)
    "astrbot_plugin_weather_tool": [
        ("weather_usage", "/weather", ("usage", "city", "error:", "weather")),
        ("weather_beijing", "/weather Beijing", ("error:", "beijing", "weather", "°", "wttr", "network")),
    ],
    "astrbot_plugin_quiz": [
        ("quiz_start", "/quiz", ("welcome", "question", "quiz")),
        # Optional multi-turn follow-up (same fixed session). Waiter is timing-
        # sensitive over sequential chat_probe; soft if Correct markers miss.
        ("quiz_answer_star", "Star", ("correct", "base class")),
    ],
    "astrbot_plugin_daily_report": [
        ("cron_list", "/cron_list", ("scheduled", "no scheduled", "daily_report", "cron")),
        ("cron_delete_usage", "/cron_delete", ("usage", "cron_delete", "task")),
    ],
    "astrbot_plugin_llm_hook": [
        ("toggle_hook", "/toggle_hook", ("llm hook", "enabled", "disabled")),
        ("hook_nl", HOOK_PROBE_MESSAGE, ()),  # hook path: any non-platform reply OK
    ],
    "astrbot_plugin_dashboard": [
        ("dashboard_info", "/dashboard", ("dashboard", "/api/plug", "stats url", "status")),
    ],
    "astrbot_plugin_agent": [
        ("agent_usage", "/agent_search", ("usage", "search", "error:", "query", "agent")),
        (
            "agent_query",
            "/agent_search AstrBot",
            ("error:", "search", "astrbot", "network", "unable", "summary", "result"),
        ),
    ],
}


def _dumps(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=2, default=str)


def _env_bool(name: str) -> bool:
    raw = (os.environ.get(name) or "").strip().lower()
    return raw in ("1", "true", "yes", "on")


# ── case generation (pure logic; unit-tested) ──────────────────


def build_smoke_cases(
    components: List[Dict[str, Any]],
    *,
    include_admin: bool = False,
    max_cases: int = DEFAULT_MAX_CASES,
    plugin_id: str = "",
) -> List[Dict[str, Any]]:
    """
    Derive smoke cases from plugin component metadata + optional curated extras.

    Priority: curated example cases (if plugin_id known) → non-admin commands
    (help/info-like first) → command_groups → one hook probe → one llm_tool.
    Deduped by message, capped at max_cases.
    """
    cases: List[Dict[str, Any]] = []
    seen_msg: set = set()

    def _add(case: Dict[str, Any]) -> None:
        msg = str(case.get("message") or "").strip()
        if not msg or msg in seen_msg:
            return
        seen_msg.add(msg)
        cases.append(case)

    pid = (plugin_id or "").strip()
    for name, message, markers in _EXAMPLE_CASES.get(pid, []):
        soft = name.startswith("quiz_answer")  # multi-turn optional under MCP probe
        _add({
            "kind": "example",
            "name": name,
            "message": message,
            "expect": "plugin-owned reply matching curated markers",
            "markers": list(markers),
            "require_markers": bool(markers) and not soft,
            "soft": soft,
        })

    commands: List[Dict[str, Any]] = []
    groups: List[Dict[str, Any]] = []
    has_hook = False
    has_llm_tool = False

    for comp in components or []:
        if not isinstance(comp, dict):
            continue
        ctype = comp.get("type")
        if ctype == "command":
            if comp.get("has_admin") and not include_admin:
                continue
            commands.append(comp)
        elif ctype == "command_group":
            groups.append(comp)
        elif ctype == "hook":
            has_hook = True
        elif ctype in ("llm_tool", "tool"):
            has_llm_tool = True

    def _info_like(c: Dict[str, Any]) -> int:
        name = str(c.get("command") or c.get("name") or "").lower()
        return 0 if any(k in name for k in ("info", "help", "version", "status", "list")) else 1

    commands.sort(key=_info_like)

    for c in commands:
        cmd = str(c.get("command") or c.get("name") or "").strip()
        if not cmd:
            continue
        _add({
            "kind": "command",
            "name": cmd,
            "message": f"/{cmd}",
            "expect": "plugin command reply (not LLM chit-chat)",
            "markers": [],
            "require_markers": False,
        })
    for g in groups:
        name = str(g.get("command") or g.get("name") or "").strip()
        if not name:
            continue
        _add({
            "kind": "command_group",
            "name": name,
            "message": f"/{name}",
            "expect": "group help or subcommand list",
            "markers": [],
            "require_markers": False,
        })
    if has_hook:
        _add({
            "kind": "hook",
            "name": "llm_hook",
            "message": HOOK_PROBE_MESSAGE,
            "expect": "LLM reply passes through plugin hook without SSE/platform error",
            "markers": [],
            "require_markers": False,
        })
    if has_llm_tool:
        _add({
            "kind": "llm_tool",
            "name": "llm_tool",
            "message": "如果有可用的插件工具，请调用它并说明结果",
            "expect": "tool call attempted (LLM may decline — soft signal)",
            "markers": [],
            "require_markers": False,
        })
    return cases[:max_cases]


# Plain-text patterns that mean the platform/LLM failed — NOT plugin success.
_PLATFORM_FAIL_MARKERS = (
    "LLM 响应错误",
    "All chat models failed",
    "AuthenticationError",
    "auth_unavailable",
    "OAuth access token",
    "Error code: 401",
    "Error code: 403",
    "Error code: 503",
    "no auth",
    "provider error",
)

# Core/framework handler failure (plugin ran but crashed in handler)
_HANDLER_FAIL_RE = re.compile(
    r"(在调用插件|处理函数|出现异常|Traceback|coroutine' object is not iterable|"
    r"got multiple values for argument|AttributeError|TypeError|NameError)",
    re.I,
)

# LLM ate the slash-command (plugin_set missing or command not bound)
_CHITCHAT_MARKERS = (
    "不太清楚",
    "什么 dashboard",
    "我这边没有",
    "我没有这个",
    "想聊点别的",
    "怎么啦",
    "突然就发",
    "是指什么",
    "没太明白",
    "bing_search",
    "future_task",
    '"name":',
    "call_",
)


def _looks_like_platform_failure(plains: List[str]) -> bool:
    blob = "\n".join(plains or "").lower()
    return any(m.lower() in blob for m in _PLATFORM_FAIL_MARKERS)


def _looks_like_handler_failure(plains: List[str]) -> bool:
    blob = "\n".join(plains or "")
    return bool(_HANDLER_FAIL_RE.search(blob))


def _looks_like_chitchat(plains: List[str]) -> bool:
    blob = "\n".join(plains or "").lower()
    return any(m.lower() in blob for m in _CHITCHAT_MARKERS)


def _markers_hit(plains: List[str], markers: Sequence[str]) -> bool:
    if not markers:
        return True
    blob = "\n".join(plains or "").lower()
    return any(m.lower() in blob for m in markers)


def judge_case(
    probe_result: Dict[str, Any],
    kind: str,
    *,
    markers: Sequence[str] = (),
    require_markers: bool = False,
) -> Dict[str, Any]:
    """Map one chat_probe JSON result to a pass/fail verdict (stricter than chat_probe.ok)."""
    summary = probe_result.get("summary") or {}
    errors = list(summary.get("errors") or [])
    plains = list(summary.get("plain_texts") or [])
    has_content = bool(plains or summary.get("records") or summary.get("attachments"))
    platform_fail = _looks_like_platform_failure(plains)
    handler_fail = _looks_like_handler_failure(plains)
    chitchat = _looks_like_chitchat(plains)
    marker_ok = _markers_hit(plains, markers)

    if platform_fail:
        errors = errors + ["platform_or_llm_failure_in_plain"]
        verdict = "platform_error"
    elif handler_fail:
        errors = errors + ["plugin_handler_exception_in_plain"]
        verdict = "handler_error"
    elif require_markers and has_content and not marker_ok:
        errors = errors + ["content_markers_miss"]
        verdict = "content_mismatch"
    elif chitchat and kind in ("command", "command_group", "example", "custom"):
        # Slash/custom command answered as pure LLM chat → treat as miss for plugin smoke
        if require_markers or kind in ("command", "command_group", "example"):
            errors = errors + ["llm_chitchat_not_plugin"]
            verdict = "content_mismatch"
        elif bool(probe_result.get("ok")):
            verdict = "pass"
        else:
            verdict = "no_content" if not has_content else "error"
    elif bool(probe_result.get("ok")):
        verdict = "pass"
    elif errors:
        verdict = "error"
    else:
        verdict = "no_content"

    # llm_tool / bare hook: soft when content exists and not platform/handler fail
    if kind == "llm_tool" and verdict not in ("pass", "platform_error", "handler_error"):
        if has_content and not platform_fail and not handler_fail:
            verdict = "soft_pass"
    if kind == "hook" and verdict == "content_mismatch" and has_content and not require_markers:
        verdict = "pass"

    return {
        "verdict": verdict,
        "sse_errors": errors[:4],
        "markers_required": list(markers) if require_markers else [],
        "markers_hit": marker_ok if markers else None,
        "content": {
            "plain": [p[:120] for p in plains[:1]],
            "records": (summary.get("records") or [])[:1],
            "attachments_count": len(summary.get("attachments") or []),
        },
        "elapsed_ms": probe_result.get("elapsed_ms"),
    }


# ── composite tool ─────────────────────────────────────────────


def astrbot_smoke_suite(
    plugin_id: str,
    *,
    confirm: bool = False,
    username: str = "",
    config_name: str = "",
    include_admin: bool = False,
    max_cases: int = DEFAULT_MAX_CASES,
    extra_messages: str = "",
    timeout_seconds: float = 0,
) -> str:
    """
    Full smoke pipeline: plugin status → failed diagnosis → derived cases → probes.

    Cases come from the plugin's OWN components (info/help-like first) — the LLM
    must not hardcode commands from other plugins (e.g. "/ttsinfo" is mimo_tts
    only). If a plugin has no component metadata or you are unsure which command
    it supports, probe "/plugin_help" first, then pass the plugin's real commands
    via extra_messages.

    extra_messages: optional '||'-separated custom messages appended as cases.
    """
    pid = (plugin_id or "").strip()
    if not pid:
        return _dumps({"ok": False, "error_kind": "bad_request", "error": "plugin_id required"})
    if not confirm and not _env_bool("ASTRBOT_ALLOW_CHAT_PROBE"):
        return _dumps({
            "ok": False,
            "error_kind": "confirm_required",
            "error": (
                "smoke_suite sends WebChat messages — needs confirm=true after "
                "user explicitly allows (or ASTRBOT_ALLOW_CHAT_PROBE env)."
            ),
        })

    client = AstrBotClient()
    out: Dict[str, Any] = {"ok": False, "plugin_id": pid, "pipeline": {}}

    # ── step 1: plugin exists / activated ──────────────────────
    got = client.get(f"/api/v1/plugins/{encode_plugin_id(pid)}")
    info: Optional[Dict[str, Any]] = None
    if got.ok and isinstance(got.data, dict):
        d = got.data.get("data")
        if isinstance(d, dict) and d:
            info = d
    if info is None:
        failed = client.get("/api/v1/plugins/failed")
        analysis = analyze_failed_payload(failed.data) if failed.ok else None
        mine = [
            x for x in (analysis or {}).get("diagnoses", [])
            if pid in (x.get("dir_name", ""), x.get("plugin_name", ""))
        ]
        out["error_kind"] = "plugin_not_loaded"
        out["error"] = f"Plugin {pid} not found among loaded plugins."
        out["failed_diagnosis"] = mine or None
        out["next_step"] = (
            "Fix load error per failed_diagnosis (fix_rule links auto-fix-guide), "
            "then astrbot_plugin_reload(failed=true) and rerun smoke_suite."
            if mine else
            "Install it first: astrbot_plugin_install_path(path)."
        )
        return _dumps(out)

    out["pipeline"]["plugin"] = {
        "name": info.get("name"),
        "version": info.get("version"),
        "activated": info.get("activated"),
        "components_total": len(info.get("components") or []),
    }
    if not info.get("activated"):
        out["error_kind"] = "plugin_disabled"
        out["error"] = "Plugin is installed but not activated."
        out["next_step"] = "Enable it: astrbot_plugin_set_enabled(plugin_id, true)."
        return _dumps(out)

    # ── step 2: derive cases ───────────────────────────────────
    cases = build_smoke_cases(
        info.get("components") or [],
        include_admin=include_admin,
        max_cases=max_cases,
        plugin_id=pid,
    )
    for i, msg in enumerate(
        m.strip() for m in (extra_messages or "").split("||") if m.strip()
    ):
        cases.append({
            "kind": "custom",
            "name": f"custom_{i + 1}",
            "message": msg,
            "expect": "user-defined",
            "markers": [],
            "require_markers": False,
        })
    cases = cases[: max(max_cases, 1)]
    if not cases:
        out["error_kind"] = "no_cases"
        out["error"] = (
            "No smoke cases derivable (no non-admin commands/hooks/tools). "
            "Pass extra_messages or include_admin=true."
        )
        return _dumps(out)
    out["pipeline"]["cases_planned"] = [
        {
            "kind": c["kind"],
            "name": c["name"],
            "message": c["message"],
            "require_markers": c.get("require_markers"),
        }
        for c in cases
    ]
    if pid in _EXAMPLE_CASES:
        out["pipeline"]["curated_example"] = True

    # ── step 3: run probes (fixed smoke session; sequential) ───
    results: List[Dict[str, Any]] = []
    t0 = time.time()
    for case in cases:
        raw = astrbot_chat_probe(
            case["message"],
            confirm_probe=True,
            username=username,
            config_name=config_name,
            timeout_seconds=timeout_seconds,
        )
        probe = json.loads(raw)
        if probe.get("error_kind") in ("bad_request", "chat_probe_disabled", "auth"):
            out["error_kind"] = probe.get("error_kind")
            out["error"] = probe.get("error")
            out["aborted_at_case"] = case["name"]
            out["results"] = results
            return _dumps(out)
        entry: Dict[str, Any] = {
            "case": case["name"],
            "kind": case["kind"],
            "message": case["message"],
        }
        judged = judge_case(
            probe,
            case["kind"],
            markers=case.get("markers") or [],
            require_markers=bool(case.get("require_markers")),
        )
        # soft multi-turn (e.g. session_waiter second hop): NOT a hard pass unless
        # the curated markers hit. Emoji/short LLM reply → soft_pass (informational).
        if case.get("soft"):
            markers = case.get("markers") or []
            mark_hit = judged.get("markers_hit")
            not_confirmed = (
                (markers and mark_hit is False)
                or judged["verdict"] == "content_mismatch"
            )
            if not_confirmed and judged["verdict"] in ("pass", "content_mismatch"):
                judged["verdict"] = "soft_pass"
                judged["sse_errors"] = list(judged.get("sse_errors") or []) + [
                    "multi_turn_soft: waiter follow-up not confirmed under sequential probe"
                ]
        entry.update(judged)
        results.append(entry)
        if case.get("name") == "quiz_start":
            time.sleep(1.0)

    # ── step 4: post-run failed re-check ───────────────────────
    failed_after = client.get("/api/v1/plugins/failed")
    crashed = False
    if failed_after.ok:
        analysis = analyze_failed_payload(failed_after.data)
        mine = [
            x for x in analysis.get("diagnoses", [])
            if pid in (x.get("dir_name", ""), x.get("plugin_name", ""))
        ]
        if mine:
            crashed = True
            out["pipeline"]["post_run_failed"] = mine
            from .error_fingerprint import record_diagnoses_if_enabled

            recorded = record_diagnoses_if_enabled(mine, source=f"smoke:{pid}")
            if recorded:
                out["pipeline"]["error_kb_recorded"] = recorded

    # ── verdict ────────────────────────────────────────────────
    good = ("pass", "soft_pass")
    passed = sum(1 for r in results if r["verdict"] in good)
    platform_fails = sum(1 for r in results if r["verdict"] == "platform_error")
    handler_fails = sum(1 for r in results if r["verdict"] == "handler_error")
    mismatch = sum(1 for r in results if r["verdict"] == "content_mismatch")
    no_content = sum(1 for r in results if r["verdict"] == "no_content")
    out["results"] = results
    out["summary"] = {
        "total": len(results),
        "passed": passed,
        "failed": len(results) - passed,
        "platform_or_llm_failures": platform_fails,
        "handler_errors": handler_fails,
        "content_mismatches": mismatch,
        "no_content": no_content,
        "plugin_crashed_during_run": crashed,
        "elapsed_ms": round((time.time() - t0) * 1000.0, 2),
    }
    out["ok"] = passed == len(results) and not crashed
    out["plugin_loaded"] = not crashed and bool(info.get("activated"))
    out["session_note"] = (
        "All messages went to the fixed smoke session (mcp-smoke-<username>); "
        "inspect/delete it in Dashboard WebChat. "
        "Ensure config profile plugin_set includes this plugin_id or commands "
        "become LLM chit-chat (content_mismatch)."
    )
    if not out["ok"]:
        fails = [r["case"] for r in results if r["verdict"] not in good]
        if platform_fails and platform_fails == len(results) - passed and not crashed:
            out["error_kind"] = "platform_or_llm_unavailable"
            out["next_step"] = (
                f"Plugin is loaded, but replies look like LLM/auth failures "
                f"(cases {fails}). Fix provider on the WebChat profile."
            )
        elif handler_fails:
            out["error_kind"] = "plugin_handler_error"
            out["next_step"] = (
                f"Handler exceptions in cases {fails} — fix plugin code "
                f"(see plain text / auto-fix-guide), reinstall, rerun."
            )
        elif no_content and no_content == len(results) - passed:
            # All failing cases returned NO output (even a pure LLM message).
            # This is NOT an API-key/auth problem (that would surface as
            # platform_error / 403). It means the WebChat profile's provider is
            # not configured/valid, so nothing produces a reply.
            out["error_kind"] = "no_content_all"
            out["next_step"] = (
                f"All failing cases ({fails}) returned no output at all — even a "
                f"plain LLM message. This is NOT an API-key/scope problem (auth "
                f"issues show as platform_error/403). It means the WebChat config "
                f"profile (plugin_dev_skill) has no valid provider configured, so "
                f"nothing replies. Fix the provider in Dashboard, or rebuild the "
                f"profile with astrbot_ensure_plugin_dev_skill (pick a provider_id)."
            )
        elif mismatch:
            out["error_kind"] = "content_mismatch"
            out["next_step"] = (
                f"Cases {fails} did not match plugin-owned content (LLM chit-chat "
                f"or wrong markers). Check plugin_set on the config profile, "
                f"command registration, and multi-turn session continuity."
            )
        else:
            out["next_step"] = (
                f"Investigate failing cases {fails}; "
                "for load crashes see pipeline.post_run_failed."
            )
    return _dumps(out)
