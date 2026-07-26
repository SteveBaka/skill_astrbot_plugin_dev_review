#!/usr/bin/env python3
# [DEV] OpenAPI contract drift detection against https://docs.astrbot.app/openapi.json
"""
Check whether the live AstrBot OpenAPI spec has drifted from the local snapshot,
with special focus on the endpoints used by mcp/runtime.

Data source (verified 2026-07):
  - https://docs.astrbot.app/scalar.html is a Scalar UI shell; the machine-readable
    source is https://docs.astrbot.app/openapi.json (no auth, ETag + Last-Modified).
  - info.version is pinned at "0.1.0" — never use it for drift; use ETag/content.

Usage (from repo root or mcp/):
  python3 mcp/scripts/check_openapi_drift.py            # check, report, exit code
  python3 mcp/scripts/check_openapi_drift.py --update   # refresh local snapshot
  python3 mcp/scripts/check_openapi_drift.py --offline  # runtime-vs-snapshot only

Exit codes:
  0  no drift (or offline check passed)
  1  drift detected that touches runtime-used endpoints  → fix runtime first
  2  drift detected elsewhere only                       → informational
  3  snapshot missing / fetch failed / bad invocation

Snapshot: "AstrBot OpenAPI v1.json" at repo root (gitignored; local dev asset).
ETag sidecar: ".astrbot_openapi.etag" next to it (gitignored) for cheap 304 checks.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Dict, List, Set, Tuple

LIVE_URL = "https://docs.astrbot.app/openapi.json"

SCRIPT_DIR = Path(__file__).resolve().parent
MCP_DIR = SCRIPT_DIR.parent
REPO_ROOT = MCP_DIR.parent
SNAPSHOT_PATH = REPO_ROOT / "AstrBot OpenAPI v1.json"
ETAG_PATH = REPO_ROOT / ".astrbot_openapi.etag"
RUNTIME_DIR = MCP_DIR / "runtime"

HTTP_METHODS = ("get", "post", "put", "patch", "delete")

# f-string path segments like {encode_plugin_id(pid)} or spec's {plugin_id};
# tolerate nested quotes/brackets inside f-string expressions
_PARAM_SEG = re.compile(r"\{[^{}]*(?:\([^()]*\))?[^{}]*\}")
# API path literals in runtime source; stop only at whitespace or quote that
# does not sit inside a {...} expression — simpler: grab up to closing quote
# after masking f-string expressions first.
_FSTRING_EXPR = re.compile(r"\{[^{}]*\}")
_USED_PATH = re.compile(r"[\"'](/api/v1/[^\"'\s]*)[\"']")


def normalize_path(path: str) -> str:
    """Collapse all {param}/{expr} segments so code paths match spec templates."""
    return _PARAM_SEG.sub("{}", path)


def extract_runtime_paths(runtime_dir: Path = RUNTIME_DIR) -> Set[str]:
    """Scan runtime/*.py for /api/v1/... literals (f-string args normalized)."""
    used: Set[str] = set()
    for py in sorted(runtime_dir.glob("*.py")):
        text = py.read_text(encoding="utf-8")
        # mask f-string expressions (may contain quotes, e.g. existing['id'])
        # so the path-literal regex does not terminate early
        masked = _FSTRING_EXPR.sub("{}", text)
        for m in _USED_PATH.finditer(masked):
            used.add(normalize_path(m.group(1)))
    return used


def _path_matches_template(used: str, template: str) -> bool:
    """
    True if a code path matches a spec template.

    Segments must align; each template segment is either "{}" (param, matches
    anything) or a literal that must equal the used segment. Also true when the
    used segment is "{}" against a template param. Handles literal ids hitting
    param slots, e.g. used /config-profiles/default vs spec /config-profiles/{}.
    """
    us, ts = used.split("/"), template.split("/")
    if len(us) != len(ts):
        return False
    for u, t in zip(us, ts):
        if t == "{}":
            # template param slot accepts any used segment (literal or param)
            continue
        if u != t:
            # used param "{}" must NOT match a literal template segment
            return False
    return True


def _resolve_against_spec(used_paths: Set[str], spec_ops: Dict[str, List[str]]) -> Dict[str, str | None]:
    """Map each used path -> matching spec template (or None)."""
    out: Dict[str, str | None] = {}
    templates = list(spec_ops)
    for up in used_paths:
        if up in spec_ops:
            out[up] = up
            continue
        hit = next((t for t in templates if _path_matches_template(up, t)), None)
        out[up] = hit
    return out


def spec_operations(spec: dict) -> Dict[str, List[str]]:
    """{normalized_path: [METHODS]} from an OpenAPI spec."""
    out: Dict[str, List[str]] = {}
    for path, item in (spec.get("paths") or {}).items():
        if not isinstance(item, dict):
            continue
        methods = [m.upper() for m in HTTP_METHODS if m in item]
        out[normalize_path(path)] = methods
    return out


def fetch_live(etag: str | None) -> Tuple[str, bytes | None, str | None]:
    """
    Return (status, body, new_etag).

    status: "not_modified" | "ok" | "error:<detail>"
    Uses If-None-Match when an ETag is available (cheap 304 fast path).
    """
    req = urllib.request.Request(LIVE_URL, headers={"User-Agent": "skill-astrbot-drift/1.0"})
    if etag:
        req.add_header("If-None-Match", etag)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return "ok", resp.read(), resp.headers.get("ETag")
    except urllib.error.HTTPError as exc:
        if exc.code == 304:
            return "not_modified", None, etag
        return f"error:HTTP {exc.code}", None, None
    except Exception as exc:  # noqa: BLE001 — report, don't crash CI
        return f"error:{type(exc).__name__}: {exc}", None, None


def diff_ops(
    old: Dict[str, List[str]], new: Dict[str, List[str]]
) -> Dict[str, List[str]]:
    """Structured drift between two {path: [methods]} maps."""
    added = sorted(set(new) - set(old))
    removed = sorted(set(old) - set(new))
    changed = sorted(
        p for p in set(old) & set(new) if sorted(old[p]) != sorted(new[p])
    )
    return {"added_paths": added, "removed_paths": removed, "changed_methods": changed}


def runtime_impact(
    drift: Dict[str, List[str]], runtime_paths: Set[str]
) -> List[str]:
    """Runtime-used endpoints hit by removed/changed entries (added is safe)."""
    hit_templates = set(drift["removed_paths"]) | set(drift["changed_methods"])
    impacted = []
    for up in runtime_paths:
        if any(_path_matches_template(up, t) for t in hit_templates):
            impacted.append(up)
    return sorted(impacted)


def check_runtime_vs_spec(
    spec_ops: Dict[str, List[str]], runtime_paths: Set[str]
) -> List[str]:
    """Runtime-used paths with no matching template in a spec (broken contract)."""
    resolved = _resolve_against_spec(runtime_paths, spec_ops)
    return sorted(p for p, hit in resolved.items() if hit is None)


def main() -> int:
    ap = argparse.ArgumentParser(description="AstrBot OpenAPI contract drift check")
    ap.add_argument("--update", action="store_true", help="refresh local snapshot from live")
    ap.add_argument("--offline", action="store_true", help="only check runtime vs local snapshot")
    args = ap.parse_args()

    if not SNAPSHOT_PATH.is_file() and not args.update:
        print(f"[drift] snapshot missing: {SNAPSHOT_PATH}")
        print("[drift] run with --update to create it from live")
        return 3

    runtime_paths = extract_runtime_paths()
    print(f"[drift] runtime-used endpoints: {len(runtime_paths)}")

    # ── offline: snapshot ↔ runtime only ───────────────────────
    if args.offline:
        snap = json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))
        missing = check_runtime_vs_spec(spec_operations(snap), runtime_paths)
        if missing:
            print("[drift] RUNTIME BROKEN vs snapshot — endpoints not in spec:")
            for p in missing:
                print(f"    ! {p}")
            return 1
        print("[drift] offline OK — all runtime endpoints exist in snapshot")
        return 0

    # ── fetch live (ETag fast path) ────────────────────────────
    etag = ETAG_PATH.read_text().strip() if ETAG_PATH.is_file() else None
    status, body, new_etag = fetch_live(etag)

    if status == "not_modified":
        print("[drift] live spec unchanged (ETag 304) — no drift")
        return 0
    if status.startswith("error"):
        print(f"[drift] fetch failed: {status}")
        print("[drift] falling back to --offline check")
        snap = json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))
        missing = check_runtime_vs_spec(spec_operations(snap), runtime_paths)
        return 1 if missing else 3

    live = json.loads(body.decode("utf-8"))
    live_ops = spec_operations(live)
    print(f"[drift] live spec: {len(live_ops)} paths (fetched fresh)")

    if args.update:
        SNAPSHOT_PATH.write_bytes(body)
        if new_etag:
            ETAG_PATH.write_text(new_etag)
        print(f"[drift] snapshot updated: {SNAPSHOT_PATH.name}")
        missing = check_runtime_vs_spec(live_ops, runtime_paths)
        if missing:
            print("[drift] WARNING — runtime endpoints missing in new snapshot:")
            for p in missing:
                print(f"    ! {p}")
            return 1
        return 0

    snap = json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))
    snap_ops = spec_operations(snap)
    drift = diff_ops(snap_ops, live_ops)
    total = sum(len(v) for v in drift.values())

    if total == 0:
        # content-identical (or param-name-only changes); refresh etag for next time
        if new_etag:
            ETAG_PATH.write_text(new_etag)
        print("[drift] no path/method drift between snapshot and live")
        return 0

    print(f"[drift] DRIFT DETECTED ({total} entries):")
    for key, label in (
        ("added_paths", "+ added"),
        ("removed_paths", "- removed"),
        ("changed_methods", "~ methods changed"),
    ):
        for p in drift[key]:
            print(f"    {label}: {p}")

    impacted = runtime_impact(drift, runtime_paths)
    missing_live = check_runtime_vs_spec(live_ops, runtime_paths)
    affected = sorted(set(impacted) | set(missing_live))
    if affected:
        print("[drift] RUNTIME AFFECTED — update mcp/runtime before trusting these tools:")
        for p in affected:
            print(f"    ! {p}")
        print("[drift] after fixing runtime, refresh snapshot: --update")
        return 1

    print("[drift] runtime endpoints unaffected; refresh snapshot when convenient (--update)")
    return 2


if __name__ == "__main__":
    sys.exit(main())
