# AstrBot Plugin Development Best Practices

## 1. Exception Handling

Always catch exceptions and provide clear feedback to users:

```python
try:
    # Business logic
except TimeoutError:
    yield event.plain_result("会话已超时，请重新开始。")
except Exception as e:
    logger.error(f"插件执行出错: {e}")
    yield event.plain_result(f"发生错误: {e}")
finally:
    event.stop_event()
```

## 2. Platform Differences

When calling underlying SDKs, check the platform:

```python
if event.get_platform_name() == "aiocqhttp":
    # OneBot-specific API
    pass
```

## 3. Tool Development

- Recommend the `agent-as-tool` pattern
- Write thorough docstrings (determines how the LLM understands the tool)
- Keep tool functionality focused and single-purpose

## 4. Resource Cleanup

Clean up timers, database connections, and file handles in `terminate()`:

```python
async def terminate(self):
    if self.scheduler:
        self.scheduler.shutdown(wait=False)
    if self.db_conn:
        await self.db_conn.close()
```

## 5. Async Conventions

- All handlers/hooks use `async def`
- Use async libraries for network I/O (`aiohttp`, `httpx`)
- Synchronous file I/O is acceptable (AstrBot does not require async file I/O)
- Do not use `time.sleep()` in handlers; use `asyncio.sleep()`

## 6. Logging Conventions

```python
from astrbot.api import logger

logger.info("信息")
logger.warning("警告")
logger.error("错误")
logger.debug("调试")
```

**Do not** use `loguru`, `logging.getLogger()`, or other logging libraries.

## 7. Security Conventions

- Do not hardcode API keys or sensitive information; use `_conf_schema.json` configuration
- Do not use `pickle.loads()` to deserialize untrusted data
- Do not use `os.system()` or `subprocess.call(shell=True)` with untrusted input
- Escape user input before embedding into HTML/SQL

## 8. Code Organization

- `main.py` focuses on entry point and orchestration; extract complex logic into submodules
- Keep functions short with single responsibility
- Add type hints for public methods
- List all third-party dependencies in requirements.txt

## 9. Configuration Design

- Expose API keys, feature toggles, thresholds, etc. through `_conf_schema.json`
- Do not hardcode provider IDs or platform-specific IDs
- Provide reasonable default values for configuration items

## 10. Plugin Size

- Keep plugins under 32MB
- Use CDNs for large resources (high-resolution images, etc.)
- Do not package large data files inside the plugin

## 11. Code Formatting & Dev Principles

From official AstrBot dev principles (`star/plugin-new.md`):

- Use [ruff](https://docs.astral.sh/ruff/) to format code before submission
- All features must be tested before release
- Include good comments
- Store persistent data in `data/` directory, NOT in the plugin directory (prevents data loss on reinstall)
- Do NOT use `requests` for network requests — use `aiohttp` or `httpx` (async)
- If extending another plugin's functionality, prefer submitting a PR to the original plugin rather than creating a new one
- Implement robust error handling — don't let a single error crash the plugin

## 12. Plugin Naming

From `star/plugin-new.md`:

- Start with `astrbot_plugin_`
- Lowercase only
- No spaces
- Concise

## 13. Skills Bundling

Plugins can provide a `skills/` directory. After AstrBot loads the plugin, valid Skills are auto-registered:

```
your_plugin/
  skills/
    web-search-helper/
      SKILL.md
    report-writer/
      SKILL.md
```

Or if `skills/` itself is one Skill:

```
your_plugin/
  skills/
    SKILL.md
```

## 14. StarTools.get_data_dir() Context Restriction

`StarTools.get_data_dir()` uses the call stack to infer the plugin name. It **MUST be called from a `Star` subclass context** (e.g., the plugin's `__init__`). Non-Star classes (Service, Manager, etc.) cannot call it directly.

```python
# ✅ CORRECT — call in Star subclass, pass to other components
class MyPlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.config = config
        data_dir = StarTools.get_data_dir()
        self.storage = StorageManager(data_dir)

class StorageManager:
    def __init__(self, data_dir: Path):  # Accept as parameter
        self._data_dir = data_dir
```

```python
# ❌ WRONG — calling from non-Star class
class StorageManager:
    def __init__(self):
        self._data_dir = StarTools.get_data_dir()  # RuntimeError!
```

## 15. Avoid Generic Package Names

In a multi-plugin environment, AstrBot adds all plugin directories to `sys.path`. Using generic names like `services`, `models`, `utils`, `pages` causes namespace collisions with other plugins.

```python
# ❌ WRONG — absolute import with generic name
from services.persona_manager import PersonaManager  # May find another plugin's services/!

# ✅ FIX — use plugin-specific prefix or sys.path.insert
# Option 1: Prefix your package name
from my_plugin_services.persona_manager import PersonaManager

# Option 2: Add plugin dir to sys.path in main.py
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from services.persona_manager import PersonaManager  # Now finds YOUR services/
```

**Rule**: If using sub-packages (handlers/, services/, etc.), add `sys.path.insert(0, os.path.dirname(__file__))` at the top of `main.py` before any relative imports. Or use plugin-prefixed package names.

## 16. Sync Code to Runtime Environment

AstrBot loads plugins from the **installation directory**, not the working directory. After modifying code locally, ensure the changes are synced to where AstrBot reads them. Use WebUI "Reload Plugin" or restart AstrBot.

**Checklist**:
- [ ] Code changes are in the directory AstrBot loads from
- [ ] No stale `.pyc` or `__pycache__` from old versions
- [ ] All imports match the current module exports (no stale variable names after refactoring)
