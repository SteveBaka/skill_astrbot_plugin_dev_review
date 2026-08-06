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
  compatibility: astrbot >=4.16 (recommend >=4.26.8 for current runtime / market / conf dict defaults)
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
Step 0:   Understand Intent
  ↓
Step 0.2: Confirm identity (plugin name + author) — GATE before scaffold
  ↓
Step 0.5: Pre-code read (MANDATORY, minimal set) — official Always-Read
          + FIX-00/02 lessons + type README/example only as needed
  ↓
Step 1:   Select Type(s)
  ↓
Step 1.5: Read type-specific official docs (ONLY the guides for chosen type)
  ↓
Step 2:   Scaffold & Implement (imports/handlers from docs+checklist, not memory)
  ↓
Step 2.5: Pre-Review Cleanup
  ↓
Step 3:   Validate Metadata (+ schema / plugin_set implications)
  ↓
Step 4A:  First-output review (runtime-critical) — enhance guidance on Star pitfalls
  ↓
Step 4B:  Full review after features done / user audit — still on-demand file reads
  ↓
Step 5:   Fix if needed → Re-review
  ↓
Install / enable / profile plugin_set (user configures in AstrBot Dashboard when needed)
  ↓
Smoke ONLY after user confirms Dashboard enable + plugin_set/profile ready
  ↓
Deliver (no git commit/push without explicit user approval)
```

> **Authority order (high → low)**: (1) Official docs under `docs/en/dev/star/**` + adapter doc; (2) this skill; (3) historical pitfall notes. **Never** use legacy `docs/en/dev/plugin.md` as authority (redirect-only / obsolete). When skill conflicts with official docs, **official wins**.
>
> **Token rule**: read **on demand** — never bulk-load the whole skill tree. Prefer MCP `search_docs` / single checklist sections. Expand only when review finds a concrete gap.

### Step 0: Understand User Intent

| User Says | Intent | Action |
|-----------|--------|--------|
| "Write a plugin that does X" | New plugin | Full workflow starting at Step 0.2 |
| "Add a command to do X" | Add command to existing | Read existing main.py, add handler (no rename without confirm) |
| "Let AI call my API" | Add LLM tool | Official `star/guides/ai.md` + `agent/tools.md` |
| "Fix this error" | Bug fix | Official docs for the API + skill FIX guide; prefer minimal diff |
| "Review my code" | Full audit | **Phase 4B** full pipeline on ALL files |
| "Add a scheduled task" | Add cron | Official + `agent/cron.md` |
| "Make a settings page" | WebUI | Official `star/guides/plugin-pages.md` + `webui/plugin-pages.md` |

### Step 0.2: Confirm Plugin Name & Author (GATE)

**Before creating any plugin directory or writing `metadata.yaml` / `main.py`**, stop and obtain explicit user confirmation:

1. **Plugin package name** (`metadata.yaml` `name` and folder name):
   - MUST match: `^astrbot_plugin_[a-z0-9_]+$` (prefix `astrbot_plugin_`, lowercase, digits/underscore only, no spaces)
   - Example: `astrbot_plugin_weather` ✅ | `WeatherPlugin` ❌ | `astrbot-plugin-weather` ❌
2. **Author** (`metadata.yaml` `author`): exact string the user wants (do not invent a GitHub handle without asking)

**How to ask** (short, in the user's language):

```text
Before scaffolding, please confirm:
1) Plugin name (folder + metadata name), format: astrbot_plugin_<name>
2) Author name for metadata.yaml
Suggested name: astrbot_plugin_<slug> — OK?
```

**Rules**:
- If the user already gave both clearly, restate once and proceed only if unambiguous
- If missing or invalid name, **do not scaffold** until corrected
- Do not rename an existing published plugin folder without explicit approval

### Step 0.5: Pre-Code Read (MANDATORY, anti-amnesia for imports/handlers)

**Do not scaffold from model memory.** Before writing `main.py` / handlers, load this **minimal** set (and nothing else unless Step 1.5 needs it):

**A. Official Always-Read** — fetch with `webfetch` from  
`https://raw.githubusercontent.com/AstrBotDevs/AstrBot/master/docs/en/dev/<path>`

| Path | Content |
|------|---------|
| `star/plugin-new.md` | Lifecycle, naming, metadata, skills/, ruff, data dir, aiohttp |
| `star/guides/simple.md` | Minimal plugin, `__init__` |
| `star/guides/listen-message-event.md` | Commands, filters, hooks (current API only) |

**B. Local FIX lessons (imports + handlers — highest false-load rate)** — read **only** these slices, not the whole skill:

| Read | Why |
|------|-----|
| `review/main-file-checklist.md` **§1 import table only** | Canonical import paths (FIX-00) |
| `review/auto-fix-guide.md` **FIX-00** + **FIX-02** sections only | Wrong import module; handler extra params / `message_str` |
| `plugin-types/README.md` | Pick type (decision tree) |
| **One** matching `plugin-types/type*/main.py` **or** `script/astrbot-plugin-demo` | Pattern copy — not all six types |

**C. Explicitly avoid at this step**: full `design_standards/**`, all `agent/**`, all six type trees, entire `auto-fix-guide`, OpenAPI dump, global logs.

**Forbidden as authority**: `docs/en/dev/plugin.md` / `docs/zh/dev/plugin.md` (legacy).

**Generation rule**: every `from astrbot...` and every `@filter.command` / hook signature must be traceable to A+B above (or to a type guide opened in Step 1.5). If unsure → re-fetch official guide or checklist §1 — do not invent paths.

### Step 1: Select Plugin Type(s)

Types may combine. Decision tree: `plugin-types/README.md`.

| Type | Core API | Skill file | Official guide (under docs/en/dev/) |
|------|----------|------------|-------------------------------------|
| Command | `@filter.command` | `references/plugin-patterns.md` | `star/guides/listen-message-event.md` |
| LLM Tool | `FunctionTool` + `add_llm_tools` | `agent/tools.md` | `star/guides/ai.md` |
| Session | `@session_waiter` | `references/plugin-patterns.md` | `star/guides/session-control.md` |
| Cron | `cron_manager` | `agent/cron.md` | `star/guides/ai.md` + runtime |
| Hook | `@filter.on_llm_*` etc. | `agent/hooks.md` | `star/guides/listen-message-event.md` |
| Web API | `register_web_api` | `webui/plugin-pages.md` | `star/guides/plugin-pages.md` |
| Agent | `tool_loop_agent` | `agent/invoke-llm.md` | `star/guides/ai.md` |
| Adapter | Platform adapter | `platform_adapters/adapter_interface.md` | **MUST** `plugin-platform-adapter.md` |

### Step 1.5: Read Type-Specific Official Docs

After type selection, fetch only what you need from `docs/en/dev/star/guides/` (same raw base URL as Step 0.5):

| Type | Path under `docs/en/dev/` |
|------|---------------------------|
| LLM Tool / Agent / Cron | `star/guides/ai.md` |
| Web API / pages | `star/guides/plugin-pages.md` |
| Config | `star/guides/plugin-config.md` |
| Session | `star/guides/session-control.md` |
| Storage / KV | `star/guides/storage.md` |
| Image | `star/guides/html-to-pic.md` |
| Send message | `star/guides/send-message.md` |
| i18n | `star/guides/plugin-i18n.md` |
| Platform adapter | `plugin-platform-adapter.md` (not under guides/) |

Also re-check changelog behavior for target version (e.g. ≥4.26.x tool enable vs plugin enable, KV on uninstall).

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

Ensure `metadata.yaml` matches **Step 0.2** confirmed `name` + `author`. First-generation: `repo` empty, `display_name`/`desc`/`_conf_schema.json`/`README.md` match user language.

Validation rules: `review/metadata-validation.md`

### Step 4A: First-Output Review (Runtime Gate)

**When**: Immediately after the **first** generation of a new plugin scaffold (or first complete dump of `main.py` + metadata + schema). **Before** telling the user it is ready to install/run.

**Goal**: Prevent first-run crash / load failure. Full pass of `review/review-workflow.md` on **all new files**, with CRITICAL focus:

- Imports (table §1), `async`/`await`, command handlers (`event.message_str`, docstrings)
- No removed filters (`on_keyword` / …), correct hooks / no yield in hooks
- `__init__(context[, config])`, `super().__init__`, `field(default_factory=...)`, tools `return str`
- `metadata.yaml` name/author, `_conf_schema.json` validity, `requirements.txt` cross-check
- Namespace / `sys.path` if multi-module; `get_data_dir` only from Star

**Must fix all 🔴 before delivery of first scaffold.** See Phase A in `review/review-workflow.md`.

### Step 4B: Full Product Review

**When**: Feature work complete, major change set finished, or user asks review/audit/校验/审核.

**Goal**: Accuracy, security, completeness — full pipeline on **ALL** project files (not only the last diff). Security dimension mandatory. See Phase B in `review/review-workflow.md`.

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
      └── review/auto-fix-guide.md (FIX-00 ~ FIX-29; dedupe by symptom, no parallel conflicting fixes)
```

### Two-Phase Review

| Phase | When | Scope | Focus |
|-------|------|--------|--------|
| **A — First-output / runtime** | After first scaffold or first full code dump | All new/touched plugin files | Load/run CRITICALS only path: imports, async, handlers, config inject, metadata name/author, schema, requirements, forbidden APIs |
| **B — Full product** | Features done, large change set, or user says review/audit/校验/审核 | **Entire** plugin tree | Accuracy, security, completeness + all Phase A checks |

Pipeline steps A→B always use: `metadata-validation` → `main-file-checklist` → `general-file-checklist` → report → fix via `auto-fix-guide` → re-audit.

### Review Triggers

| Trigger | Phase | Scope |
|---------|-------|--------|
| First plugin scaffold generated | **A** | All new files (mandatory, no skip) |
| Incremental feature edits | **A** on changed files + known CRITICAL classes | Prefer minimal diff |
| Feature complete / "review" request | **B** | **ALL** files |
| Internal fix loop | Incremental | Final handoff still needs Phase A clean; user audit needs Phase B |

### Review Principles

1. **Official docs + current version behavior are authoritative** — re-verify APIs against `star/plugin-new.md` + relevant guides; defer to official docs on conflict. Do **not** treat legacy `plugin.md` as source.
2. **Also verify runtime behaviors** (v4.26.x+): plugin enable ≠ tool enable; uninstall clears plugin KV; schema may have UTF-8 BOM; handler binding is idempotent (still avoid double-register). On **≥4.26.8**: conf dict defaults mapped; local upload hang fixed; per-plugin log level available; publish via AstrBot Cloud (ZIP ≤16MB).
3. **Phase A fails closed** — do not claim "ready to install" if any 🔴 remains.
4. **Report only issues** — skip passing checks. If none: `✅ PASS — Phase A/B — 0 issues in N files.`
5. **Severity**: 🔴 CRITICAL / 🟡 WARNING / 🔵 INFO
6. **Conclusion**: ✅ PASS (0 critical, ≤2 warnings) / ⚠️ CONDITIONAL / ❌ FAIL
7. **Review teaches Star mechanics** — for each 🔴/🟡, cite the mechanism (import table, handler binding, config inject, event yield rules, etc.) and the FIX id / official guide section so the agent internalizes AstrBot Star pitfalls — not only “change this line”.
8. **On-demand reading during review** — start with `review_path` (MCP) or checklists for **touched files only** (Phase A). Open `auto-fix-guide` **only for FIX ids that fired**. Open deep design/agent docs **only** if an issue needs that subsystem. Never re-read all Tier 3 files “for thoroughness”.

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

### Project, Gates & Review

- **Identity gate**: before scaffold, confirm plugin `name` = `astrbot_plugin_<slug>` and `author` with the user
- **Pre-code gate (Step 0.5)**: official Always-Read + import table §1 + FIX-00/02 + one type example — **before** first `main.py`; no coding from bare memory for astrbot imports/handlers
- After **first** code generation, run **Phase A** runtime review on all new files; fix 🔴 before claiming runnable; prefer MCP `astrbot_review_path` then open only matching FIX sections
- After features complete or user audit request, run **Phase B** full-tree review (accuracy, security, completeness)
- User requests "review"/"audit"/"校验"/"审核" → **Phase B** on ALL files
- Before review, validate metadata.yaml (`name`/`author` match confirmation)
- First generation: `repo` empty, user-facing text matches user language
- `requirements.txt` must list all third-party deps, no `astrbot`/`quart`
- After splitting main.py, verify all import paths
- **Dashboard config before smoke** (mandatory UX):
  1. After **new plugin** install, or after adding/changing anything the user must set in AstrBot UI — including **`_conf_schema.json` fields**, profile **`plugin_set`**, per-tool enable, provider, etc. — **stop and tell the user** to adjust in **AstrBot Dashboard** (plugin config + WebChat profile `plugin_dev_skill` / `plugin_set`).
  2. **Do not** run `astrbot_smoke_suite` / `chat_probe` until the user confirms those settings are done (or explicitly asks to smoke anyway).
  3. Agent does **not** silently rewrite live profile `plugin_set` or plugin config to “make smoke pass” unless the user clearly orders that mutation.
- **Observability scope**: for the plugin under development only — `plugins/failed` + smoke/SSE; **no** system-wide AstrBot log tail in MCP
- **High-risk ops require explicit user approval before execution** — never do these until the user clearly allows:
  - `git commit`, `git push`, `git push --force` / force-with-lease, `git amend` of shared commits
  - Deleting repos/files en masse, publishing/releasing packages
  - **Large rewrites** of code that already runs (prefer minimal patches unless user asks for refactor)
  - **Plugin uninstall** (MCP `astrbot_plugin_uninstall` or any equivalent): see **Uninstall data safety** below
- **Uninstall data safety** (mandatory for agents using Runtime MCP or manual uninstall):
  1. When the user asks to uninstall a plugin, **ask** whether to **keep configuration** and **keep persistent data** (`data/` / plugin data dir).
  2. If the user does **not** answer those questions → **default KEEP both** (`delete_config=false`, `delete_data=false`).
  3. **Never** silently delete plugin config or persistent data; only set delete flags after **explicit** user approval.
  4. MCP tool defaults: `keep_config=true`, `keep_data=true`, `confirm_uninstall` required; deleting config/data needs extra `confirm_delete_*`.
  5. Prefer non-destructive test sandbox `astrbot_plugin_mimo_tts` only when user allows; do not uninstall production plugins during routine MCP tests.
  6. Note: framework may still clear **plugin KV** on uninstall (≥4.26.2) even when file data is kept — tell the user if relevant.
- **Local install / update via Runtime MCP (Scheme A)** — preferred LAN workflow:
  1. Plugin root must contain `metadata.yaml` + `main.py`.
  2. `astrbot_plugin_pack_preview(path)` optional dry-run (respects `.gitignore` + hard excludes).
  3. `astrbot_plugin_install_path(path)` → ZIP → `POST /api/v1/plugins/install/upload` → enable → reload → `failed` probe.
  4. **Update loop (primary)**: edit on dev machine → `install_path` again (re-upload) → reload/failed (defaults on). **Do not uninstall first** when re-upload works.
  5. **`success=true` ≠ code replaced.** Same `metadata.version` re-upload may leave old files (stale components/behavior). If no effect: bump `version` then install, or `install_path(..., force_refresh=true)` (uninstall **keep config+data** then upload). Default never auto-uninstall; tool may set `warning=possible_stale_install`.
  6. ZIP **filename** is generated from `metadata.yaml`: `{name}-{version}.zip` (fallback `{name}.zip` / folder name). Archive top-level folder prefers `metadata.name`.
  7. ZIP **contents** exclusions follow plugin/parent `.gitignore` so packages align with GitHub Download ZIP / marketplace; always drop `.git`/`.venv`/`__pycache__`/etc.
  8. **Same-name conflict (fallback only)**: if upload fails because the plugin is already installed / name conflicts, then uninstall with **keep config + keep data** (`delete_config=false`, `delete_data=false`; MCP: `keep_config=true`, `keep_data=true`, `confirm_uninstall=true`) and run `install_path` again — or use `force_refresh=true`. Never wipe config/data unless the user explicitly approves. Prefer primary re-upload path whenever possible.
  9. Requires `ASTRBOT_ALLOW_MUTATIONS=true`. Do not use chat `file` APIs as install channel.
  10. Routine tests: prefer user-approved sandbox (`astrbot_plugin_mimo_tts`); do not mass-install unrelated plugins.
- **Dev WebChat profile `plugin_dev_skill` (Runtime MCP)** — isolation for functional tests:
  1. Do **not** use AstrBot `default` profile to validate plugin features (`plugin_set` is often empty / polluted).
  2. Before create: list providers (`astrbot_providers_brief`), **user picks** `provider_id`; target `plugin_id` known.
  3. `astrbot_ensure_plugin_dev_skill(plugin_id, provider_id, confirm_create=true, …)` builds from **default** config with `plugin_set=[plugin]` (+ optional extras). Never return full config body (secrets).
  4. If profile already exists: **stop** — user chooses `exist_policy=abort|recreate|rename_old` (recreate needs `confirm_delete_existing`; deletes **profile only**, not the plugin).
  5. After create: tell user to open **Dashboard → WebChat → select `plugin_dev_skill`** for manual testing.
  6. MCP WebChat smoke: `astrbot_chat_probe` — **default OFF**; call only with `confirm_probe=true` after user allows (or `ASTRBOT_ALLOW_CHAT_PROBE`). Needs **chat-scoped** API key, `username`, default `config_name=plugin_dev_skill`. All probes reuse ONE fixed smoke session (`mcp-smoke-<username>`, override via `session_id` / `ASTRBOT_CHAT_SMOKE_SESSION_ID`) — a single stable Dashboard WebChat entry the user manages there; API keys **cannot** delete user-owned sessions (creator check, source-verified), so never attempt auto-deletion or system-scope workarounds. Prefer user-driven Dashboard chat for primary testing.
  6b. `astrbot_chat_sessions_cleanup` — **webchat-platform-only** deletion with verification against the username's session list (other platforms → `scope_violation`); needs mutations + `confirm_cleanup=true` + user-reviewed list; can only delete sessions created via the API key itself.
  6c. `astrbot_scaffold_plugin(name, author, plugin_type=command|llm_tool|session|cron|hook|web|agent|adapter, …)` — contracts skeleton; **must** finish with review error=0. `adapter` = frame only (no WebChat smoke until you provide a live adapter). BUSINESS edits only after.
  6c-bis. **Staging → install, never hand-copy**: `output_dir` is only a staging area (default `ASTRBOT_DEV_WORKSPACE` or `~/.astrbot_skill_workspace`; **never cwd**). Always upload via `astrbot_plugin_install_path(path)`; the INSTALLED path is `<data>/plugins/<root_dir_name>/` no matter where the staging dir is. Do **not** ask the user to copy files into `/AstrBot/<name>/`. Use `extra_files_json` to deliver the full plugin in one call (main.py / metadata.yaml / requirements.txt / **_conf_schema.json** / README.md). If a plugin reads `config`, it **must ship `_conf_schema.json`**, or `config_set` returns 400 "没有注册配置".
  6d. `astrbot_review_path(path, profile=plugin|adapter)` — AST review (shared contracts); FIX-03 hooks on plugin profile; **FIX-06** on adapter (`id`/`enable` ban, **no `_conf_schema.json`**, no Platform attr shadow); **FIX-30** adapter dual-registration (`register_platform_adapter` without a `Star` subclass → "未通过 Star 注册"); **FIX-32** prefix custom config_metadata fields (shared-items collision). Before install_path; fix all `error` first.
  6d-adapter: Follow official `astrbot/core/platform/register.py` + plugin-platform-adapter.md — custom fields only in tmpl (core injects type/enable/id); **never** Star `_conf_schema.json` for adapters.
  6e. `astrbot_smoke_suite(plugin_id, confirm=true, username=…)` — only **after** user configures Dashboard (enable, profile `plugin_set`, `_conf_schema`). Loop: scaffold → review_path → install_path → **user Dashboard** → smoke_suite.
  6f. `astrbot_chat_probe(message=…)` — fill `message` with the **plugin's own command** (from components). Use `/plugin_help` as a minimal discovery probe when unsure; **never hardcode other plugins' commands** (e.g. `/ttsinfo` is mimo_tts-only).
  6g. `astrbot_plugin_log_level_get/set` — per-plugin log level (v4.27.0). `set` needs mutations; DEBUG raises verbosity and may capture user message content — reset to follow-global (empty level) after debugging.
  7. Do **not** auto-bind global config-routes unless user explicitly requests.
- **Privacy — configs**:
  1. After install: only **Dashboard checklists** by plugin type (`astrbot_post_install_hints` / install response `dashboard_hints`) — **no** automatic `plugin_config_get` or full profile reads.
  2. Agent/skill must **not** privately scan plugin or AstrBot configuration; read a value only when the user **names** the parameter/key to inspect.
  3. Never commit tokens, full configs, or WebChat transcripts into the skill repo.
- Use ruff to format before submission <!-- Source: plugin-new.md -->
- Do NOT use `requests` for network requests — use `aiohttp` or `httpx` (async) <!-- Source: plugin-new.md -->
- Store persistent data in `data/` directory (via `StarTools.get_data_dir()`), NOT in the plugin's own directory — prevents data loss on reinstall <!-- Source: plugin-new.md -->
- `StarTools.get_data_dir()` MUST be called from a `Star` subclass (e.g., plugin `__init__`), NOT from Service/Manager classes — pass `data_dir` as parameter <!-- Source: real-world bug -->
- If using sub-packages (handlers/, services/, etc.), add `sys.path.insert(0, os.path.dirname(__file__))` at top of main.py to avoid namespace collision with other plugins <!-- Source: real-world bug -->
- Plugin naming: start with `astrbot_plugin_`, lowercase, no spaces, concise <!-- Source: plugin-new.md -->
- `short_desc` field in metadata.yaml: one-line summary for marketplace cards; falls back to `desc` if omitted <!-- Source: plugin-new.md -->
- `support_platforms` field: list of platform keys (e.g., `telegram`, `discord`, `aiocqhttp`) <!-- Source: plugin-new.md -->
- `astrbot_version` field: PEP 440 format, no `v` prefix (e.g., `>=4.16,<5`) <!-- Source: plugin-new.md -->
- `skills/` directory: bundle Skill definitions with plugin; auto-registered by AstrBot <!-- Source: plugin-new.md -->
- Plugin enabled ≠ every LLM tool enabled — WebUI can disable tools independently (≥4.26.0 / 4.26.2) <!-- Source: releases -->
- Plugin uninstall clears plugin KV storage (≥4.26.2) — do not assume KV survives uninstall <!-- Source: releases -->
- `_conf_schema.json` may include UTF-8 BOM (≥4.26.7); still prefer UTF-8 without BOM for editors <!-- Source: releases -->
- Dict-type fields in `_conf_schema.json`: core maps defaults correctly (≥4.26.8 #9414) — still use explicit schema defaults; do not rely on accidental `{}` sharing <!-- Source: v4.26.8 -->
- Marketplace publish: use [AstrBot Cloud](https://cloud.astrbot.app/publish) (WebUI market syncs from Cloud); package **ZIP ≤ 16MB**; include clean tree (no `.git` / `__pycache__` / venv) — aligns with MCP `zip_pack` excludes <!-- Source: plugin-publish.md / v4.26.8 -->
- Per-plugin log level: Dashboard + plugin API `PUT /api/v1/plugins/{id}/log-level` with body `{"level": "DEBUG"|"INFO"|...|null}` (null = follow global); `log_level` also appears on plugin config GET (source ≥4.26.8 #9342; **in public OpenAPI since 4.27.0**) <!-- Source: v4.26.8 source / 4.27.0 spec -->
- Prefer official recommended Python **3.12** for development; skill minimum remains 3.10 for tooling <!-- Source: docs 4.26.2 -->

---

## Token Efficiency Guide

This skill contains 50+ files. **Reading all of them is forbidden by default.**  
Goal: stronger Star understanding **and** low token/time cost via **strict on-demand reads**.

### Hard caps

| Phase | Max extra local files beyond Step 0.5 / current checklists | Notes |
|-------|------------------------------------------------------------|--------|
| Scaffold / first implement | 0–2 Tier-2 files | Plus **one** type example only |
| Phase A review | MCP `review_path` first; then only FIX sections that fired | No full `auto-fix-guide` dump |
| Phase B | Checklists + files under audit; deep docs only per open issue | Still no “read entire skill” |
| Smoke prep | SETUP smoke gates + user Dashboard reminder | No log APIs |

### Reading Priority (Tiered)

**Tier 0 — Official docs** (Step 0.5 Always-Read; then **only** type guides you selected):
- Always (before code): `star/plugin-new.md`, `star/guides/simple.md`, `star/guides/listen-message-event.md`
- By type (Step 1.5 only): matching file under `docs/en/dev/star/guides/`
- Adapters MUST: `plugin-platform-adapter.md`
- Publish / market / OpenAPI: only when shipping or doing API work
- **Ignore as authority**: `docs/en/dev/plugin.md` (legacy redirect)

**Tier 1 — Core rules** (session entry + pre-code):
- `SKILL.md` — Mandatory Rules + Workflow + this guide
- `review/main-file-checklist.md` **§1 only** until a review needs more sections
- FIX-00 / FIX-02 from `review/auto-fix-guide.md` at pre-code (Step 0.5)

**Tier 2 — Task-specific** (**pick 1–2**, never the whole column):

| Task | File |
|------|------|
| New plugin | `plugin-development-workflow.md` |
| LLM tools | `agent/tools.md` |
| Cron | `agent/cron.md` |
| Hooks | `agent/hooks.md` |
| Config / `_conf_schema` | `references/conf-schema.md` |
| WebUI | `webui/plugin-pages.md` |
| Split main.py | `references/modular-split.md` |
| Platform adapter | `platform_adapters/adapter_interface.md` |
| Storage | `storage_utils/kv_storage.md` and/or `file_storage.md` as needed |
| Image rendering | `design_standards/visual_utils.md` |

**Tier 3 — Reference** (open **one file for one question**; default closed):

| File | Purpose |
|------|---------|
| `references/core-concepts.md` | API quick index |
| `references/best-practices.md` | Best practices / install true-update |
| `references/plugin-patterns.md` | Patterns (prefer type example first) |
| `agent/*` (except tools/cron/hooks above) | Only if implementing that subsystem |
| `design_standards/*` | Only if debugging architecture-level issues |
| `messages/*` / `platform_adapters/*` | Only if touching message/adapter code |
| `review/general-file-checklist.md` | Phase B / non-main files |
| `plugin-types/type*/main.py` | **One** type; not all six |

### With MCP

- `search_docs(query)` / `get_doc` — prefer over reading multi-file trees  
- `astrbot_review_path` — first pass static gate; then FIX-guided reads only  
- `validate_import` — when a single symbol is doubtful  
- Do **not** fetch OpenAPI or full logs for ordinary plugin codegen

### Error feedback loop (regression → auto-fix-guide)

When running regression on `plugin-types/type*` or an adapter and hitting
install/smoke errors:

1. `export ASTRBOT_ERROR_KB="$(pwd)/.error_kb.json"` (absolute; gitignored) so
   `install_path` / `smoke_suite` failures auto-record **desensitized** fingerprints.
   Never set it to a literal `$PWD/...` (unexpanded) — that creates a `$PWD` dir
   inside the CWD (see FIX-33).
2. `python3 mcp/scripts/error_kb.py --store <path> report` — review samples/counts.
3. `python3 mcp/scripts/error_kb.py --store <path> propose --guide review/auto-fix-guide.md --min 2`
   — writes drafts **only for validated entries** (no duplicates / not too generic);
   rejected ones are listed as skipped and must not be appended as-is.
4. Manually verify root cause, add the FIX section to `auto-fix-guide.md`, and fold
   the fingerprint regex into `failure_analysis._SIGNATURES` so next runs auto-classify.

Full flow: `mcp/SETUP.md` §3.2 Maintenance · `README.md` 维护章节.

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
