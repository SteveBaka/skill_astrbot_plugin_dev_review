# Platform Adapter Interface

Platform adapters connect external messaging platforms to AstrBot. Plugins can register custom adapters.

## Register Adapter

```python
@register_platform_adapter(
    adapter_name="id",
    desc="Adapter description",
    default_config_tmpl={"token": ""},
    adapter_display_name="Display Name",
    logo_path="logo.png",
    support_streaming_message=True
)
```

## Platform Base Class

Inherit `Platform` and implement the following methods:

### Required

- `run() -> Coroutine`: Async blocking method, starts client and continuously listens
- `meta() -> PlatformMetadata`: Returns adapter metadata
- `send_by_session(session: MessageSession, message_chain: MessageChain)`: Send message via session

### Optional Override

- `terminate()`: Terminate platform operation
- `get_client() -> object`: Get platform client
- `webhook_callback(request) -> Any`: Unified webhook entry point

### Helper Methods

- `commit_event(event: AstrMessageEvent)`: Submit event to queue
- `get_stats() -> dict`: Get statistics

## PlatformMetadata

```python
PlatformMetadata(
    name="adapter_id",
    description="适配器描述",
    id="adapter_id",
    default_config_tmpl={},
    adapter_display_name="显示名",
    logo_path="logo.png",
    support_streaming_message=True,
    support_proactive_message=True,
)
```

## MessageSession

```python
MessageSession(
    platform_name="adapter_id",
    message_type=MessageType.GROUP_MESSAGE,
    session_id="session_id",
)
# String format: "platform_id:message_type:session_id"
```

## Complete Adapter Example

```python
from astrbot.api.platform import (
    Platform, AstrBotMessage, MessageMember, MessageType, PlatformMetadata
)
from astrbot.core.platform.register import register_platform_adapter
from astrbot.api.event import AstrMessageEvent, MessageChain
from astrbot.api.message_components import Plain

@register_platform_adapter("myplatform", "My Platform Adapter", default_config_tmpl={
    "token": "",
})
class MyPlatformAdapter(Platform):
    def __init__(self, platform_config: dict, platform_settings: dict, event_queue: asyncio.Queue):
        super().__init__(platform_config, event_queue)
        self.settings = platform_settings

    def meta(self) -> PlatformMetadata:
        return PlatformMetadata(
            name="myplatform",
            description="我的平台",
            id=self.config.get("id", "myplatform")
        )

    async def run(self):
        async def on_message(data):
            abm = await self.convert_message(data)
            await self.handle_msg(abm)
        # Start client listening...

    async def convert_message(self, data: dict) -> AstrBotMessage:
        abm = AstrBotMessage()
        abm.type = MessageType.GROUP_MESSAGE
        abm.session_id = data["session_id"]
        abm.message_id = data["message_id"]
        abm.sender = MessageMember(user_id=data["user_id"], nickname=data["nickname"])
        abm.message_str = data["content"]
        abm.message = [Plain(text=data["content"])]
        abm.raw_message = data
        return abm

    async def handle_msg(self, message: AstrBotMessage):
        event = MyPlatformEvent(
            message_str=message.message_str,
            message_obj=message,
            platform_meta=self.meta(),
            session_id=message.session_id,
            client=self.client,
        )
        self.commit_event(event)

    async def send_by_session(self, session, message_chain):
        await super().send_by_session(session, message_chain)

class MyPlatformEvent(AstrMessageEvent):
    def __init__(self, message_str, message_obj, platform_meta, session_id, client):
        super().__init__(message_str, message_obj, platform_meta, session_id)
        self.client = client

    async def send(self, message: MessageChain):
        for comp in message.chain:
            if isinstance(comp, Plain):
                await self.client.send_text(self.get_sender_id(), comp.text)
        await super().send(message)
```

## Notes

- `run()` must be a blocking method that continuously listens for messages
- `convert_message()` must correctly set `session_id`, which determines LLM context isolation
- `commit_event()` submits events to the queue; do not omit it
- Event classes must implement the `send()` method, and call `await super().send(message)` at the end

## config_metadata: Avoid Built-in Field Conflicts

<!-- Source: Real-world bug from astrbot_plugin_synochat_adapter — "enable" in default_config_tmpl caused WebUI toggle position swap -->

AstrBot automatically manages certain fields for **all** platform adapters. These are **built-in fields** that you must NOT redefine in `config_metadata`:

| Built-in Field | Purpose |
|---------------|---------|
| `id` | Adapter instance ID (auto-generated) |
| `enable` | Whether the adapter is enabled (auto-managed by AstrBot) |

### The Problem

If you include `"enable"` or `"id"` in your `default_config_tmpl`, AstrBot's WebUI may:
- Render the "Enable" toggle in the wrong position
- Show incorrect hint text (e.g., borrowing hints from other adapters)
- Cause the adapter name and enable switch to swap positions

### ❌ WRONG: Including built-in fields in default_config_tmpl

```python
@register_platform_adapter(
    "my_adapter",
    "My Adapter",
    default_config_tmpl={
        "id": "my_adapter",       # ❌ REMOVE — AstrBot manages this
        "enable": True,           # ❌ REMOVE — AstrBot manages this
        "api_key": "",            # ✅ Custom field
        "base_url": "",           # ✅ Custom field
    },
    config_metadata={...},
)
```

### ✅ CORRECT: Only custom fields in default_config_tmpl

```python
@register_platform_adapter(
    "my_adapter",
    "My Adapter",
    default_config_tmpl={
        "api_key": "",            # ✅ Custom field
        "base_url": "",           # ✅ Custom field
    },
    config_metadata={
        "api_key": {
            "description": "API Key",
            "type": "string",
            "hint": "Your API key",
            "secret": True,
        },
        "base_url": {
            "description": "Service URL",
            "type": "string",
            "hint": "Base URL of the service",
        },
    },
)
```

### config_metadata Type and Hint Rules

- `type` must be one of: `string`, `text`, `int`, `float`, `bool`
- `hint` should describe what the field does and any format requirements
- `secret: True` masks the value in the WebUI (for API keys, tokens)
- `invisible: True` hides the field from the WebUI entirely
- All custom fields in `default_config_tmpl` should have corresponding entries in `config_metadata`
