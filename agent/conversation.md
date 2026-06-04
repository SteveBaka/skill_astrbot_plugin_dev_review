# Conversation and Dialog Branches

Plugins manage conversation branches through `self.context.conversation_manager`.

## Entry Point

```python
conv_mgr = self.context.conversation_manager
umo = event.unified_msg_origin
```

## Conversation Dataclass

```python
@dataclass
class Conversation:
    platform_id: str          # Platform ID in AstrBot
    user_id: str              # User ID associated with the conversation
    cid: str                  # Conversation ID (UUID format)
    history: str = ""         # Conversation history as string
    title: str | None = ""    # Conversation title
    persona_id: str | None = ""  # Associated persona ID
    created_at: int = 0       # Creation timestamp
    updated_at: int = 0       # Last update timestamp
```

## ConversationManager Methods

- `register_on_session_deleted(callback)`: Register session deletion callback
- `new_conversation(umo, platform_id=None, content=None, title=None, persona_id=None) -> str`: Create new branch
- `switch_conversation(umo, conversation_id)`: Switch branch
- `delete_conversation(umo, conversation_id=None)`: Delete branch (deletes current if no id provided)
- `delete_conversations_by_user_id(umo)`: Delete all branches under this session
- `get_curr_conversation_id(umo) -> str | None`: Current branch ID
- `get_conversation(umo, conversation_id, create_if_not_exists=False) -> Conversation | None`: Read branch
- `get_conversations(umo=None, platform_id=None) -> list[Conversation]`: List branches
- `get_filtered_conversations(page, page_size, platform_ids, search_query) -> tuple[list, int]`: Paginated filter
- `update_conversation(umo, conversation_id=None, history=None, title=None, persona_id=None, token_usage=None)`: Update
- `add_message_pair(cid, user_message, assistant_message)`: Append message pair
- `get_human_readable_context(umo, conversation_id, page, page_size) -> tuple[list[str], int]`: Readable context

## Minimal Example

```python
cid = await conv_mgr.get_curr_conversation_id(umo)
cid = await conv_mgr.new_conversation(umo, title="New branch")
await conv_mgr.update_conversation(umo, conversation_id=cid, title="Renamed", persona_id="assistant_default")
contexts, total = await conv_mgr.get_human_readable_context(umo, cid, page=1, page_size=10)
```

## add_message_pair Example

Quickly add an LLM interaction record to conversation history:

```python
from astrbot.core.agent.message import (
    AssistantMessageSegment, UserMessageSegment, TextPart,
)

conv_mgr = self.context.conversation_manager
provider_id = await self.context.get_current_chat_provider_id(event.unified_msg_origin)
curr_cid = await conv_mgr.get_curr_conversation_id(event.unified_msg_origin)

user_msg = UserMessageSegment(content=[TextPart(text="hi")])
llm_resp = await self.context.llm_generate(
    chat_provider_id=provider_id,
    contexts=[user_msg],
)
await conv_mgr.add_message_pair(
    cid=curr_cid,
    user_message=user_msg,
    assistant_message=AssistantMessageSegment(
        content=[TextPart(text=llm_resp.completion_text)]
    ),
)
```

## MUST

- All branch operations must use the current session's `umo`
- When updating history, must pass OpenAI-style `list[dict]` message structure

---

## LLM Request Prompt Injection

Intercept and modify LLM requests via `@filter.on_llm_request()`:

```python
@filter.on_llm_request()
async def on_req(self, event: AstrMessageEvent, req: ProviderRequest):
    req.system_prompt += "\n\nGlobal rule: answer concisely."
```

### ProviderRequest Key Properties

| Property | Type | Purpose |
|----------|------|---------|
| `system_prompt` | `str` | System prompt |
| `prompt` | `str \| None` | Current round user input |
| `extra_user_content_parts` | `list[ContentPart]` | Additional content after user message |
| `contexts` | `list[dict]` | Full context in OpenAI format |

### Injection Strategies

- **`system_prompt += ...`**: Append stable long-term settings. **Warning**: changing content each round breaks cache, increasing costs 7-20x <!-- Source: guides/listen-message-event.md §LLM 请求时 WARNING -->
- **`extra_user_content_parts.append(...)`**: Append per-round dynamic context without affecting cache. Recommended for "current time", "affinity", "short-term memory" etc.
- **`req.contexts = [...]`**: Directly replace full context (higher risk)

### Dynamic Content Example (v4.24.0+)

```python
from astrbot.core.agent.message import TextPart

@filter.on_llm_request()
async def add_dynamic_context(self, event, req):
    part = TextPart(text=f"<context>Current time: {datetime.now()}</context>")
    part.mark_as_temp()  # Not written to conversation history
    req.extra_user_content_parts.append(part)
```
