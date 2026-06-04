# LLM Invocation

Provider is the model capability entry point (Chat/STT/TTS/Embedding).

## Get Current Chat Provider ID

```python
prov_id = await ctx.get_current_chat_provider_id(umo)
```

## Simplified LLM Call (v4.5.7+)

```python
llm_resp = await ctx.llm_generate(
    chat_provider_id=prov_id,
    prompt="Hello!",
    system_prompt="You are a helpful assistant.",
)
print(llm_resp.completion_text)
```

## Tool Loop Agent (v4.5.7+)

```python
llm_resp = await ctx.tool_loop_agent(
    event=event,
    chat_provider_id=prov_id,
    prompt="搜索 AstrBot 相关信息",
    tools=ToolSet([SearchTool()]),
    max_steps=30,
    tool_call_timeout=60,
)
```

### Parameter Description

- `event`: AstrMessageEvent
- `chat_provider_id`: chat provider ID
- `prompt`: user prompt
- `contexts`: message history context (optional)
- `image_urls`: list of image URLs (optional)
- `tools`: ToolSet
- `system_prompt`: system prompt (optional)
- `max_steps`: maximum rounds (default 30)
- `tool_call_timeout`: single timeout in seconds (default 120)
- `**kwargs`: extension parameters (stream, agent_hooks, agent_context, etc.)

## Legacy Methods

```python
get_using_provider(umo) -> Provider | None
get_using_stt_provider(umo) -> STTProvider | None
get_using_tts_provider(umo) -> TTSProvider | None
get_provider_by_id(provider_id) -> Provider
get_all_providers() -> list[Provider]
```

## Agent Runner (v4.7.0+)

```python
runner = ctx.get_using_agent_runner(umo=event.unified_msg_origin)
runner = ctx.get_agent_runner_by_id(runner_id="your_runner_id")
```

## Notes

- Calls within a session must pass `umo`; otherwise it falls back to the default configuration
- `get_provider_by_id` does not necessarily return a chat provider
- Do not hardcode provider IDs; prefer reading from configuration
