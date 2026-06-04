# Plugin Development Workflow

## 1. Project Scaffold

Standard AstrBot plugin directory structure:

```text
astrbot_plugin_example/
├── main.py                 # Plugin entry point, implements Star subclass
├── metadata.yaml           # Plugin metadata (required)
├── _conf_schema.json       # Configuration Schema (recommended)
├── requirements.txt        # Python dependencies
├── README.md               # Documentation
├── LICENSE                 # Open source license
├── .gitignore              # Ignore __pycache__, venv, etc.
└── tools/                  # Optional: LLM FunctionTool classes
```

## 2. metadata.yaml Template

```yaml
name: astrbot_plugin_example        # Unique identifier, astrbot_plugin_ prefix recommended
display_name: Example               # Display name — match user's language (Chinese user → Chinese, English → English)
desc: Short description.            # Short description — match user's language
version: v1.0.0                     # Version
author: YourName                    # Author name
repo: ""                            # Leave empty on first generation; user fills after creating repo
astrbot_version: ">=4.16,<5"        # AstrBot version range
```

> **First-generation rules**: `display_name`, `desc`, `_conf_schema.json` descriptions/hints, and `README.md` should all use the same language as the user's input. `repo` should be left empty. `author` should use the user's name if provided.

## 3. Implementing the Plugin Class

```python
from astrbot.api import logger
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star

class ExamplePlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)

    async def initialize(self):
        """Plugin initialization, called automatically after instantiation."""

    @filter.command("hello")
    async def hello(self, event: AstrMessageEvent):
        """hello command"""
        user_name = event.get_sender_name()
        yield event.plain_result(f"Hello, {user_name}!")

    async def terminate(self):
        """Clean up resources when the plugin is unloaded."""
```

**Key Rules**:
- Handler methods must be on a `Star` subclass, with `self` + `event`
- All handlers/hooks use `async def`
- Handlers need brief docstrings (AstrBot displays them to users)
- Clean up timers, connections, file handles in `terminate()`

## 4. Event Listening

Available filter decorators (v4.x):

| Decorator | Purpose |
|-----------|---------|
| `@filter.command("name")` | Register a command |
| `@filter.command_group("group")` | Command group (must use function pattern) |
| `@filter.event_message_type(...)` | Message type filter (`EventMessageType.ALL` etc.) |
| `@filter.platform_adapter_type(...)` | Platform filter |
| `@filter.permission_type(...)` | Permission filter |
| `@filter.on_llm_request()` | LLM request hook |
| `@filter.on_llm_response()` | LLM response hook |
| `@filter.on_decorating_result()` | Result decorating hook |
| `@filter.after_message_sent()` | After message sent hook |

> ⚠️ `on_full_match`, `on_keyword`, `on_regex`, `on_prefix` are **REMOVED** in v4.x. Use `@filter.event_message_type(filter.EventMessageType.ALL)` + Python string matching instead.

Special hooks (`on_llm_request`, `on_llm_response`, `on_decorating_result`, `after_message_sent`):
- Use `await event.send(...)` instead of `yield`
- Must be `async def`, signature `(self, event, req/resp)`

## 5. Message Handling

```python
# Plain text
text = event.message_str

# Message chain
from astrbot.api.message_components import Comp
chain = event.get_messages()

# Build message chain
yield event.chain_result([Comp.Plain("文字"), Comp.Image.fromURL("url")])
```

## 6. Configuration System

Define configuration items in `_conf_schema.json`, read them in code via `self.config`:

```python
api_key = self.config.get("api_key")
```

See `references/conf-schema.md` for details.

## 7. Data Persistence

```python
from astrbot.api.star import StarTools

data_dir = StarTools.get_data_dir()  # Returns a Path object
# Path: data/plugin_data/<plugin_name>/
```

KV Storage (v4.9.2+):

```python
await self.put_kv_data("key", value)
data = await self.get_kv_data("key", default=None)
await self.delete_kv_data("key")
```

## 8. AI Calls and Tools

LLM calls:

```python
provider_id = await self.context.get_current_chat_provider_id(event.unified_msg_origin)
resp = await self.context.llm_generate(provider_id, prompt)
```

Tool registration (v4.5.7+ recommended dataclass pattern):

```python
from dataclasses import field
from pydantic.dataclasses import dataclass
from astrbot.core.agent.tool import FunctionTool
from astrbot.core.agent.run_context import ContextWrapper
from astrbot.core.astr_agent_context import AstrAgentContext

@dataclass
class MyTool(FunctionTool[AstrAgentContext]):
    name: str = "my_tool"
    description: str = "Tool description"
    parameters: dict = field(default_factory=lambda: {
        "type": "object",
        "properties": {"query": {"type": "string", "description": "Query"}},
        "required": ["query"]
    })

    async def call(self, context: ContextWrapper[AstrAgentContext], **kwargs) -> str:
        return "result"
```

> ⚠️ `parameters` MUST use `field(default_factory=lambda: {...})`, NOT direct dict literal (causes `ValueError: mutable default`).
> ⚠️ `call()` MUST return `str`, NOT `ToolExecResult` (Python 3.12 issue).

## 9. requirements.txt

Every plugin that uses third-party libraries MUST have a `requirements.txt`.

**Rules**:
- Only list third-party packages NOT provided by AstrBot or Python stdlib
- Do NOT include `astrbot`, `quart`, `asyncio`, `json`, `pathlib`, etc.
- One package per line
- No version pinning needed for simple cases

**How to create**: Scan all `.py` files for imports. Filter out:
- `astrbot.*` (AstrBot runtime)
- Python stdlib (`asyncio`, `json`, `os`, `sys`, `pathlib`, `typing`, `collections`, etc.)
- AstrBot-bundled (`quart`)

**Example** (from real plugin `astrbot_plugin_synochat_adapter`):
```
aiohttp
```

**Cross-check**: After creating requirements.txt, verify:
- Every entry is actually imported somewhere
- Every third-party import has an entry

## 10. Debugging and Verification

- Log via `astrbot.api.logger`
- When debugging message parsing, check `event.message_obj.message` and `event.message_obj.raw_message`
- Test: command registration, default config values, permissions, reload/unload, platform component compatibility
- After completion, execute the review workflow: `review/review-workflow.md`

## When to Split main.py

If main.py exceeds ~200 lines or has 5+ commands, consider splitting into modules.
See `references/modular-split.md` for the full guide with real-world examples.

**Quick rule**: Command handlers → `handlers/`, API clients → `services/`, constants → `constants.py`.
