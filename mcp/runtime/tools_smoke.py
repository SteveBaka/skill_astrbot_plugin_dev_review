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

Safety / privacy — same posture as chat_probe:
  - Needs confirm=true (or ASTRBOT_ALLOW_CHAT_PROBE) + chat-scoped key
  - All messages land in the ONE fixed smoke session (mcp-smoke-<username>)
  - Output truncated summaries only; no transcripts stored
  - max_cases hard cap; admin-only commands skipped by default
"""

from __future__ import annotations

import json
import os
import time
from typing import Any, Dict, List, Optional

from .client import AstrBotClient, encode_plugin_id
from .failure_analysis import analyze_failed_payload
from .tools_chat import astrbot_chat_probe

DEFAULT_MAX_CASES = 8
HOOK_PROBE_MESSAGE = "请用一句话回复：现在是插件冒烟测试"


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
) -> List[Dict[str, str]]:
    """
    Derive smoke cases from plugin component metadata.

    Priority: non-admin commands (help/info-like first) → command_groups →
    one hook probe → one llm_tool probe. Deduped, capped at max_cases.
    """
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
        # info/help/version-style commands are safest and most diagnostic
        return 0 if any(k in name for k in ("info", "help", "version", "status", "list")) else 1

    commands.sort(key=_info_like)

    cases: List[Dict[str, str]] = []
    seen: set = set()
    for c in commands:
        cmd = str(c.get("command") or c.get("name") or "").strip()
        if not cmd or cmd in seen:
            continue
        seen.add(cmd)
        cases.append({
            "kind": "command",
            "name": cmd,
            "message": f"/{cmd}",
            "expect": "any non-error reply (plain/record/attachment)",
        })
    for g in groups:
        name = str(g.get("command") or g.get("name") or "").strip()
        if not name or name in seen:
            continue
        seen.add(name)
        cases.append({
            "kind": "command_group",
            "name": name,
            "message": f"/{name}",
            "expect": "group help or subcommand list",
        })
    if has_hook:
        cases.append({
            "kind": "hook",
            "name": "llm_hook",
            "message": HOOK_PROBE_MESSAGE,
            "expect": "LLM reply passes through plugin hook without SSE error",
        })
    if has_llm_tool:
        cases.append({
            "kind": "llm_tool",
            "name": "llm_tool",
            "message": "如果有可用的插件工具，请调用它并说明结果",
            "expect": "tool call attempted (LLM may decline — soft signal)",
        })
    return cases[:max_cases]


def judge_case(probe_result: Dict[str, Any], kind: str) -> Dict[str, Any]:
    """Map one chat_probe JSON result to a pass/fail verdict."""
    summary = probe_result.get("summary") or {}
    errors = summary.get("errors") or []
    has_content = bool(
        summary.get("plain_texts") or summary.get("records") or summary.get("attachments")
    )
    ok = bool(probe_result.get("ok"))
    verdict = "pass" if ok else ("error" if errors else "no_content")
    # llm_tool is a soft check: content without tool evidence is not a failure
    if kind == "llm_tool" and not ok and has_content:
        verdict = "soft_pass"
    return {
        "verdict": verdict,
        "sse_errors": errors[:2],
        "content": {
            "plain": [p[:120] for p in (summary.get("plain_texts") or [])[:1]],
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
        # ── step 1b: not found → failed-list diagnosis ─────────
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
    )
    for i, msg in enumerate(
        m.strip() for m in (extra_messages or "").split("||") if m.strip()
    ):
        cases.append({
            "kind": "custom",
            "name": f"custom_{i + 1}",
            "message": msg,
            "expect": "user-defined",
        })
    cases = cases[:max(max_cases, 1)]
    if not cases:
        out["error_kind"] = "no_cases"
        out["error"] = (
            "No smoke cases derivable (no non-admin commands/hooks/tools). "
            "Pass extra_messages or include_admin=true."
        )
        return _dumps(out)
    out["pipeline"]["cases_planned"] = [
        {"kind": c["kind"], "name": c["name"], "message": c["message"]} for c in cases
    ]

    # ── step 3: run probes (fixed smoke session; sequential) ───
    results: List[Dict[str, Any]] = []
    t0 = time.time()
    for case in cases:
        raw = astrbot_chat_probe(
            case["message"],
            confirm_probe=True,  # suite-level confirm already passed
            username=username,
            config_name=config_name,
            timeout_seconds=timeout_seconds,
        )
        probe = json.loads(raw)
        if probe.get("error_kind") in ("bad_request", "chat_probe_disabled", "auth"):
            # config-level failure — abort suite, surface reason
            out["error_kind"] = probe.get("error_kind")
            out["error"] = probe.get("error")
            out["aborted_at_case"] = case["name"]
            out["results"] = results
            return _dumps(out)
        entry = {"case": case["name"], "kind": case["kind"], "message": case["message"]}
        entry.update(judge_case(probe, case["kind"]))
        results.append(entry)

    # ── step 4: post-run failed re-check (runtime crash detector) ─
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

    # ── verdict ────────────────────────────────────────────────
    passed = sum(1 for r in results if r["verdict"] in ("pass", "soft_pass"))
    out["results"] = results
    out["summary"] = {
        "total": len(results),
        "passed": passed,
        "failed": len(results) - passed,
        "plugin_crashed_during_run": crashed,
        "elapsed_ms": round((time.time() - t0) * 1000.0, 2),
    }
    out["ok"] = passed == len(results) and not crashed
    out["session_note"] = (
        "All messages went to the fixed smoke session (mcp-smoke-<username>); "
        "inspect/delete it in Dashboard WebChat."
    )
    if not out["ok"]:
        fails = [r["case"] for r in results if r["verdict"] not in ("pass", "soft_pass")]
        out["next_step"] = (
            f"Investigate failing cases {fails}: read sse_errors/content above; "
            "for runtime crashes see pipeline.post_run_failed (fix_rule links)."
        )
    return _dumps(out)
