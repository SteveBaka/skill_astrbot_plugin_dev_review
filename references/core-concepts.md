# AstrBot Core API Reference

This file is a quick index. For detailed usage, refer to the respective topic documentation.

## 1. Decorators

See `messages/events.md`, `agent/hooks.md`

- `@filter.command(name, alias, priority)`: Register a command
- `@filter.command_group(name)`: Command group
- `@filter.event_message_type(type)`: Message type filter (`ALL`, `PRIVATE_MESSAGE`, `GROUP_MESSAGE`)
- `@filter.platform_adapter_type(type)`: Platform filter (`AIOCQHTTP`, `TELEGRAM`, etc.)
- `@filter.permission_type(type)`: Permission check (`ADMIN`, `MEMBER`)
- `@filter.regex(pattern)`: Regex match
- `@filter.llm_tool(name)`: Register as AI tool (see `agent/tools.md`)
- `@filter.on_full_match(...)` / `@filter.on_prefix(...)` / `@filter.on_keyword(...)` / `@filter.on_regex(...)`: Text matching
- `@filter.on_llm_request()` / `@filter.on_llm_response()`: LLM hooks (see `agent/hooks.md`)
- `@session_waiter(timeout, record_history_chains)`: Wait for user input (see `references/plugin-patterns.md` Pattern 3)

## 2. Message Components

See `messages/components.md`

```python
from astrbot.api.message_components import Comp
```

- `Comp.Plain(text)` / `Comp.At(user_id)` / `Comp.Image.fromURL(url)` / `Comp.Record` / `Comp.Video` / `Comp.File` / `Comp.Face` / `Comp.Reply` / `Comp.Node` / `Comp.Nodes`

## 3. Core Objects

See `messages/events.md`, `design_standards/context_usage.md`

### AstrMessageEvent (Event Object)

- `event.message_str` / `event.get_messages()` / `event.message_obj.raw_message`
- `event.get_sender_name()` / `event.get_sender_id()`
- `event.unified_msg_origin` / `event.session_id` (see `messages/umo.md`)
- `event.get_platform_name()` / `event.get_group_id()` / `event.is_private_chat()`
- `event.plain_result(text)` / `event.chain_result(components)` / `event.image_result(url)`
- `event.send(chain)` / `event.stop_event()`

### Context (Core Hub)

See `design_standards/context_usage.md`

- `context.send_message(umo, chain)` / `context.get_platform_inst(platform_id)` (v4.0.0+)
- `context.add_llm_tools(*tools)` (see `agent/tools.md`)
- `context.register_web_api(path, handler, methods, desc)` (see `webui/plugin-pages.md`)

### LLM API (v4.5.7+)

See `agent/invoke-llm.md`

```python
prov_id = await context.get_current_chat_provider_id(umo)
resp = await context.llm_generate(chat_provider_id=prov_id, prompt="Hello!", system_prompt="You are helpful.")
resp = await context.tool_loop_agent(event=event, chat_provider_id=prov_id, prompt="搜索", tools=ToolSet([...]), max_steps=30)
```

## 4. Storage

See `storage_utils/kv_storage.md`, `storage_utils/file_storage.md`, `storage_utils/text_to_image.md`

```python
# KV Storage (v4.9.2+, plugin-isolated)
await self.put_kv_data("key", value)
data = await self.get_kv_data("key", default=None)
await self.delete_kv_data("key")

# File Storage — StarTools.get_data_dir() returns a Path object
from astrbot.api.star import StarTools
data_dir = StarTools.get_data_dir()  # data/plugin_data/<plugin_name>/

# HTML render to image
img_url = await self.html_render(tmpl="<h1>{{ title }}</h1>", data={"title": "Hello"})
```

## 5. Configuration Access

See `references/conf-schema.md`

```python
from astrbot.api import AstrBotConfig

class MyPlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.config = config
        api_key = self.config.get("api_key")
```

## 6. Tool Definition (v4.5.7+ dataclass pattern)

See `agent/tools.md`

```python
from astrbot.core.agent.tool import FunctionTool, ToolExecResult
```

Registration: `self.context.add_llm_tools(MyTool())`

## 7. Conversation Management

See `agent/conversation.md`

```python
conv_mgr = self.context.conversation_manager
umo = event.unified_msg_origin
conv_id = await conv_mgr.get_curr_conversation_id(umo)
await conv_mgr.new_conversation(umo, title="新分支")
```

## 8. Scheduled Tasks

See `agent/cron.md`

```python
cron_mgr = self.context.cron_manager
await cron_mgr.add_basic_job(name="job_name", cron_expression="0 * * * *", handler=my_handler)
```
