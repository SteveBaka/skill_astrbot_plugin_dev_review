# [RUNTIME P1] Plugin management tools (config read + gated mutations).
"""
Manage installed AstrBot plugins via OpenAPI v1.

Read (no ASTRBOT_ALLOW_MUTATIONS needed):
  astrbot_plugin_config_get
  astrbot_plugin_config_schema

Write (require ASTRBOT_ALLOW_MUTATIONS=true):
  astrbot_plugin_reload       POST /api/v1/plugins/{id}/reload
                              or failed path POST .../failed/{id}/reload
  astrbot_plugin_set_enabled  PATCH /api/v1/plugins/{id}/enabled  body {enabled}
  astrbot_plugin_config_set   PUT  /api/v1/plugins/{id}/config   body DynamicConfig

Safety:
  - Mutations refuse with error_kind=mutations_disabled if env gate is off.
  - Uninstall lives in tools_lifecycle.py (P2) with keep-data defaults.
  - config_set expects full JSON object string (agent should GET first then edit).
  - Response may still contain plugin secrets from AstrBot; we light-redact common keys.
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, Optional

from .client import AstrBotClient, encode_plugin_id
from .config import load_config, mutation_denied_payload


def _dumps(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=2, default=str)


_SECRET_KEY_RE = re.compile(
    r"(api[_-]?key|token|secret|password|passwd|authorization|private[_-]?key)",
    re.I,
)


def _redact_secrets(obj: Any, *, depth: int = 0) -> Any:
    """
    [RUNTIME] Best-effort redaction for agent-facing config dumps.

    Does not claim perfect secret detection — operators should still treat
    config_get output as sensitive. Never redacts structure keys needed to edit.
    """
    if depth > 12:
        return obj
    if isinstance(obj, dict):
        out: Dict[str, Any] = {}
        for k, v in obj.items():
            if isinstance(k, str) and _SECRET_KEY_RE.search(k) and not isinstance(v, (dict, list)):
                out[k] = "***REDACTED***" if v not in (None, "", []) else v
            else:
                out[k] = _redact_secrets(v, depth=depth + 1)
        return out
    if isinstance(obj, list):
        return [_redact_secrets(x, depth=depth + 1) for x in obj[:500]]
    return obj


def _require_plugin_id(plugin_id: str) -> Optional[str]:
    pid = (plugin_id or "").strip()
    return pid or None


def _mutation_or_none(action: str) -> Optional[str]:
    """Return JSON refusal string if mutations disabled; else None."""
    cfg = load_config()
    if not cfg.allow_mutations:
        return _dumps(mutation_denied_payload(action))
    return None


def astrbot_plugin_config_get(plugin_id: str, redact: bool = True) -> str:
    """
    GET /api/v1/plugins/{plugin_id}/config — read-only.

    redact=True (default): always prefer for non-edit reads.
    redact=False: only when preparing config_set with real values — not for
    browsing, logging, or chat. Agent should not keep unredacted dumps.
    """
    pid = _require_plugin_id(plugin_id)
    if not pid:
        return _dumps({"ok": False, "error": "plugin_id is required", "error_kind": "bad_request"})
    client = AstrBotClient()
    result = client.get(f"/api/v1/plugins/{encode_plugin_id(pid)}/config")
    payload = result.to_dict()
    payload["plugin_id"] = pid
    payload["redacted"] = bool(redact)
    if result.ok and redact and payload.get("data") is not None:
        payload["data"] = _redact_secrets(payload["data"])
        payload["note"] = (
            "Sensitive-looking keys redacted (api_key/token/secret/password). "
            "redact=false ONLY when editing → config_set; never for casual read/log/chat."
        )
    elif result.ok and not redact:
        payload["warning"] = (
            "UNREDACTED config (redact=false). Use solely to prepare config_set; "
            "do not echo secrets to the user chat or commit them."
        )
    return _dumps(payload)


def astrbot_plugin_config_schema(plugin_id: str) -> str:
    """GET /api/v1/plugins/{plugin_id}/config/schema — read-only."""
    pid = _require_plugin_id(plugin_id)
    if not pid:
        return _dumps({"ok": False, "error": "plugin_id is required", "error_kind": "bad_request"})
    client = AstrBotClient()
    result = client.get(f"/api/v1/plugins/{encode_plugin_id(pid)}/config/schema")
    payload = result.to_dict()
    payload["plugin_id"] = pid
    return _dumps(payload)


def astrbot_plugin_config_set(plugin_id: str, config_json: str) -> str:
    """
    PUT /api/v1/plugins/{plugin_id}/config

    config_json: JSON object string of the full config body (DynamicConfig).
    Prefer: config_get(redact=false) → edit → config_set.
    """
    denied = _mutation_or_none("plugin_config_set")
    if denied:
        return denied
    pid = _require_plugin_id(plugin_id)
    if not pid:
        return _dumps({"ok": False, "error": "plugin_id is required", "error_kind": "bad_request"})
    raw = (config_json or "").strip()
    if not raw:
        return _dumps(
            {
                "ok": False,
                "error": "config_json is required (JSON object string)",
                "error_kind": "bad_request",
            }
        )
    try:
        body = json.loads(raw)
    except json.JSONDecodeError as exc:
        return _dumps(
            {
                "ok": False,
                "error": f"config_json is not valid JSON: {exc}",
                "error_kind": "bad_request",
            }
        )
    if not isinstance(body, dict):
        return _dumps(
            {
                "ok": False,
                "error": "config_json must decode to a JSON object (dict)",
                "error_kind": "bad_request",
            }
        )

    client = AstrBotClient()
    result = client.put(
        f"/api/v1/plugins/{encode_plugin_id(pid)}/config",
        json_body=body,
    )
    payload = result.to_dict()
    payload["plugin_id"] = pid
    payload["mutation"] = "config_set"
    # [RUNTIME] do not echo full config body back (may contain secrets agent just sent)
    payload["config_keys_written"] = sorted(str(k) for k in body.keys())
    if result.ok:
        payload["next_step"] = (
            "If plugin reads config only at load time, call astrbot_plugin_reload. "
            "Then astrbot_plugin_failed to confirm clean load."
        )
    return _dumps(payload)


def astrbot_plugin_set_enabled(plugin_id: str, enabled: bool) -> str:
    """PATCH /api/v1/plugins/{plugin_id}/enabled  body {enabled: bool}."""
    denied = _mutation_or_none("plugin_set_enabled")
    if denied:
        return denied
    pid = _require_plugin_id(plugin_id)
    if not pid:
        return _dumps({"ok": False, "error": "plugin_id is required", "error_kind": "bad_request"})

    client = AstrBotClient()
    result = client.patch(
        f"/api/v1/plugins/{encode_plugin_id(pid)}/enabled",
        json_body={"enabled": bool(enabled)},
    )
    payload = result.to_dict()
    payload["plugin_id"] = pid
    payload["mutation"] = "set_enabled"
    payload["requested_enabled"] = bool(enabled)
    if result.ok:
        payload["next_step"] = (
            "Verify with astrbot_plugin_get; if enabling after code change, "
            "astrbot_plugin_reload + astrbot_plugin_failed."
        )
    return _dumps(payload)


def astrbot_plugin_reload(plugin_id: str, failed: bool = False) -> str:
    """
    Reload a plugin.

    failed=False: POST /api/v1/plugins/{plugin_id}/reload
    failed=True:  POST /api/v1/plugins/failed/{plugin_id}/reload
                  (use when plugin is on the failed list)

    After reload, callers should check astrbot_plugin_failed.
    """
    denied = _mutation_or_none("plugin_reload")
    if denied:
        return denied
    pid = _require_plugin_id(plugin_id)
    if not pid:
        return _dumps({"ok": False, "error": "plugin_id is required", "error_kind": "bad_request"})

    enc = encode_plugin_id(pid)
    path = f"/api/v1/plugins/failed/{enc}/reload" if failed else f"/api/v1/plugins/{enc}/reload"
    client = AstrBotClient()
    result = client.post(path)
    payload = result.to_dict()
    payload["plugin_id"] = pid
    payload["mutation"] = "reload"
    payload["failed_endpoint"] = bool(failed)
    payload["path"] = path

    # [RUNTIME] Auto-follow with failed list snapshot for agent convenience
    # (read-only; helps confirm load success without a second manual tool call)
    if result.ok:
        failed_snap = client.get("/api/v1/plugins/failed")
        payload["post_reload_failed_probe"] = {
            "ok": failed_snap.ok,
            "status_code": failed_snap.status_code,
            "data": failed_snap.data if failed_snap.ok else failed_snap.error,
            "error_kind": failed_snap.error_kind,
        }
        payload["next_step"] = (
            "If post_reload_failed_probe still lists this plugin, read error and fix code. "
            "Optional: astrbot_plugin_get to confirm activated=true."
        )
    return _dumps(payload)


# ── per-plugin log level (v4.27.0 public API) ────────────────

_LOG_LEVELS = ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")
# empty/aliases → None (follow global)
_NULL_ALIASES = {"", "none", "null", "global", "default"}


def _normalize_log_level(level: str) -> tuple[str | None, str | None]:
    """Return (api_level, error). None api_level means 'follow global'."""
    raw = (level or "").strip()
    if raw.lower() in _NULL_ALIASES:
        return None, None
    up = raw.upper()
    if up in _LOG_LEVELS:
        return up, None
    return None, (
        f"invalid level {raw!r}; use one of {list(_LOG_LEVELS)} "
        "or none/global/null to follow the global level"
    )


def astrbot_plugin_log_level_get(plugin_id: str) -> str:
    """
    GET current per-plugin log level — read-only.

    Returns ONLY {plugin_id, log_level} from the plugin config endpoint
    (log_level: null means "follow global"). Does NOT dump the full config,
    which may contain secrets.
    """
    pid = _require_plugin_id(plugin_id)
    if not pid:
        return _dumps({"ok": False, "error": "plugin_id is required", "error_kind": "bad_request"})
    client = AstrBotClient()
    result = client.get(f"/api/v1/plugins/{encode_plugin_id(pid)}/config")
    payload: Dict[str, Any] = {"ok": result.ok, "plugin_id": pid, "error": result.error}
    if result.ok and isinstance(result.data, dict):
        d = result.data.get("data") or result.data
        if isinstance(d, dict):
            payload["log_level"] = d.get("log_level")
            if payload["log_level"] is None:
                payload["note"] = "null → follows the global log level"
    else:
        payload["error_kind"] = result.error_kind or "http_status"
    return _dumps(payload)


def astrbot_plugin_log_level_set(
    plugin_id: str, level: str, *, confirm: bool = False
) -> str:
    """
    PUT /api/v1/plugins/{plugin_id}/log-level — set per-plugin log level.

    level: DEBUG | INFO | WARNING | ERROR | CRITICAL, or "" / "none" / "global"
    / "null" to follow the global level.

    Safety:
      - Requires ASTRBOT_ALLOW_MUTATIONS=true.
      - DEBUG raises log verbosity and may record user message content — reset to
        follow-global (empty level) after debugging.
    """
    denied = _mutation_or_none("plugin_log_level_set")
    if denied:
        return denied
    pid = _require_plugin_id(plugin_id)
    if not pid:
        return _dumps({"ok": False, "error": "plugin_id is required", "error_kind": "bad_request"})
    api_level, err = _normalize_log_level(level)
    if err:
        return _dumps({"ok": False, "error": err, "error_kind": "bad_request"})

    client = AstrBotClient()
    result = client.put(
        f"/api/v1/plugins/{encode_plugin_id(pid)}/log-level",
        json_body={"level": api_level},
    )
    payload = result.to_dict()
    payload["plugin_id"] = pid
    payload["mutation"] = "log_level_set"
    payload["level_applied"] = api_level  # null = follow global
    if result.ok:
        payload["next_step"] = (
            "Log level applied. DEBUG may capture user message content; "
            "call log_level_set with empty level to follow global again."
        )
    return _dumps(payload)
