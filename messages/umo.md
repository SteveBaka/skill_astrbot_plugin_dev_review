# Unified Message Origin (UMO)

UMO is AstrBot's core identifier for cross-platform session recognition.

## Format

`platform_id:message_type:session_id`

- **`platform_id`**: Platform ID (e.g., `aiocqhttp`, `qqofficial`)
- **`message_type`**: Message type (`group` or `private`)
- **`session_id`**: Session ID (group number or user ID)

## How to Get

```python
umo = event.unified_msg_origin  # "aiocqhttp:group:123456"
```

## Usage Scenarios

| Scenario | Usage | Reference |
|----------|-------|-----------|
| Proactive messaging | `context.send_message(umo, chain)` | `design_standards/context_usage.md` |
| Conversation branch management | `conv_mgr.get_curr_conversation_id(umo)` | `agent/conversation.md` |
| LLM Provider retrieval | `await context.get_current_chat_provider_id(umo)` | `agent/invoke-llm.md` |
| KV storage isolation | Data automatically isolated by plugin ID | `storage_utils/kv_storage.md` |
| Scheduled task payload | `{"session": umo, "note": "指令"}` | `agent/cron.md` |

> For complete UMO property details, see `messages/events.md`
