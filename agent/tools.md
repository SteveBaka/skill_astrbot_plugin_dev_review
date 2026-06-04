# Tool Definition

Tools are the mechanism that allows LLMs to call external capabilities (retrieval, computation, command execution).

> For LLM invocation, see `agent/invoke-llm.md`
> For Agent hooks, see `agent/hooks.md`
> For built-in official tools, see `agent/official-tools.md`

## Method 1: Class Definition (Recommended, v4.5.7+)

```python
from pydantic import Field
from pydantic.dataclasses import dataclass
from astrbot.core.agent.run_context import ContextWrapper
from astrbot.core.agent.tool import FunctionTool
from astrbot.core.astr_agent_context import AstrAgentContext

@dataclass
class BilibiliTool(FunctionTool[AstrAgentContext]):
    name: str = "bilibili_videos"
    description: str = "A tool to fetch Bilibili videos."
    parameters: dict = Field(
        default_factory=lambda: {
            "type": "object",
            "properties": {
                "keywords": {"type": "string", "description": "Keywords to search for Bilibili videos."}
            },
            "required": ["keywords"],
        }
    )

    async def call(self, context: ContextWrapper[AstrAgentContext], **kwargs) -> str:
        return "1. Video title: How to use AstrBot\nLink: xxxxxx"
```

### Return Value

**Always return a plain `str`**. The framework auto-wraps it.

```python
# ✅ CORRECT — return string directly
async def call(self, context, **kwargs) -> str:
    return "result text"

# ✅ CORRECT — return error as string
async def call(self, context, **kwargs) -> str:
    return "Error: something went wrong"
```

> ⚠️ **Do NOT use `ToolExecResult(result=...)`** — in Python 3.12, the `|` union type syntax (`ToolExecResult | str`) causes `types.UnionType` to be non-callable. Always return a plain `str`.

> ⚠️ If you must use `ToolExecResult` (e.g., for `image_url`), import it explicitly and test on your target Python version:
> ```python
> from astrbot.core.agent.tool import ToolExecResult
> return ToolExecResult(result="text", image_url="https://...")
> ```

### Register to Global Tool Pool

```python
class MyPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        # >= v4.5.7:
        self.context.add_llm_tools(BilibiliTool(), SecondTool())
```

> ⚠️ `context.register_llm_tool()` is **DEPRECATED**. Do not use in new plugins. Use `add_llm_tools()` instead. <!-- Source: guides/ai.md WARNING -->

## Method 2: Decorator (Backward Compatible)

```python
@filter.llm_tool(name="get_weather")
async def get_weather(self, event: AstrMessageEvent, location: str) -> MessageEventResult:
    """Get weather information.

    Args:
        location(string): The city name
    """
    resp = self.get_weather_from_api(location)
    yield event.plain_result("Weather: " + resp)
```

### Args Format Requirements

The `Args:` section in the docstring is **mandatory** and must follow this exact format:

```
Args:
    param_name(type): description
```

Supported types: `string`, `number`, `object`, `boolean`, `array`, `array[string]` (v4.5.7+).

> ⚠️ The decorator parses the docstring to generate the tool's parameter schema. It does **NOT** read type annotations from the function signature. If `Args:` is missing or incorrectly formatted, the schema will be empty and LLM parameters will be silently dropped.

> ⚠️ The decorator does **NOT** support `parameters=...` to pass schema explicitly. Use the `@dataclass` + `add_llm_tools()` approach for manual schema control.

## Internal Tools (Not Globally Registered)

Only visible within a single `tool_loop_agent` call:

```python
from astrbot.core.agent.tool import ToolSet

resp = await self.context.tool_loop_agent(
    event=event,
    chat_provider_id=provider_id,
    prompt="Use tools to complete the task",
    tools=ToolSet([BilibiliTool()]),
)
```

## Tips

- `parameters` must be valid JSON Schema
- Decorator approach requires well-written docstrings, otherwise schema parsing fails
- New projects are recommended to use the class definition approach
- `@filter.permission_type` cannot be combined with `@filter.llm_tool`
- **Always return `str` from `call()`** — do not use `ToolExecResult` unless you need `image_url`
