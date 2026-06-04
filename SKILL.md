---
name: skill_astrbot_plugin_dev_review
description: |
  AstrBot plugin development with automated review and quality assurance.

  Use this skill when you are:
  - Writing AstrBot plugins, hooks, decorators, or message handlers
  - Implementing platform adapters, message chains, or event flows
  - Configuring plugin schemas, sessions, or lifecycle management
  - Working with Agent system (tools, subagents, personas, sandboxes, cron jobs)
  - Reviewing or auditing AstrBot plugin code for stability and security
  - Auto-fixing common plugin issues (import errors, async patterns, logger misuse, etc.)
  - Validating plugin metadata, config schemas, and project structure
  - Choosing between different plugin patterns (command, tool, session, cron, hook, web, agent)

  Provides: development guide + 10 plugin patterns + automated review checklist + auto-fix guide.
metadata:
  short-description: AstrBot plugin dev + auto review
  version: "2.0"
  compatibility: astrbot >=4.16
  license: MIT
---

# skill_astrbot_plugin_dev_review

AstrBot plugin development + automated review integrated Skill.

This Skill consolidates the complete knowledge base of AstrBot plugin development with an automated code review workflow, enabling LLM/Vibe Coding tools to:
1. **Understand** AstrBot plugin architecture and runtime mechanisms
2. **Select** the most suitable plugin type and implementation pattern
3. **Generate** spec-compliant plugin code
4. **Review** code stability, security, and compliance
5. **Auto-fix** common issues

## Core Workflow

```
Step 0: Understand Intent
  ↓
Step 0.5: Read "Always Read" Docs (3 files)
  ↓
Step 1: Select Type(s)
  ↓
Step 1.5: Read Type-Specific Docs
  ↓
Step 2: Scaffold & Implement
  ↓
Step 2.5: Pre-Review Cleanup
  ↓
Step 3: Validate Metadata
  ↓
Step 4: Review
  ↓
Step 5: Fix if needed → Re-review
  ↓
Deliver
```

> **Critical**: Official AstrBot dev docs on GitHub are the **authoritative source**. The skill's internal docs are supplementary. Always read official docs BEFORE generating code. Do NOT rely on cached knowledge or the skill's internal docs alone — they may be outdated.

### Step 0: Understand User Intent

| User Says | Intent | Action |
|-----------|--------|--------|
| "Write a plugin that does X" | New plugin | Full workflow |
| "Add a command to do X" | Add command to existing | Read existing main.py, add handler |
| "Let AI call my API" | Add LLM tool | `agent/tools.md` + register in `__init__` |
| "Fix this error" | Bug fix | Read error, find root cause, fix |
| "Review my code" | Full audit | Run complete review pipeline on ALL files |
| "Add a scheduled task" | Add cron | `agent/cron.md` |
| "Make a settings page" | WebUI | `webui/plugin-pages.md` |

### Step 1: Select Plugin Type(s)

Plugin types are NOT mutually exclusive. A single plugin can combine multiple types:

```
Command + LLM Tool:     /weather command AND AI auto-calls weather API
Command + Cron:         /remind command AND scheduled daily report
LLM Tool + Hook:        AI calls tool AND hook injects context
Command + Web API:      /status command AND dashboard page
```

Decision tree: `plugin-types/README.md`

| Type | Core API | File |
|------|----------|------|
| Command | `@filter.command` | `references/plugin-patterns.md` §1 |
| LLM Tool | `FunctionTool` + `add_llm_tools` | `agent/tools.md` |
| Session | `@session_waiter` | `references/plugin-patterns.md` §3 |
| Cron | `cron_manager.add_basic_job` | `agent/cron.md` |
| Hook | `@filter.on_llm_request` | `agent/hooks.md` |
| Web API | `register_web_api` | `webui/plugin-pages.md` |
| Agent | `tool_loop_agent` | `agent/invoke-llm.md` |

### Step 0.5: Read "Always Read" Docs (3 files)

Before anything else, read these 3 official docs regardless of plugin type:

**Source**: `https://github.com/AstrBotDevs/AstrBot/tree/master/docs/en/dev/star/guides`

> `docs/en/dev/plugin.md` is the OLD doc — it redirects to `star/plugin-new.md`. Always use `star/` paths.

| File | Content |
|------|---------|
| `star/plugin-new.md` | Plugin lifecycle, naming conventions, metadata.yaml fields, skills/ bundling, support_platforms, astrbot_version, ruff, development principles |
| `star/guides/simple.md` | Minimal plugin, `__init__` signature |
| `star/guides/listen-message-event.md` | Event hooks, filter decorators, command_group |

**How**: `webfetch` → `https://raw.githubusercontent.com/AstrBotDevs/AstrBot/master/docs/en/dev/<path>`

### Step 1: Select Plugin Type(s)

Plugin types are NOT mutually exclusive. A single plugin can combine multiple types:

```
Command + LLM Tool:     /weather command AND AI auto-calls weather API
Command + Cron:         /remind command AND scheduled daily report
LLM Tool + Hook:        AI calls tool AND hook injects context
Command + Web API:      /status command AND dashboard page
```

Decision tree: `plugin-types/README.md`

| Type | Core API | File |
|------|----------|------|
| Command | `@filter.command` | `references/plugin-patterns.md` §1 |
| LLM Tool | `FunctionTool` + `add_llm_tools` | `agent/tools.md` |
| Session | `@session_waiter` | `references/plugin-patterns.md` §3 |
| Cron | `cron_manager.add_basic_job` | `agent/cron.md` |
| Hook | `@filter.on_llm_request` | `agent/hooks.md` |
| Web API | `register_web_api` | `webui/plugin-pages.md` |
| Agent | `tool_loop_agent` | `agent/invoke-llm.md` |

### Step 1.5: Read Type-Specific Official Docs

After selecting the type, read only the relevant official docs:

| Type | Read |
|------|------|
| LLM Tool / Agent / Cron | `star/guides/ai.md` |
| Web API | `star/guides/plugin-pages.md` |
| Platform Adapter | **MUST** use `https://github.com/AstrBotDevs/AstrBot/blob/master/docs/en/dev/plugin-platform-adapter.md` |
| Config | `star/guides/plugin-config.md` |
| Image Rendering | `star/guides/html-to-pic.md` |
| Storage | `star/guides/storage.md` |
| Message Sending | `star/guides/send-message.md` |

### Step 2: Scaffold & Implement

| Topic | File |
|-------|------|
| Development Workflow | `plugin-development-workflow.md` |
| Implementation Patterns | `references/plugin-patterns.md` |
| Core API | `references/core-concepts.md` |
| Best Practices | `references/best-practices.md` |
| Configuration System | `references/conf-schema.md` |
| Modular Split (>200 lines) | `references/modular-split.md` |

### Step 2.5: Pre-Review Cleanup

Before running review, clean up the generated code to avoid wasting review cycles:

1. **Remove unused imports** — scan every `import X` / `from X import Y`, verify it's used
2. **Remove dead code** — unused variables, unreachable branches, commented-out blocks
3. **Deduplicate** — same list/data defined in multiple places → extract to shared constant
4. **Verify `@filter.command` handlers** — no function parameters for user input, use `event.message_str`
5. **Verify `@dataclass` fields** — dict/list fields use `field(default_factory=...)`, not literals
6. **Verify `__init__` signature** — if using config, must have `config: AstrBotConfig`

### Step 3: Validate Metadata

Ensure `metadata.yaml` is complete. First-generation rules: `author` uses user's name, `repo` leaves empty, `display_name`/`desc`/`_conf_schema.json`/`README.md` match user's language.

Validation rules: `review/metadata-validation.md`

### Step 4: Review

See **Review Architecture** section below.

---

## Review Architecture

### Pipeline

```
review/review-workflow.md (orchestrator)
  │
  ├── Step A: Structure Validation
  │   └── review/metadata-validation.md
  │       - Required files exist
  │       - metadata.yaml fields correct
  │       - requirements.txt cross-check
  │
  ├── Step B: main.py Audit
  │   └── review/main-file-checklist.md
  │       §1: Import reference table (35+ entries)
  │       §2: Star subclass + __init__
  │       §3: LLM hook signatures
  │       §4: Event listener signatures
  │       §5: @filter.llm_tool + permission_type
  │       §6: Message sending in hooks
  │       §7: terminate()
  │       §8: Principle & API correctness
  │
  ├── Step C: General Code Audit
  │   └── review/general-file-checklist.md
  │       - 5-dimension model (quality, functional, security, maintainability, defects)
  │       - AstrBot framework checks
  │       - Dependency & import stability
  │       - Modular structure
  │       - Platform adapter config_metadata
  │       - WebUI plugin pages
  │       - API deprecation checks
  │
  └── Fix & Re-audit
      └── review/auto-fix-guide.md (20 patterns: FIX-00 ~ FIX-19)
```

### Review Triggers

| Trigger | Scope |
|---------|-------|
| Code generated or modified | Full pipeline on changed files |
| User requests "review"/"audit"/"校验"/"审核" | Full pipeline on **ALL** files |
| LLM iterating on fixes (internal) | Incremental on changed files; final delivery must pass full |

### Review Principles

1. **Official docs are authoritative** — during review, verify all API calls against official AstrBot docs (Step 0.5). When skill rules conflict with official docs, defer to official docs.
2. **Report only issues** — skip passing checks in output. If no issues: `✅ PASS — 0 issues in N files.`
3. **Severity levels**: 🔴 CRITICAL (must fix) / 🟡 WARNING (strongly recommend) / 🔵 INFO (optional)
4. **Conclusion**: ✅ PASS (0 critical, ≤2 warnings) / ⚠️ CONDITIONAL PASS (0 critical, warnings) / ❌ FAIL (critical exist)

### Output Format

```markdown
## Plugin Audit Report

### Issues Found
| # | Severity | File:Line | Issue |
|---|----------|-----------|-------|
| 1 | 🔴 CRITICAL | helpers.py:8 | Sync `requests.get()` blocks event loop |
| 2 | 🟡 WARNING | main.py:42 | Missing docstring on `@filter.command("speed")` |

### Summary
- Files checked: 4
- Issues: 1 CRITICAL / 1 WARNING / 0 INFO
- Conclusion: ❌ FAIL
```

---

## Mandatory Rules

### API & Imports

- During code generation, fixing, and review — always reference official AstrBot dev docs. Do NOT guess API signatures. Official docs are authoritative; when this skill conflicts, defer to official docs.
- `__init__` must accept `context: Context`. If using config, add `config: AstrBotConfig` and call `self.config = config` <!-- Source: guides/plugin-config.md -->
- Logging must use `from astrbot.api import logger` <!-- Source: guides/simple.md -->
- `filter` must be from `astrbot.api.event.filter` <!-- Source: guides/listen-message-event.md -->
- `@filter.on_keyword`, `@filter.on_full_match`, `@filter.on_regex` are **REMOVED** in v4.x — use `@filter.event_message_type(filter.EventMessageType.ALL)` + Python string matching <!-- Source: real-world bug, AstrBot v4.25.2 -->
- Every import path must be verified against `review/main-file-checklist.md` §1
- In `@dataclass` classes, dict/list fields MUST use `field(default_factory=lambda: {...})`, not direct dict/list literals <!-- Source: real-world bug -->
- `context.register_llm_tool()` is DEPRECATED — use `context.add_llm_tools()` <!-- Source: guides/ai.md -->
- `Tool.call()` MUST return `str` — do NOT use `ToolExecResult` (Python 3.12 issue) <!-- Source: real-world bug -->

### Command & Handler

- All handlers must use `async def` <!-- Source: guides/listen-message-event.md -->
- All `@filter.command` must have a docstring (WebUI displays it) <!-- Source: guides/simple.md -->
- Do NOT use function parameters for user text input — use `event.message_str.strip()` <!-- Source: real-world bug -->
- `@filter.command_group` must use function pattern (`def math(): pass`), NOT class <!-- Source: guides/listen-message-event.md -->
- `@filter.permission_type` cannot combine with `@filter.llm_tool` <!-- Source: guides/listen-message-event.md -->
- `@filter.llm_tool` Args: must follow `param_name(type): description` <!-- Source: guides/ai.md -->

### Hooks & Bridge

- `yield` is forbidden in `on_llm_request`/`on_llm_response`/`on_decorating_result`/`after_message_sent` — use `event.send()` <!-- Source: guides/listen-message-event.md -->
- `system_prompt += ...` only for stable settings; use `extra_user_content_parts` for per-round dynamic (7-20x cost) <!-- Source: guides/listen-message-event.md -->
- `self.text_to_image()` and `self.html_render()` are Star methods, not SDK functions <!-- Source: guides/html-to-pic.md -->
- Bridge API: `onContext()`, NOT `onContextChange()` <!-- Source: guides/plugin-pages.md -->
- Bridge endpoint: no `/` prefix, no `..`, query via `params` <!-- Source: guides/plugin-pages.md -->

### Project & Review

- After generating/modifying code, must execute review workflow
- User requests "review"/"audit" → full pipeline on ALL files
- Before review, validate metadata.yaml
- First generation: `repo` empty, text matches user language
- `requirements.txt` must list all third-party deps, no `astrbot`/`quart`
- After splitting main.py, verify all import paths
- Sensitive ops (git push, delete) require user confirmation
- Use ruff to format before submission <!-- Source: plugin-new.md -->
- Do NOT use `requests` for network requests — use `aiohttp` or `httpx` (async) <!-- Source: plugin-new.md -->
- Store persistent data in `data/` directory (via `StarTools.get_data_dir()`), NOT in the plugin's own directory — prevents data loss on reinstall <!-- Source: plugin-new.md -->
- Plugin naming: start with `astrbot_plugin_`, lowercase, no spaces, concise <!-- Source: plugin-new.md -->
- `short_desc` field in metadata.yaml: one-line summary for marketplace cards; falls back to `desc` if omitted <!-- Source: plugin-new.md -->
- `support_platforms` field: list of platform keys (e.g., `telegram`, `discord`, `aiocqhttp`) <!-- Source: plugin-new.md -->
- `astrbot_version` field: PEP 440 format, no `v` prefix (e.g., `>=4.16,<5`) <!-- Source: plugin-new.md -->
- `skills/` directory: bundle Skill definitions with plugin; auto-registered by AstrBot <!-- Source: plugin-new.md -->

---

## Token Efficiency Guide

This skill contains 50+ files. Reading all of them wastes tokens. Follow these rules:

### Reading Priority (Tiered)

**Tier 0 — Official docs** (mandatory, targeted by type):
- `https://github.com/AstrBotDevs/AstrBot/tree/master/docs/en/dev/star/guides`
- Platform adapters MUST use: `https://github.com/AstrBotDevs/AstrBot/blob/master/docs/en/dev/plugin-platform-adapter.md`

**Tier 1 — Core rules** (always read, ~300 lines):
- `SKILL.md` — this file (Mandatory Rules + Workflow)
- `review/main-file-checklist.md` §1 — Import reference table (35+ entries)

**Tier 2 — Task-specific** (pick 1-2 based on intent):

| Task | File |
|------|------|
| New plugin | `plugin-development-workflow.md` |
| LLM tools | `agent/tools.md` |
| Cron | `agent/cron.md` |
| Hooks | `agent/hooks.md` |
| Config | `references/conf-schema.md` |
| WebUI | `webui/plugin-pages.md` |
| Split main.py | `references/modular-split.md` |
| Platform adapter | `platform_adapters/adapter_interface.md` |
| Storage | `storage_utils/kv_storage.md` + `storage_utils/file_storage.md` |
| Image rendering | `design_standards/visual_utils.md` |

**Tier 3 — Reference** (read when needed):

| File | Purpose |
|------|---------|
| `references/core-concepts.md` | API quick index |
| `references/best-practices.md` | Best practices |
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

### With MCP

Use `search_docs(query)` to find content across all 46 documents without reading entire files.

---

## Complete File Map

```
skill_astrbot_plugin_dev_review/
│
├── SKILL.md                              # This file — primary entry
├── AGENTS.md                             # Skill system identifier (AI auto-detects)
├── README.md                             # Chinese-language overview
├── plugin-development-workflow.md        # 9-step development workflow
│
├── design_standards/                     # Architecture and design
│   ├── architecture_overview.md          # Core architecture (5 managers)
│   ├── event_flow.md                     # Message flow model (9 steps)
│   ├── context_usage.md                  # Context object API
│   ├── sandbox.md                        # Sandbox storage mounting
│   └── visual_utils.md                   # HTML rendering / text-to-image
│
├── messages/                             # Message model
│   ├── model.md                          # AstrBotMessage structure
│   ├── components.md                     # Message components
│   ├── events.md                         # AstrMessageEvent API
│   └── umo.md                            # Unified message origin
│
├── platform_adapters/                    # Platform adapters
│   ├── adapter_interface.md              # Adapter interface + config_metadata rules
│   ├── message_conversion.md             # Message conversion logic
│   └── telegram_media_group.md           # Telegram media group handling
│
├── agent/                                # Agent system
│   ├── index.md                          # Overview + minimal example
│   ├── tools.md                          # Tool definition (class/decorator/internal)
│   ├── invoke-llm.md                     # LLM call API
│   ├── hooks.md                          # Plugin Hooks + Agent Runner Hooks
│   ├── conversation.md                   # Conversation + prompt injection
│   ├── cron.md                           # Scheduled tasks
│   ├── subagents.md                      # Sub-agent handoff
│   ├── official-tools.md                 # Built-in tool list
│   ├── sandbox.md                        # Sandbox runtime
│   ├── agent-runner.md                   # Agent Runner (v4.7.0+)
│   ├── context-compression.md            # Context compression
│   ├── persona-control.md                # Persona management
│   └── register-skill.md                 # Skill registration
│
├── storage_utils/                        # Storage and utilities
│   ├── kv_storage.md                     # KV storage
│   ├── file_storage.md                   # File storage
│   ├── text_to_image.md                  # Text-to-image / HTML rendering
│   └── plugin-i18n.md                    # Internationalization
│
├── webui/                                # WebUI
│   └── plugin-pages.md                   # Dashboard + Bridge API + SSE
│
├── references/                           # Reference documentation
│   ├── core-concepts.md                  # Core API index
│   ├── best-practices.md                 # 11 best practices
│   ├── conf-schema.md                    # Configuration schema
│   ├── plugin-patterns.md                # 10 implementation patterns
│   └── modular-split.md                  # main.py split guide
│
├── review/                               # Review system
│   ├── review-workflow.md                # Pipeline orchestrator
│   ├── metadata-validation.md            # Structure validation
│   ├── main-file-checklist.md            # main.py 10 checks + import table
│   ├── general-file-checklist.md         # General code 5-dimension review
│   └── auto-fix-guide.md                 # 20 fix patterns (FIX-00 ~ FIX-19)
│
├── plugin-types/                         # Plugin type examples
│   ├── README.md                         # Type selection guide
│   ├── REVIEW-REPORTS.md                 # Review report examples
│   ├── type1-llm-tool/                   # LLM tool plugin
│   ├── type2-session-waiter/             # Multi-turn conversation
│   ├── type3-scheduled-task/             # Scheduled task
│   ├── type4-llm-hook/                   # LLM hook
│   ├── type5-web-api/                    # Web API
│   └── type6-agent-subagent/             # Agent sub-agent
│
├── mcp/                                  # Built-in MCP server
│   ├── server.py                         # MCP server (6 tools)
│   ├── requirements.txt                  # Dependencies
│   └── SETUP.md                          # Setup guide
│
└── script/astrbot-plugin-demo/           # Basic command plugin template
```

## MCP Server (Optional)

See `mcp/SETUP.md` for setup. Tools: `get_skill_info`, `list_docs`, `get_doc`, `search_docs`, `validate_import`, `get_review_checklist`.
