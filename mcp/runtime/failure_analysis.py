# [RUNTIME P2+] Failure analysis: mine /plugins/failed records for actionable causes.
"""
Turn raw failed-plugin records into classified, FIX-rule-linked diagnoses.

Data source (source-verified, star_manager.py `_build_failed_plugin_record`):
  GET /api/v1/plugins/failed → {dir_name: record}
  record = {
    "name", "error" (str(exception)), "traceback" (full format_exc text),
    "reserved", + metadata fields when readable (version/author/plugin_id/...)
  }
This is the richest zero-extra-permission error signal AstrBot exposes:
plugin scope only — no system-scope /logs access needed for load failures.

Design:
  - Pure logic (no HTTP) so it is unit-testable and reusable by future
    smoke_suite / review tooling.
  - Classification maps to the skill's FIX catalog (review/auto-fix-guide.md)
    so an agent can jump straight to the fix pattern.
  - Output keeps a short traceback tail, never the full text (token economy);
    the raw record is still available from the unmodified API payload.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

# ── error signature → (error_class, fix_rule, hint) ────────────
# Ordered: first match wins; most specific patterns first.
# fix_rule refers to review/auto-fix-guide.md; None = no direct FIX entry.
_SIGNATURES: List[Tuple[re.Pattern[str], str, Optional[str], str]] = [
    (
        re.compile(r"No module named ['\"]astrbot\.api\.logger['\"]"),
        "wrong_import_path",
        "FIX-00",
        "Use `from astrbot.api import logger` — astrbot.api.logger module does not exist.",
    ),
    (
        re.compile(r"(ModuleNotFoundError|ImportError).*['\"]astrbot[\w.]*['\"]", re.S),
        "wrong_import_path",
        "FIX-00",
        "Import path not in AstrBot API. Check review/main-file-checklist.md import table.",
    ),
    (
        re.compile(r"No module named ['\"]([A-Za-z0-9_]+)['\"]"),
        "missing_dependency",
        None,
        "Third-party module missing: add it to requirements.txt "
        "(AstrBot installs plugin requirements on install/reload).",
    ),
    (
        re.compile(r"cannot import name ['\"]([A-Za-z0-9_]+)['\"]"),
        "wrong_import_symbol",
        "FIX-00",
        "Symbol does not exist at that path (renamed/removed API?). "
        "Validate with the import table / validate_import tool.",
    ),
    (
        re.compile(r"SyntaxError|IndentationError"),
        "syntax_error",
        None,
        "Python cannot parse the file — see the traceback line/column below.",
    ),
    (
        re.compile(r"got multiple values for argument"),
        "handler_signature",
        "FIX-02",
        "Command handler parameter binding conflict. Read user input from "
        "event.message_str instead of extra function parameters.",
    ),
    (
        re.compile(r"ToolExecResult"),
        "tool_exec_result",
        "FIX-07",
        "Tool.call() must return str on Python 3.12 — do not use ToolExecResult.",
    ),
    (
        re.compile(r"mutable default .* field|default should be a .*Field", re.I),
        "dataclass_mutable_default",
        "FIX-20",
        "dict/list dataclass fields need field(default_factory=...).",
    ),
    (
        re.compile(r"has no attribute ['\"]on_(keyword|full_match|regex)['\"]"),
        "deprecated_filter_api",
        "FIX-21",
        "on_keyword/on_full_match/on_regex removed in v4.x — "
        "use event_message_type + Python matching.",
    ),
    (
        re.compile(r"has no attribute ['\"]config['\"]"),
        "config_not_injected",
        "FIX-22",
        "__init__ must accept `config: AstrBotConfig` and set self.config = config.",
    ),
    (
        re.compile(r"register_llm_tool"),
        "deprecated_register_llm_tool",
        "FIX-13",
        "register_llm_tool() is deprecated — use @filter.llm_tool decorator.",
    ),
    (
        re.compile(r"__init__\(\) (takes|missing)"),
        "init_signature",
        "FIX-01",
        "Star subclass __init__ signature mismatch (missing super().__init__ "
        "or wrong parameters).",
    ),
    (
        re.compile(r"metadata\.yaml|yaml\.(parser|scanner)|ScannerError|ParserError", re.I),
        "metadata_invalid",
        None,
        "metadata.yaml unreadable/invalid — check review/metadata-validation.md.",
    ),
    (
        re.compile(r"PermissionError|Errno 13"),
        "permission_error",
        None,
        "Filesystem permission problem in the plugin store — check AstrBot data dir.",
    ),
]

# Traceback frames worth surfacing: prefer lines inside the plugin's own dir.
_TB_FILE = re.compile(r'File "([^"]+)", line (\d+)')


def _truncate(s: str, limit: int) -> str:
    s = s or ""
    return s if len(s) <= limit else s[:limit] + "…"


def classify_error(error: str, traceback_text: str = "") -> Dict[str, Any]:
    """Classify one error+traceback into {error_class, fix_rule, hint}."""
    haystack = f"{error}\n{traceback_text}"
    for pattern, error_class, fix_rule, hint in _SIGNATURES:
        if pattern.search(haystack):
            return {"error_class": error_class, "fix_rule": fix_rule, "hint": hint}
    return {
        "error_class": "unclassified",
        "fix_rule": None,
        "hint": (
            "No known signature matched. Read the traceback tail; if this is a "
            "recurring pattern, consider adding it to review/auto-fix-guide.md."
        ),
    }


def extract_plugin_frames(
    traceback_text: str, dir_name: str = "", max_frames: int = 3
) -> List[str]:
    """
    Pull the most relevant `File "...", line N` frames from a traceback.

    Preference: frames whose path contains the plugin dir (the developer's own
    code) over framework frames; last frames win (closest to the raise site).
    """
    if not traceback_text:
        return []
    frames = _TB_FILE.findall(traceback_text)
    if not frames:
        return []
    formatted = [f"{path}:{line}" for path, line in frames]
    if dir_name:
        own = [f for f in formatted if dir_name in f]
        if own:
            return own[-max_frames:]
    return formatted[-max_frames:]


def traceback_tail(traceback_text: str, max_lines: int = 6, line_limit: int = 200) -> List[str]:
    """Last N non-empty traceback lines (the exception + raise site)."""
    if not traceback_text:
        return []
    lines = [ln.rstrip() for ln in traceback_text.splitlines() if ln.strip()]
    return [_truncate(ln, line_limit) for ln in lines[-max_lines:]]


def analyze_failed_record(dir_name: str, record: Any) -> Dict[str, Any]:
    """
    Analyze one failed-plugin record from GET /plugins/failed.

    Handles both dict records (normal) and bare-string errors (legacy shape).
    """
    if not isinstance(record, dict):
        err = str(record or "")
        out = {"dir_name": dir_name, "error": _truncate(err, 300)}
        out.update(classify_error(err))
        return out

    error = str(record.get("error") or "")
    tb = str(record.get("traceback") or "")
    out: Dict[str, Any] = {
        "dir_name": dir_name,
        "plugin_name": record.get("name") or dir_name,
        "version": record.get("version"),
        "reserved": bool(record.get("reserved")),
        "error": _truncate(error, 300),
    }
    out.update(classify_error(error, tb))
    out["plugin_frames"] = extract_plugin_frames(tb, dir_name)
    out["traceback_tail"] = traceback_tail(tb)
    return out


def analyze_failed_payload(payload: Any) -> Dict[str, Any]:
    """
    Analyze the whole /plugins/failed response payload.

    Accepts the API envelope ({status, data: {...}}) or the bare dict.
    Returns {failed_count, diagnoses: [...], by_class: {class: count}}.
    """
    data = payload
    if isinstance(data, dict) and "data" in data and isinstance(data["data"], (dict, type(None))):
        data = data.get("data") or {}
    if not isinstance(data, dict):
        return {"failed_count": 0, "diagnoses": [], "by_class": {}}

    diagnoses = [analyze_failed_record(k, v) for k, v in data.items()]
    by_class: Dict[str, int] = {}
    for d in diagnoses:
        by_class[d["error_class"]] = by_class.get(d["error_class"], 0) + 1
    return {
        "failed_count": len(diagnoses),
        "diagnoses": diagnoses,
        "by_class": by_class,
    }
