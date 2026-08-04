# [RUNTIME P2] Install/uninstall lifecycle with data-preservation safety.
"""
Plugin lifecycle tools (OpenAPI v1).

Uninstall safety (MANDATORY — do not weaken):
  OpenAPI DELETE /api/v1/plugins/{plugin_id} accepts:
    { "delete_config": bool, "delete_data": bool }

  Product rule (user / skill):
    1. Before uninstall, agent MUST ask the user whether to keep config files
       and persistent data (data_dir / plugin data).
    2. If the user does not answer → DEFAULT KEEP both
       (delete_config=false, delete_data=false).
    3. NEVER silently set delete_config/delete_data true.
    4. delete_*=true requires explicit tool flags + confirm_uninstall=true.
    5. confirm_uninstall must be true for ANY uninstall API call
       (even when keeping data) so agents cannot "drive-by" uninstall.

  Framework note: AstrBot may still clear plugin KV on uninstall (≥4.26.2)
  regardless of delete_data — document this in tool output; that is platform
  behavior, not something this MCP should force by deleting files.

Test sandbox preference: use astrbot_plugin_mimo_tts only when the user
explicitly allows destructive tests; default development tests should not
uninstall production plugins.
"""

from __future__ import annotations

import json
from typing import Any, Dict, Optional

from .client import AstrBotClient, encode_plugin_id
from .config import load_config, mutation_denied_payload


def _dumps(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=2, default=str)


def _require_plugin_id(plugin_id: str) -> Optional[str]:
    pid = (plugin_id or "").strip()
    return pid or None


def uninstall_policy_help() -> Dict[str, Any]:
    """Static policy text for agents (also returned on soft refusals)."""
    return {
        "policy": "keep_config_and_data_by_default",
        "ask_user": (
            "Before uninstall, ask the user: "
            "(1) keep plugin config? (2) keep persistent data (data_dir)? "
            "If unanswered → keep both."
        ),
        "defaults": {
            "keep_config": True,
            "keep_data": True,
            "delete_config": False,
            "delete_data": False,
        },
        "forbidden": (
            "Do not call uninstall with delete_config/delete_data true unless "
            "the user explicitly approved deleting that data. "
            "Do not invent delete flags."
        ),
        "tool_params": {
            "confirm_uninstall": "must be true to call OpenAPI at all",
            "keep_config": "default true; false only after user OK to drop config",
            "keep_data": "default true; false only after user OK to drop data",
            "confirm_delete_config": "required true if keep_config=false",
            "confirm_delete_data": "required true if keep_data=false",
        },
        "openapi_body": {
            "delete_config": "inverted from keep_config",
            "delete_data": "inverted from keep_data",
        },
        "framework_kv_note": (
            "Even when delete_data=false, AstrBot ≥4.26.2 may clear plugin KV "
            "on uninstall. File data under StarTools.get_data_dir() depends on "
            "delete_data and platform behavior."
        ),
    }


def astrbot_plugin_uninstall(
    plugin_id: str,
    *,
    confirm_uninstall: bool = False,
    keep_config: bool = True,
    keep_data: bool = True,
    confirm_delete_config: bool = False,
    confirm_delete_data: bool = False,
) -> str:
    """
    DELETE /api/v1/plugins/{plugin_id}

    Defaults preserve config + data. Destructive delete flags are double-gated.
    """
    policy = uninstall_policy_help()

    # ── Gate 0: mutations env ───────────────────────────────────
    cfg = load_config()
    if not cfg.allow_mutations:
        payload = mutation_denied_payload("plugin_uninstall")
        payload["policy"] = policy
        return _dumps(payload)

    pid = _require_plugin_id(plugin_id)
    if not pid:
        return _dumps(
            {
                "ok": False,
                "error": "plugin_id is required",
                "error_kind": "bad_request",
                "policy": policy,
            }
        )

    # ── Gate 1: explicit confirm for any uninstall ──────────────
    # [RUNTIME] Soft refuse: OpenAPI NOT called — agent must re-ask user.
    if not confirm_uninstall:
        return _dumps(
            {
                "ok": False,
                "error": (
                    "Uninstall not executed: confirm_uninstall=false. "
                    "Ask the user first; then call again with confirm_uninstall=true. "
                    "Default keeps config and data unless user says otherwise."
                ),
                "error_kind": "confirm_required",
                "plugin_id": pid,
                "would_send": {
                    "delete_config": False if keep_config else True,
                    "delete_data": False if keep_data else True,
                    "note": "preview only — not sent",
                },
                "policy": policy,
            }
        )

    # ── Gate 2: default keep; require extra confirm to delete ───
    # Map keep_* → OpenAPI delete_* (never default delete to true)
    delete_config = not bool(keep_config)
    delete_data = not bool(keep_data)

    if delete_config and not confirm_delete_config:
        return _dumps(
            {
                "ok": False,
                "error": (
                    "Refused: keep_config=false would delete plugin config, but "
                    "confirm_delete_config is not true. "
                    "Only set both after the user explicitly approves deleting config. "
                    "If user did not answer about config, use keep_config=true (default)."
                ),
                "error_kind": "delete_config_confirm_required",
                "plugin_id": pid,
                "policy": policy,
            }
        )

    if delete_data and not confirm_delete_data:
        return _dumps(
            {
                "ok": False,
                "error": (
                    "Refused: keep_data=false would delete persistent plugin data, but "
                    "confirm_delete_data is not true. "
                    "Only set both after the user explicitly approves deleting data. "
                    "If user did not answer about data, use keep_data=true (default)."
                ),
                "error_kind": "delete_data_confirm_required",
                "plugin_id": pid,
                "policy": policy,
            }
        )

    # ── Execute ─────────────────────────────────────────────────
    body = {
        "delete_config": bool(delete_config),
        "delete_data": bool(delete_data),
    }
    client = AstrBotClient(cfg)
    result = client.delete(
        f"/api/v1/plugins/{encode_plugin_id(pid)}",
        json_body=body,
    )
    payload = result.to_dict()
    payload["plugin_id"] = pid
    payload["mutation"] = "uninstall"
    payload["request_body"] = body
    payload["kept"] = {
        "config": not delete_config,
        "data": not delete_data,
    }
    payload["policy"] = policy
    if result.ok:
        payload["next_step"] = (
            "Verify with astrbot_plugin_list / astrbot_plugin_get "
            "(expect missing). If reinstalling, install then reload."
        )
        payload["warning_kv"] = policy["framework_kv_note"]
    return _dumps(payload)


def astrbot_plugin_failed_remove(
    plugin_id: str,
    *,
    confirm: bool = False,
    keep_config: bool = True,
    keep_data: bool = True,
    confirm_delete_config: bool = False,
    confirm_delete_data: bool = False,
) -> str:
    """
    DELETE /api/v1/plugins/failed/{plugin_id} — remove a FAILED-plugin record.

    This is the ONLY API that clears a stale failed entry (v4.27.0). Plugins that
    exist only in the failed list block ALL normal mutations (install/enable/
    reload/uninstall return generic '插件操作失败') and cannot be removed via
    DELETE /plugins/{id} or force_refresh.

    Safety mirrors plugin_uninstall: mutations env + confirm required; config/data
    deleted only with explicit keep_*=false AND the matching confirm_delete_*.
    """
    policy = uninstall_policy_help()

    cfg = load_config()
    if not cfg.allow_mutations:
        payload = mutation_denied_payload("plugin_failed_remove")
        payload["policy"] = policy
        return _dumps(payload)

    pid = _require_plugin_id(plugin_id)
    if not pid:
        return _dumps(
            {
                "ok": False,
                "error": "plugin_id is required",
                "error_kind": "bad_request",
                "policy": policy,
            }
        )

    if not confirm:
        return _dumps(
            {
                "ok": False,
                "error": (
                    "failed_remove not executed: confirm=false. "
                    "Ask the user first (this deletes the plugin's failed record); "
                    "default keeps config and data unless user says otherwise."
                ),
                "error_kind": "confirm_required",
                "plugin_id": pid,
                "policy": policy,
            }
        )

    delete_config = not bool(keep_config)
    delete_data = not bool(keep_data)
    if delete_config and not confirm_delete_config:
        return _dumps(
            {
                "ok": False,
                "error": "Refused: keep_config=false needs confirm_delete_config=true.",
                "error_kind": "delete_config_confirm_required",
                "plugin_id": pid,
                "policy": policy,
            }
        )
    if delete_data and not confirm_delete_data:
        return _dumps(
            {
                "ok": False,
                "error": "Refused: keep_data=false needs confirm_delete_data=true.",
                "error_kind": "delete_data_confirm_required",
                "plugin_id": pid,
                "policy": policy,
            }
        )

    body = {
        "delete_config": bool(delete_config),
        "delete_data": bool(delete_data),
    }
    client = AstrBotClient(cfg)
    result = client.delete(
        f"/api/v1/plugins/failed/{encode_plugin_id(pid)}",
        json_body=body,
    )
    payload = result.to_dict()
    payload["plugin_id"] = pid
    payload["mutation"] = "failed_remove"
    payload["request_body"] = body
    payload["kept"] = {"config": not delete_config, "data": not delete_data}
    if result.ok:
        payload["next_step"] = (
            "Failed record removed. Now re-run astrbot_plugin_install_path(path) "
            "to upload a fresh copy."
        )
    return _dumps(payload)
