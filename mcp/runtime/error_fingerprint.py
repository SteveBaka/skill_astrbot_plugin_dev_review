# [RUNTIME P2+] Desensitized error fingerprints → auto-fix-guide feedback.
"""
Turn runtime errors (install failures / smoke SSE / failed-list diagnoses) into
stable, **desensitized** fingerprints, accumulate them locally, and propose new
`review/auto-fix-guide.md` entries for recurring unclassified patterns.

Why:
  - AstrBot evolves; new error shapes appear that _SIGNATURES cannot predict.
  - We want to capture real-world errors during regression runs (plugin-types +
    adapter smoke) WITHOUT leaking paths/tokens/plugin ids into the repo.
  - Recurring fingerprints become candidate FIX entries → the skill learns.

Design:
  - Pure logic (no HTTP). Store is an opt-in local JSON (gitignored), only
    written when the caller passes a store path (default off).
  - `desensitize` strips: absolute paths, /data/plugins/<slug>, UUIDs, long hex,
    tokens (>=8 chars), line numbers, quoted literal values, plugin class names.
  - `fingerprint_of` returns a stable key per normalized error message.
  - `propose_fix_entries` emits draft sections for unclassified keys seen >= N
    times, in auto-fix-guide.md `### FIX-xx` format.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# ── desensitization patterns ───────────────────────────────────

_UUID_RE = re.compile(
    r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
)
_HEX_RE = re.compile(r"\b[0-9a-fA-F]{16,}\b")
_LINE_RE = re.compile(r", line \d+")
_PATH_RE = re.compile(
    r"(?:/\w+){2,}(?:\.\w+)?|(?:\w:)?[\\/][A-Za-z0-9_.\\/-]+\.(?:py|json|yaml|yml|log)"
)
_PLUGIN_RE = re.compile(r"\bastrbot_plugin_[a-z0-9_]+\b")
_CLASS_RE = re.compile(r"\b[A-Z][A-Za-z0-9_]*Plugin\b")
_TOKEN_RE = re.compile(r"\b(?:sk-|ak_|abk_|token[=: ]|key[=: ]|bearer )[^\s\"']{8,}\b", re.I)
_QUOTED_LITERAL_RE = re.compile(r"['\"][A-Za-z0-9_.:-]{6,}['\"]")
_NUMBER_RE = re.compile(r"\b\d{2,}\b")
_WS_RE = re.compile(r"\s+")
_BLANK = re.compile(r"[ \t]+")


def desensitize(text: str) -> str:
    """Normalize an error string so paths/UUIDs/tokens/ids become stable placeholders."""
    if not text:
        return ""
    s = text
    s = _UUID_RE.sub("<UUID>", s)
    s = _HEX_RE.sub("<HEX>", s)
    s = _TOKEN_RE.sub("<TOKEN>", s)
    s = _PATH_RE.sub("<PATH>", s)
    s = _PLUGIN_RE.sub("<PLUGIN>", s)
    s = _CLASS_RE.sub("<Plugin>", s)
    s = _LINE_RE.sub(", line <N>", s)
    s = _QUOTED_LITERAL_RE.sub("<lit>", s)
    s = _NUMBER_RE.sub("<N>", s)
    # collapse whitespace (also protects multi-line tracebacks from key drift)
    s = _BLANK.sub(" ", s).strip()
    s = _WS_RE.sub(" ", s)
    return s[:500]


def fingerprint_of(
    error: str,
    traceback_text: str = "",
    error_class: str = "",
    fix_rule: Optional[str] = None,
) -> Tuple[str, str, Dict[str, Any]]:
    """
    Return (key, desensitized_sample, meta).

    key = sha256 of desensitized error (+ first traceback line when present).
    Fix-rule/error_class passed through for reporting; unclassified stays None.
    """
    tb = (traceback_text or "").strip()
    # use the tail of the traceback (exception line) for signal, desensitized
    tb_tail = "\n".join(tb.splitlines()[-2:]) if tb else ""
    sample = desensitize(f"{error}\n{tb_tail}")
    hashed = hashlib.sha256(sample.encode("utf-8")).hexdigest()[:20]
    meta: Dict[str, Any] = {
        "error_class": error_class or None,
        "fix_rule": fix_rule or None,
    }
    return hashed, sample, meta


# ── store ──────────────────────────────────────────────────────


class FingerprintStore:
    """Append-only local store of desensitized error fingerprints (opt-in)."""

    def __init__(self, path: Optional[str | Path] = None) -> None:
        self.path = Path(path).expanduser().resolve() if path else None
        self.records: Dict[str, Dict[str, Any]] = {}
        if self.path and self.path.is_file():
            self.load()

    def load(self) -> None:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            self.records = data.get("records", {}) if isinstance(data, dict) else {}
        except Exception:
            self.records = {}

    def save(self) -> None:
        if not self.path:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"updated_at": int(time.time()), "records": self.records}
        self.path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def record(
        self,
        error: str,
        traceback_text: str = "",
        error_class: str = "",
        fix_rule: Optional[str] = None,
        source: str = "",
    ) -> str:
        key, sample, meta = fingerprint_of(
            error, traceback_text, error_class=error_class, fix_rule=fix_rule
        )
        rec = self.records.get(key)
        if rec is None:
            rec = {
                "key": key,
                "sample": sample,
                "count": 0,
                "first_seen": int(time.time()),
                "last_seen": int(time.time()),
                "error_class": meta["error_class"],
                "fix_rule": meta["fix_rule"],
                "sources": [],
            }
            self.records[key] = rec
        rec["count"] = int(rec.get("count", 0)) + 1
        rec["last_seen"] = int(time.time())
        if source and source not in rec["sources"]:
            rec["sources"].append(source)
        if self.path:
            self.save()
        return key

    def record_analysis(
        self, diagnoses: List[Dict[str, Any]], source: str = ""
    ) -> int:
        """Record every diagnosis from analyze_failed_payload (returns count)."""
        n = 0
        for d in diagnoses or []:
            self.record(
                str(d.get("error") or ""),
                str(d.get("traceback_tail") or ""),
                error_class=str(d.get("error_class") or ""),
                fix_rule=d.get("fix_rule"),
                source=source or str(d.get("dir_name") or ""),
            )
            n += 1
        return n

    def unclassified(self, min_occurrences: int = 1) -> List[Dict[str, Any]]:
        return [
            r
            for r in self.records.values()
            if not r.get("fix_rule") and int(r.get("count", 0)) >= min_occurrences
        ]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "path": str(self.path) if self.path else None,
            "total_records": len(self.records),
            "records": self.records,
        }


# ── env-gated recording hook (used by install / smoke failure paths) ─


def record_diagnoses_if_enabled(
    diagnoses: List[Dict[str, Any]], source: str = ""
) -> int:
    """
    Record diagnoses into the KB only when ASTRBOT_ERROR_KB points to a store path.

    No-op by default (returns 0) — keeps MCP privacy posture. Samples stored are
    always desensitized; fix_rule-bearing diagnoses are tracked but not proposed.
    """
    path = (os.environ.get("ASTRBOT_ERROR_KB") or "").strip()
    if not path:
        return 0
    try:
        store = FingerprintStore(path)
        return store.record_analysis(diagnoses, source=source)
    except Exception:
        return 0


# ── auto-fix-guide feedback ────────────────────────────────────

# Placeholder tokens emitted by desensitize (not concrete error keywords)
PLACEHOLDER_TOKENS: frozenset = frozenset(
    {"<UUID>", "<HEX>", "<TOKEN>", "<PATH>", "<PLUGIN>", "<Plugin>", "<lit>", "<N>"}
)


def max_fix_number(guide_path: str | Path) -> int:
    """Scan auto-fix-guide.md for highest `### FIX-<N>` number."""
    p = Path(guide_path)
    if not p.is_file():
        return 29
    nums = [int(m) for m in re.findall(r"###\s*FIX-(\d+)", p.read_text(encoding="utf-8"))]
    return max(nums) if nums else 29


def validate_fix_entry(
    entry: Dict[str, Any],
    guide_path: str | Path,
    *,
    min_concrete_tokens: int = 3,
) -> Dict[str, Any]:
    """
    Pre-approval validation: reject duplicates and non-actionable proposals.

    Checks:
      1. empty / too short sample
      2. placeholder-only sample (no concrete error keyword) → not actionable
      3. not enough concrete tokens (e.g. "No module named <lit>" → 1) → too generic
      4. regex compiles
      5. pattern already present in auto-fix-guide.md → duplicate
      6. title text already used in auto-fix-guide.md → duplicate

    Returns {"ok": bool, "reasons": [str]}.
    """
    reasons: List[str] = []
    sample = (entry.get("sample") or "").strip()
    if not sample:
        reasons.append("empty_sample")
    elif len(sample) < 10:
        reasons.append(f"too_short:{len(sample)}")

    stripped = sample.replace("<", "").replace(">", "").strip()
    all_tokens = [t for t in re.split(r"\s+", sample) if t]
    if all_tokens and all(t in PLACEHOLDER_TOKENS for t in all_tokens):
        reasons.append("placeholder_only")
    elif stripped and not stripped.strip():
        reasons.append("placeholder_only")
    tokens = [
        t
        for t in re.split(r"\s+", sample)
        if t and t not in PLACEHOLDER_TOKENS and len(t) >= 4
    ]
    if len(tokens) < min_concrete_tokens:
        reasons.append(
            f"too_generic:{len(tokens)}_concrete_tokens<{min_concrete_tokens}"
        )

    pattern = entry.get("pattern") or ""
    if pattern:
        try:
            re.compile(pattern)
        except re.error as exc:
            reasons.append(f"invalid_pattern:{exc}")
    else:
        reasons.append("missing_pattern")

    guide_text = ""
    gp = Path(guide_path)
    if gp.is_file():
        guide_text = gp.read_text(encoding="utf-8")
    if guide_text:
        if pattern and pattern in guide_text:
            reasons.append("duplicate_pattern_in_guide")
        title = (entry.get("title") or "").strip()
        if title and f"FIX-{entry.get('fix_rule', '')}: {title}" in guide_text:
            reasons.append("duplicate_title_in_guide")

    return {"ok": not reasons, "reasons": reasons}


def propose_fix_entries(
    store: FingerprintStore,
    guide_path: str | Path,
    *,
    min_occurrences: int = 2,
    max_entries: int = 5,
) -> List[Dict[str, Any]]:
    """
    Draft auto-fix-guide sections for recurring unclassified fingerprints.

    Returns list of dicts:
      {fix_rule, title, pattern, sample, hint, sources, occurrences}
    Pattern is a conservative regex built from the desensitized sample (quoted).
    """
    unclassified = store.unclassified(min_occurrences=min_occurrences)
    unclassified.sort(key=lambda r: int(r.get("count", 0)), reverse=True)
    start = max_fix_number(guide_path) + 1
    entries: List[Dict[str, Any]] = []
    for i, rec in enumerate(unclassified[:max_entries]):
        sample = rec.get("sample", "")
        # escape regex metacharacters except the <PLACEHOLDER> markers
        quoted = re.escape(sample)
        for ph in ("<UUID>", "<HEX>", "<TOKEN>", "<PATH>", "<PLUGIN>", "<Plugin>", "<lit>", "<N>"):
            quoted = quoted.replace(re.escape(ph), r".+?")
        entry = {
            "fix_rule": f"FIX-{start + i}",
            "title": sample[:60],
            "pattern": quoted,
            "sample": sample,
            "hint": (
                "Recurring unclassified error (desensitized). Verify it in a "
                "real traceback, then document the root cause + correct code in "
                "auto-fix-guide.md under this FIX id."
            ),
            "sources": rec.get("sources", []),
            "occurrences": int(rec.get("count", 0)),
        }
        entry["validation"] = validate_fix_entry(entry, guide_path)
        entries.append(entry)
    return entries


def render_fix_entries(entries: List[Dict[str, Any]]) -> str:
    """Render proposed entries as a paste-ready auto-fix-guide.md section."""
    lines: List[str] = []
    for e in entries:
        lines.append(f"### {e['fix_rule']}: {e['title']}")
        lines.append("")
        lines.append("**Problem** (desensitized fingerprint):")
        lines.append("")
        lines.append("```text")
        lines.append(e["sample"])
        lines.append("```")
        lines.append("")
        lines.append("**Fingerprint regex (auto-check):**")
        lines.append("")
        lines.append("```python")
        lines.append(f're.compile(r"{e["pattern"]}")')
        lines.append("```")
        lines.append("")
        lines.append(f"**Occurrences**: {e['occurrences']} · **sources**: {', '.join(e['sources'] or [])}")
        lines.append("")
        lines.append(f"**Hint**: {e['hint']}")
        lines.append("")
        lines.append("---")
        lines.append("")
    return "\n".join(lines)
