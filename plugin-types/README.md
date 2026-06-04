# Plugin Type Selection Guide

Choose the appropriate plugin type based on your needs, then refer to the corresponding example code and review reports.

## Type Overview

| Type | Directory | Use Case | Core Mechanism |
|------|-----------|----------|----------------|
| Simple Command | `script/astrbot-plugin-demo/` | Basic command response | `@filter.command` |
| LLM Tool | `type1-llm-tool/` | Let AI call external capabilities | `FunctionTool` + `add_llm_tools` |
| Multi-Turn Conversation | `type2-session-waiter/` | Q&A, games, form collection | `@session_waiter` |
| Scheduled Task | `type3-scheduled-task/` | Timed reminders, data collection | `cron_manager` |
| LLM Hook | `type4-llm-hook/` | Intercept/modify LLM request/response | `@filter.on_llm_request/response` |
| Web API | `type5-web-api/` | Dashboard integration, frontend pages | `register_web_api` |
| Agent | `type6-agent-subagent/` | AI Agent multi-tool collaboration | `tool_loop_agent` + `ToolSet` |

## How to Choose

```
What does your plugin need to do?
│
├─ Respond to user commands (/xxx)
│   └─ Simple command plugin → script/astrbot-plugin-demo/
│
├─ Let AI automatically call your functionality
│   └─ LLM tool plugin → type1-llm-tool/
│
├─ Multi-turn Q&A, waiting for user input
│   └─ Multi-turn conversation plugin → type2-session-waiter/
│
├─ Scheduled execution, periodic tasks
│   └─ Scheduled task plugin → type3-scheduled-task/
│
├─ Modify/intercept AI behavior
│   └─ LLM hook plugin → type4-llm-hook/
│
├─ Frontend pages, API endpoints
│   └─ Web API plugin → type5-web-api/
│
└─ AI autonomously decides to call multiple tools
    └─ Agent sub-agent plugin → type6-agent-subagent/
```

## Combining Types

A single plugin can include multiple types simultaneously. For example:

- **Command + LLM Tool**: Respond to `/weather` command while also letting AI automatically call weather queries
- **LLM Hook + Command**: Intercept AI requests to inject context, while providing `/toggle` control switch
- **Scheduled Task + Web API**: Collect data on a schedule, display it on Dashboard via API

## File Structure for Each Type

Each type example includes:

- `main.py` — Complete runnable plugin code
- `metadata.yaml` — Plugin metadata
- `_conf_schema.json` — Configuration schema (if needed)
- `README.md` — Usage instructions

## Review Mechanism

**Each plugin type comes with a review report** showing common issues and passing criteria for that type.

In actual development, follow the complete review workflow in `review/review-workflow.md`.
