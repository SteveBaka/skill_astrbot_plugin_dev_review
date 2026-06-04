# Agent-Related Hooks

Hooks directly related to Agent request/tool loops, divided into two layers.

## Plugin Hooks

### LLM Request Phase

```python
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.provider import ProviderRequest, LLMResponse

@filter.on_waiting_llm_request()
async def on_waiting(self, event: AstrMessageEvent) -> None:
    """Fires before AstrBot acquires the session lock. Use for 'thinking...' feedback."""
    await event.send(event.plain_result("Thinking..."))

@filter.on_llm_request()
async def on_req(self, event: AstrMessageEvent, request: ProviderRequest) -> None: ...

@filter.on_llm_response()
async def on_resp(self, event: AstrMessageEvent, response: LLMResponse) -> None: ...
```

### Agent Phase (v4.23.1+)

```python
from astrbot.core.agent.run_context import ContextWrapper
from astrbot.core.astr_agent_context import AstrAgentContext

@filter.on_agent_begin()
async def on_agent_begin(self, event: AstrMessageEvent, run_context: ContextWrapper[AstrAgentContext]) -> None: ...

@filter.on_agent_done()
async def on_agent_done(self, event: AstrMessageEvent, run_context: ContextWrapper[AstrAgentContext], resp: LLMResponse) -> None: ...
```

### Tool Call Phase

```python
from astrbot.core.agent.tool import FunctionTool
from mcp.types import CallToolResult

@filter.on_using_llm_tool()
async def on_tool_start(self, event: AstrMessageEvent, tool: FunctionTool, tool_args: dict | None) -> None: ...

@filter.on_llm_tool_respond()
async def on_tool_end(self, event: AstrMessageEvent, tool: FunctionTool, tool_args: dict | None, tool_result: CallToolResult | None) -> None: ...
```

### Result Sending Phase

```python
@filter.on_decorating_result()
async def on_decorating(self, event: AstrMessageEvent) -> None: ...

@filter.after_message_sent()
async def after_sent(self, event: AstrMessageEvent) -> None: ...
```

## Agent Runner Hooks

Used for runtime extension in `context.tool_loop_agent(..., agent_hooks=...)`:

```python
from astrbot.core.agent.hooks import BaseAgentRunHooks
from astrbot.core.agent.run_context import ContextWrapper

class MyAgentHooks(BaseAgentRunHooks):
    async def on_agent_begin(self, run_context: ContextWrapper) -> None: ...
    async def on_tool_start(self, run_context, tool, tool_args) -> None: ...
    async def on_tool_end(self, run_context, tool, tool_args, tool_result) -> None: ...
    async def on_agent_done(self, run_context, llm_response) -> None: ...
```

## Mapping Relationship

- `on_tool_start` -> `@filter.on_using_llm_tool()`
- `on_tool_end` -> `@filter.on_llm_tool_respond()`
- `on_agent_done` -> `@filter.on_llm_response()`

## MUST

- Hook handler functions must use `async def`
- Using `yield` is forbidden in these hooks; you must use `event.send()`
