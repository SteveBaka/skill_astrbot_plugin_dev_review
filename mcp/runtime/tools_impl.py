# [RUNTIME] P0 read-only tool implementations (pure functions → string for FastMCP).
"""
Read-only runtime tools for stable connection verification.

Tools (P0):
  astrbot_runtime_info   — env + optional live probe (does not print token)
  astrbot_plugin_list    — GET /api/v1/plugins
  astrbot_plugin_failed  — GET /api/v1/plugins/failed
  astrbot_plugin_get     — GET /api/v1/plugins/{plugin_id}

P1 manage tools live in tools_manage.py (reload / enable / config).

Analysis of expected outcomes (for operators):
  - not_configured: only docs MCP works; set ASTRBOT_BASE_URL
  - connect/timeout: LAN routing / firewall / wrong IP:port / AstrBot down
  - auth: token missing or wrong mode
  - ok + plugins: control plane reachable
  - mutations: see config.allow_mutations / capabilities in runtime_info
"""

from __future__ import annotations

import json
from typing import Any, Dict, Optional

from .client import AstrBotClient
from .config import load_config


def _dumps(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=2, default=str)


def astrbot_runtime_info(probe: bool = True) -> str:
    """
    Show runtime config (no secrets) and optionally probe OpenAPI.

    probe=True (default): GET /api/v1/plugins?include_reserved=true with limit of
    response size — proves LAN path + auth without mutating state.
    """
    cfg = load_config()
    out: Dict[str, Any] = {
        "phase": "P0+P1",
        "purpose": "stable_connection + plugin_manage(reload/enable/config)",
        "config": cfg.public_dict(),
        "docs_mcp": "unaffected — always available regardless of ASTRBOT_*",
        "mutations_gate": (
            "open" if cfg.allow_mutations else "closed — set ASTRBOT_ALLOW_MUTATIONS=true"
        ),
        "manage_tools": [
            "astrbot_plugin_config_get",
            "astrbot_plugin_config_schema",
            "astrbot_plugin_config_set",
            "astrbot_plugin_set_enabled",
            "astrbot_plugin_reload",
            "astrbot_plugin_pack_preview",
            "astrbot_plugin_install_path",
            "astrbot_plugin_uninstall",
            "astrbot_providers_brief",
            "astrbot_config_profiles_brief",
            "astrbot_post_install_hints",
            "astrbot_ensure_plugin_dev_skill",
            "astrbot_chat_sessions_brief",
            "astrbot_chat_probe",
            "astrbot_chat_sessions_cleanup",
            "astrbot_review_path",
            "astrbot_smoke_suite",
        ],
        "install_scheme_a": "pack(.gitignore) → install/upload → enable → reload → failed",
        "plugin_dev_skill": (
            "ensure from default + user provider; WebChat main test; "
            "no auto config dump; chat smoke opt-in only"
        ),
        "chat_probe": (
            "confirm_probe + username + config_name=plugin_dev_skill; "
            "SSE parse; fixed smoke session mcp-smoke-<username>; "
            "chat-scoped API key"
        ),
        "uninstall_default": "keep_config=true, keep_data=true; ask user first",
    }

    if not cfg.enabled:
        out["probe"] = {
            "skipped": True,
            "reason": "ASTRBOT_BASE_URL empty",
            "next_step": (
                "On MCP host set env ASTRBOT_BASE_URL=http://<astrbot-lan-ip>:6185 "
                "and ASTRBOT_TOKEN if required, then restart MCP client."
            ),
        }
        return _dumps(out)

    if not probe:
        out["probe"] = {"skipped": True, "reason": "probe=false"}
        return _dumps(out)

    client = AstrBotClient(cfg)
    # Lightweight list call — same auth path as other plugin tools
    result = client.get("/api/v1/plugins", params={"include_reserved": True})
    probe_info: Dict[str, Any] = result.to_dict()
    # Truncate large plugin lists for readability in agent context
    if result.ok and isinstance(result.data, dict):
        # SuccessEnvelope often {status, message, data: ...} — keep structure, summarize list
        data = result.data.get("data", result.data)
        if isinstance(data, list):
            probe_info["summary"] = {
                "plugin_count": len(data),
                "sample_ids": [
                    (item.get("name") or item.get("id") or item.get("plugin_id") or str(item)[:80])
                    for item in data[:8]
                    if isinstance(item, dict)
                ],
            }
            # Drop full list from probe to keep tool output small
            probe_info["data"] = {
                "envelope_keys": list(result.data.keys()) if isinstance(result.data, dict) else None,
                "note": "full list via astrbot_plugin_list",
                "plugin_count": len(data),
            }
        elif isinstance(data, dict):
            # Some versions nest plugins under a key
            for key in ("plugins", "items", "list"):
                if isinstance(data.get(key), list):
                    probe_info["summary"] = {
                        "plugin_count": len(data[key]),
                        "nested_key": key,
                    }
                    break
    out["probe"] = probe_info
    if result.ok:
        out["connection"] = "ok"
        out["next_step"] = (
            "Read: list/get/failed/config_get. "
            "Manage: reload/set_enabled/config_set (need allow_mutations)."
        )
    else:
        out["connection"] = "failed"
        out["next_step"] = (
            "Fix error_kind: connect|timeout|auth|http_status — see probe.error. "
            "Docs tools remain usable while runtime is down."
        )
    return _dumps(out)


def astrbot_plugin_list(
    include_reserved: bool = True,
    enabled: Optional[bool] = None,
) -> str:
    """GET /api/v1/plugins — list installed plugins (read-only)."""
    client = AstrBotClient()
    params: Dict[str, Any] = {"include_reserved": include_reserved}
    if enabled is not None:
        params["enabled"] = enabled
    result = client.get("/api/v1/plugins", params=params)
    return _dumps(result.to_dict())


def astrbot_plugin_failed() -> str:
    """GET /api/v1/plugins/failed — failed plugins with classified diagnoses."""
    from .failure_analysis import analyze_failed_payload

    client = AstrBotClient()
    result = client.get("/api/v1/plugins/failed")
    out = result.to_dict()
    if result.ok:
        analysis = analyze_failed_payload(result.data)
        out["analysis"] = analysis
        if analysis["failed_count"]:
            out["next_step"] = (
                "Each diagnosis links a fix_rule from review/auto-fix-guide.md. "
                "Fix the plugin code, then astrbot_plugin_reload(failed=true). "
                "Unclassified errors: read traceback_tail; recurring patterns "
                "should be added to the FIX catalog."
            )
    return _dumps(out)


def astrbot_plugin_get(plugin_id: str) -> str:
    """GET /api/v1/plugins/{plugin_id} — single plugin details (read-only)."""
    pid = (plugin_id or "").strip()
    if not pid:
        return _dumps(
            {
                "ok": False,
                "error": "plugin_id is required",
                "error_kind": "bad_request",
            }
        )
    # Prefer path-style resource; OpenAPI also has by-id query variants
    client = AstrBotClient()
    result = client.get(f"/api/v1/plugins/{pid}")
    return _dumps(result.to_dict())
