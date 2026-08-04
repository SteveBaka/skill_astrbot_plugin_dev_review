# [RUNTIME] Env-only configuration. Secrets never appear in tool return values.
"""
Read AstrBot runtime settings from the MCP host environment.

Authority / placement:
  - Configure on MCP host (kilo.jsonc / mcp_settings.json `env`), NOT in this repo.
  - LAN multi-device: set ASTRBOT_BASE_URL to the AstrBot host IP, e.g.
    http://192.168.1.50:6185  (not localhost on the Kilo machine unless AstrBot is local)

Env (P0 read + P1 manage):
  ASTRBOT_BASE_URL       Required for runtime tools. Empty => runtime disabled (docs OK).
  ASTRBOT_TOKEN          Optional API secret (X-API-Key or Bearer; never logged).
  ASTRBOT_AUTH_MODE      "api_key" (default, header X-API-Key) | "bearer" | "auto"
  ASTRBOT_HTTP_TIMEOUT   Seconds, default 15 (LAN may need higher if NAS/path is slow).
  ASTRBOT_ALLOW_MUTATIONS  "true"/"1" enables write tools
                           (reload/enable/config_set/install_path/uninstall).
                           Default false: manage tools refuse without calling OpenAPI.
  ASTRBOT_ALLOW_CHAT_PROBE "true"/"1" allows chat_probe without per-call confirm
                           (still prefer confirm_probe=true after user OK).
  ASTRBOT_CHAT_USERNAME    Default WebChat username for chat_probe.
  ASTRBOT_CHAT_CONFIG_NAME Default config profile name (default: plugin_dev_skill).
  ASTRBOT_CHAT_SMOKE_SESSION_ID  Fixed smoke session id for chat_probe
                           (default: mcp-smoke-<username>; user manages it in
                           Dashboard WebChat).
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Dict, Optional
from urllib.parse import urlparse


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


def _env_float(name: str, default: float) -> float:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return float(raw)
    except ValueError:
        # [RUNTIME] bad env must not crash MCP process — fall back + note later in info tool
        return default


@dataclass(frozen=True)
class RuntimeConfig:
    """Immutable snapshot of runtime env (token held but never printed by tools)."""

    base_url: str
    token: str
    auth_mode: str
    timeout: float
    allow_mutations: bool
    allow_chat_probe: bool
    chat_username: str
    chat_config_name: str

    @property
    def enabled(self) -> bool:
        return bool(self.base_url)

    @property
    def token_configured(self) -> bool:
        return bool(self.token)

    def public_dict(self) -> dict:
        """Safe for agent/UI: no token value, only presence flags."""
        host = ""
        scheme = ""
        port: Optional[int] = None
        parse_ok = False
        parse_error = ""
        try:
            u = urlparse(self.base_url)
            host = u.hostname or ""
            scheme = u.scheme or ""
            port = u.port
            parse_ok = bool(scheme and host)
        except Exception as exc:  # noqa: BLE001 — surface config issues only
            parse_error = str(exc)

        return {
            "runtime_enabled": self.enabled,
            "base_url": self.base_url or None,
            "base_url_parse_ok": parse_ok,
            "base_url_host": host or None,
            "base_url_scheme": scheme or None,
            "base_url_port": port,
            "base_url_parse_error": parse_error or None,
            "token_configured": self.token_configured,
            "auth_mode": self.auth_mode,
            "http_timeout_seconds": self.timeout,
            "allow_mutations": self.allow_mutations,
            "allow_chat_probe": self.allow_chat_probe,
            "chat_username_configured": bool(self.chat_username),
            "chat_config_name_default": self.chat_config_name or "plugin_dev_skill",
            # [RUNTIME P1] what agents can do with current env (no secrets)
            "capabilities": {
                "read_plugins": self.enabled,
                "read_config": self.enabled,
                "reload_enable_config_write": self.enabled and self.allow_mutations,
                # [RUNTIME P2] lifecycle tools; mutations + (uninstall) confirms
                "uninstall": self.enabled and self.allow_mutations,
                "install_path": self.enabled and self.allow_mutations,
                "pack_preview": True,  # local only, no OpenAPI
                "providers_brief": self.enabled,
                "config_profiles_brief": self.enabled,
                "ensure_plugin_dev_skill": self.enabled and self.allow_mutations,
                "chat_probe": self.enabled,  # still needs confirm_probe or ALLOW_CHAT_PROBE
                "chat_sessions_cleanup": self.enabled and self.allow_mutations,
                "review_path": True,  # pure static analysis, no OpenAPI
                "smoke_suite": self.enabled,  # + confirm / ALLOW_CHAT_PROBE at call time
                "log_level_get": self.enabled,  # read-only (v4.27.0)
                "log_level_set": self.enabled and self.allow_mutations,  # v4.27.0
                "failed_remove": self.enabled and self.allow_mutations,  # v4.27.0 failed cleanup
            },
            "privacy": {
                "no_auto_read_plugin_config": True,
                "no_auto_read_full_profile": True,
                "config_get_only_if_user_names_keys": True,
                "chat_smoke_default_off": True,
                "plugin_dev_skill_profile": "plugin_dev_skill",
            },
            "uninstall_safety": {
                "default_keep_config": True,
                "default_keep_data": True,
                "require_confirm_uninstall": True,
                "require_extra_confirm_to_delete_config_or_data": True,
                "rule": (
                    "Ask user keep config/data; unanswered → keep. "
                    "Never delete plugin config/data without explicit user approval."
                ),
            },
            "note_lan": (
                "On different LAN devices use http://<astrbot-host-ip>:<port> "
                "(localhost on Kilo machine only works if AstrBot runs there)."
            ),
            "note_mutations": (
                "Set ASTRBOT_ALLOW_MUTATIONS=true on MCP host and restart MCP to allow "
                "astrbot_plugin_reload / set_enabled / config_set / "
                "install_path / uninstall."
            ),
            "note_install_scheme_a": (
                "Local install: astrbot_plugin_install_path(path) packs ZIP "
                "(filename from metadata name/version; .gitignore + hard excludes) "
                "→ POST install/upload → enable → reload → failed. "
                "Update: prefer re-upload via install_path; if same-name conflict, "
                "uninstall keep_config/data then install_path again."
            ),
            "note_chat_probe": (
                "astrbot_chat_probe: need chat-scoped API key; username + "
                "config_name=plugin_dev_skill; confirm_probe=true after user allow; "
                "fixed smoke session mcp-smoke-<username> (override via session_id / "
                "ASTRBOT_CHAT_SMOKE_SESSION_ID); user manages it in Dashboard WebChat; "
                "message = plugin's OWN command (use /plugin_help to discover when "
                "unsure; never hardcode /ttsinfo etc.); parse SSE not JSON-only."
            ),
        }


def mutation_denied_payload(action: str) -> Dict[str, Any]:
    """
    [RUNTIME P1] Structured refusal when write tools are gated off.

    Result analysis: error_kind=mutations_disabled means OpenAPI was NOT called;
    enable env and restart MCP host process to pick up the flag.
    """
    return {
        "ok": False,
        "error": (
            f"Mutation denied for '{action}'. "
            "Set ASTRBOT_ALLOW_MUTATIONS=true in MCP host env and restart the MCP server."
        ),
        "error_kind": "mutations_disabled",
        "action": action,
        "hint": (
            "Read-only tools (list/get/failed/config_get) still work. "
            "Docs MCP is unaffected."
        ),
    }


def load_config() -> RuntimeConfig:
    """Load once per tool call (cheap; picks up env changes after MCP restart)."""
    base = (os.environ.get("ASTRBOT_BASE_URL") or "").strip().rstrip("/")
    token = (os.environ.get("ASTRBOT_TOKEN") or "").strip()
    auth = (os.environ.get("ASTRBOT_AUTH_MODE") or "api_key").strip().lower()
    if auth not in ("api_key", "bearer", "auto"):
        # Invalid mode: keep process alive; client will treat as api_key with warning field
        auth = "api_key"
    timeout = _env_float("ASTRBOT_HTTP_TIMEOUT", 15.0)
    if timeout <= 0:
        timeout = 15.0
    chat_user = (os.environ.get("ASTRBOT_CHAT_USERNAME") or "").strip()
    chat_cfg = (os.environ.get("ASTRBOT_CHAT_CONFIG_NAME") or "").strip() or "plugin_dev_skill"
    return RuntimeConfig(
        base_url=base,
        token=token,
        auth_mode=auth,
        timeout=timeout,
        allow_mutations=_env_bool("ASTRBOT_ALLOW_MUTATIONS", False),
        allow_chat_probe=_env_bool("ASTRBOT_ALLOW_CHAT_PROBE", False),
        chat_username=chat_user,
        chat_config_name=chat_cfg,
    )
