# Plugin Implementation Patterns

This document covers all major implementation patterns in AstrBot plugin development, for LLMs and Vibe Coding tools to understand code structures in different scenarios.

---

## Pattern 1: Command Plugin

**Scenario**: User sends `/xxx` to trigger functionality.

**Core Structure**:

```python
from astrbot.api import logger
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star

class MyPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)

    @filter.command("指令名")
    async def handler(self, event: AstrMessageEvent):
        """指令描述（会展示给用户）"""
        user_input = event.message_str  # 用户发送的文本
        yield event.plain_result("回复内容")

    async def terminate(self):
        """清理资源"""
```

**Key Points**:
- `@filter.command("name")` registers a command; user sends `/name` to trigger
- `yield event.plain_result(text)` sends a plain text reply
- Command arguments can be obtained via `event.message_str`, or parsed automatically using function parameters

**Simple Command (recommended — use `event.message_str`)**:

```python
@filter.command("weather")
async def weather(self, event: AstrMessageEvent):
    """Query weather for a city."""
    city = event.message_str.strip()
    if not city:
        yield event.plain_result("Usage: /weather <city>")
        return
    result = await fetch_weather(city)
    yield event.plain_result(result)
```

**Command with Typed Arguments** (for numeric parsing):

```python
@filter.command("add")
async def add(self, event: AstrMessageEvent, a: int, b: int):
    yield event.plain_result(f"Result: {a + b}")
```

> ⚠️ **Parameter binding warning**: AstrBot's `context_utils.py` may cause `got multiple values for argument` errors when using string function parameters with default values (e.g., `city: str = ""`). For text input, always use `event.message_str.strip()` instead of function parameters. Typed parameters (`a: int, b: int`) for numeric parsing are safe.

**Command Group** (official pattern):

```python
@filter.command_group("math")
def math():
    pass  # Command group function body must be empty

@math.command("add")
async def add(self, event: AstrMessageEvent, a: int, b: int):
    yield event.plain_result(f"Result: {a + b}")

@math.command("sub")
async def sub(self, event: AstrMessageEvent, a: int, b: int):
    yield event.plain_result(f"Result: {a - b}")
```

Nested command groups use `.group()` instead of `.command_group()`:

```python
@filter.command_group("math")
def math():
    pass

@math.group("calc")
def calc():
    pass

@calc.command("add")
async def add(self, event: AstrMessageEvent, a: int, b: int):
    yield event.plain_result(f"Result: {a + b}")
```

**Message Filter Composition**:

```python
@filter.command("admin")
@filter.permission_type(filter.PermissionType.ADMIN)
@filter.event_message_type(filter.EventMessageType.GROUP_MESSAGE)
async def admin_cmd(self, event: AstrMessageEvent):
    yield event.plain_result("管理员群聊专用")
```

---

## Pattern 2: LLM Tool Plugin

**Scenario**: Let the AI model automatically call your functionality (e.g., weather query, database query).

**Core Structure (v4.5.7+ recommended dataclass approach)**:

```python
from pydantic import Field
from pydantic.dataclasses import dataclass
from astrbot.core.agent.tool import FunctionTool
from astrbot.core.agent.run_context import ContextWrapper
from astrbot.core.astr_agent_context import AstrAgentContext

@dataclass
class MyTool(FunctionTool[AstrAgentContext]):
    name: str = "tool_name"
    description: str = "Tool description (AI uses this to decide whether to call)"
    parameters: dict = Field(default_factory=lambda: {
        "type": "object",
        "properties": {
            "param1": {"type": "string", "description": "Parameter description"}
        },
        "required": ["param1"],
    })

    async def call(self, context: ContextWrapper[AstrAgentContext], **kwargs) -> str:
        param1 = kwargs.get("param1", "")
        result = do_something(param1)
        return result  # Always return str, framework auto-wraps

class MyPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        self.context.add_llm_tools(MyTool())  # 注册到全局工具池
```

**Key Points**:
- `description` determines whether the AI will call this tool; it must be clear and accurate
- `parameters` must be valid JSON Schema
- Return `str` directly from `call()` — framework auto-wraps. Do NOT use `ToolExecResult` (Python 3.12 compatibility issue)
- After registration, AI in all conversations can detect this tool

**Decorator Approach (backward compatible)**:

```python
@filter.llm_tool(name="get_weather")
async def get_weather(self, event: AstrMessageEvent, location: str):
    """获取天气信息。

    Args:
        location(string): 地点
    """
    result = await fetch_weather(location)
    yield event.plain_result(f"天气: {result}")
```

**Internal Tools (not globally registered)**:

```python
from astrbot.core.agent.tool import ToolSet

resp = await self.context.tool_loop_agent(
    event=event,
    chat_provider_id=provider_id,
    prompt="使用工具完成任务",
    tools=ToolSet([MyTool()]),
    max_steps=5,
)
```

---

## Pattern 3: Multi-Turn Conversation Plugin

**Scenario**: Quiz games, form collection, guided interaction.

**Core Structure**:

```python
from astrbot.core.utils.session_waiter import session_waiter, SessionController

@filter.command("start")
async def start(self, event: AstrMessageEvent):
    yield event.plain_result("Enter your name:")

    @session_waiter(timeout=60, record_history_chains=False)
    async def waiter(controller: SessionController, event: AstrMessageEvent):
        name = event.message_str.strip()

        if name == "quit":
            await event.send(event.plain_result("Exited."))
            controller.stop()
            return

        await event.send(event.plain_result(f"Hello, {name}!"))
        controller.keep(timeout=60, reset_timeout=True)

    try:
        await waiter(event)
    except TimeoutError:
        yield event.plain_result("Timed out!")
    finally:
        event.stop_event()
```

**Key Points**:
- `@session_waiter(timeout=seconds, record_history_chains=False)` creates a session
- `record_history_chains=True` to record message history (accessible via `controller.get_history_chains()`)
- Inside the session, you **must** use `await event.send()` instead of `yield`
- `controller.keep(timeout, reset_timeout=True)` continues waiting; `reset_timeout=True` resets the timer
- `controller.stop()` immediately ends the session
- `controller.get_history_chains() -> List[List[Comp.BaseMessageComponent]]` gets recorded history
- `TimeoutError` is thrown on timeout; must be caught with try/except
- Sessions are isolated by `sender_id` by default

**Custom Session Isolation (group-level)**:

```python
from astrbot.core.utils.session_waiter import SessionFilter

class GroupFilter(SessionFilter):
    def filter(self, event: AstrMessageEvent) -> str:
        return event.get_group_id() if event.get_group_id() else event.unified_msg_origin

await waiter(event, session_filter=GroupFilter())
```

This makes all users in the same group share one session.

---

## Pattern 4: Scheduled Task Plugin

**Scenario**: Timed reminders, data collection, periodic AI wake-ups.

**Core Structure**:

```python
class MyPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        self.cron_mgr = context.cron_manager

    async def initialize(self):
        await self.cron_mgr.add_basic_job(
            name="task_name",
            cron_expression="*/5 * * * *",
            handler=self._handler,
            persistent=True,
            description="每5分钟执行",
            enabled=True,
        )

    async def _handler(self, payload: dict = None):
        """定时处理函数"""
        logger.info("定时任务执行")

    async def terminate(self):
        self.cron_mgr.delete_job("task_name")
```

**Cron Expression Format**: `minute hour day month weekday`

| Expression | Meaning |
|------------|---------|
| `*/5 * * * *` | Every 5 minutes |
| `0 9 * * *` | Every day at 9:00 |
| `0 */2 * * *` | Every 2 hours |
| `0 9 * * 1` | Every Monday at 9:00 |

**AI Wake-up Task**:

```python
await self.cron_mgr.add_active_job(
    name="ai_daily",
    cron_expression="0 8 * * *",
    payload={"session": umo, "note": "生成今日摘要"},
    run_once=False,
    description="每天 8 点 AI 生成摘要",
)
```

---

## Pattern 5: LLM Hook Plugin

**Scenario**: Inject system prompts, filter sensitive content, log AI interactions.

**Core Structure**:

```python
from astrbot.api.provider import ProviderRequest, LLMResponse

class MyPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)

    @filter.on_llm_request()
    async def on_request(self, event: AstrMessageEvent, req: ProviderRequest):
        """在 LLM 请求发出前修改"""
        req.system_prompt += "\n额外指令"

    @filter.on_llm_response()
    async def on_response(self, event: AstrMessageEvent, resp: LLMResponse):
        """在 LLM 响应返回后处理"""
        logger.info(f"响应长度: {len(resp.completion_text)}")

    @filter.on_decorating_result()
    async def on_decorating(self, event: AstrMessageEvent):
        """在结果装饰阶段处理"""

    @filter.after_message_sent()
    async def after_sent(self, event: AstrMessageEvent):
        """在消息发送后处理"""
```

**Key Points**:
- **Do not** use `yield` in these four hooks; you **must** use `await event.send()`
- Hook signatures **must** be `(self, event: AstrMessageEvent, req/resp)`
- `ProviderRequest` allows modifying `system_prompt`, `prompt`, `contexts`, etc.
- `LLMResponse` allows reading `completion_text`

**Tool Call Phase Hooks**:

```python
from astrbot.core.agent.tool import FunctionTool
from mcp.types import CallToolResult

@filter.on_using_llm_tool()
async def on_tool_start(self, event, tool: FunctionTool, tool_args: dict | None):
    logger.info(f"AI 调用工具: {tool.name}")

@filter.on_llm_tool_respond()
async def on_tool_end(self, event, tool, tool_args, tool_result: CallToolResult | None):
    logger.info(f"工具返回: {tool_result}")
```

---

## Pattern 6: Web API / Dashboard Plugin

**Scenario**: Frontend pages, REST APIs, status monitoring panels.

**Core Structure**:

```python
from quart import jsonify

PLUGIN_NAME = "astrbot_plugin_myplugin"

class MyPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        context.register_web_api(
            f"/{PLUGIN_NAME}/status",
            self.api_status,
            ["GET"],
            "获取状态",
        )

    async def api_status(self):
        return jsonify({"status": "ok"})

    async def initialize(self):
        self.data_dir = StarTools.get_data_dir()
        self.data_dir.mkdir(parents=True, exist_ok=True)
```

**Frontend Page Structure**:

```
my_plugin/
├── main.py
└── pages/
    └── my-page/
        ├── index.html
        ├── app.js
        └── style.css
```

**Frontend Bridge API**:

```js
const bridge = window.AstrBotPluginPage;
const context = await bridge.ready();

// Call backend API
const result = await bridge.apiGet("status");
const data = await bridge.apiPost("action", { key: "value" });

// Internationalization
const title = bridge.t("pages.my-page.title");
```

---

## Pattern 7: Agent Sub-Agent Plugin

**Scenario**: AI autonomously decides to call multiple tools to complete complex tasks.

**Core Structure**:

```python
from astrbot.core.agent.tool import ToolSet

class MyPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        self.context.add_llm_tools(SearchTool(), CalcTool())

    @filter.command("agent")
    async def run_agent(self, event: AstrMessageEvent):
        query = event.message_str.strip()
        provider_id = await self.context.get_current_chat_provider_id(
            event.unified_msg_origin
        )
        resp = await self.context.tool_loop_agent(
            event=event,
            chat_provider_id=provider_id,
            prompt=query,
            tools=ToolSet([SearchTool(), CalcTool()]),
            system_prompt="你是智能助手，请使用工具完成任务。",
            max_steps=10,
            tool_call_timeout=60,
        )
        yield event.plain_result(resp.completion_text)
```

**Key Points**:
- `tool_loop_agent` lets the AI autonomously decide which tools to call and in what order
- `max_steps` controls the maximum number of tool call rounds to prevent infinite loops
- `ToolSet` wraps a tool list; can be globally registered or internal
- `system_prompt` guides the AI on how to use tools

**Agent Runner Hooks**:

```python
from astrbot.core.agent.hooks import BaseAgentRunHooks

class MyHooks(BaseAgentRunHooks):
    async def on_agent_begin(self, run_context):
        logger.info("Agent started")

    async def on_tool_start(self, run_context, tool, tool_args):
        logger.info(f"Calling tool: {tool.name}")

    async def on_agent_done(self, run_context, llm_response):
        logger.info(f"Agent done: {llm_response.completion_text[:100]}")

resp = await self.context.tool_loop_agent(
    event=event,
    chat_provider_id=provider_id,
    prompt="Task description",
    tools=ToolSet([MyTool()]),
    agent_hooks=MyHooks(),
)
```

**Multi-Agent Pattern (agent-as-tool)**:

Define sub-agents as `FunctionTool` subclasses. Each sub-agent can call `tool_loop_agent` internally:

```python
@dataclass
class SubAgent(FunctionTool[AstrAgentContext]):
    name: str = "weather_agent"
    description: str = "Get weather information for a location"
    parameters: dict = Field(default_factory=lambda: {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Weather query"}
        },
        "required": ["query"],
    })

    async def call(self, context: ContextWrapper[AstrAgentContext], **kwargs) -> str:
        ctx = context.context.context  # Get Context from wrapper
        event = context.context.event  # Get event from wrapper
        llm_resp = await ctx.tool_loop_agent(
            event=event,
            chat_provider_id=await ctx.get_current_chat_provider_id(event.unified_msg_origin),
            prompt=kwargs["query"],
            tools=ToolSet([WeatherTool()]),
            max_steps=30,
        )
        return llm_resp.completion_text

# Register sub-agents as tools for the main agent
@filter.command("weather")
async def weather(self, event: AstrMessageEvent):
    prov_id = await self.context.get_current_chat_provider_id(event.unified_msg_origin)
    resp = await self.context.tool_loop_agent(
        event=event,
        chat_provider_id=prov_id,
        prompt="Get weather for Beijing",
        tools=ToolSet([SubAgent()]),
        system_prompt="You are the main agent. Delegate weather tasks to the weather agent.",
        max_steps=30,
    )
    yield event.plain_result(resp.completion_text)
```

---

## Pattern 8: Message Component Construction

**Scenario**: Send images, @mentions, audio, video, and other rich media messages.

```python
from astrbot.api.message_components import Comp

# Plain text
yield event.plain_result("文字")

# Image
yield event.image_result("https://example.com/image.png")

# Message chain (combine multiple components)
yield event.chain_result([
    Comp.Plain("请查看: "),
    Comp.Image.fromURL("https://example.com/chart.png"),
    Comp.At(event.get_sender_id()),
])

# Send image from file
yield event.chain_result([
    Comp.Image.fromFileSystem("/path/to/local/image.png"),
])

# Audio
yield event.chain_result([Comp.Record.fromFileSystem("/path/to/audio.wav")])
```

---

## Pattern 9: Data Persistence

**KV Storage (lightweight state)**:

```python
await self.put_kv_data("user_score", {"alice": 100, "bob": 85})
scores = await self.get_kv_data("user_score", default={})
await self.delete_kv_data("user_score")
```

**File Storage (large files, logs)**:

```python
from astrbot.api.star import StarTools
from pathlib import Path

data_dir = StarTools.get_data_dir()  # data/plugin_data/<plugin_name>/
data_dir.mkdir(parents=True, exist_ok=True)

log_file = data_dir / "log.txt"
with open(log_file, "a") as f:
    f.write("log entry\n")
```

---

## Pattern 10: Text-to-Image / HTML Rendering

**Scenario**: Long text, leaderboards, data tables that need image display.

```python
# Simple text-to-image
url = await self.text_to_image("这是一段长文本...")
yield event.image_result(url)

# Custom HTML rendering
tmpl = """
<div style="font-size: 24px; padding: 20px;">
  <h1>{{ title }}</h1>
  <ul>
    {% for item in items %}
    <li>{{ item }}</li>
    {% endfor %}
  </ul>
</div>
"""
url = await self.html_render(tmpl, {"title": "排行榜", "items": ["Alice: 100", "Bob: 85"]})
yield event.image_result(url)
```
