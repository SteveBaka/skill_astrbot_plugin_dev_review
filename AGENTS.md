# AGENTS.md — AstrBot Plugin Development Skill

This directory is a **complete skill system** for AstrBot plugin development with automated code review.

## How to Use

1. Read `SKILL.md` — Mandatory Rules, Workflow, Token Efficiency Guide, File Map
2. Follow the workflow steps in order
3. **Gates (do not skip)**:
   - Before scaffold: confirm plugin name `astrbot_plugin_*` + author with the user
   - High-risk ops (`git commit` / `git push` / force / large rewrite of working code): wait for explicit user OK
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

If MCP is configured, use: `get_skill_info`, `validate_import`, `get_review_checklist`, `search_docs`, `list_docs`, `get_doc`

Setup: `mcp/SETUP.md`

## Language

- `SKILL.md`, review files, reference files: **English**
- `README.md`: **Chinese**
