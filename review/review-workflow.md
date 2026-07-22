# Plugin Review Workflow

This file defines the automated review workflow. **Must run after first scaffold (Phase A) and after feature completion / user audit (Phase B).**

## Review Pipeline (both phases)

```
Step 1: Structure Validation (metadata-validation.md)
   ↓ PASS
Step 2: main.py Audit (main-file-checklist.md)
   ↓ PASS
Step 3: General Code Audit (general-file-checklist.md)
   ↓ PASS
Step 4: Summary Report → Fix (auto-fix-guide.md) → Re-audit
```

Re-verify public APIs against official docs: `star/plugin-new.md` + relevant `star/guides/*` (never legacy `plugin.md`).

---

## Two Phases

### Phase A — First-output / Runtime Gate

**When**

- Immediately after **first** generation of a new plugin (`main.py` + `metadata.yaml` + optional schema/requirements/README)
- After a large first dump of code intended to be installable

**Scope**: All new files (no skipping).

**Goal**: First install/load does not crash.

**CRITICAL focus (must be zero 🔴)**

| Area | Checks |
|------|--------|
| Identity | `metadata.name` = folder; format `astrbot_plugin_[a-z0-9_]+`; `author` set as confirmed |
| Imports | Table in `main-file-checklist.md` §1; no unused/stale imports |
| Star / config | `super().__init__(context)`; `config: AstrBotConfig` if schema used |
| Handlers | `async def`; docstring on commands; `event.message_str` for text input; no removed filters |
| Hooks | Correct signatures; no `yield` in hooks |
| Tools | `add_llm_tools`; `call` returns `str`; `field(default_factory=...)` for dict params |
| Multi-module | `sys.path.insert` if generic packages; `get_data_dir` only from Star |
| Deps | `requirements.txt` matches third-party imports; no `astrbot`/`quart`/`requests` preferred aiohttp |

**Output label**: `## Plugin Audit Report (Phase A — Runtime)`

Do **not** tell the user the plugin is ready to run until Phase A is ✅ (0 CRITICAL).

### Phase B — Full Product Audit

**When**

- Features finished
- Large change set done
- User says review / audit / check / 校验 / 审核

**Scope**: **Entire** plugin tree (all files). Do not limit to last diff.

**Goal**: Accurate, complete, secure.

**Additional focus beyond Phase A**

| Dimension | Checks |
|-----------|--------|
| Accuracy | Logic matches requirements; APIs match official docs |
| Security | No secrets; no injection; path safety; no unsafe eval/pickle; adapter no enable/id hijack |
| Completeness | README, schema language, terminate cleanup, error handling, permissions |
| Runtime awareness | Tool enable vs plugin enable; KV on uninstall; BOM schema OK ≥4.26.7 |

**Output label**: `## Plugin Audit Report (Phase B — Full)`

---

## Execution Rules

### User-requested review

Always **Phase B** on **ALL** files.

### After first generation

Always **Phase A** automatically.

### After small incremental fixes

May re-run Phase A checks on changed files only; **final** handoff of a runnable plugin still needs clean Phase A; user-facing audit needs Phase B.

### High-risk actions during fix

Do **not** `git commit` / `git push` / force-push, or mass-rewrite working code, without explicit user permission (see SKILL.md gates).

---

## Five-Dimension Audit Model (Phase B full; Phase A emphasizes 2+3)

1. **Code Quality & PEP 8** — Naming, simplicity, unused imports, dead code  
2. **Functional Correctness** — Logic, async, AstrBot handlers  
3. **Security** — Secrets, injection, paths, unsafe APIs  
4. **Maintainability** — Structure, docstrings, split modules  
5. **Potential Defects** — Resources, exceptions, concurrency  

### AstrBot Framework Checks

- Official docs: `star/plugin-new.md` + guides (not legacy `plugin.md`)
- Logger: `from astrbot.api import logger`
- Import table: `review/main-file-checklist.md` §1
- Network: async (`aiohttp`/`httpx`)
- `StarTools.get_data_dir()` from Star only
- Hooks: correct signatures; no yield
- Tools: `add_llm_tools`; tool enable independent of plugin enable (≥4.26.x)
- KV cleared on uninstall (≥4.26.2)

## Issue Severity

| Level | Meaning | Action |
|-------|---------|--------|
| 🔴 CRITICAL | Crash, security hole, load/runtime error | **Must fix** (blocks Phase A) |
| 🟡 WARNING | Bad practice / likely bug | Strongly fix (Phase B) |
| 🔵 INFO | Style / optional | Optional |

## Audit Conclusion

- ✅ **PASS**: No critical; warnings ≤ 2  
- ⚠️ **CONDITIONAL PASS**: No critical; warnings need attention  
- ❌ **FAIL**: Critical remain  

## Output Format

```markdown
## Plugin Audit Report (Phase A — Runtime | Phase B — Full)

### Issues Found
| # | Severity | File:Line | Issue |
|---|----------|-----------|-------|
| 1 | 🔴 CRITICAL | main.py:15 | wrong logger import |

### Summary
- Phase: A|B
- Files checked: N
- Issues: X CRITICAL / Y WARNING / Z INFO
- Conclusion: ✅ PASS | ⚠️ CONDITIONAL | ❌ FAIL
```

If clean:

```markdown
## Plugin Audit Report (Phase A — Runtime)
✅ PASS — 0 issues in N files checked.
```

## Fix & Re-audit

1. Map issues to `review/auto-fix-guide.md` (FIX-00–29)
2. Prefer minimal patches unless user approved large rewrite
3. Re-run the **same phase** until PASS
4. User audit request always ends with Phase B
