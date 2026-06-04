# Context Compression

Controls how conversation history is compressed when it exceeds token limits.

## Parameters for tool_loop_agent

```python
resp = await context.tool_loop_agent(
    event=event,
    chat_provider_id=provider_id,
    prompt="...",
    tools=ToolSet([...]),
    # Compression parameters:
    enforce_max_turns=50,
    truncate_turns=20,
    llm_compress_instruction="Summarize the conversation so far.",
    llm_compress_keep_recent=5,
    llm_compress_provider=None,  # uses default provider
    custom_token_counter=None,
    custom_compressor=None,
)
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `enforce_max_turns` | int | Hard limit on conversation turns |
| `truncate_turns` | int | Truncate to N most recent turns |
| `llm_compress_instruction` | str | Instruction for LLM-based compression |
| `llm_compress_keep_recent` | int | Keep N most recent turns during compression |
| `llm_compress_provider` | str | Provider ID for compression (defaults to main) |
| `custom_token_counter` | callable | Custom token counting function |
| `custom_compressor` | callable | Custom compression function |

## Helper Methods

```python
provider_id = await context.get_provider_by_id("your_provider_id")
current_id = await context.get_current_chat_provider_id(umo)
config = context.get_config()
```
