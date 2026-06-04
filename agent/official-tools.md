# AstrBot Official Tool List

Built-in tool list for AstrBot Core.

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

## Proactive Message

- `send_message_to_user` (injected when platform supports proactive messaging): Proactively send a message
  - `{"messages":[{"type":"plain","text":"任务已完成"}]}`

## Dynamic Handoff

- `transfer_to_<agent_name>` (subagent_orchestrator.main_enable=true): Transfer task
  - `{"input":"请处理这段文本并给出结构化结论"}`
