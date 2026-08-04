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

## Config: follow official `register_platform_adapter`

**Source of truth**: [`astrbot/core/platform/register.py`](https://github.com/AstrBotDevs/AstrBot/blob/master/astrbot/core/platform/register.py) and [plugin-platform-adapter.md](https://docs.astrbot.app/dev/plugin-platform-adapter.html) (FakePlatform).

### Core auto-fills (do not re-invent)

If `default_config_tmpl` is not `None`, the decorator ensures:

| Key | If missing, core sets |
|-----|------------------------|
| `type` | adapter name |
| `enable` | `False` |
| `id` | adapter name |

**Author practice (official sample):** only put **custom** keys (`token`, `username`, …) in `default_config_tmpl`. Prefer **not** listing `id` / `enable` yourself so WebUI and core stay consistent. Re-listing them is redundant; wrong `config_metadata` for those keys has caused toggle/layout glitches historically.

### Do NOT use `_conf_schema.json` for adapters

`_conf_schema.json` is for **Star plugins** (插件配置). Platform instances are configured under **消息平台** via `default_config_tmpl` + `config_metadata` only.

### ✅ CORRECT (matches official FakePlatform style)

```python
@register_platform_adapter(
    "my_adapter",
    "My Adapter",
    default_config_tmpl={
        "api_key": "",
        "base_url": "",
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

### ❌ Avoid

```python
default_config_tmpl={
    "id": "my_adapter",   # core will set if omitted
    "enable": True,       # core will set if omitted
    "api_key": "",
}
# and never ship _conf_schema.json in an adapter package
```

### FIX-32: prefix custom config_metadata field names

`config_service.inject_platform_metadata_with_i18n` merges **all** adapters'
`config_metadata` into ONE shared `platform_group.metadata.platform.items` dict
via `dict.update()` (by field name). Core built-ins in that dict include
`port` (回调服务器端口), `callback_server_host`, `unified_webhook_mode`,
`webhook_uuid`. **Redefining any of these names overwrites the built-in entry
(and its `condition`) for every adapter's form** — e.g. QQ 官方/公众号 forms
would show your adapter's `port` description.

**Always prefix custom fields** with your adapter id:

```python
# ✅ prefixed (safe)
default_config_tmpl={"xx_token": "", "xx_port": 7300},
config_metadata={
    "xx_port": {"description": "Platform WebUI 端口", "type": "int", ...},
}
# read: self.config.get("xx_port")
```

Reviewer warns (`FIX-32`) on core built-in names in tmpl/metadata.

### config_metadata Type and Hint Rules

- `type` must be one of: `string`, `text`, `int`, `float`, `bool`
- `hint` should describe what the field does and any format requirements
- `secret: True` masks the value in the WebUI (for API keys, tokens)
- `invisible: True` hides the field from the WebUI entirely
- All custom fields in `default_config_tmpl` should have corresponding entries in `config_metadata`
