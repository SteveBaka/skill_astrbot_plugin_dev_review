#!/usr/bin/env python3
# [DEV] Verify contract tables against AstrBot tag/master sources.
"""
Check whether contracts.FILTER_ATTR_KNOWN (the @filter.* export surface) still
matches astrbot/api/event/filter/__init__.py at a given ref. Run after each
AstrBot release; this keeps version claims in the skill repo-verified instead
of remembered.

  python3 mcp/scripts/check_contract_drift.py              # ref=master, exact match
  python3 mcp/scripts/check_contract_drift.py --ref v4.16.0  # subset check

Exit codes:
  0  no drift
  1  drift detected (update contracts.py)
  3  fetch failed / bad ref
"""

from __future__ import annotations

import argparse
import sys
import urllib.error
import urllib.request
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR.parent))

from runtime.contract_drift import (  # noqa: E402
    FILTER_API_PATH,
    RAW_BASE,
    drift_report,
    parse_filter_api_exports,
)


def fetch(ref: str) -> str:
    url = f"{RAW_BASE}/{ref}/{FILTER_API_PATH}"
    with urllib.request.urlopen(url, timeout=30) as resp:
        if resp.status != 200:
            raise RuntimeError(f"HTTP {resp.status} for {url}")
        return resp.read().decode("utf-8", errors="replace")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--ref", default="master", help="tag or branch (default: master)")
    args = ap.parse_args()

    try:
        source = fetch(args.ref)
    except (urllib.error.URLError, RuntimeError) as exc:
        print(f"[contract-drift] fetch failed: {exc}", file=sys.stderr)
        return 3

    aliases, classes = parse_filter_api_exports(source)
    report = drift_report(aliases, classes, ref=args.ref)
    print(f"[contract-drift] ref={args.ref}")
    print(f"  decorator aliases: {len(aliases)}, filter classes: {len(classes)}")
    if report["problems"]:
        for p in report["problems"]:
            print(f"  DRIFT  {p}")
        print("  → update contracts.FILTER_ATTR_KNOWN / CONTRACT_PROVENANCE")
        return 1
    print("  no drift — contract matches source")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
