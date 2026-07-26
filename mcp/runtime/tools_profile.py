# [RUNTIME P2.5] plugin_dev_skill profile + privacy-safe helpers.
"""
Dev-test configuration profile workflow (no chat smoke by default).

Rules (Skill R1–R3):
  - Profile name fixed: plugin_dev_skill
  - Built from default profile config (deep copy server-side only)
  - plugin_set = [target plugin (+ optional extras user listed)]
  - User must pick provider_id before create
  - Existing same name: abort | recreate | rename_old (user decides)
  - Never dump full config / secrets in tool output
  - Do not auto-read plugin configs; post-install only returns Dashboard hints
  - chat_probe NOT implemented here; smoke requires separate user allow later
"""

from __future__ import annotations

import copy
import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .client import AstrBotClient, encode_plugin_id
from .config import load_config, mutation_denied_payload

PROFILE_NAME = "plugin_dev_skill"


def _dumps(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=2, default=str)


def _envelope_data(result_data: Any) -> Any:
    if isinstance(result_data, dict) and "data" in result_data:
        return result_data.get("data")
    return result_data


def post_install_dashboard_hints(
    plugin_id: str,
    plugin_type: str = "",
) -> Dict[str, Any]:
    """
    Privacy-safe install follow-up: text only, no config reads.

    plugin_type: optional hint — command|llm_tool|session|cron|hook|web|adapter|auto
    """
    pid = (plugin_id or "").strip() or "<plugin_id>"
    ptype = (plugin_type or "auto").strip().lower()
    if ptype in ("", "auto"):
        # Heuristic from id only (no API)
        low = pid.lower()
        if "adapter" in low:
            ptype = "adapter"
        elif any(x in low for x in ("tts", "hook", "filter")):
            ptype = "hook"
        elif "cron" in low or "schedul" in low:
            ptype = "cron"
        else:
            ptype = "command"

    common = [
        f"In Dashboard WebChat, select configuration profile **{PROFILE_NAME}** "
        "(create it via astrbot_ensure_plugin_dev_skill if missing).",
        "Do not rely on profile `default` for plugin functional tests "
        "(often empty plugin_set / unrelated plugins).",
        "Agent will not auto-read plugin or AstrBot configs unless you name the keys to inspect.",
    ]

    by_type: Dict[str, List[str]] = {
        "command": [
            "Plugins → enable the plugin → try commands in WebChat under plugin_dev_skill.",
            "Admin-only commands need an admin account in WebChat.",
        ],
        "llm_tool": [
            "Enable the plugin AND per-tool switches (≥4.26.x: plugin on ≠ every tool on).",
            "Use a model/provider that supports tools.",
        ],
        "session": [
            "Test multi-turn in the same WebChat session; do not switch sessions mid-flow.",
        ],
        "cron": [
            "Check scheduled jobs / timezone in Dashboard; use a short interval only for self-test.",
        ],
        "hook": [
            "Enable the plugin; for TTS/output hooks, keep plugin_dev_skill free of splitter/output filters.",
            "Framework TTS settings may still need Dashboard toggles — configure there, not via Agent guessing.",
        ],
        "web": [
            "Open the plugin page under Dashboard plugin pages; verify Bridge endpoints if any.",
        ],
        "adapter": [
            "Configure under Platform / Adapters (not only plugin list).",
            "Tokens/Webhooks: enter only in Dashboard; Agent must not request or store secrets.",
        ],
    }
    steps = by_type.get(ptype, by_type["command"]) + common
    return {
        "plugin_id": pid,
        "plugin_type_assumed": ptype,
        "dashboard_checklist": steps,
        "privacy": (
            "No configuration values were read. "
            "Ask the user to open Dashboard for secrets and full forms."
        ),
        "next_optional": (
            f"After Dashboard setup, create/update profile with "
            f"astrbot_ensure_plugin_dev_skill(plugin_id={pid!r}, provider_id=..., confirm_create=true)."
        ),
    }


def astrbot_providers_brief() -> str:
    """
    List providers for user selection (ids/names only). Read-only.

    Does not print api keys. If API fails, returns error without probing configs.
    """
    client = AstrBotClient()
    # Prefer top-level providers list
    result = client.get("/api/v1/providers")
    out: Dict[str, Any] = {
        "ok": result.ok,
        "purpose": "pick provider_id for plugin_dev_skill (user choice required)",
        "privacy": "ids/names only; secrets never requested",
    }
    if not result.ok:
        out["error"] = result.error
        out["error_kind"] = result.error_kind
        out["status_code"] = result.status_code
        # fallback sources list names only
        src = client.get("/api/v1/provider-sources")
        out["fallback_provider_sources"] = {
            "ok": src.ok,
            "error": src.error,
            "error_kind": src.error_kind,
        }
        if src.ok:
            data = _envelope_data(src.data)
            items = data if isinstance(data, list) else (
                data.get("items") or data.get("list") or data.get("sources") or []
                if isinstance(data, dict) else []
            )
            brief = []
            for it in items if isinstance(items, list) else []:
                if isinstance(it, dict):
                    brief.append(
                        {
                            "id": it.get("id") or it.get("source_id"),
                            "name": it.get("name") or it.get("id"),
                            "provider": it.get("provider"),
                            "provider_type": it.get("provider_type"),
                        }
                    )
            out["provider_sources_brief"] = brief
            out["hint"] = (
                "Use Dashboard provider id as shown in UI, or an id from this list "
                "as default_provider_id when creating plugin_dev_skill."
            )
        return _dumps(out)

    data = _envelope_data(result.data)
    items: List[Any]
    if isinstance(data, list):
        items = data
    elif isinstance(data, dict):
        items = (
            data.get("providers")
            or data.get("items")
            or data.get("list")
            or data.get("data")
            or []
        )
        if not isinstance(items, list):
            items = []
    else:
        items = []

    brief = []
    for it in items:
        if not isinstance(it, dict):
            continue
        brief.append(
            {
                "id": it.get("id") or it.get("provider_id"),
                "name": it.get("name") or it.get("display_name") or it.get("id"),
                "type": it.get("type") or it.get("provider_type") or it.get("provider"),
                "enable": it.get("enable") if "enable" in it else it.get("enabled"),
            }
        )
    out["providers"] = brief
    out["count"] = len(brief)
    out["hint"] = (
        "Ask the user which provider_id to use for plugin_dev_skill, "
        "then call astrbot_ensure_plugin_dev_skill."
    )
    return _dumps(out)


def astrbot_config_profiles_brief() -> str:
    """List configuration profile names/ids only (no full config bodies)."""
    client = AstrBotClient()
    result = client.get("/api/v1/config-profiles")
    out: Dict[str, Any] = {
        "ok": result.ok,
        "privacy": "names/ids only — full config not fetched",
        "plugin_dev_skill_name": PROFILE_NAME,
    }
    if not result.ok:
        out["error"] = result.error
        out["error_kind"] = result.error_kind
        out["status_code"] = result.status_code
        return _dumps(out)
    data = _envelope_data(result.data)
    info_list = []
    if isinstance(data, dict):
        info_list = data.get("info_list") or data.get("list") or []
    elif isinstance(data, list):
        info_list = data
    profiles = []
    found = False
    for it in info_list if isinstance(info_list, list) else []:
        if not isinstance(it, dict):
            continue
        name = it.get("name")
        if name == PROFILE_NAME:
            found = True
        profiles.append({"name": name, "id": it.get("id"), "path": it.get("path")})
    out["profiles"] = profiles
    out["plugin_dev_skill_exists"] = found
    return _dumps(out)


def _find_profile(
    client: AstrBotClient, name: str
) -> Optional[Dict[str, str]]:
    result = client.get("/api/v1/config-profiles")
    if not result.ok:
        return None
    data = _envelope_data(result.data)
    info_list = []
    if isinstance(data, dict):
        info_list = data.get("info_list") or []
    for it in info_list if isinstance(info_list, list) else []:
        if isinstance(it, dict) and it.get("name") == name:
            return {
                "name": str(it.get("name")),
                "id": str(it.get("id")),
            }
    return None


def _build_dev_config(
    default_config: Dict[str, Any],
    *,
    plugin_id: str,
    provider_id: str,
    extra_plugins: List[str],
) -> Dict[str, Any]:
    """
    Deep-copy default and apply minimal test overrides.

    [RUNTIME] Do not strip unrelated keys (keeps AstrBot validation happy).
    Do not log the returned dict (may contain secrets from default clone).
    """
    cfg = copy.deepcopy(default_config)
    plugin_set = [plugin_id]
    for extra in extra_plugins:
        e = (extra or "").strip()
        if e and e not in plugin_set:
            plugin_set.append(e)
    cfg["plugin_set"] = plugin_set
    ps = cfg.get("provider_settings")
    if not isinstance(ps, dict):
        ps = {}
        cfg["provider_settings"] = ps
    ps["default_provider_id"] = provider_id
    return cfg


def astrbot_ensure_plugin_dev_skill(
    plugin_id: str,
    provider_id: str,
    *,
    confirm_create: bool = False,
    exist_policy: str = "abort",
    confirm_delete_existing: bool = False,
    rename_old_to: str = "",
    extra_plugins: str = "",
) -> str:
    """
    Create/recreate configuration profile plugin_dev_skill from default.

    exist_policy: abort | recreate | rename_old
    extra_plugins: comma-separated optional extra plugin ids for plugin_set
    """
    cfg = load_config()
    if not cfg.allow_mutations:
        return _dumps(mutation_denied_payload("ensure_plugin_dev_skill"))

    pid = (plugin_id or "").strip()
    provid = (provider_id or "").strip()
    policy = (exist_policy or "abort").strip().lower()
    if policy not in ("abort", "recreate", "rename_old"):
        return _dumps(
            {
                "ok": False,
                "error_kind": "bad_request",
                "error": "exist_policy must be abort|recreate|rename_old",
            }
        )

    if not pid or not provid:
        return _dumps(
            {
                "ok": False,
                "error_kind": "bad_request",
                "error": "plugin_id and provider_id are required (user must choose provider)",
                "hint": "Call astrbot_providers_brief first; ask user to pick provider_id.",
            }
        )

    if not confirm_create:
        return _dumps(
            {
                "ok": False,
                "error_kind": "confirm_required",
                "error": (
                    "Profile not created: confirm_create=false. "
                    "Ask user to choose provider and same-name policy, then call again "
                    "with confirm_create=true."
                ),
                "will_create": {
                    "name": PROFILE_NAME,
                    "base": "default config deep copy",
                    "plugin_set": [pid] + [
                        x.strip()
                        for x in (extra_plugins or "").split(",")
                        if x.strip()
                    ],
                    "default_provider_id": provid,
                },
                "dashboard_hint": (
                    "After create, user should open Dashboard WebChat and select "
                    f"configuration **{PROFILE_NAME}**."
                ),
                "privacy": "Full config body is never returned by this tool.",
            }
        )

    extras = [x.strip() for x in (extra_plugins or "").split(",") if x.strip()]
    client = AstrBotClient(cfg)
    steps: Dict[str, Any] = {}

    existing = _find_profile(client, PROFILE_NAME)
    if existing:
        steps["existing"] = existing
        if policy == "abort":
            return _dumps(
                {
                    "ok": False,
                    "error_kind": "profile_exists",
                    "error": (
                        f"Profile {PROFILE_NAME!r} already exists. "
                        "User must choose: recreate (delete then create), "
                        "rename_old (rename existing then create), or abort."
                    ),
                    "existing": existing,
                    "exist_policy_options": ["abort", "recreate", "rename_old"],
                }
            )
        if policy == "recreate":
            if not confirm_delete_existing:
                return _dumps(
                    {
                        "ok": False,
                        "error_kind": "delete_confirm_required",
                        "error": (
                            "recreate requires confirm_delete_existing=true "
                            "(deletes only the config profile, NOT the plugin)."
                        ),
                        "existing": existing,
                    }
                )
            del_r = client.delete(
                f"/api/v1/config-profiles/{encode_plugin_id(existing['id'])}"
            )
            steps["delete_existing"] = {
                "ok": del_r.ok,
                "status_code": del_r.status_code,
                "error": del_r.error,
                "error_kind": del_r.error_kind,
            }
            if not del_r.ok:
                return _dumps(
                    {
                        "ok": False,
                        "error_kind": "delete_failed",
                        "error": del_r.error,
                        "steps": steps,
                    }
                )
        elif policy == "rename_old":
            new_name = (rename_old_to or "").strip()
            if not new_name:
                ts = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
                new_name = f"{PROFILE_NAME}_bak_{ts}"
            ren = client.patch(
                f"/api/v1/config-profiles/{encode_plugin_id(existing['id'])}",
                json_body={"name": new_name},
            )
            steps["rename_old"] = {
                "ok": ren.ok,
                "status_code": ren.status_code,
                "error": ren.error,
                "error_kind": ren.error_kind,
                "new_name": new_name,
            }
            if not ren.ok:
                return _dumps(
                    {
                        "ok": False,
                        "error_kind": "rename_failed",
                        "error": ren.error,
                        "steps": steps,
                    }
                )

    # Load default config (server-side only; not returned)
    def_r = client.get("/api/v1/config-profiles/default")
    if not def_r.ok:
        return _dumps(
            {
                "ok": False,
                "error_kind": def_r.error_kind or "http_status",
                "error": def_r.error or "failed to load default profile",
                "status_code": def_r.status_code,
                "steps": steps,
            }
        )
    def_payload = _envelope_data(def_r.data)
    if not isinstance(def_payload, dict):
        return _dumps(
            {
                "ok": False,
                "error_kind": "bad_response",
                "error": "default profile response unexpected",
                "steps": steps,
            }
        )
    default_config = def_payload.get("config")
    if not isinstance(default_config, dict):
        return _dumps(
            {
                "ok": False,
                "error_kind": "bad_response",
                "error": "default profile missing config object",
                "steps": steps,
            }
        )

    new_config = _build_dev_config(
        default_config,
        plugin_id=pid,
        provider_id=provid,
        extra_plugins=extras,
    )
    # [RUNTIME] Never put new_config into response
    create = client.post(
        "/api/v1/config-profiles",
        json_body={"name": PROFILE_NAME, "config": new_config},
    )
    steps["create"] = {
        "ok": create.ok,
        "status_code": create.status_code,
        "error": create.error,
        "error_kind": create.error_kind,
    }
    # Extract new id if present without dumping config
    new_id = None
    if create.ok and isinstance(create.data, dict):
        d = _envelope_data(create.data)
        if isinstance(d, dict):
            new_id = d.get("id") or d.get("config_id")
        elif isinstance(d, str):
            new_id = d
    if create.ok and not new_id:
        found = _find_profile(client, PROFILE_NAME)
        if found:
            new_id = found.get("id")
            steps["resolve_id"] = found

    out: Dict[str, Any] = {
        "ok": create.ok,
        "profile_name": PROFILE_NAME,
        "profile_id": new_id,
        "plugin_id": pid,
        "provider_id": provid,
        "plugin_set_applied": [pid] + [e for e in extras if e != pid],
        "base": "default",
        "steps": steps,
        "config_body_returned": False,
        "dashboard_hint": (
            f"Open AstrBot Dashboard → WebChat → select configuration "
            f"**{PROFILE_NAME}** → test the plugin there. "
            "MCP chat smoke is opt-in only (not enabled by this tool)."
        ),
        "privacy": (
            "Full profile config (may include secrets from default clone) "
            "was sent only to AstrBot API and is not included in this response."
        ),
    }
    if not create.ok:
        # May include server message but strip huge bodies
        ud = create.data
        if isinstance(ud, dict):
            out["upload_message"] = ud.get("message") or ud.get("status")
        out["next_step"] = "Check provider_id validity and mutations; retry after user confirm."
    else:
        out["next_step"] = (
            "User tests in Dashboard WebChat with this profile. "
            "Agent: fix code → install_path → user retests. "
            "Do not auto chat_probe unless user explicitly allows."
        )
        out["post_install_hints"] = post_install_dashboard_hints(pid)
    return _dumps(out)


def astrbot_post_install_hints(plugin_id: str, plugin_type: str = "") -> str:
    """Public tool: Dashboard checklist only (no API config reads)."""
    return _dumps(
        {
            "ok": True,
            **post_install_dashboard_hints(plugin_id, plugin_type),
        }
    )
