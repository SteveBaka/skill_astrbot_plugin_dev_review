# Message Model (AstrBotMessage)

`AstrBotMessage` is a standardized message object generated at the adapter layer, masking differences across platforms so plugins can "write once, run everywhere."

> For how adapters construct this object, see `platform_adapters/message_conversion.md`
> For message component types, see `messages/components.md`
> For event objects, see `messages/events.md`

## AstrBotMessage Structure

```python
class AstrBotMessage:
    type: MessageType      # GROUP_MESSAGE / FRIEND_MESSAGE / OTHER_MESSAGE
    self_id: str           # Bot ID
    session_id: str        # Session ID, determines context isolation
    message_id: str        # Message ID
    group_id: str          # Group ID (empty for private chat)
    sender: MessageMember  # Sender info (contains user_id and nickname)
    message: list[BaseMessageComponent]  # Message chain (component list)
    message_str: str       # Plain text summary
    raw_message: object    # Raw platform message object
    timestamp: int         # Timestamp
```

## Property Details

- **`session_id`**: Core field that determines LLM conversation context isolation
- **`message_str`**: Plain text content commonly used in plugin logic
- **`message`**: Structured message content, composed of various message components
- **`raw_message`**: Raw platform data, used for debugging or platform-specific operations

## MessageType Enum

- `MessageType.GROUP_MESSAGE`: Group message
- `MessageType.FRIEND_MESSAGE`: Private message
- `MessageType.OTHER_MESSAGE`: Other message

## MessageMember

```python
MessageMember(user_id="uid", nickname="nickname")
```

## Group

```python
Group(
    group_id="123",
    group_name="群名",
    group_avatar="头像URL",
    group_owner="群主ID",
    group_admins=["admin1", "admin2"],
    members=[MessageMember(...)],
)
```
