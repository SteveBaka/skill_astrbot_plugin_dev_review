# Auto-Fix Guide

This guide covers the most common AstrBot plugin issues and their automatic fix patterns.

## Fix Priority

1. 🔴 **CRITICAL** — Must fix, plugin will crash or malfunction
2. 🟡 **WARNING** — Strongly recommended to fix
3. 🔵 **INFO** — Optional improvement

---

## 🔴 Critical Fixes

### FIX-00: Wrong Import Path

**Problem**: LLMs hallucinate incorrect AstrBot import paths, or use wrong libraries (loguru, logging). See `review/main-file-checklist.md` §1 for the full reference table.

```python
# ❌ WRONG — astrbot.api.logger does not exist
from astrbot.api.logger import logger
# ✅ CORRECT
from astrbot.api import logger

# ❌ WRONG — filter is not directly under astrbot.api
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

# ❌ WRONG — using loguru or logging
from loguru import logger
import logging
logger = logging.getLogger(__name__)
# ✅ CORRECT
from astrbot.api import logger
```

### FIX-01: Star Subclass Missing super().__init__

```python
# ❌ WRONG
class MyPlugin(Star):
    def __init__(self, context: Context):
        self.context = context

# ✅ FIX
class MyPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)
```

### FIX-02: Handler Signature Errors

**Problem**: Handler missing `async`, missing `event` parameter, or using function parameters for user input.

```python
# ❌ WRONG — missing async
@filter.command("hello")
def hello(self, event: AstrMessageEvent):
    yield event.plain_result("Hello")

# ❌ WRONG — missing event parameter
@filter.command("hello")
async def hello(self):
    yield event.plain_result("Hello")

# ❌ WRONG — function parameter causes "got multiple values" error
@filter.command("weather")
async def weather(self, event: AstrMessageEvent, city: str = ""):
    result = await fetch_weather(city)
    yield event.plain_result(result)

# ✅ FIX — async + event + event.message_str
@filter.command("weather")
async def weather(self, event: AstrMessageEvent):
    city = event.message_str.strip()
    if not city:
        yield event.plain_result("Usage: /weather <city>")
        return
    result = await fetch_weather(city)
    yield event.plain_result(result)
```

### FIX-03: LLM Hook Signature Error

**Problem**: `on_llm_request`/`on_llm_response` has wrong parameter count, or using `yield` in hooks.

```python
# ❌ WRONG — missing req parameter
@filter.on_llm_request()
async def on_req(self, event):
    pass

# ❌ WRONG — yield in hook (must use event.send())
@filter.on_llm_request()
async def on_req(self, event, req):
    yield event.plain_result("test")

# ✅ FIX
@filter.on_llm_request()
async def on_req(self, event: AstrMessageEvent, req: ProviderRequest):
    await event.send(event.plain_result("test"))
```

### FIX-04: Synchronous Network Call

```python
# ❌ WRONG
import requests
resp = requests.get(url)

# ✅ FIX
import aiohttp
async with aiohttp.ClientSession() as session:
    async with session.get(url) as resp:
        data = await resp.json()
```

### FIX-05: @filter.permission_type + @filter.llm_tool

```python
# ❌ WRONG
@filter.llm_tool("my_tool")
@filter.permission_type(filter.PermissionType.ADMIN)
async def my_tool(self, ...):
    pass

# ✅ FIX — remove permission_type
@filter.llm_tool("my_tool")
async def my_tool(self, ...):
    pass
```

### FIX-06: Platform Adapter Built-in Field Conflict

**Problem**: Including `"enable"` or `"id"` in `default_config_tmpl` causes WebUI rendering issues.

```python
# ❌ WRONG
@register_platform_adapter("my_adapter", "My Adapter",
    default_config_tmpl={"id": "my_adapter", "enable": True, "api_key": ""},
)

# ✅ FIX — only custom fields
@register_platform_adapter("my_adapter", "My Adapter",
    default_config_tmpl={"api_key": ""},
    config_metadata={"api_key": {"description": "API Key", "type": "string", "hint": "Your API key", "secret": True}},
)
```

### FIX-07: ToolExecResult Python 3.12 Incompatibility

**Problem**: `ToolExecResult(result=...)` causes `TypeError: 'types.UnionType' object is not callable` in Python 3.12.

```python
# ❌ WRONG
from astrbot.core.agent.tool import FunctionTool, ToolExecResult
async def call(self, context, **kwargs) -> ToolExecResult:
    return ToolExecResult(result="text")

# ✅ FIX — return string directly
from astrbot.core.agent.tool import FunctionTool
async def call(self, context, **kwargs) -> str:
    return "text"
```

---

## 🟡 Warnings

### FIX-08: Hardcoded Secrets

```python
# ❌ WRONG
api_key = "sk-xxxx"

# ✅ FIX — read from config
api_key = self.config.get("api_key")
```

### FIX-09: Hardcoded File Paths

```python
# ❌ WRONG
data_path = "/tmp/my_plugin_data"

# ✅ FIX
from astrbot.api.star import StarTools
data_path = StarTools.get_data_dir()  # Path object
```

### FIX-10: Unhandled Exceptions

```python
# ❌ WRONG
async def fetch_data(self, url):
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            return await resp.json()

# ✅ FIX
async def fetch_data(self, url):
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                return await resp.json()
    except aiohttp.ClientError as e:
        logger.error(f"Request failed: {e}")
        return None
```

### FIX-11: Resource Leak

```python
# ❌ WRONG
f = open("file.txt")
data = f.read()

# ✅ FIX
with open("file.txt") as f:
    data = f.read()
```

### FIX-12: Missing terminate() Cleanup

```python
async def terminate(self):
    if hasattr(self, 'task') and self.task:
        self.task.cancel()
    if hasattr(self, 'session') and self.session:
        await self.session.close()
```

### FIX-13: Deprecated register_llm_tool()

```python
# ❌ WRONG
self.context.register_llm_tool(my_tool)

# ✅ FIX
self.context.add_llm_tools(my_tool)
```

### FIX-14: command_group as Class

```python
# ❌ WRONG
@filter.command_group("manage")
class ManageCommands:
    @manage.command("list")
    async def list_items(self, event):
        pass

# ✅ FIX
@filter.command_group("math")
def math():
    pass

@math.command("add")
async def add(self, event: AstrMessageEvent, a: int, b: int):
    yield event.plain_result(f"{a + b}")
```

### FIX-15: @filter.llm_tool Args Format

```python
# ❌ WRONG — missing type in Args
@filter.llm_tool(name="get_weather")
async def get_weather(self, event, location: str):
    """Get weather.
    Args:
        location: The city
    """

# ✅ FIX — Args must be param_name(type): description
@filter.llm_tool(name="get_weather")
async def get_weather(self, event, location: str):
    """Get weather.

    Args:
        location(string): The city name
    """
```

### FIX-16: Bridge API Errors

```javascript
// ❌ WRONG — method name does not exist
bridge.onContextChange(handler)

// ✅ FIX
bridge.onContext(handler)

// ❌ WRONG — endpoint violations
await bridge.apiGet("/stats")        // starts with /
await bridge.apiGet("../stats")      // contains ..
await bridge.apiGet("stats?limit=20") // query in endpoint

// ✅ FIX
await bridge.apiGet("stats", { limit: 20 })
```

---

## 🔵 Suggestions

### FIX-17: Missing Docstring

```python
@filter.command("hello")
async def hello(self, event: AstrMessageEvent):
    """Send a greeting to the user."""
    yield event.plain_result("Hello!")
```

### FIX-18: Magic Numbers

```python
# ❌ WRONG
if retry > 3:
    pass

# ✅ FIX
MAX_RETRY = 3
if retry > MAX_RETRY:
    pass
```

### FIX-19: Missing Type Hints

```python
# ❌ WRONG
async def process(self, data):
    return data

# ✅ FIX
async def process(self, data: dict) -> dict:
    return data
```

### FIX-20: Pydantic @dataclass Mutable Default Value

**Problem**: `ValueError: mutable default <class 'dict'> for field parameters is not allowed: use default_factory`. Python dataclasses (and pydantic) forbid mutable objects as direct field defaults because all instances would share the same reference.

```python
# ❌ WRONG — dict literal as default value
@dataclass
class MyTool(FunctionTool[AstrAgentContext]):
    parameters: dict = {"type": "object", "properties": {...}}

# ✅ FIX — use field(default_factory=...)
from dataclasses import field

@dataclass
class MyTool(FunctionTool[AstrAgentContext]):
    parameters: dict = field(default_factory=lambda: {
        "type": "object",
        "properties": {
            "city": {"type": "string", "description": "City name"}
        },
        "required": ["city"]
    })
```

**Rule**: In `@dataclass` classes, dict/list fields MUST use `field(default_factory=lambda: {...})`, not direct dict/list literals.

### FIX-21: Deprecated filter Decorators (on_keyword, on_full_match, on_regex)

**Problem**: `AttributeError: module 'astrbot.api.event.filter' has no attribute 'on_keyword'`. These decorators were removed in AstrBot v4.x. The current filter module only provides: `command`, `command_group`, `event_message_type`, `platform_adapter_type`, `permission_type`, `on_llm_request`, `on_llm_response`, `on_decorating_result`, `after_message_sent`, `on_waiting_llm_request`, `on_agent_begin`, `on_agent_done`, `on_using_llm_tool`, `on_llm_tool_respond`.

```python
# ❌ WRONG — removed in v4.x
@filter.on_keyword("你好")
async def on_hello(self, event):
    yield event.plain_result("你好！")

@filter.on_full_match("ping")
async def on_ping(self, event):
    yield event.plain_result("pong")

@filter.on_regex(r"^查询\s+(.+)$")
async def on_query(self, event, match):
    yield event.plain_result(f"查询: {match.group(1)}")

# ✅ FIX — use event_message_type + Python string matching
@filter.event_message_type(filter.EventMessageType.ALL)
async def on_message(self, event: AstrMessageEvent):
    text = event.message_str.strip()
    if text.lower() in ["你好", "hello", "hi"]:
        yield event.plain_result("你好！")
        return
    if text == "ping":
        yield event.plain_result("pong")
        return
    match = re.match(r"^查询\s+(.+)$", text)
    if match:
        yield event.plain_result(f"查询: {match.group(1)}")
```

### FIX-22: self.config AttributeError

**Problem**: `'DemoPlugin' object has no attribute 'config'`. AstrBot only injects config when `__init__` declares the `config: AstrBotConfig` parameter.

```python
# ❌ WRONG — no config parameter, self.config doesn't exist
class MyPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)
    async def hello(self, event):
        api_key = self.config.get("api_key")  # AttributeError!

# ✅ FIX — declare config parameter
from astrbot.api import AstrBotConfig

class MyPlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.config = config
    async def hello(self, event):
        api_key = self.config.get("api_key")  # Works
```

### FIX-23: Unused Imports

**Problem**: LLMs often generate imports that are never used (e.g., `import json`, `from typing import Any`). This wastes tokens and reduces code clarity.

```python
# ❌ WRONG — json and Any are never used
import json
import re
from typing import Any
from astrbot.api import logger

# ✅ FIX — remove unused imports
import re
from astrbot.api import logger
```

**Rule**: Every `import X` / `from X import Y` must be referenced at least once in the file. Remove all unused imports before review.

### FIX-24: Duplicate Code

**Problem**: LLMs may define the same data (e.g., joke list, API URLs) in multiple places instead of extracting to a shared constant.

```python
# ❌ WRONG — same joke list defined twice
class JokeTool(FunctionTool):
    async def call(self, context, **kwargs) -> str:
        jokes = ["Why did the chicken...", "What do you call..."]
        return random.choice(jokes)

@filter.command("joke")
async def joke_cmd(self, event):
    jokes = ["Why did the chicken...", "What do you call..."]
    yield event.plain_result(random.choice(jokes))

# ✅ FIX — extract shared constant
JOKES = ["Why did the chicken...", "What do you call..."]

class JokeTool(FunctionTool):
    async def call(self, context, **kwargs) -> str:
        return random.choice(JOKES)

@filter.command("joke")
async def joke_cmd(self, event):
    yield event.plain_result(random.choice(JOKES))
```

### FIX-25: Dead Code (Unused Variables/Lists)

**Problem**: LLMs may define API endpoint lists or variables that are never referenced.

```python
# ❌ WRONG — apis[1] is never used
apis = [
    "https://api.example.com/v1",
    "https://api.example.com/v2",  # Dead code
]
resp = await fetch(apis[0])

# ✅ FIX — remove unused entries
api_url = "https://api.example.com/v1"
resp = await fetch(api_url)
```

---

## Verification

After each fix, re-run the full audit from `review/review-workflow.md`:
1. Original issue is resolved
2. No new issues introduced
3. Audit conclusion is ✅ PASS
