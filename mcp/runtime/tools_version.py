# [RUNTIME P1] Version compatibility probe (official gate, read-only).
"""
astrbot_version_check — ask the RUNNING AstrBot whether a plugin's declared
`astrbot_version` range is supported, via POST /api/v1/plugins/version-support/check
(scope: plugin; the exact same validator that blocks plugin loading in core:
star_manager._validate_astrbot_version_specifier → SpecifierSet.contains(VERSION)).

Dual use:
  1. plugin_dir given  → read metadata.yaml astrbot_version and check it
  2. spec given        → check an arbitrary PEP 440 range

Side channel: an impossible spec (e.g. ">=99") makes core reply
"AstrBot <VERSION> does not satisfy ..." — the running core version, without
the dashboard-only `system` scope. Include_probe_version uses that to report
the target's version alongside the verdict.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import yaml

from .client import AstrBotClient
from .config import load_config

_ENDPOINT = "/api/v1/plugins/version-support/check"
_IMPOSSIBLE_SPEC = ">=999999"
_VERSION_RE = re.compile(r"AstrBot (\S+) does not satisfy")


def _dumps(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=2, default=str)


def _read_declared_spec(plugin_dir: str) -> tuple[str | None, str | None]:
    meta = Path(plugin_dir).expanduser() / "metadata.yaml"
    if not meta.is_file():
        return None, f"metadata.yaml not found: {meta}"
    try:
        fields = yaml.safe_load(meta.read_text(encoding="utf-8")) or {}
    except Exception as exc:  # noqa: BLE001
        return None, f"metadata.yaml unreadable: {exc}"
    spec = fields.get("astrbot_version")
    if spec is None:
        return None, None  # declared nothing → core treats as supported
    return str(spec), None


def astrbot_version_check(
    spec: str = "",
    plugin_dir: str = "",
    include_probe_version: bool = False,
) -> str:
    """Check an astrbot_version range against the running AstrBot gate."""
    declared: str | None = None
    if plugin_dir:
        declared, err = _read_declared_spec(plugin_dir)
        if err:
            return _dumps({"ok": False, "error_kind": "metadata_unreadable", "error": err})
        if declared is None:
            return _dumps(
                {
                    "ok": True,
                    "supported": True,
                    "astrbot_version": "",
                    "note": "metadata.yaml declares no astrbot_version — core treats "
                    "it as unconditioned (always supported).",
                }
            )
    checked = declared or (spec or "").strip()
    if not checked:
        return _dumps(
            {
                "ok": False,
                "error_kind": "bad_args",
                "error": "Provide plugin_dir (read metadata astrbot_version) or spec.",
            }
        )

    cfg = load_config()
    if not cfg.enabled:
        return _dumps(
            {
                "ok": False,
                "error_kind": "not_configured",
                "error": "Runtime disabled: set ASTRBOT_BASE_URL on the MCP host env.",
            }
        )
    client = AstrBotClient(cfg)

    out: dict[str, Any] = {}
    res = client.post(_ENDPOINT, json_body={"astrbot_version": checked})
    out["astrbot_version"] = checked
    if not res.ok:
        out["ok"] = False
        out["error_kind"] = res.error_kind
        out["error"] = res.error
        return _dumps(out)
    data = res.data.get("data") if isinstance(res.data, dict) else None
    out["ok"] = True
    out["supported"] = bool(data.get("supported")) if isinstance(data, dict) else None
    out["message"] = (data or {}).get("message")
    # Even when supported=True the reply message carries the running VERSION
    # for unsupported specs only; supported=True replies have message=None.
    if include_probe_version:
        probe = client.post(_ENDPOINT, json_body={"astrbot_version": _IMPOSSIBLE_SPEC})
        m = _VERSION_RE.search(
            str((probe.data or {}).get("data", {}).get("message", ""))
            if isinstance(probe.data, dict)
            else ""
        )
        out["running_astrbot_version"] = m.group(1) if m else None
    return _dumps(out)
