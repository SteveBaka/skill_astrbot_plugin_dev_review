# When and How to Split main.py

This guide helps you decide when main.py is too large and how to split it into clean modules.

## Decision: Should You Split?

| main.py Size | Recommendation |
|-------------|----------------|
| < 100 lines | Keep as-is. Single file is fine. |
| 100-200 lines | Consider extracting constants and config. |
| 200-500 lines | **Recommended**: split handlers into separate files. |
| > 500 lines | **Strongly recommended**: full modular split. |

> **Exception**: If your plugin only has 1-2 commands and no complex state, a 300-line main.py is acceptable.

## Recommended Split Structure

```
my_plugin/
├── main.py              # Star subclass, lifecycle, hooks, command routing
├── core/
│   ├── config.py        # Config wrapper with typed getters
│   └── constants.py     # Static data (lists, enums, patterns)
├── handlers/
│   ├── group_a.py       # Related commands (e.g. tts_on, tts_off)
│   ├── group_b.py       # Related commands (e.g. speed, pitch)
│   └── group_c.py       # Related commands (e.g. voice, voiceclone)
└── services/
    └── api_client.py    # External API client with async close()
```

## What Stays in main.py

main.py keeps **only** these responsibilities:

1. **Star subclass** — class definition and `__init__`
2. **Lifecycle** — `initialize()`, `terminate()`
3. **Hooks** — `on_decorating_result()`, `on_llm_request()`, etc.
4. **Command routing** — thin `@filter.command` methods that delegate to handlers
5. **Shared state accessors** — helper methods used by multiple handlers

## What Gets Extracted

| Module | Contains | Pattern |
|--------|----------|---------|
| `handlers/*.py` | Command implementations | Pure async functions receiving `plugin` + `event` |
| `core/config.py` | Config wrapper | Class with typed getters |
| `core/constants.py` | Static data | Python constants |
| `services/*.py` | External API clients | Async classes with `close()` |

## Split Pattern: Handler Delegation

The key pattern: **thin command methods delegate to handler functions**.

```python
# main.py
from .handlers.group_a import handle_speed

class MyPlugin(Star):
    @filter.command("speed")
    async def cmd_speed(self, event: AstrMessageEvent):
        async for item in handle_speed(self, event):
            yield item
```

```python
# handlers/group_a.py
async def handle_speed(plugin, event: AstrMessageEvent):
    """Handler receives the plugin instance for state access."""
    uid = plugin._get_user_id(event)
    # ... implementation ...
    yield event.plain_result("done")
```

**Why this works**:
- Handler is a plain async generator (testable independently)
- `plugin` parameter gives access to state without global variables
- `yield` in handler → `yield` in command method (streaming compatible)

## Split Pattern: External Service Class

For API clients or complex external integrations:

```python
# services/api_client.py
class APIClient:
    def __init__(self, api_key, base_url):
        self._session = aiohttp.ClientSession(...)

    async def fetch(self, ...) -> bytes:
        ...

    async def close(self):
        await self._session.close()
```

```python
# main.py
class MyPlugin(Star):
    def __init__(self, context):
        super().__init__(context)
        self._client = None

    def _ensure_client(self):
        if self._client is None:
            self._client = APIClient(...)
        return self._client

    async def terminate(self):
        if self._client:
            await self._client.close()
```

## Split Pattern: Constants Extraction

```python
# core/constants.py
VOICE_LIST = [{"id": "default", "name": "Default"}, ...]
SUPPORTED_FORMATS = {"wav", "mp3", "ogg"}
SKIP_PATTERNS = [r"^[\s]*$", r"^[/!！]", ...]
```

```python
# main.py
from .core.constants import VOICE_LIST, SKIP_PATTERNS
```

## Anti-Patterns to Avoid

### ❌ Don't: Inline all handler logic in main.py

```python
# BAD — main.py becomes 1000+ lines
@filter.command("speed")
async def cmd_speed(self, event):
    # 50 lines of logic here
    ...

@filter.command("pitch")
async def cmd_pitch(self, event):
    # 50 lines of logic here
    ...
```

### ❌ Don't: Use global variables for state

```python
# BAD — state leaks between instances
_user_settings = {}

class MyPlugin(Star):
    def __init__(self, context):
        global _user_settings
        _user_settings = {}
```

### ✅ Do: Keep state on the plugin instance

```python
class MyPlugin(Star):
    def __init__(self, context):
        super().__init__(context)
        self._user_settings = {}
```

### ❌ Don't: Forget to clean up extracted resources

```python
# BAD — session leaks on unload
class MyPlugin(Star):
    def __init__(self, context):
        self._session = aiohttp.ClientSession()
```

### ✅ Do: Implement terminate() for all resources

```python
class MyPlugin(Star):
    async def terminate(self):
        if self._session:
            await self._session.close()
```

## Review Checklist

When reviewing a plugin:

- [ ] If main.py > 200 lines, is it split into modules?
- [ ] Each handler file contains related handlers only
- [ ] External API clients are in separate service classes
- [ ] Constants are extracted to a dedicated file
- [ ] `terminate()` cleans up resources from all modules
- [ ] No global variables for plugin state
- [ ] Handler functions receive `plugin` instance, not global state
- [ ] **All import paths are correct after splitting** (see below)

## Post-Split Import Verification

After splitting main.py into modules, **every import path must be verified**. Common mistakes:

```python
# ❌ WRONG — normalize_tts_mode was moved to tts/synthesis.py, not core/user_state.py
from .core.user_state import normalize_tts_mode

# ✅ CORRECT
from .tts.synthesis import normalize_tts_mode
```

**Rule**: After each split operation, scan all `.py` files for `from .X import Y` and verify that `Y` actually exists in module `X`. If a function was moved to a different module than originally planned, update all import references.

**Checklist**:
- [ ] Every `from .module import symbol` references a file that exists
- [ ] Every imported symbol is actually defined in the target file
- [ ] No circular imports between split modules
- [ ] main.py still imports everything it needs from the new modules
