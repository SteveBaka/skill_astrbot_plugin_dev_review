# AGENTS.md — AstrBot Plugin Development Skill

This directory is a **complete skill system** for AstrBot plugin development with automated code review.

## How to Use

1. Read `SKILL.md` — it contains everything: Mandatory Rules, Workflow, Token Efficiency Guide, File Map
2. Follow the workflow steps in order
3. Use `review/` files for code review

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

## Official AstrBot Docs

Before generating code, verify API signatures from:
`https://github.com/AstrBotDevs/AstrBot/tree/master/docs/en/dev/star/guides`

Platform adapters MUST use:
`https://github.com/AstrBotDevs/AstrBot/blob/master/docs/en/dev/plugin-platform-adapter.md`

## MCP Server (Optional)

If MCP is configured, use: `get_skill_info`, `validate_import`, `get_review_checklist`, `search_docs`, `list_docs`, `get_doc`

Setup: `mcp/SETUP.md`

## Language

- `SKILL.md`, review files, reference files: **English**
- `README.md`: **Chinese**
