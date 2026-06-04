# Message Event (AstrMessageEvent)

`AstrMessageEvent` is the core context object for plugin processing logic.

> For message model structure, see `messages/model.md`
> For message component types, see `messages/components.md`
> For UMO format, see `messages/umo.md`

## Core Properties

- `event.unified_msg_origin` (UMO): Unified identifier `platform_id:message_type:session_id`, supports getter/setter
- `event.session_id`: Session ID, supports getter/setter
- `event.message_str`: Plain text message
- `event.message_obj`: AstrBotMessage full message object
- `event.platform_meta`: Platform metadata
- `event.session`: MessageSession object
- `event.role`: User role ("member" / "admin")
- `event.is_wake`: Whether woken up
- `event.call_llm`: Whether to call LLM

## Information Retrieval Methods

- `get_platform_name() -> str`: Platform type
- `get_message_str() -> str`: Message text
- `get_message_outline() -> str`: Message summary (images become `[图片]`)
- `get_messages() -> list`: Message chain
- `get_message_type() -> MessageType`: Message type
- `get_session_id() -> str`: Session ID
- `get_group_id() -> str`: Group ID (returns empty string for private chat)
- `get_sender_id() -> str`: Sender ID
- `get_sender_name() -> str`: Sender nickname
- `is_private_chat() -> bool`: Whether private chat
- `is_admin() -> bool`: Whether admin

## Message Sending Methods

- `send(message: MessageChain)`: Send message
- `send_streaming(generator, use_fallback)`: Streaming message
- `react(emoji: str)`: Emoji reaction
- `get_group(group_id) -> Group | None`: Get group data

## Result Construction Methods

- `plain_result(text) -> MessageEventResult`: Text result
- `image_result(url_or_path) -> MessageEventResult`: Image result
- `chain_result(chain: list) -> MessageEventResult`: Message chain result
- `make_result() -> MessageEventResult`: Empty result

## Event Control

- `stop_event()`: Stop event propagation
- `continue_event()`: Continue event propagation
- `is_stopped() -> bool`: Whether stopped
- `should_call_llm(bool)`: Whether to call LLM
- `set_result(result)`: Set event result
- `get_result() -> MessageEventResult | None`: Get result

## Dynamic Session Switching

Modifying `event.unified_msg_origin` can dynamically redirect the event to another session context. Internally re-parsed via `MessageSession.from_str()`.

> **Note**: Modifying UMO will cause `platform_name` and `message_type` to change simultaneously. If you only need to modify the user ID, prefer using the `event.session_id` setter.
