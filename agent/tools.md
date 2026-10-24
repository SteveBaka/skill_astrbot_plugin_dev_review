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

### Plugin Enable ≠ Tool Enable (≥ v4.26.0 / v4.26.2)

- Registering a tool does **not** guarantee it is available in every chat.
- WebUI can manage **per-tool** permission / activation separately from the plugin toggle.
- If the model never calls your tool, check:
  1. Plugin is enabled
  2. Tool is enabled / allowed in WebUI tools panel
  3. Persona tool list is not empty-restricting (persona `tools=[]` disables all)
  4. Docstring `Args:` format (decorator tools) or `parameters` schema (class tools)

Official: `docs/en/dev/star/guides/ai.md` + runtime WebUI tool panel.

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

- `parameters` must be valid JSON Schema, and its **root must be `{"type": "object"}`**
  (see the Anthropic rule below)
- Decorator approach requires well-written docstrings, otherwise schema parsing fails
- New projects are recommended to use the class definition approach
- `@filter.permission_type` cannot be combined with `@filter.llm_tool`
- **Always return `str` from `call()`** — do not use `ToolExecResult` unless you need `image_url`

### Object-root schema is mandatory (v4.29.0+ #10520)

Anthropic requests now raise instead of silently degrading:

```
ValueError: Anthropic tool '<name>' input schema must have an object root.
```

Before 4.29, `anthropic_schema()` copied only `properties` and `required`, quietly dropping
every other JSON Schema constraint. It now does
`input_schema.update(copy.deepcopy(tool.parameters))`, preserving `$ref`, `oneOf`,
numeric ranges and other constraints — and it **rejects a non-object root**.

| Declaration | 4.28.x | 4.29.0+ |
|---|---|---|
| `{"type": "object", "properties": {...}}` | fine | fine |
| `{"properties": {...}}` (root type omitted) | fine | fine — defaults to `object` |
| `{"type": "array", ...}` / `{"type": "string", ...}` | constraints dropped, call went out | **`ValueError`** |

Also: `openai_schema()` sorts tools by name for prompt-cache stability, so **registration
order is not schema order** — keep tool names unique, or the wrong one silently shadows
another.

### Enum values on Gemini (AstrBot ≥4.29.3, #10635)

Gemini rejects non-string `enum`s ("enum: only allowed for STRING type"). `convert_schema()`
in `astrbot/core/agent/tool.py` now normalizes them instead of failing the request:

| Declared | Sent to Gemini |
|---|---|
| `{"type": "string", "enum": ["a", 1]}` | `enum` kept, non-string members JSON-stringified (`"1"`) |
| `{"type": "integer", "enum": [1, 2]}` | **`enum` removed**; type stays `integer`; `Allowed values: 1, 2` appended to `description` |
| `{"enum": [..., null]}` | `nullable: true` added, `null` dropped from the list |

Two consequences for plugin authors:

- the allowed-values contract becomes **advisory text**, not schema enforcement on
  non-string types — so **the handler must still validate** and reject out-of-range input;
- do **not** rely on the model receiving an `enum` for int/bool params; put the accepted
  values in the parameter description as well if the call must be accurate.

Nullability differs per provider: `nullable` is a Gemini/OpenAPI-ism — OpenAI/Anthropic
express the same intent differently, so do not hand-roll provider-specific schema keys.
