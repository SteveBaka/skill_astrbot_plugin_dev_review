# Agent System Overview

The Agent is AstrBot's intelligent agent system, composed of instructions + tools + providers + runtime.

## Quick Links

- Tool Definition: `agent/tools.md`
- LLM Invocation: `agent/invoke-llm.md`
- Hook System: `agent/hooks.md`
- Conversation Management: `agent/conversation.md`
- Scheduled Tasks: `agent/cron.md`
- Sub-Agents: `agent/subagents.md`
- Official Tools: `agent/official-tools.md`

## Minimal Agent Example

```python
from astrbot.core.agent.tool import ToolSet

resp = await self.context.tool_loop_agent(
    event=event,
    chat_provider_id=provider_id,
    prompt="搜索 AstrBot 相关信息",
    tools=ToolSet([SearchTool()]),
    max_steps=30,
)
print(resp.completion_text)
```

## Key Parameters

- `event`: AstrMessageEvent, the session context source
- `chat_provider_id`: chat provider ID
- `prompt`: user prompt
- `tools`: ToolSet, the set of tools the AI can call
- `system_prompt`: system prompt (optional)
- `max_steps`: maximum tool call rounds (default 30)
- `tool_call_timeout`: single tool call timeout in seconds (default 120)
- `agent_hooks`: Agent runtime hooks (optional)
- `stream`: whether to stream output (optional)
