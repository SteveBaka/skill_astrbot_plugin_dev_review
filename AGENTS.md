# AGENTS.md — AstrBot Plugin Development Skill

This directory is a **complete skill system** for AstrBot plugin development with automated code review.

## How to Use

1. Read `SKILL.md` — Mandatory Rules, Workflow, Token Efficiency Guide, File Map
2. Follow the workflow steps in order
3. **Gates (do not skip)**:
   - Before scaffold: confirm plugin name `astrbot_plugin_*` + author with the user
   - High-risk ops (`git commit` / `git push` / force / large rewrite of working code): wait for explicit user OK
   - **Plugin uninstall**: ask keep config? keep data? Unanswered → **keep both**. Never delete config/data without explicit user OK (`mcp/runtime/tools_lifecycle.py`, `SKILL.md` Uninstall data safety)
   - **Local install/update**: Scheme A — `astrbot_plugin_install_path` (metadata-named ZIP + gitignore → install/upload → enable → reload → failed). Prefer re-upload; same-name conflict fallback: uninstall keep config/data then install. See `SKILL.md` + `mcp/SETUP.md`
   - **WebChat test profile**: `plugin_dev_skill` via `astrbot_ensure_plugin_dev_skill` (user picks provider; from default; no secret dump). Main test in Dashboard WebChat; MCP `astrbot_chat_probe` only with user allow + `confirm_probe=true` (chat-scoped key, username, SSE). All probes reuse ONE fixed smoke session `mcp-smoke-<username>` — user manages/deletes it in Dashboard WebChat; API keys cannot delete user-owned sessions, never attempt auto-deletion or scope escalation
   - **WebChat session cleanup**: `astrbot_chat_sessions_cleanup` is **webchat-platform-only** (other platforms → refuse whole call); needs mutations + `confirm_cleanup=true` + user-reviewed list; can only delete sessions created via the API key itself
   - **Privacy**: do not auto-read plugin/AstrBot configs unless user names the keys; post-install = Dashboard hints only
   - After first code output: **Phase A** runtime review (`review/review-workflow.md`)
   - After feature-complete or user audit: **Phase B** full-tree review
4. Use `review/` files for code review

## Quick Reference

| Task | Read |
|------|------|
| Create a plugin | `plugin-development-workflow.md` |
| Pick plugin type | `plugin-types/README.md` |
| Check import paths | `review/main-file-checklist.md` §1 |
| Review code | `review/review-workflow.md` |
| Fix issues | `review/auto-fix-guide.md` |
| LLM tools | `agent/tools.md` |
| Cron jobs | `agent/cron.md` |
| WebUI pages | `webui/plugin-pages.md` |
| Platform adapter | `platform_adapters/adapter_interface.md` |

## Official AstrBot Docs (authority)

**Always fetch** (before code generation / review):

- `https://raw.githubusercontent.com/AstrBotDevs/AstrBot/master/docs/en/dev/star/plugin-new.md`
- `https://raw.githubusercontent.com/AstrBotDevs/AstrBot/master/docs/en/dev/star/guides/simple.md`
- `https://raw.githubusercontent.com/AstrBotDevs/AstrBot/master/docs/en/dev/star/guides/listen-message-event.md`

**By type**: other files under `docs/en/dev/star/guides/` (ai, plugin-config, plugin-pages, storage, session-control, …)

**Adapters MUST**:
`https://github.com/AstrBotDevs/AstrBot/blob/master/docs/en/dev/plugin-platform-adapter.md`

**Do not use as authority**: `docs/en/dev/plugin.md` (legacy redirect only)

Skill pitfall notes (`review/auto-fix-guide.md`) are **secondary** to official docs.

## MCP Server (Optional)

If MCP is configured:

- **Docs tools (6)**: `get_skill_info`, `validate_import`, `get_review_checklist`, `search_docs`, `list_docs`, `get_doc`
- **Runtime tools (19, `astrbot_*`)**: P0 read (`runtime_info`/`plugin_list`/`failed`/`get`) → P1 manage (config/enable/reload, **mutations**) → P2 lifecycle (`install_path`/`pack_preview`/`uninstall`) → P2.5 profile (`ensure_plugin_dev_skill`/`providers_brief`/`post_install_hints`/`config_profiles_brief`) → P3 chat (`chat_sessions_brief`/`chat_probe`/`chat_sessions_cleanup`, opt-in)

Setup + authoritative tool rules: `mcp/SETUP.md`

## Language

- `SKILL.md`, review files, reference files: **English**
- `README.md`: **Chinese**
