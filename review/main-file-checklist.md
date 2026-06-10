# main.py Review Checklist (Priority)

This file defines review rules specific to main.py. **These rules take priority over general review.**

## 1. Import Syntax Validation

Every AstrBot import path must be **exact**. LLMs frequently hallucinate plausible-looking but wrong module paths (e.g., `from astrbot.api.logger import logger`). **Verify every import line.**

### Correct Import Reference Table

| Symbol | Correct Import | Common WRONG Import |
|--------|---------------|---------------------|
| `logger` | `from astrbot.api import logger` | `from astrbot.api.logger import logger` |
| `filter` | `from astrbot.api.event import filter` | `from astrbot.api import filter` |
| `AstrMessageEvent` | `from astrbot.api.event import AstrMessageEvent` | `from astrbot.api import AstrMessageEvent` |
| `Star` | `from astrbot.api.star import Star` | `from astrbot.api import Star` |
| `Context` | `from astrbot.api.star import Context` | `from astrbot.api import Context` |
| `StarTools` | `from astrbot.api.star import StarTools` | `from astrbot.api import StarTools` |
| `register` | `from astrbot.api.star import register` | DEPRECATED — use `metadata.yaml` instead |
| `ProviderRequest` | `from astrbot.api.provider import ProviderRequest` | `from astrbot.api import ProviderRequest` |
| `LLMResponse` | `from astrbot.api.provider import LLMResponse` | `from astrbot.api import LLMResponse` |
| `Comp` | `from astrbot.api.message_components import Comp` | `from astrbot.api import Comp` |
| `MessageChain` | `from astrbot.api.event import MessageChain` | `from astrbot.api import MessageChain` |
| `session_waiter` | `from astrbot.core.utils.session_waiter import session_waiter` | `from astrbot.api import session_waiter` |
| `SessionController` | `from astrbot.core.utils.session_waiter import SessionController` | — |
| `FunctionTool` | `from astrbot.core.agent.tool import FunctionTool` | `from astrbot.api import FunctionTool` |
| `ToolExecResult` | `from astrbot.core.agent.tool import ToolExecResult` | **AVOID** — return `str` instead (Python 3.12 issue) |
| `ToolSet` | `from astrbot.core.agent.tool import ToolSet` | — |
| `AstrBotConfig` | `from astrbot.api import AstrBotConfig` | — |
| `BaseAgentRunHooks` | `from astrbot.core.agent.hooks import BaseAgentRunHooks` | — |
| `ContextWrapper` | `from astrbot.core.agent.run_context import ContextWrapper` | — |
| `AstrAgentContext` | `from astrbot.core.astr_agent_context import AstrAgentContext` | — |
| `Plain` | `from astrbot.api.message_components import Plain` | `from astrbot.api import Plain` |
| `Image` | `from astrbot.api.message_components import Image` | `from astrbot.api import Image` |
| `At` | `from astrbot.api.message_components import At` | — |
| `Record` | `from astrbot.api.message_components import Record` | — |
| `Video` | `from astrbot.api.message_components import Video` | — |
| `Platform` | `from astrbot.api.platform import Platform` | `from astrbot.api import Platform` |
| `PlatformMetadata` | `from astrbot.api.platform import PlatformMetadata` | — |
| `AstrBotMessage` | `from astrbot.api.platform import AstrBotMessage` | — |
| `MessageMember` | `from astrbot.api.platform import MessageMember` | — |
| `MessageType` | `from astrbot.api.platform import MessageType` | — |
| `register_platform_adapter` | `from astrbot.core.platform.register import register_platform_adapter` | — |
| `MessageSession` | `from astrbot.core.platform.astr_message_event import MessageSesion` | — |

> **Note**: AstrBot uses the typo `MessageSesion` (one 's') in its actual codebase. Use exactly that spelling.

### Alternative Import Style (Also Valid)

The real plugin `astrbot_plugin_synochat_adapter` uses this pattern in main.py:

```python
from astrbot.api import star

class Main(star.Star):
    def __init__(self, context: star.Context):
        super().__init__(context)
```

This is **also valid** — importing the module and using `module.Class`. Both styles work:

```python
# Style A — import symbols directly (recommended for readability)
from astrbot.api.star import Context, Star

# Style B — import module, use qualified names
from astrbot.api import star
# then use star.Star, star.Context
```

### Audit Rules

- [ ] Every `from astrbot.api.X import Y` must be checked against the table above
- [ ] `logger` must be `from astrbot.api import logger` — **NOT** `from astrbot.api.logger import logger`
- [ ] `filter` must be `from astrbot.api.event import filter` — **NOT** `from astrbot.api import filter`
- [ ] `Star` / `Context` must be `from astrbot.api.star import ...` — **NOT** `from astrbot.api import ...`
- [ ] No third-party loggers (`loguru`, `logging.getLogger()`)

### Common Import Mistakes (Real Bugs)

```python
# ❌ WRONG — AstrBot has no astrbot.api.logger module
from astrbot.api.logger import logger

# ✅ CORRECT
from astrbot.api import logger

# ❌ WRONG — filter is under astrbot.api.event, not astrbot.api
from astrbot.api import filter

# ✅ CORRECT
from astrbot.api.event import filter, AstrMessageEvent

# ❌ WRONG — Star/Context are under astrbot.api.star
from astrbot.api import Star, Context

# ✅ CORRECT
from astrbot.api.star import Context, Star

# ❌ WRONG — ProviderRequest is under astrbot.api.provider
from astrbot.api import ProviderRequest

# ✅ CORRECT
from astrbot.api.provider import ProviderRequest, LLMResponse

# ❌ WRONG — session_waiter is under astrbot.core.utils
from astrbot.api import session_waiter

# ✅ CORRECT
from astrbot.core.utils.session_waiter import session_waiter, SessionController
```

## 2. Plugin Registration & Main Class

- [ ] File MUST contain a class inheriting from `Star`
- [ ] `__init__` MUST accept `context: Context`
- [ ] `__init__` MUST call `super().__init__(context)`
- [ ] If plugin uses config, `__init__` MUST also accept `config: AstrBotConfig` and call `self.config = config`

```python
# ✅ CORRECT — with config
from astrbot.api import AstrBotConfig

class MyPlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.config = config

# ✅ CORRECT — without config
class MyPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)

# ❌ WRONG — missing super().__init__(context)
class MyPlugin(Star):
    def __init__(self, context: Context):
        self.context = context

# ❌ WRONG — wrong base class
class MyPlugin:
    def __init__(self, context):
        pass
```

## 3. LLM Hook Signatures

- [ ] `on_llm_request` / `on_llm_response` MUST be `async def`
- [ ] MUST accept exactly 3 params: `self, event: AstrMessageEvent, req/resp`
- [ ] These 4 hooks MUST NOT use `yield` — use `event.send()` instead

```python
# ✅ CORRECT
@filter.on_llm_request()
async def on_llm_req(self, event: AstrMessageEvent, req: ProviderRequest):
    req.system_prompt += "\nExtra instruction"

# ❌ WRONG — missing req parameter
@filter.on_llm_request()
async def on_llm_req(self, event):
    pass

# ❌ WRONG — not async
@filter.on_llm_request()
def on_llm_req(self, event, req):
    pass

# ❌ WRONG — yield in hook
@filter.on_llm_request()
async def on_llm_req(self, event, req):
    yield event.plain_result("test")
```

## 4. Event Listener Signatures

- [ ] All `@filter`-decorated methods MUST include `event` parameter (except `on_astrbot_loaded`)
- [ ] Handler methods MUST be `async def`
- [ ] All `@filter.command` methods MUST have a docstring — AstrBot displays it in the WebUI as the command description
- [ ] **Do NOT use function parameters for command user input** — AstrBot's parameter binding may cause `got multiple values for argument` errors. Use `event.message_str.strip()` instead.

```python
# ✅ CORRECT — use event.message_str for user input
@filter.command("weather")
async def weather(self, event: AstrMessageEvent):
    """Query weather for a city."""
    city = event.message_str.strip()
    if not city:
        yield event.plain_result("Usage: /weather <city>")
        return
    result = await fetch_weather(city)
    yield event.plain_result(result)

# ❌ WRONG — function parameter causes "got multiple values" error
@filter.command("weather")
async def weather(self, event: AstrMessageEvent, city: str = ""):
    """Query weather for a city."""
    result = await fetch_weather(city)
    yield event.plain_result(result)
```

> **Why**: AstrBot's `context_utils.py` parameter binding logic passes matched args through both positional and keyword arguments internally, causing `TypeError: got multiple values for argument 'city'` when the handler has a parameter with the same name. Always use `event.message_str` to get user input.

```python
# ✅ CORRECT
@filter.command("hello")
async def hello(self, event: AstrMessageEvent):
    """Send a greeting to the user."""
    yield event.plain_result("Hello!")

# ❌ WRONG — missing event
@filter.command("hello")
async def hello(self):
    yield event.plain_result("Hello!")

# ❌ WRONG — missing docstring (WebUI will show empty description)
@filter.command("hello")
async def hello(self, event: AstrMessageEvent):
    yield event.plain_result("Hello!")
    yield event.plain_result("Hello!")
```

## 5. @filter.llm_tool + @filter.permission_type

- [ ] `@filter.permission_type` CANNOT be used on `@filter.llm_tool` methods

```python
# ❌ WRONG — invalid combination
@filter.llm_tool("my_tool")
@filter.permission_type(filter.PermissionType.ADMIN)
async def my_tool(self, ...):
    pass
```

## 6. Message Sending in Hooks

These 4 hooks MUST NOT use `yield` — use `event.send()`:

- `on_llm_request`
- `on_llm_response`
- `on_decorating_result`
- `after_message_sent`

```python
# ✅ CORRECT
@filter.on_llm_request()
async def on_req(self, event: AstrMessageEvent, req: ProviderRequest):
    await event.send(event.plain_result("notification"))

# ❌ WRONG
@filter.on_llm_request()
async def on_req(self, event: AstrMessageEvent, req: ProviderRequest):
    yield event.plain_result("notification")
```

## 7. terminate() Method

- [ ] If plugin creates background tasks, connections, or timers, MUST clean up in `terminate()`
- [ ] `terminate()` MUST be `async def`

```python
async def terminate(self):
    if hasattr(self, 'scheduler'):
        self.scheduler.shutdown(wait=False)
```

## 8. Principle & API Correctness (from official docs)

<!-- Source: https://github.com/AstrBotDevs/AstrBot/blob/master/docs/en/dev/star/guides/listen-message-event.md -->
<!-- Source: https://github.com/AstrBotDevs/AstrBot/blob/master/docs/en/dev/star/guides/ai.md -->
<!-- Source: https://github.com/AstrBotDevs/AstrBot/blob/master/docs/en/dev/star/guides/plugin-pages.md -->

- [ ] `@filter.command_group` MUST use function pattern (`def math(): pass`), NOT a class
- [ ] `@filter.on_keyword`, `@filter.on_full_match`, `@filter.on_regex` are **REMOVED** in v4.x — use `@filter.event_message_type(filter.EventMessageType.ALL)` + Python string matching
- [ ] In `@dataclass` classes, dict/list fields MUST use `field(default_factory=lambda: {...})`, not direct dict/list literals
- [ ] `context.register_llm_tool()` is **DEPRECATED** — must use `context.add_llm_tools()`
- [ ] `@filter.llm_tool` decorator: `Args:` section in docstring MUST follow `param_name(type): description` format
- [ ] `Tool.call()` MUST return `str` directly — do NOT use `ToolExecResult` (Python 3.12 `|` union type causes `types.UnionType` not callable)
- [ ] `self.text_to_image()` and `self.html_render()` are **Star class methods**, not SDK functions
- [ ] Bridge API method is `onContext()`, NOT `onContextChange()`
- [ ] Bridge `endpoint` must NOT start with `/`, must NOT contain `..`, query params via `params` argument
- [ ] `session_waiter`: `record_history_chains` parameter controls history recording
- [ ] `system_prompt += ...` should only be used for stable long-term settings; use `extra_user_content_parts` for per-round dynamic content (breaks cache otherwise, costs 7-20x)

```python
# ❌ WRONG — command_group as class
@filter.command_group("manage")
class ManageCommands:
    @manage.command("list")
    async def list_items(self, event):
        pass

# ✅ CORRECT — command_group as function
@filter.command_group("math")
def math():
    pass

@math.command("add")
async def add(self, event: AstrMessageEvent, a: int, b: int):
    yield event.plain_result(f"{a + b}")
```

```python
# ❌ WRONG — deprecated API
self.context.register_llm_tool(my_tool)

# ✅ CORRECT
self.context.add_llm_tools(my_tool)
```

```python
# ❌ WRONG — Args format incorrect (will silently drop parameters)
@filter.llm_tool(name="get_weather")
async def get_weather(self, event, location: str):
    """Get weather.
    Args:
        location: The city
    """

# ✅ CORRECT — Args format: param_name(type): description
@filter.llm_tool(name="get_weather")
async def get_weather(self, event, location: str):
    """Get weather.

    Args:
        location(string): The city name
    """
```

## Audit Output Format

```markdown
### main.py Audit Result

| Check | Status | Line | Detail |
|-------|--------|------|--------|
| Import syntax | ✅ | 2 | Correct: `from astrbot.api import logger` |
| Star subclass | ✅ | 5 | Correct inheritance |
| super().__init__ | ✅ | 7 | Called correctly |
| filter import | ✅ | 2 | From astrbot.api.event |
| logger import | ⚠️ | 3 | Used logging.getLogger instead of astrbot.api |
| Event listener signature | ✅ | 14 | Contains event parameter |
| LLM hook signature | ❌ | 25 | on_llm_request missing req parameter |
| Message sending | ✅ | 30 | Uses event.send() |
| terminate | ✅ | 35 | Resources cleaned up |
```
