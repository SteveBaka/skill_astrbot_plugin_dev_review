#!/usr/bin/env python3
# [DEV] Desensitized error-fingerprint KB — record/report/propose for auto-fix-guide.
"""
Capture errors during plugin-types / adapter regression and feed auto-fix-guide.

Usage (from mcp/):
  # record one error (from install failure / smoke / failed diagnosis)
  python3 scripts/error_kb.py --store /tmp/err_kb.json record \
      --error "No module named 'aiofiles'" --class missing_dependency --rule FIX-00 \
      --source astrbot_plugin_quiz

  # record many diagnoses from a JSON payload (analyze_failed_payload output)
  python3 scripts/error_kb.py --store /tmp/err_kb.json record-json diagnoses.json

  # show collected fingerprints (desensitized, counts)
  python3 scripts/error_kb.py --store /tmp/err_kb.json report

  # propose new auto-fix-guide entries for recurring unclassified errors
  python3 scripts/error_kb.py --store /tmp/err_kb.json propose \
      --guide ../review/auto-fix-guide.md --min 2

Default store: mcp/.error_kb.json (gitignored). All samples are desensitized.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from runtime.error_fingerprint import (  # noqa: E402
    FingerprintStore,
    propose_fix_entries,
    render_fix_entries,
)

DEFAULT_STORE = Path(__file__).resolve().parent.parent / ".error_kb.json"


def _store(args) -> FingerprintStore:
    return FingerprintStore(args.store)


def cmd_record(args) -> int:
    store = _store(args)
    key = store.record(
        args.error,
        args.traceback or "",
        error_class=args.class_name or "",
        fix_rule=args.rule,
        source=args.source or "",
    )
    rec = store.records[key]
    print(json.dumps(
        {
            "ok": True,
            "key": key,
            "sample": rec["sample"],
            "count": rec["count"],
            "fix_rule": rec.get("fix_rule"),
            "error_class": rec.get("error_class"),
        },
        ensure_ascii=False,
        indent=2,
    ))
    return 0


def cmd_record_json(args) -> int:
    store = _store(args)
    payload = json.loads(Path(args.json_path).read_text(encoding="utf-8"))
    diagnoses = payload.get("diagnoses", payload) if isinstance(payload, dict) else payload
    n = store.record_analysis(diagnoses, source=args.source or "")
    print(json.dumps({"ok": True, "recorded": n, "store": str(store.path)}))
    return 0


def cmd_report(args) -> int:
    store = _store(args)
    out = store.to_dict()
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


def cmd_propose(args) -> int:
    store = _store(args)
    guide = Path(args.guide)
    entries = propose_fix_entries(
        store, guide, min_occurrences=args.min, max_entries=args.max
    )
    if not entries:
        print("No recurring unclassified fingerprints to propose.")
        return 0
    validated = [e for e in entries if e.get("validation", {}).get("ok")]
    rejected = [e for e in entries if not e.get("validation", {}).get("ok")]
    if validated:
        print(render_fix_entries(validated))
        print(f"# Next FIX number: {validated[-1]['fix_rule']}")
    if rejected:
        print("\n# Skipped by validation (do NOT write without review):")
        for e in rejected:
            reasons = "; ".join(e["validation"].get("reasons", []))
            print(f"- {e['fix_rule']}: {e['title']}  [{reasons}]")
    print(
        f"\n# VALIDATION SUMMARY: {len(validated)} ok / {len(rejected)} rejected"
        " (of proposed; not-ok entries are duplicates/too generic and must not "
        "be appended to auto-fix-guide.md as-is)."
    )
    return 0 if validated else 1


def main() -> int:
    ap = argparse.ArgumentParser(description="Error-fingerprint KB for auto-fix-guide")
    ap.add_argument("--store", default=str(DEFAULT_STORE), help="store json path")
    sub = ap.add_subparsers(dest="command", required=True)

    r = sub.add_parser("record", help="record one error")
    r.add_argument("--error", required=True)
    r.add_argument("--traceback", default="")
    r.add_argument("--class", dest="class_name", default="")
    r.add_argument("--rule", default="")
    r.add_argument("--source", default="")
    r.set_defaults(func=cmd_record)

    rj = sub.add_parser("record-json", help="record diagnoses from analyze_failed_payload JSON")
    rj.add_argument("json_path")
    rj.add_argument("--source", default="")
    rj.set_defaults(func=cmd_record_json)

    rep = sub.add_parser("report", help="list collected fingerprints")
    rep.set_defaults(func=cmd_report)

    pr = sub.add_parser("propose", help="propose auto-fix-guide entries")
    pr.add_argument("--guide", default=str(Path(__file__).resolve().parent.parent.parent / "review" / "auto-fix-guide.md"))
    pr.add_argument("--min", type=int, default=2)
    pr.add_argument("--max", type=int, default=5)
    pr.set_defaults(func=cmd_propose)

    args = ap.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
