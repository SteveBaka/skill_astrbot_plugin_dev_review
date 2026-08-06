# [RUNTIME] Register optional tools onto the existing FastMCP instance.
"""
Hook point used by server.py AFTER all docs tools are defined.

Failure policy:
  - Import/register errors are caught in server.py so Docs MCP still starts.
  - This module only adds tools; it never patches docs tool functions.

Phases registered here:
  P0 read:  runtime_info, plugin_list, plugin_failed, plugin_get
  P1 manage: config_get/schema/set, set_enabled, reload
  P2 lifecycle: uninstall (keep config/data by default; double-confirm deletes)
  P2 install:   local path → gitignore ZIP → install/upload → enable/reload/failed
  P2.5 profile: plugin_dev_skill ensure + providers brief + post-install hints
  P3 chat:      chat_probe (SSE) + sessions brief (opt-in)
"""

from __future__ import annotations

import json
from typing import Any

from . import (
    review_static,
    scaffold_plugin,
    tools_chat,
    tools_impl,
    tools_install,
    tools_lifecycle,
    tools_manage,
    tools_profile,
    tools_smoke,
)


def register_runtime_tools(mcp: Any) -> None:
    """
    Attach P0+P1+P2 runtime tools to `mcp` (FastMCP).

    Tool names are prefixed with astrbot_ to avoid colliding with docs tools.
    """

    # ── P0 read ────────────────────────────────────────────────

    @mcp.tool()
    def astrbot_runtime_info(probe: bool = True) -> str:
        """
        [RUNTIME P0] Show AstrBot runtime env (no secrets) and optionally probe OpenAPI.

        Use first when debugging LAN connectivity. Set ASTRBOT_BASE_URL on MCP host.
        Docs tools work even if this reports not_configured / connect failed.
        """
        return tools_impl.astrbot_runtime_info(probe=probe)

    @mcp.tool()
    def astrbot_plugin_list(
        include_reserved: bool = True,
        enabled: str = "",
    ) -> str:
        """
        [RUNTIME P0] List installed plugins via GET /api/v1/plugins (read-only).

        enabled: empty = all; "true"/"false" filter when supported by the instance.
        """
        en: bool | None = None
        raw = (enabled or "").strip().lower()
        if raw in ("1", "true", "yes", "on"):
            en = True
        elif raw in ("0", "false", "no", "off"):
            en = False
        return tools_impl.astrbot_plugin_list(include_reserved=include_reserved, enabled=en)

    @mcp.tool()
    def astrbot_plugin_failed() -> str:
        """
        [RUNTIME P0] List failed plugins and load errors (GET /api/v1/plugins/failed).

        Primary signal after install/reload when a plugin crashes on load.
        """
        return tools_impl.astrbot_plugin_failed()

    @mcp.tool()
    def astrbot_plugin_get(plugin_id: str) -> str:
        """
        [RUNTIME P0] Get one plugin's details (GET /api/v1/plugins/{plugin_id}).

        plugin_id: installed plugin id/name as reported by astrbot_plugin_list.
        """
        return tools_impl.astrbot_plugin_get(plugin_id=plugin_id)

    # ── P1 manage ──────────────────────────────────────────────

    @mcp.tool()
    def astrbot_plugin_config_get(plugin_id: str, redact: bool = True) -> str:
        """
        [RUNTIME P1] Get plugin configuration (GET .../config). Read-only.

        redact=true (DEFAULT, preferred): masks api_key/token/secret/password-like
        fields. Use for inspection, debugging structure, or any non-edit read.

        redact=false: ONLY when you are about to edit and then call config_set
        (need raw values). Do NOT use for casual dumps, logs, chat replies, or
        "just looking". Never commit or paste unredacted output into the repo.
        Prefer: user names keys → config_get(redact=false) → edit → config_set
        → do not retain raw payload in agent memory longer than needed.
        """
        return tools_manage.astrbot_plugin_config_get(plugin_id=plugin_id, redact=redact)

    @mcp.tool()
    def astrbot_plugin_config_schema(plugin_id: str) -> str:
        """
        [RUNTIME P1] Get plugin config schema (GET .../config/schema). Read-only.
        """
        return tools_manage.astrbot_plugin_config_schema(plugin_id=plugin_id)

    @mcp.tool()
    def astrbot_plugin_config_set(plugin_id: str, config_json: str) -> str:
        """
        [RUNTIME P1] Save plugin configuration (PUT .../config). Requires mutations.

        config_json: full JSON object string. Prefer config_get(redact=false) then edit.
        Needs ASTRBOT_ALLOW_MUTATIONS=true.
        """
        return tools_manage.astrbot_plugin_config_set(
            plugin_id=plugin_id, config_json=config_json
        )

    @mcp.tool()
    def astrbot_plugin_set_enabled(plugin_id: str, enabled: bool) -> str:
        """
        [RUNTIME P1] Enable or disable a plugin (PATCH .../enabled). Requires mutations.

        Needs ASTRBOT_ALLOW_MUTATIONS=true.
        """
        return tools_manage.astrbot_plugin_set_enabled(plugin_id=plugin_id, enabled=enabled)

    @mcp.tool()
    def astrbot_plugin_reload(plugin_id: str, failed: bool = False) -> str:
        """
        [RUNTIME P1] Reload a plugin. Requires mutations.

        failed=false: normal reload. failed=true: reload via failed-plugins endpoint.
        On success, includes post_reload_failed_probe snapshot.
        Needs ASTRBOT_ALLOW_MUTATIONS=true.

        NOTE for Platform adapters: reload success does NOT replace the running
        adapter instance. After updating adapter code, fully restart the AstrBot
        process — otherwise the old Platform instance continues to run.
        """
        return tools_manage.astrbot_plugin_reload(plugin_id=plugin_id, failed=failed)

    # ── P1 per-plugin log level (v4.27.0 public API) ───────────

    @mcp.tool()
    def astrbot_plugin_log_level_get(plugin_id: str) -> str:
        """
        [RUNTIME P1] Get per-plugin log level (read-only, v4.27.0).

        Returns only {plugin_id, log_level}; log_level null = follow global.
        Does NOT dump the full config (may contain secrets). Needs `plugin` scope.
        """
        return tools_manage.astrbot_plugin_log_level_get(plugin_id=plugin_id)

    @mcp.tool()
    def astrbot_plugin_log_level_set(
        plugin_id: str, level: str, confirm: bool = False
    ) -> str:
        """
        [RUNTIME P1] Set per-plugin log level via PUT .../log-level (v4.27.0).

        level: DEBUG | INFO | WARNING | ERROR | CRITICAL, or "" / "none" / "global"
        / "null" to follow the global level. Needs ASTRBOT_ALLOW_MUTATIONS=true.
        Privacy: DEBUG raises verbosity and may record user message content —
        reset to follow-global (empty level) after debugging.
        """
        return tools_manage.astrbot_plugin_log_level_set(
            plugin_id=plugin_id, level=level, confirm=confirm
        )

    # ── P2 lifecycle (uninstall safety) ────────────────────────

    @mcp.tool()
    def astrbot_plugin_uninstall(
        plugin_id: str,
        confirm_uninstall: bool = False,
        keep_config: bool = True,
        keep_data: bool = True,
        confirm_delete_config: bool = False,
        confirm_delete_data: bool = False,
    ) -> str:
        """
        [RUNTIME P2] Uninstall a plugin (DELETE .../plugins/{id}). Requires mutations.

        SAFETY (mandatory):
        - Ask the user whether to keep config files and persistent data.
        - If the user does not answer → keep both (defaults keep_config/keep_data true).
        - NEVER silently delete config/data; delete requires keep_*=false AND
          confirm_delete_config / confirm_delete_data true after explicit user OK.
        - confirm_uninstall must be true or the API is not called.
        - Do not uninstall production plugins during routine tests; prefer
          astrbot_plugin_mimo_tts only when user allows destructive tests.

        Needs ASTRBOT_ALLOW_MUTATIONS=true.
        """
        return tools_lifecycle.astrbot_plugin_uninstall(
            plugin_id=plugin_id,
            confirm_uninstall=confirm_uninstall,
            keep_config=keep_config,
            keep_data=keep_data,
            confirm_delete_config=confirm_delete_config,
            confirm_delete_data=confirm_delete_data,
        )

    # ── P2 install (Scheme A: zip + upload) ────────────────────

    @mcp.tool()
    def astrbot_plugin_pack_preview(path: str) -> str:
        """
        [RUNTIME P2] Dry-run pack local plugin dir to ZIP stats (no upload).

        Uses .gitignore + hard excludes (venv/__pycache__/.git/...).
        Does not require ASTRBOT_ALLOW_MUTATIONS. Use before install_path.
        """
        return tools_install.astrbot_plugin_pack_preview(path=path)

    @mcp.tool()
    def astrbot_plugin_install_path(
        path: str,
        enable: bool = True,
        reload: bool = True,
        ignore_version_check: bool = False,
        force_refresh: bool = False,
        clear_failed: bool = False,
    ) -> str:
        """
        [RUNTIME P2] Scheme A: pack local plugin → install/upload → enable → reload → failed.

        path: plugin root with metadata.yaml + main.py (absolute path recommended).
        ZIP excludes match .gitignore (+ hard denylist) so contents align with
        GitHub/marketplace packages.
        Dev update loop: edit → install_path → (reload/failed included by default).
        success=true does NOT guarantee on-disk code replaced (same version may be
        stale). If components/behavior unchanged: bump metadata.version, or set
        force_refresh=true (uninstall keep config+data → re-upload). Default never
        auto-uninstall; may return warning possible_stale_install.
        clear_failed=true: if the plugin exists only in the FAILED list (stale
        failed record blocking all mutations), DELETE .../plugins/failed/{id}
        (keep config+data) first, then upload. Opt-in; never auto-clears.
        Needs ASTRBOT_ALLOW_MUTATIONS=true. Prefer testing on user-approved sandbox
        plugins (e.g. astrbot_plugin_mimo_tts) only.
        """
        return tools_install.astrbot_plugin_install_path(
            path=path,
            enable=enable,
            reload=reload,
            ignore_version_check=ignore_version_check,
            force_refresh=force_refresh,
            clear_failed=clear_failed,
        )

    # ── P2.5 plugin_dev_skill + privacy-safe hints ─────────────

    @mcp.tool()
    def astrbot_plugin_failed_remove(
        plugin_id: str,
        confirm: bool = False,
        keep_config: bool = True,
        keep_data: bool = True,
        confirm_delete_config: bool = False,
        confirm_delete_data: bool = False,
    ) -> str:
        """
        [RUNTIME P2] Remove a FAILED-plugin record (DELETE .../plugins/failed/{id}).

        The ONLY API that clears a stale failed entry (v4.27.0). Plugins present
        only in the failed list block all normal mutations (generic '插件操作失败')
        and can't be removed via uninstall or force_refresh — remove the failed
        record first, then re-install. Needs mutations + confirm. Config/data are
        kept by default; deletes need explicit keep_*=false + confirm_delete_*.
        """
        return tools_lifecycle.astrbot_plugin_failed_remove(
            plugin_id=plugin_id,
            confirm=confirm,
            keep_config=keep_config,
            keep_data=keep_data,
            confirm_delete_config=confirm_delete_config,
            confirm_delete_data=confirm_delete_data,
        )

    @mcp.tool()
    def astrbot_providers_brief() -> str:
        """
        [RUNTIME P2.5] List providers (id/name only) for user to pick default_provider_id.

        No secrets. Use before astrbot_ensure_plugin_dev_skill.
        """
        return tools_profile.astrbot_providers_brief()

    @mcp.tool()
    def astrbot_config_profiles_brief() -> str:
        """
        [RUNTIME P2.5] List config profile names/ids only (no full config bodies).

        Check whether plugin_dev_skill already exists before create.
        """
        return tools_profile.astrbot_config_profiles_brief()

    @mcp.tool()
    def astrbot_post_install_hints(plugin_id: str, plugin_type: str = "") -> str:
        """
        [RUNTIME P2.5] Dashboard checklist after install (no config API reads).

        plugin_type: command|llm_tool|session|cron|hook|web|adapter|auto
        Reminds user to use WebChat with profile plugin_dev_skill.
        """
        return tools_profile.astrbot_post_install_hints(
            plugin_id=plugin_id, plugin_type=plugin_type
        )

    @mcp.tool()
    def astrbot_ensure_plugin_dev_skill(
        plugin_id: str,
        provider_id: str,
        confirm_create: bool = False,
        exist_policy: str = "abort",
        confirm_delete_existing: bool = False,
        rename_old_to: str = "",
        extra_plugins: str = "",
    ) -> str:
        """
        [RUNTIME P2.5] Create profile plugin_dev_skill from default (minimal overrides).

        REQUIRED interaction before confirm_create=true:
        - User picks provider_id (from astrbot_providers_brief / Dashboard)
        - If profile exists: user chooses exist_policy=abort|recreate|rename_old
        - recreate needs confirm_delete_existing=true (deletes profile only, not plugin)
        Sets plugin_set to plugin_id (+ optional comma-separated extra_plugins).
        Never returns full config body. Needs ASTRBOT_ALLOW_MUTATIONS=true.
        After success: tell user to select plugin_dev_skill in Dashboard WebChat.
        Does NOT send WebChat messages (smoke is separate opt-in; not implemented here).
        """
        return tools_profile.astrbot_ensure_plugin_dev_skill(
            plugin_id=plugin_id,
            provider_id=provider_id,
            confirm_create=confirm_create,
            exist_policy=exist_policy,
            confirm_delete_existing=confirm_delete_existing,
            rename_old_to=rename_old_to,
            extra_plugins=extra_plugins,
        )

    # ── P3 chat probe (opt-in SSE smoke) ───────────────────────

    @mcp.tool()
    def astrbot_chat_sessions_brief(
        username: str = "",
        page: int = 1,
        page_size: int = 20,
    ) -> str:
        """
        [RUNTIME P3] List WebChat sessions (metadata only). Needs chat-scoped API key.

        username: WebChat creator (or ASTRBOT_CHAT_USERNAME). Message bodies not returned;
        GET by id may still be Permission denied — use astrbot_chat_probe for smoke text.
        """
        return tools_chat.astrbot_chat_sessions_brief(
            username=username, page=page, page_size=page_size
        )

    @mcp.tool()
    def astrbot_chat_probe(
        message: str,
        confirm_probe: bool = False,
        username: str = "",
        config_name: str = "",
        config_id: str = "",
        session_id: str = "",
        enable_streaming: bool = False,
        timeout_seconds: float = 0,
    ) -> str:
        """
        [RUNTIME P3] Opt-in WebChat smoke: POST /api/v1/chat, parse SSE summary.

        SAFETY: confirm_probe=true after user explicitly allows (or ASTRBOT_ALLOW_CHAT_PROBE).
        Defaults: config_name=plugin_dev_skill; username required (arg or
        ASTRBOT_CHAT_USERNAME). Needs chat-scoped API key.
        Session policy: all probes reuse ONE fixed smoke session
        ("mcp-smoke-<username>", override via session_id arg or
        ASTRBOT_CHAT_SMOKE_SESSION_ID) — a single stable Dashboard WebChat entry
        the user manages/deletes there (API keys cannot delete user sessions).
        Do not use for production chatter; prefer Dashboard WebChat for main testing.

        MESSAGE GUIDANCE (LLM): fill `message` with the PLUGIN'S OWN command from
        its component list (astrbot_plugin_get / smoke_suite derive them). When
        unsure which command the plugin supports, use "/plugin_help" as a minimal
        discovery probe FIRST, then probe the plugin's real commands. Never hardcode
        mimo_tts-specific commands like "/ttsinfo" for other plugins.
        """
        return tools_chat.astrbot_chat_probe(
            message=message,
            confirm_probe=confirm_probe,
            username=username,
            config_name=config_name,
            config_id=config_id,
            session_id=session_id,
            enable_streaming=enable_streaming,
            timeout_seconds=timeout_seconds,
        )

    @mcp.tool()
    def astrbot_chat_sessions_cleanup(
        session_ids: str = "",
        username: str = "",
        all_for_username: bool = False,
        confirm_cleanup: bool = False,
        max_delete: int = 50,
    ) -> str:
        """
        [RUNTIME P3] Delete WebChat sessions ONLY (batch-delete with per-id fallback).

        KNOWN LIMIT (source-verified): AstrBot checks session.creator ==
        auth identity, and API-key identity is "api_key:<key_id>" — so this tool
        CANNOT delete sessions created by Dashboard users; those return
        Permission denied and must be deleted in Dashboard WebChat. It can only
        delete sessions created via this API key.
        HARD SCOPE: webchat platform only. Every id (caller-supplied included) is
        verified against the username's webchat session list; any id from another
        platform/source (QQ/Telegram/... real conversations) fails the whole call
        with scope_violation — those are privacy-protected and never deleted.
        Modes: session_ids="id1,id2,..." (surgical) OR all_for_username=true.
        username required in both modes (arg or ASTRBOT_CHAT_USERNAME).
        SAFETY: needs ASTRBOT_ALLOW_MUTATIONS=true AND confirm_cleanup=true —
        first show the user the list via astrbot_chat_sessions_brief and get
        explicit OK. Hard cap max_delete per call (default 50).
        """
        return tools_chat.astrbot_chat_sessions_cleanup(
            session_ids=session_ids,
            username=username,
            all_for_username=all_for_username,
            confirm_cleanup=confirm_cleanup,
            max_delete=max_delete,
        )

    # ── P2+ scaffold (contracts + review invariant) ────────────

    @mcp.tool()
    def astrbot_scaffold_plugin(
        name: str,
        author: str,
        plugin_type: str = "command",
        output_dir: str = "",
        command: str = "",
        display_name: str = "",
        desc: str = "",
        overwrite: bool = False,
        extra_files_json: str = "",
    ) -> str:
        """
        [RUNTIME P2+] Scaffold from shared contracts (multi-type + adapter frame).

        plugin_type: command|llm_tool|session|cron|hook|web|agent|adapter
        Star plugins: metadata + main + requirements; review profile=plugin.
        adapter: framework-only Platform skeleton; review profile=adapter (FIX-06);
        NOT WebChat-smokeable — supply a working adapter later for E2E.
        **Invariant:** fresh scaffold review error count must be 0.
        Confirm name/author (or adapter id) with the user first. Dashboard
        config before any smoke for Star plugins.

        WORKFLOW (staging → install): output_dir is only a STAGING area (default
        ASTRBOT_DEV_WORKSPACE or ~/.astrbot_skill_workspace; never cwd). After
        scaffolding — with or without extra_files_json — upload the plugin with
        astrbot_plugin_install_path(path). The INSTALLED location is always
        <data>/plugins/<root_dir_name>/, regardless of staging path; never ask
        the user to copy files into /AstrBot/<name>/.
        extra_files_json: optional JSON {relpath: content} to deliver the FULL
        plugin in one call (allowlist: main.py/metadata.yaml/requirements.txt/
        _conf_schema.json/README.md) — avoids needing a file-system tool when the
        MCP runs inside AstrBot. If the plugin reads `config`, ship
        `_conf_schema.json` here or astrbot_plugin_config_set will 400
        "没有注册配置".
        """
        return scaffold_plugin.astrbot_scaffold_plugin(
            name=name,
            author=author,
            plugin_type=plugin_type,
            output_dir=output_dir,
            command=command,
            display_name=display_name,
            desc=desc,
            overwrite=overwrite,
            extra_files_json=extra_files_json,
        )

    # ── P2+ static reviewer (no AstrBot needed) ────────────────

    @mcp.tool()
    def astrbot_review_path(path: str, profile: str = "plugin") -> str:
        """
        [RUNTIME P2+] AST static review of a local plugin or adapter dir.

        profile=plugin (default): Star plugin FIX/META/REQ checks + FIX-03 hooks.
        profile=adapter: Platform subclass required methods + FIX-06 reserved attrs.
        No AstrBot instance needed. errors block install; judgment stays Phase A/B.
        """
        report = review_static.review_path(path, profile=profile)
        return json.dumps(report.to_dict(), ensure_ascii=False, indent=2)

    # ── P3+ smoke suite (composite) ────────────────────────────

    @mcp.tool()
    def astrbot_smoke_suite(
        plugin_id: str,
        confirm: bool = False,
        username: str = "",
        config_name: str = "",
        include_admin: bool = False,
        max_cases: int = 8,
        extra_messages: str = "",
        timeout_seconds: float = 0,
    ) -> str:
        """
        [RUNTIME P3+] Composite smoke test for an installed plugin.

        Pipeline: plugin status (+failed diagnosis with FIX links if not
        loaded) → auto-derive cases from components (non-admin commands
        prioritized info/help-first, command groups, one hook probe, one
        llm_tool soft probe) → run each via chat_probe into the ONE fixed
        smoke session → post-run failed re-check (runtime crash detector) →
        aggregated pass/fail verdict.
        SAFETY: same posture as chat_probe — confirm=true after user allows
        (or ASTRBOT_ALLOW_CHAT_PROBE); chat-scoped key; username required
        (arg or ASTRBOT_CHAT_USERNAME); admin commands skipped unless
        include_admin=true; hard cap max_cases (default 8).
        extra_messages: optional '||'-separated custom case messages.
        """
        return tools_smoke.astrbot_smoke_suite(
            plugin_id,
            confirm=confirm,
            username=username,
            config_name=config_name,
            include_admin=include_admin,
            max_cases=max_cases,
            extra_messages=extra_messages,
            timeout_seconds=timeout_seconds,
        )
