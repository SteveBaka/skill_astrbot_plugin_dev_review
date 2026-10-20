# AstrBot Official Tool List

Built-in tool list for AstrBot Core.

> **AstrBot ≥4.28 (#9767)**: built-in web search provider **AnySearch** may appear alongside other search providers. Tool names/availability still depend on profile config (`websearch` / provider settings) — do not hardcode provider-specific tool names in plugins; discover via runtime when needed.

## Web Search (provider-dependent)

- Web search tools are injected when a web-search provider is enabled on the profile.
  Providers selectable on `≥4.29.1`: **SerpApi**, DeepSeek Search API, Tavily,
  Baidu AI Search, Bocha, Brave, Firecrawl, Exa, AnySearch
  (`websearch_provider` in `CONFIG_METADATA_3`; #9767 added AnySearch in 4.28,
  #10599 SerpApi + DeepSeek in 4.29.1).
- **4.28.1 (#9979)** fixed field loss / swallowed error codes / parameter validation in
  web-search tools — if your plugin wraps search results, expect stricter arg
  validation on new cores.
- Provider-specific extras: SerpApi adds Google web / image / scholar / finance search
  (#10601); DeepSeek adds web search + page-content extraction (#10599). Tool names and
  availability remain **profile-dependent** — never hardcode a provider's tool name;
  discover at runtime.
- Config keys follow the provider (`websearch_<provider>_key`, list-valued for
  round-robin, `secret: true`). A plugin that ships its own search wrapper should keep
  its own key under its own namespace rather than reusing `websearch_*`.

## Computer Use

- `astrbot_execute_shell` (sandbox|local): Execute shell commands
  - `{"command":"pwd","background":false}`
- `astrbot_execute_ipython` (sandbox): Execute code in sandbox IPython
  - `{"code":"print(1+1)","silent":false}`
- `astrbot_execute_python` (local): Execute Python locally (admin only)
  - `{"code":"print(1+1)","silent":false}`
- `astrbot_upload_file` (sandbox): Upload file to sandbox
  - `{"local_path":"C:/tmp/a.txt"}`
- `astrbot_download_file` (sandbox): Download file from sandbox
  - `{"remote_path":"/workspace/out.txt","also_send_to_user":true}`

## Knowledge Base

- `astr_kb_search` (kb_agentic_mode=true): Search knowledge base
  - `{"query":"AstrBot provider isolation"}`

## Cron / Proactive Task

- `create_future_task` (add_cron_tools=true): Create a future task
  - `{"note":"明早提醒我同步日报","cron_expression":"0 9 * * *"}`
- `delete_future_task`: Delete a future task
  - `{"job_id":"cron_xxx"}`
- `list_future_tasks`: List future tasks
  - `{"job_type":"active_agent"}`

> **≥4.28.0 (#9801)**: `max_agent_step` applies to **scheduled / background** agent tasks as well.

## Proactive Message

- `send_message_to_user` (injected when platform supports proactive messaging): Proactively send a message
  - `{"messages":[{"type":"plain","text":"任务已完成"}]}`

## Dynamic Handoff

- `transfer_to_<agent_name>` (subagent_orchestrator.main_enable=true): Transfer task
  - `{"input":"请处理这段文本并给出结构化结论"}`

## OpenAI tool schema order (≥4.28.0 #9798)

Core **sorts tool schemas alphabetically by name** when building OpenAI-compatible tool lists. Plugin `FunctionTool.name` uniqueness still matters; registration order no longer controls provider-visible schema order.
