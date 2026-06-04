# Plugin Review Workflow

This file defines the automated review workflow. **Must be executed after every code generation or modification.**

## Review Pipeline

```
Step 1: Structure Validation (metadata-validation.md)
   ↓ PASS
Step 2: main.py Audit (main-file-checklist.md)
   ↓ PASS
Step 3: General Code Audit (general-file-checklist.md)
   ↓ PASS
Step 4: Summary Report → Fix → Re-audit
```

## Execution

### When User Requests Review/Audit

When the user says "review", "audit", "check", "校验", "审核", or similar, run the **full pipeline on ALL files**. Do NOT skip steps or files.

### Auto Review After Code Generation

After generating or modifying code, run the full pipeline automatically.

### Incremental Review (Internal Optimization)

When the LLM itself is iterating on fixes (not user-requested), it may skip unchanged files to save tokens. But the final delivery must pass a full review.

## Five-Dimension Audit Model

Each file is reviewed across 5 dimensions:

1. **Code Quality & PEP 8** — Naming, simplicity, style
2. **Functional Correctness** — Logic, edge cases, async usage
3. **Security** — Command injection, secrets, unsafe deserialization
4. **Maintainability** — Structure, single responsibility, docstrings
5. **Potential Defects** — Performance, exception handling, resource leaks

### AstrBot Framework Checks

- Logger MUST be `from astrbot.api import logger`
- All import paths MUST match the reference table in `review/main-file-checklist.md` §1
- Network I/O MUST be async
- Data persistence via `StarTools.get_data_dir()`
- LLM hook signatures MUST be correct
- `filter` MUST be from `astrbot.api.event.filter`

## Issue Severity

| Level | Meaning | Action |
|-------|---------|--------|
| 🔴 CRITICAL | Crash, security hole, runtime error | **Must fix** |
| 🟡 WARNING | Potential issue, bad practice | **Strongly recommend fix** |
| 🔵 INFO | Style, readability improvement | Optional |

## Audit Conclusion

- ✅ **PASS**: No critical issues, warnings ≤ 2
- ⚠️ **CONDITIONAL PASS**: No critical, but warnings need attention
- ❌ **FAIL**: Critical issues exist, must fix and re-audit

## Output Format

Keep reports concise. Only report issues, skip passing checks.

```markdown
## Plugin Audit Report

### Issues Found
| # | Severity | File:Line | Issue |
|---|----------|-----------|-------|
| 1 | 🔴 CRITICAL | helpers.py:8 | Sync `requests.get()` blocks event loop |
| 2 | 🔴 CRITICAL | main.py:15 | `from astrbot.api.logger import logger` (wrong path) |
| 3 | 🟡 WARNING | main.py:42 | Missing docstring on `@filter.command("speed")` |

### Summary
- Files checked: 4
- Issues: 2 CRITICAL / 1 WARNING / 0 INFO
- Conclusion: ❌ FAIL
```

If no issues found, output only:
```markdown
## Plugin Audit Report
✅ PASS — 0 issues in 4 files checked.
```

## Fix & Re-audit

1. Locate issues from audit report
2. Fix using `review/auto-fix-guide.md`
3. Re-run full audit after fixing
4. Repeat until audit passes
