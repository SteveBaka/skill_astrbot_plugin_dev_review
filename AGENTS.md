# AGENTS.md — AstrBot Plugin Development Skill

This directory is a **complete skill system** for AstrBot plugin development with automated code review.

## How to Use

1. Read `SKILL.md` — Mandatory Rules, Workflow, Token Efficiency Guide, File Map
2. Follow the workflow steps in order
3. **Gates (do not skip)**:
   - Before scaffold: confirm plugin name `astrbot_plugin_*` + author with the user
   - **Pre-code**: official Always-Read + `main-file-checklist` §1 + FIX-00/02 + **one** type example — do not invent astrbot imports/handlers from memory (`SKILL.md` Step 0.5)
   - **On-demand reads only**: never load the whole skill tree; Tier caps in `SKILL.md` Token Efficiency Guide; review opens FIX sections that fired only
   - High-risk ops (`git commit` / `git push` / force / large rewrite of working code): wait for explicit user OK
   - **Plugin uninstall**: ask keep config? keep data? Unanswered → **keep both**. Never delete config/data without explicit user OK (`mcp/runtime/tools_lifecycle.py`, `SKILL.md` Uninstall data safety)
   - **Local install/update**: Scheme A — `astrbot_plugin_install_path` (…); stale same-version → bump version or `force_refresh` keep config/data. See `SKILL.md` + `mcp/SETUP.md`
   - **Dashboard before smoke**: after new plugin or new `_conf_schema` / profile `plugin_set` / tool toggles — **remind user to configure in AstrBot Dashboard**, then smoke only after they confirm (or explicitly override)
   - **WebChat test profile**: `plugin_dev_skill` … fixed session `mcp-smoke-<username>`; no auto-deletion / no system log tail
   - **chat_probe message**: always use the **plugin's own command**; `/plugin_help` to discover when unsure; never hardcode `/ttsinfo` (mimo_tts only)
   - **Staging → install (no hand-copy)**: `scaffold_plugin` output_dir is staging only (default `ASTRBOT_DEV_WORKSPACE` / `~/.astrbot_skill_workspace`, never cwd). Upload via `install_path`; installed path is always `<data>/plugins/<root_dir_name>/`. Never tell the user to copy files into `/AstrBot/<name>/`. Deliver full files (incl. `_conf_schema.json` when the plugin uses `config`) via `extra_files_json`, else `config_set` 400s "没有注册配置"
   - **WebChat session cleanup**: webchat-only + confirms; API key cannot delete user sessions
   - **Privacy**: do not auto-read plugin/AstrBot configs unless user names the keys; post-install = Dashboard hints only
   - After first code output: **Phase A** review (prefer `astrbot_review_path` + targeted FIX reads)
   - After feature-complete or user audit: **Phase B** full-tree review
 4. Use `review/` files for code review — **on demand**, not wholesale

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

**Publish / market** (authoritative for shipping):
- `https://docs.astrbot.app/dev/star/plugin-publish.html` (Cloud: `https://cloud.astrbot.app`)
- ZIP ≤16MB; clean package tree

**Adapters MUST**:
`https://github.com/AstrBotDevs/AstrBot/blob/master/docs/en/dev/plugin-platform-adapter.md`

**OpenAPI**: `https://docs.astrbot.app/openapi.json` (UI: `/scalar.html`); re-check after each core release via `mcp/scripts/check_openapi_drift.py`

**Do not use as authority**: `docs/en/dev/plugin.md` (legacy redirect only)

**Target core for current notes**: **≥4.26.8** (recommend); skill still documents ≥4.16 floor

Skill pitfall notes (`review/auto-fix-guide.md`) are **secondary** to official docs.

## MCP Server (Optional)

If MCP is configured:

- **Docs tools (6)**: `get_skill_info`, `validate_import`, `get_review_checklist`, `search_docs`, `list_docs`, `get_doc`
- **Runtime tools (24, `astrbot_*`)**: P0–P3 as before, plus P2+ **`scaffold_plugin`** (command|llm_tool|session|cron|hook|web|agent|adapter; contracts + review error=0) and **`review_path`** (profile=plugin|adapter), and P1 **`log_level_get/set`** (v4.27.0)

**Recommended loop**: `astrbot_scaffold_plugin` (or hand code after Step 0.5) → `astrbot_review_path` → `astrbot_plugin_install_path` → **user Dashboard** (enable / plugin_set / schema) → `astrbot_smoke_suite` (only after user confirms)

**Error feedback (regression)**: set `ASTRBOT_ERROR_KB` to a gitignored store so install/smoke failures auto-record desensitized fingerprints; `mcp/scripts/error_kb.py report` reviews them, `propose` writes auto-fix-guide drafts **only after built-in validation** (dedupe + non-generic; rejected entries skipped). Details: `SKILL.md` Error feedback loop / `mcp/SETUP.md` §3.2.

Setup + authoritative tool rules: `mcp/SETUP.md`

## Language

- `SKILL.md`, review files, reference files: **English**
- `README.md`: **Chinese**
