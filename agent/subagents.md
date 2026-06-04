# Sub-Agents (Handoff)

Subagent is a handoff tool for the main Agent. The main model transfers tasks via `transfer_to_<name>`.

## Configuration-Based (Recommended)

```json
{
  "subagent_orchestrator": {
    "main_enable": true,
    "remove_main_duplicate_tools": false,
    "router_system_prompt": "You are a task router...",
    "agents": [
      {
        "enabled": true,
        "name": "writer",
        "public_description": "负责技术文档整理与重写",
        "persona_id": null,
        "system_prompt": "你是文档子智能体，输出精简且结构化。",
        "provider_id": "openai_gpt4o_mini",
        "tools": ["search_docs", "rewrite_text"]
      }
    ]
  }
}
```

### agents[] Fields

- `enabled`: Whether enabled
- `name`: Sub-agent name; tool name is generated as `transfer_to_<name>`
- `public_description`: Tool description exposed to the main model (determines whether it is called)
- `persona_id`: Optional; when present, persona configuration is used preferentially
- `system_prompt`: Used when no persona matches
- `provider_id`: Optional, dedicated chat provider for the sub-agent
- `tools`: List of available tool names (strings)

## Runtime Rules

- When `main_enable=true`, the main Agent includes all handoff tools
- When `remove_main_duplicate_tools=true`, tools with the same name already assigned are removed from the main Agent
- `router_system_prompt` is appended to the main Agent's system_prompt
- When `provider_id` is not empty, that provider is used preferentially

## SDK/Code-Based (Advanced)

```python
from astrbot.api import agent

@agent(name="writer", instruction="你是写作子智能体。")
async def writer_agent(event):
    return None
```

## MUST

- `name` must be non-empty and unique within the same instance
- `public_description` must describe applicable tasks; do not write vague persona descriptions
- `tools` must be explicitly written as a string list
