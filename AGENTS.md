# AGENTS.md — AstrBot Plugin Development Skill

This directory is a **complete skill system** for AstrBot plugin development with automated code review.

## What This Skill Does

When you are asked to create, modify, or review an AstrBot plugin, use this skill to:

1. **Understand** AstrBot plugin architecture and APIs
2. **Generate** correct, spec-compliant plugin code
3. **Review** code for stability, security, and compliance
4. **Fix** common issues automatically

## How to Use This Skill

### Entry Point

Start by reading `SKILL.md` — it contains:
- Mandatory Rules (must follow)
- Core Workflow (step-by-step)
- Token Efficiency Guide (what to read when)
- Official docs references

### Architecture Overview

Read `architecture.md` for:
- Complete file map with purpose of each file
- Workflow sequence
- Review pipeline
- Import reference table
- MCP server tools

### Quick Reference

| Need | File |
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

### Official AstrBot Docs

Before generating code, verify API signatures from:
`https://github.com/AstrBotDevs/AstrBot/tree/master/docs/en/dev/star/guides`

Read all `.md` files in this directory. Also read:
- `https://github.com/AstrBotDevs/AstrBot/blob/master/docs/en/dev/star/plugin-new.md` (plugin lifecycle, naming, metadata, skills/ bundling)
- Platform adapters MUST use: `https://github.com/AstrBotDevs/AstrBot/blob/master/docs/en/dev/plugin-platform-adapter.md`

Note: `docs/en/dev/plugin.md` is the OLD doc — it redirects to `star/plugin-new.md`. Always use `star/` paths.

### MCP Server (Optional)

If MCP is configured, use these tools:
- `get_skill_info` — Overview of this skill
- `validate_import(symbol)` — Check if an import path is correct
- `get_review_checklist(file_type)` — Get review checklist
- `search_docs(query)` — Search all documentation

## File Structure

```
skill_astrbot_plugin_dev_review/
├── SKILL.md                      # Primary entry — rules + workflow
├── AGENTS.md                     # This file — skill system identifier
├── architecture.md               # Machine-readable architecture overview
├── README.md                     # Chinese-language overview
├── plugin-development-workflow.md # 9-step development guide
├── design_standards/             # Architecture, events, context, sandbox, rendering
├── messages/                     # Message model, components, events, UMO
├── platform_adapters/            # Adapter interface, message conversion
├── agent/                        # Tools, LLM, hooks, conversation, cron, subagents
├── storage_utils/                # KV, file, text-to-image, i18n
├── webui/                        # Dashboard pages, Bridge API
├── references/                   # Core API, best practices, config, patterns, modular split
├── review/                       # Review workflow, checklists, auto-fix guide
├── plugin-types/                 # 6 plugin type examples + review reports
├── script/                       # Basic command plugin template
└── mcp/                          # MCP server (optional)
```

## Language

- `SKILL.md`, all review files, all reference files: **English** (for LLM processing)
- `README.md`: **Chinese** (for human developers)
- Code examples: English comments and variable names
- Official AstrBot docs: Chinese (source of truth)
