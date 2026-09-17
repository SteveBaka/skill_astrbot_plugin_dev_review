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

### FIX-02: Handler Signature Errors (incl. Command Arg Policy)

**Problem**: Handler missing `async`, missing `event`, **or** command arguments use a style that violates the **H1-B command arg policy** (official typed params are legal; models must not invent mixed/untyped free-text bindings).

**Runtime evidence (AstrBot 4.27.4, probe `astrbot_plugin_skill_probe` v0.2.0)**:
- `@filter.command` + `a: int, b: int` → works (`add=3`)
- `city: str = ""` → works when user supplies a token (`weather_city='Taipei'`); default applies when omitted
- `command_group` + typed ints → works
- Missing/wrong-type args → framework messages (`必要参数缺失` / `参数 a 类型错误`), **not** a crash
- `event.message_str` is the **full plaintext** (`skillprobe hello`), not args-only

**Policy (codegen models MUST follow — pick ONE style per command)**:

| Case | Required style | Review |
|------|----------------|--------|
| Numbers / flags / fixed schema | Annotated typed params: `a: int, b: int`, `flag: bool = False` | 🔵 info (allowed) |
| Free-text remainder (spaces, URLs) | **No extra params**; parse `event.message_str` after stripping command prefix | ✅ recommended |
| Untyped extras (`text`, `city`) | ❌ Annotate or use message_str remainder | 🟡 FIX-02 warning |
| Free-text `str` extras | Prefer message_str remainder; if typed, keep single-token semantics | 🟡 FIX-02 warning |
| Invented filters (`on_keyword`…) | Never — see FIX-21 | 🟡 / ❌ |

```python
# ❌ WRONG — missing async
@filter.command("hello")
def hello(self, event: AstrMessageEvent):
    yield event.plain_result("Hello")

# ❌ WRONG — missing event parameter
@filter.command("hello")
async def hello(self):
    yield event.plain_result("Hello")

# ❌ WRONG (policy) — untyped free-text extra; message_str is full plaintext
@filter.command("weather")
async def weather(self, event: AstrMessageEvent, city):
    result = await fetch_weather(city)
    yield event.plain_result(result)

# ✅ FIX A — structured numeric: official typed params (allowed ≥4.27.4)
@filter.command("add")
async def add(self, event: AstrMessageEvent, a: int, b: int):
    """Add two integers."""
    yield event.plain_result(f"{a + b}")

# ✅ FIX B — free-text remainder: strip command prefix from full message_str
@filter.command("weather")
async def weather(self, event: AstrMessageEvent):
    """Query weather for a city."""
    # message_str includes the command token, e.g. "weather Taipei"
    raw = event.message_str.strip()
    parts = raw.split(None, 1)
    city = parts[1].strip() if len(parts) > 1 else ""
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

### FIX-06: Platform Adapter Config Channel & Field Discipline

**Authority**: official `astrbot/core/platform/register.py` + `docs/en/dev/plugin-platform-adapter.md` (FakePlatform example).

**How core works** (do not fight this):

When `default_config_tmpl` is provided, `register_platform_adapter` **auto-fills** missing keys:

- `type` ← adapter name  
- `enable` ← `False` if absent  
- `id` ← adapter name if absent  

So authors should list **only custom** fields (token, base_url, …), same as the official FakePlatform sample. Telegram core adapter often omits tmpl entirely and reads `self.config` after core merge.

**Problems to avoid**:

1. **Redundant / conflicting `id` or `enable` in author tmpl or `config_metadata`** — core already manages them; re-declaring (especially in `config_metadata` with wrong hints) has caused WebUI enable-toggle layout bugs in the wild. Prefer **omit**; let core inject.  
2. **`_conf_schema.json` on an adapter package** — that is the **Star plugin** config channel (插件配置). Platform instances use **消息平台** + `default_config_tmpl` / `config_metadata` only.  
3. **Shadowing Platform runtime attrs** such as `self.client` / `self.event_queue` in ways that break the base class (prefer `_client`, private names). `Platform.__init__` already sets `self.config`.

```python
# ✅ CORRECT — official style (custom fields only; core adds type/enable/id)
@register_platform_adapter(
    "my_adapter",
    "My Adapter",
    default_config_tmpl={"api_key": "", "base_url": ""},
    config_metadata={
        "api_key": {"description": "API Key", "type": "string", "hint": "…", "secret": True},
        "base_url": {"description": "Service URL", "type": "string", "hint": "…"},
    },
)

# ❌ Avoid — do not re-list id/enable; do not add _conf_schema.json for adapters
default_config_tmpl={"id": "…", "enable": True, "api_key": ""}
```

**Reviewer** (`profile=adapter`): error if `_conf_schema.json` present; warning if tmpl/metadata redefines `id`/`enable`; error on risky `self.client` / `self.event_queue` stores.

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

> **v4.27.0 (#9468)**: the deprecation is now **formalized** — `Context.register_llm_tool`
> (and `unregister_llm_tool` / `register_commands` / `register_task`) carry an official
> `@deprecated` decorator and emit `DeprecationWarning` at call sites. Use
> `add_llm_tools()` (docs `guides/ai.md`, ≥ v4.5.1). <!-- Source: PR #9468 + guides/ai.md -->

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

### FIX-21: Unknown filter Attribute (Typo / Non-existent API)

**Problem**: `AttributeError: module 'astrbot.api.event.filter' has no attribute 'on_keyword'`.

**Provenance (repo-verified)**: `on_keyword` / `on_full_match` / `on_prefix` / `on_regex` **never existed** in AstrBot — absent from tag sources (v3.4.0 / v4.0.0 / v4.10.0 / master `astrbot/api/event/filter/__init__.py`), all 200+ changelogs, and PR history. Do not describe them as "removed in v4.x"; they are hallucinated/foreign API names. The reviewer flags ANY `filter.<attr>` not in the verified export surface (`contracts.FILTER_ATTR_KNOWN`), as a warning (AttributeError risk), not an error.

**Verified export surface** (v3.4.0 → master): `command`, `command_group`, `event_message_type`, `regex`, `platform_adapter_type`, `permission_type`, `custom_filter`, `llm_tool`, `after_message_sent`, `on_astrbot_loaded`, `on_llm_request`, `on_llm_response`, `on_decorating_result`, `on_waiting_llm_request`, `on_agent_begin`, `on_agent_done`, `on_using_llm_tool`, `on_llm_tool_respond`, `on_plugin_loaded`, `on_plugin_unloaded`, `on_plugin_error`, `on_platform_loaded` + classes `EventMessageType(-Filter)`, `PermissionType(-Filter)`, `PlatformAdapterType(-Filter)`, `CustomFilter`.

```python
# ❌ WRONG — this API never existed in AstrBot
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

**Exemptions (language/typing standards, not style)**: the checker never flags

- `from __future__ import ...` — language feature imports (PEP 563) bind no name and are never a runtime dependency;
- imports inside `if TYPE_CHECKING:` — type-checker-only imports (PEP 484) never execute at runtime and are intentional;
- names used only in string annotations (`x: "Foo"`, `Optional["Foo"]`) — PEP 484/563 forward references are real uses even though `"Foo"` is an `ast.Constant`, not a name load.

These mirror pyflakes/ruff F401 behavior and hold regardless of Python version or AstrBot release. A plain `if False:` guard is **not** exempt — only the canonical `if TYPE_CHECKING:` form.

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

### FIX-26: Namespace Collision (Generic Package Names)

**Problem**: plugins that split into sub-packages with generic names (`services`, `handlers`, `utils`, `models`, `core`, `api`, `common`) can collide with another plugin's same-named package.

**How AstrBot loads plugins** (`astrbot/core/star/star_manager.py`): each plugin is imported as a sub-package of the `data.plugins` namespace — `__import__("data.plugins.<plugin_dir>.<module>")`. So:

- **RELATIVE imports are safe by construction.** `from .core import x` resolves to `data.plugins.my_plugin.core`, isolated from every other plugin. This is the recommended style.
- **ABSOLUTE imports are the actual risk.** `from core import x` resolves against top-level `sys.path`; Python picks the first `core` it finds (another plugin's, or none → `ImportError`).

```python
# ❌ WRONG — absolute import resolves against top-level sys.path,
#   can hit another plugin's core/ (or fail with ImportError)
from core.persona_manager import PersonaManager

# ✅ FIX — use relative import; plugin lives under data.plugins.<name>
from .core.persona_manager import PersonaManager

# ⚠️ WORKAROUND (if absolute imports must stay, e.g. legacy code):
#   push your own plugin dir to the front so `from core ...` hits YOUR core
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
```

**Rule / review grading**:
- Generic sub-package(s) present + **absolute import** of a generic package + no `sys.path.insert` → **warning** (real collision risk).
- Generic sub-package(s) present + **only relative imports** + no `sys.path.insert` → **info** (defensive note; no action needed — keep relative imports).
- `sys.path.insert(...)` guard present → clean.

### FIX-27: StarTools.get_data_dir() Called Outside Star Subclass

**Problem**: `RuntimeError: 无法获取模块 xxx 的元数据信息`. `StarTools.get_data_dir()` uses the call stack to infer the plugin name — it must be called from within a `Star` subclass.

```python
# ❌ WRONG — called from non-Star class
class StorageManager:
    def __init__(self):
        self._data_dir = StarTools.get_data_dir()  # RuntimeError!

# ✅ FIX — call in Star subclass, pass as parameter
class MyPlugin(Star):
    def __init__(self, context, config):
        super().__init__(context)
        data_dir = StarTools.get_data_dir()
        self.storage = StorageManager(data_dir)

class StorageManager:
    def __init__(self, data_dir: Path):
        self._data_dir = data_dir
```

### FIX-28: Stale Imports After Refactoring

**Problem**: `ImportError: cannot import name 'xxx' from 'yyy'`. After refactoring a module (e.g., changing functions to classes), the importing file still references old names.

```python
# ❌ WRONG — emotion_engine.py was refactored, old variables no longer exist
from services.emotion_engine import emotion_engine, persona_simulator

# ✅ FIX — update imports to match current module exports
from services.emotion_engine import LightweightEmotionAnalyzer, EmotionEngine
```

**Rule**: After any refactoring, scan all files that import from the changed module and verify the imported names still exist.

### FIX-29: Missing async on Non-Handler Methods

**Problem**: `SyntaxError: 'await' outside async function`. A regular method (not a `@filter` handler) uses `await` but is missing `async`.

```python
# ❌ WRONG
class PromptBuilder:
    def build_context(self, memories):  # Missing async!
        result = await self.llm.generate(memories)  # SyntaxError

# ✅ FIX
class PromptBuilder:
    async def build_context(self, memories):  # Add async
        result = await self.llm.generate(memories)
```

**Note**: FIX-04 covers handlers missing `async`. This FIX covers non-handler methods (utility classes, services, builders) that also need `async` when using `await`.

---

### FIX-30: Adapter missing Star entry (dual registration)

**Problem**: `plugins/failed` reports `插件 … 未通过 Star 注册`（或 `未找到旧版插件类`）for a platform adapter. The package has `@register_platform_adapter(...)` but **no Star subclass**.

**Why**: AstrBot adapters are **dual-registration**:
1. `@register_platform_adapter` registers the platform into the platform list (Dashboard 适配器) at import time.
2. The plugin directory **still needs a `Star` subclass** (class name ends with `Plugin` or is `Main`) so `star_manager` recognizes it as a loaded plugin.

Both are required. Missing the Star class does **not** say "adapter not found" — it says "未通过 Star 注册".

```python
from astrbot.api.star import Context, Star  # correct import path

class MyAdapterPlugin(Star):                # name ends with Plugin
    def __init__(self, context: Context):
        super().__init__(context)
```

**Reviewer**: `astrbot_review_path(path, profile="adapter")` flags this as `FIX-30` (error) when `register_platform_adapter` is present but no `Star` subclass is found anywhere in the package.

---

### FIX-31: Stale failed record blocks all plugin mutations

**Problem**: `install_path` / `set_enabled` / `reload` / `uninstall` all return a **generic** `插件操作失败，请查看服务端日志。` while GET endpoints (plugin list, failed probe) work fine.

**Cause**: the plugin exists **only in the failed list** (a stale/half-broken failed record). The upload does not overwrite it, and uninstall/enable/reload cannot touch it → a deadlock that only manual cleanup resolves.

**Diagnosis (MCP)**: `astrbot_plugin_install_path` auto-detects this (`stale_failed` in the result): `snapshot_before.present=false` + plugin present in `/plugins/failed`.

**Fix order**:
1. `astrbot_plugin_failed` → if the plugin is there but not in the normal list: **stop retrying**.
2. Clean it in Dashboard (or the AstrBot filesystem) → failed list empty → re-upload succeeds.
3. `force_refresh` does **not** clear failed-list-only entries (it uninstalls from the normal list first).

---

### FIX-32: Adapter config_metadata field-name collision (shared items dict)

**Problem**: redefining a **core shared** metadata field name in `config_metadata`
/ `default_config_tmpl` overwrites it for **ALL** adapters' forms.

**Why (source-verified, v4.27.0)**:
`astrbot/dashboard/services/config_service.py:913-929` `inject_platform_metadata_with_i18n`
merges every adapter's `config_metadata` into **one shared dict**
`platform_group.metadata.platform.items` via `dict.update()` (by field name).
That dict already holds core built-ins such as:

| key | description | built-in condition |
|-----|-------------|--------------------|
| `port` | 回调服务器端口 | `{unified_webhook_mode: False}` |
| `callback_server_host` | 回调服务器主机 | `{unified_webhook_mode: False}` |
| `unified_webhook_mode` | 统一 Webhook 模式 | — |
| `webhook_uuid` | Webhook UUID | invisible |

If any adapter registers `port` (or `token`/`host`/`api_key`, etc. shared with
another adapter), `items.update()` replaces the built-in entry **and drops its
`condition`** — the frontend then shows that adapter's description for **every**
platform that renders the shared items (QQ 官方 / 公众号 / 企微 / …).

**Fix (plugin-side)**: **prefix all custom fields** with the adapter id:

```python
# ❌ generic names risk cross-adapter collision
default_config_tmpl={"token": "", "port": 7300}

# ✅ prefixed
default_config_tmpl={"xx_token": "", "xx_port": 7300}
# ...and read self.config.get("xx_token") everywhere
```

**Reviewer**: `astrbot_review_path(profile="adapter")` warns (`FIX-32`) when
`config_metadata`/`default_config_tmpl` uses core built-in names
(`port`/`callback_server_host`/`unified_webhook_mode`/`webhook_uuid`/`id`/`enable`/`type`).

Real-world case: an adapter that registered `port` polluted other platforms'
forms; fixed by prefixing every field (`xx_port`, `xx_token`).

---

### FIX-33: error_kb `$PWD` pollution — and NEVER `rm -rf "$PWD"` (shell hazard)

**Problem A (pollution)**: setting `ASTRBOT_ERROR_KB` to a **literal** `$PWD/...`
(unexpanded by the shell) makes `FingerprintStore` create a directory literally
named `$PWD` in the current working directory. If that CWD is a plugin being
packed, `install_path`'s ZIP gets polluted with `<plugin>/$PWD/mcp/.error_kb.json`.
- `zip_pack` now **hard-excludes** any `$`-prefixed dir/file and `.error_kb.json`.
- Prevention: use an absolute path — `export ASTRBOT_ERROR_KB="$(pwd)/.error_kb.json"`.

**Problem B (incident, 2026-08 — data-loss)**: deleting the polluted dir with
`rm -rf "$PWD"` is **catastrophic**: the shell expands `$PWD` to the current
working directory, so the command deletes the whole CWD (e.g. the entire plugin
directory). Never use unescaped `$PWD` inside `rm -rf`.

**Safe cleanup**:
```bash
# literal "$PWD" directory name — escape the dollar
rm -rf "\$PWD"
# or target by name without shell expansion
find <plugin_dir> -maxdepth 1 -name '$PWD' -exec rm -rf {} +
```

**Rule for agents doing shell cleanup**: quote/escape `$` when the intent is a
literal `$` character; double-check `pwd` before any `rm -rf`; prefer `find
-name '...' -exec rm -rf {} +` for unusual names.

---

### FIX-34: Adapter component field access — check components.py first

**Problem**: `'At' object has no attribute 'uid'` (or similar `AttributeError` on
message components at runtime). Adapter code accesses a field name that does not
exist in the current AstrBot version's `astrbot/core/message/components.py`.

**Why**: AstrBot's component classes (`At`, `Reply`, `Image`, …) are pydantic
`BaseModel` subclasses. Field names change across versions (e.g. `qq` vs `uid`).
Constructing a component with an unknown field name is silently ignored
(pydantic discards extras); reading a non-existent field raises `AttributeError`.

**Fix**:
```python
# ❌ uid may not exist in current version
target = comp.uid

# ✅ read priority: check known field names
target = getattr(comp, "qq") or getattr(comp, "uid") or ""
# ✅ construct with known field (qq is the canonical identifier)
from astrbot.api.message_components import At
at_comp = At(qq=user_id, name=user_name)
```

**Rules**:
- Before accessing any component field, check the **current version's**
  `astrbot/core/message/components.py` for field names.
- `qq` is the canonical user-identifier field (OneBot semantics, works in
  non-QQ platforms as the general user ID).
- Do **not** try to add new fields to core components (pydantic `BaseModel`
  rejects unknown fields via extra validation). Use read-priority + semantic
  mapping instead.

---

### FIX-35: Adapter reply target — use get_session_id(), not get_sender_id()

**Problem**: Group message replies are sent to the **sender** (private chat)
instead of the **group conversation** (the whole group sees it as a private
reply, or the reply goes to the wrong conversation).

**Why**: `AstrMessageEvent.get_sender_id()` returns the message **author**.
`get_session_id()` returns the **conversation/session** identifier. For group
messages, the session id is the group id (e.g. `xxx@chatroom`); the sender id
is the individual user.

```python
# ❌ sends to the user, not the group
await self.client.send_text(self.get_sender_id(), comp.text)

# ✅ sends to the group/session
await self.client.send_text(self.get_session_id(), comp.text)
```

**Rule**: `send()` → `get_session_id()` (or `get_session_id() or get_sender_id()`
for fallback). `get_sender_id()` is only for @-mentioning the user.

---

### FIX-36: Adapter wakeup — set self_id + At(qq==self_id)/AtAll

**Problem**: `@bot 在做什么` cannot wake the bot. The message is delivered but
the adapter never generates an `At` component, or `self_id` is unset.

**Wakeup chain** (source: `astrbot/core/waking_check/stage.py`):
1. `AstrBotMessage.self_id` **must be set** (the bot's own user ID) — otherwise
   `get_self_id()` returns empty, and the `waking_check` cannot match the bot.
2. The adapter must **generate `At` components** from the platform's at-user
   list: if at_users contains `self_id` → insert `At(qq=self_id)` at the front
   of the message component chain.
3. `@all` or `@everyone` → generate `AtAll()`.

```python
# In convert_message():
abm = AstrBotMessage(...)
abm.self_id = data.get("self_id") or ""  # MUST set

# At component generation:
at_users = data.get("at_users") or []
if at_users:
    for uid in at_users:
        if uid == abm.self_id:
            chain.insert(0, At(qq=uid))
        elif uid in ("all", "everyone", "notify@all"):
            chain.insert(0, AtAll())
```

**Cross-platform @ detection**: do not rely solely on XML `atuserlist` —
different platforms encode @ mentions differently (XML structured, plaintext
with `@nickname`, etc.). Use a platform-specific check that:
1. Checks structured at-user list (if available).
2. Falls back to regex matching `@(wxid|nickname)` in the message content.
3. Resolves group nicknames via the platform's API (with caching).

---

### FIX-37: Debug log variable reference order — UnboundLocalError

**Problem**: Adding a temporary debug log crashes the handler with
`cannot access local variable 'X' where it is not associated with a value`
(UnboundLocalError), silently dropping all messages.

**Why**: Python's scoping rule — if a variable is assigned **anywhere** in a
function, it is treated as **local** throughout the entire function. If a log
statement references it **before** the assignment, Python raises
`UnboundLocalError` at runtime.

```python
# ❌ crashes: logger.info references 'text' before assignment
async def _handle_message(self, data):
    logger.info(f"msg={text}")        # UnboundLocalError!
    text = data.get("content", "")
    ...

# ✅ fix: assign before any reference
async def _handle_message(self, data):
    text = data.get("content", "")
    logger.info(f"msg={text}")        # ok
    ...
```

**Rule**: before adding any temporary debug log, verify all referenced
variables are assigned **before** the log line. Remove temporary logs after
the debugging session.

---

### FIX-38: Hot-reload does NOT replace running Platform adapter instance

**Problem**: After reloading a Platform adapter via `POST /plugins/{id}/reload`
(or `astrbot_plugin_reload`), the **running adapter instance** continues to
use the old code. The reload API returns success, but the Platform instance
that was already `run()`-ing is not replaced — only new instances pick up
updated code.

**Fix**: After deploying adapter code changes, **fully restart the AstrBot
process** (or container). Do not rely on `reload` for adapters — it works for
regular Star plugins but not for Platform adapters whose instances are
long-lived.

**MCP note**: `astrbot_plugin_reload`'s `ok=true` does NOT guarantee the
running adapter is using the new code. Check the log line numbers or behavior
to confirm the restart actually happened.

---

## Verification

After each fix, re-run the full audit from `review/review-workflow.md`:
1. Original issue is resolved
2. No new issues introduced
3. Audit conclusion is ✅ PASS
