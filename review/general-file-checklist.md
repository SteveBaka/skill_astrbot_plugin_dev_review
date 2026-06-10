# General Code Review Checklist

This file applies to all .py files **except** main.py, and to general code patterns within main.py.

## Review Dimensions

### 1. Code Quality & PEP 8

- [ ] Clear naming (functions `snake_case`, classes `CamelCase`, constants `UPPER_CASE`)
- [ ] No overly complex code blocks (ideally < 50 lines per function)
- [ ] **No unused imports** — every `import X` / `from X import Y` must be used somewhere in the file
- [ ] **No stale imports** — after refactoring, verify all imported names still exist in the source module
- [ ] **No dead code** — every variable, function, and data structure must be referenced; remove unused API lists, unreachable branches, commented-out code
- [ ] **No duplicate code** — the same list/data should not be defined in multiple places; extract to a shared constant or module
- [ ] No magic numbers (use constants or config)
- [ ] Consistent indentation (4 spaces)

### 2. Functional Correctness

- [ ] Logic is correct, edge cases handled
- [ ] No off-by-one errors
- [ ] Consistent return value types
- [ ] **All `await` calls are inside `async def` functions** — not just handlers, but also utility methods, service classes, builders
- [ ] Async functions correctly use `await`

### 3. Security

- [ ] **No command injection**: No `os.system()` or `subprocess.call(shell=True)` with untrusted input
- [ ] **No hardcoded secrets**: API keys, passwords read from config
- [ ] **No unsafe deserialization**: No `pickle.loads()` on untrusted data
- [ ] **No SQL injection**: Use parameterized queries
- [ ] **No unsafe eval/exec**: No `eval()` on user input
- [ ] **No unsafe path joining**: Use `pathlib.Path` or `os.path.join()`

### 4. Maintainability

- [ ] Functions have single responsibility
- [ ] Classes have clear purpose
- [ ] Docstrings on public methods
- [ ] All `@filter.command` methods have docstrings (AstrBot shows them in WebUI)
- [ ] Complex logic has comments

### 5. Potential Defects

- [ ] **Exception handling**: Network calls, file ops wrapped in try/except
- [ ] **Resource leaks**: File handles, connections closed (or use `async with`)
- [ ] **Performance**: No unnecessary large loops, no redundant computation
- [ ] **Concurrency safety**: Shared state protected by locks if needed

## AstrBot Framework Checks

### Logging

- [ ] Uses `from astrbot.api import logger`
- [ ] Does NOT use `loguru`, `logging.getLogger()`, or other logging libraries
- [ ] **Import path must match reference table in `review/main-file-checklist.md` §1**

### Concurrency

- [ ] Network I/O uses async libraries (`aiohttp`, `httpx`)
- [ ] No sync network calls (`requests.get()`) in async context
- [ ] File I/O may use sync (AstrBot does not require async file I/O)

### Data Persistence

- [ ] Uses `StarTools.get_data_dir()` for data directory (returns `Path`)
- [ ] `StarTools.get_data_dir()` is called from a `Star` subclass (not from Service/Manager classes)
- [ ] No hardcoded file paths
- [ ] Data path is `data/plugin_data/<plugin_name>/`

### Namespace Safety

- [ ] No generic package names (`services`, `models`, `utils`, `pages`) without `sys.path.insert(0, os.path.dirname(__file__))` in main.py
- [ ] All sub-package imports resolve to the correct plugin's directory

### Error Handling

- [ ] Catches specific exceptions, not bare `except:`
- [ ] Exception messages include sufficient context
- [ ] Exceptions are not silently swallowed (at least log them)

### Dependency & Import Stability

- [ ] All import paths match the reference table in `review/main-file-checklist.md` §1
- [ ] Every third-party import has a corresponding entry in `requirements.txt`
- [ ] `requirements.txt` does NOT include `astrbot` or `quart` (already provided by AstrBot)
- [ ] No `from astrbot.api.logger import logger` — must be `from astrbot.api import logger`
- [ ] No `from astrbot.api import filter` — must be `from astrbot.api.event import filter`
- [ ] No `from astrbot.api import Star` — must be `from astrbot.api.star import Star`
- [ ] External HTTP calls use async libraries with explicit timeouts
- [ ] Resources (sessions, connections) cleaned up in `terminate()`

### Modular Structure (for plugins > 200 lines)

See `references/modular-split.md` for the full guide.

- [ ] main.py > 200 lines? Consider splitting into modules
- [ ] Command handlers in separate `handlers/` files
- [ ] API clients in separate service classes
- [ ] Constants extracted to dedicated file
- [ ] No global variables for plugin state (use instance attributes)
- [ ] Handler functions receive `plugin` instance for state access
- [ ] `terminate()` cleans up resources from all extracted modules

### Platform Adapter Specific (if applicable)

See `platform_adapters/adapter_interface.md` § "config_metadata" for full rules.

- [ ] `default_config_tmpl` does NOT include `"enable"` — AstrBot manages this
- [ ] `default_config_tmpl` does NOT include `"id"` — AstrBot manages this
- [ ] All custom fields in `default_config_tmpl` have matching entries in `config_metadata`
- [ ] `config_metadata` entries have `description`, `type`, and `hint`
- [ ] `secret: True` used for API keys and tokens
- [ ] `invisible: True` used only for internal fields

### WebUI Plugin Pages (if applicable)

- [ ] Bridge API method is `onContext()`, NOT `onContextChange()`
- [ ] Bridge `endpoint` does NOT start with `/`, does NOT contain `..`
- [ ] Query params passed via `params` argument, not in endpoint string
- [ ] `self.text_to_image()` / `self.html_render()` called as Star methods (not SDK functions)
- [ ] SSE subscriptions cleaned up on page unload
- [ ] Security: no sensitive data in `localStorage` (iframe sandbox may restrict access)

### API Deprecation Checks

- [ ] `context.register_llm_tool()` NOT used — use `context.add_llm_tools()` instead
- [ ] `context.get_platform()` NOT used — use `context.get_platform_inst(platform_id)` (v4.0.0+)
- [ ] `@filter.llm_tool` docstring `Args:` follows `param_name(type): description` format

## File Priority for Review

When reviewing multiple files, prioritize:

1. `main.py` (highest)
2. Root-level `.py` files
3. Subdirectory `.py` files (shallowest first)

Max 15 files, token budget = 70% of model max input.

## Output Format

```markdown
### <file_path> Audit Result

| Dimension | Status | Issues |
|-----------|--------|--------|
| Code Quality | ✅ | 0 |
| Functional | ⚠️ | 1 |
| Security | ✅ | 0 |
| Maintainability | ✅ | 0 |
| Defects | ❌ | 2 |

**Details**:

1. ⚠️ [Functional] Line 23: `asyncio.sleep(0)` may cause infinite loop
2. ❌ [Defects] Line 45: Sync `requests.get()` blocks event loop → use `aiohttp`
3. ❌ [Defects] Line 67: File handle not closed → use `with open(...)`
```
