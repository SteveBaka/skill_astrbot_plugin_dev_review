# Skill Architecture

This document defines the complete architecture of the `skill_astrbot_plugin_dev_review` skill system. It is designed to be machine-readable — LLMs should read this file first to understand the full system.

## System Purpose

This skill enables LLMs to:
1. Read and understand AstrBot plugin architecture
2. Generate spec-compliant plugin code
3. Review code for stability, security, and compliance
4. Auto-fix common issues

## Entry Points

| Entry | File | When to Use |
|-------|------|-------------|
| **Primary** | `SKILL.md` | Always start here — contains Mandatory Rules + Workflow |
| **Architecture** | `architecture.md` | This file — system overview and call map |
| **Chinese README** | `README.md` | Chinese-language overview for human developers |

## Workflow (Sequential)

```
Step 0:   Understand user intent (SKILL.md §Step 0)
Step 0.5: Read "Always Read" docs — 3 files (SKILL.md §Step 0.5)
Step 1:   Select plugin type(s) (plugin-types/README.md)
Step 1.5: Read type-specific official docs (SKILL.md §Step 1.5)
Step 2:   Scaffold & implement (plugin-development-workflow.md)
Step 2.5: Pre-review cleanup (SKILL.md §Step 2.5)
Step 3:   Validate metadata.yaml (review/metadata-validation.md)
Step 4:   Run review pipeline (review/review-workflow.md)
Step 5:   Fix issues if any (review/auto-fix-guide.md)
Step 6:   Deliver
```

## File Map — What to Read When

### Tier 0: Official Docs (External, Read After Selecting Type)

Source: `https://github.com/AstrBotDevs/AstrBot/tree/master/docs/en/dev/star/guides`

Read only the docs relevant to your selected plugin type (see SKILL.md §Step 1.5).

### Tier 1: Core Rules (Always Read)

| File | Purpose | Lines |
|------|---------|-------|
| `SKILL.md` | Mandatory Rules, Workflow, Token Efficiency | ~375 |
| `review/main-file-checklist.md` §1 | Import reference table (35+ entries) | ~110 |

### Tier 2: Task-Specific (Read Based on Intent)

| Task | Primary File | Secondary File |
|------|-------------|----------------|
| New plugin | `plugin-development-workflow.md` | `plugin-types/README.md` |
| LLM tools | `agent/tools.md` | `agent/invoke-llm.md` |
| Cron jobs | `agent/cron.md` | — |
| LLM hooks | `agent/hooks.md` | `agent/conversation.md` |
| Session control | `references/plugin-patterns.md` §3 | — |
| Config schema | `references/conf-schema.md` | — |
| WebUI pages | `webui/plugin-pages.md` | — |
| Platform adapter | `platform_adapters/adapter_interface.md` | — |
| Split main.py | `references/modular-split.md` | — |
| Message components | `messages/components.md` | — |
| Storage | `storage_utils/kv_storage.md` | `storage_utils/file_storage.md` |
| Image rendering | `design_standards/visual_utils.md` | `storage_utils/text_to_image.md` |
| Review code | `review/review-workflow.md` | `review/main-file-checklist.md` |
| Fix issues | `review/auto-fix-guide.md` | — |

### Tier 3: Reference (Read When Needed)

| File | Purpose |
|------|---------|
| `references/core-concepts.md` | API quick index |
| `references/best-practices.md` | 11 best practices |
| `references/plugin-patterns.md` | 10 implementation patterns |
| `agent/official-tools.md` | Built-in tool list |
| `agent/subagents.md` | Sub-agent handoff |
| `agent/conversation.md` | Prompt injection strategies |
| `agent/persona-control.md` | Persona CRUD |
| `agent/context-compression.md` | Compression parameters |
| `agent/agent-runner.md` | Agent Runner (v4.7.0+) |
| `agent/sandbox.md` | Sandbox runtime |
| `agent/register-skill.md` | Skill registration |
| `design_standards/architecture_overview.md` | AstrBot core architecture |
| `design_standards/event_flow.md` | Message flow model |
| `design_standards/context_usage.md` | Context object API |
| `design_standards/sandbox.md` | Sandbox storage mounting |
| `messages/model.md` | AstrBotMessage structure |
| `messages/events.md` | AstrMessageEvent API |
| `messages/umo.md` | Unified Message Origin |
| `platform_adapters/message_conversion.md` | Message conversion |
| `platform_adapters/telegram_media_group.md` | Telegram media groups |
| `storage_utils/plugin-i18n.md` | Internationalization |
| `review/general-file-checklist.md` | General code review |
| `plugin-types/REVIEW-REPORTS.md` | Review report examples |
| `plugin-types/type*/main.py` | Plugin type examples |

## Review Pipeline

```
review/review-workflow.md          → Orchestrator (3-step pipeline)
  ├── review/metadata-validation.md → Step 1: Structure + metadata.yaml
  ├── review/main-file-checklist.md → Step 2: main.py (10 checks + import table)
  └── review/general-file-checklist.md → Step 3: All other .py files

review/auto-fix-guide.md           → 20 fix patterns (FIX-00 ~ FIX-19)
```

## MCP Server (Optional Enhancement)

```
mcp/server.py       → 6 tools for querying docs and validating imports
mcp/SETUP.md        → Installation guide
mcp/requirements.txt → Dependencies (mcp, pyyaml, uvicorn, starlette)
```

MCP tools:
- `get_skill_info` — Skill overview
- `list_docs` — List categories and documents
- `get_doc(category, doc_name)` — Fetch specific document
- `search_docs(query)` — Search all documents
- `validate_import(symbol)` — Check import path correctness
- `get_review_checklist(file_type)` — Get review checklist

## Import Reference Table

The authoritative import reference is in `review/main-file-checklist.md` §1. Key entries:

| Symbol | Correct Import |
|--------|---------------|
| `logger` | `from astrbot.api import logger` |
| `filter` | `from astrbot.api.event import filter` |
| `AstrMessageEvent` | `from astrbot.api.event import AstrMessageEvent` |
| `Star` | `from astrbot.api.star import Star` |
| `Context` | `from astrbot.api.star import Context` |
| `StarTools` | `from astrbot.api.star import StarTools` |
| `AstrBotConfig` | `from astrbot.api import AstrBotConfig` |
| `ProviderRequest` | `from astrbot.api.provider import ProviderRequest` |
| `LLMResponse` | `from astrbot.api.provider import LLMResponse` |
| `Comp` | `from astrbot.api.message_components import Comp` |
| `FunctionTool` | `from astrbot.core.agent.tool import FunctionTool` |
| `ToolSet` | `from astrbot.core.agent.tool import ToolSet` |
| `session_waiter` | `from astrbot.core.utils.session_waiter import session_waiter` |
| `register_platform_adapter` | `from astrbot.core.platform.register import register_platform_adapter` |

## Mandatory Rules Summary

All rules are in `SKILL.md` §Mandatory Rules. Key rules:

1. Always reference official AstrBot dev docs during code generation, fixing, and review — do NOT guess
2. All `@filter.command` must have docstrings
3. Use `event.message_str.strip()` for user input, NOT function parameters
4. `Tool.call()` MUST return `str`, NOT `ToolExecResult`
5. `__init__` must call `super().__init__(context)`
6. If using config: `__init__(self, context, config: AstrBotConfig)`
7. `@filter.command_group` uses function pattern, NOT class
8. Bridge API method is `onContext()`, NOT `onContextChange()`
9. Sensitive operations require user confirmation
10. Full review on ALL files when user requests audit
