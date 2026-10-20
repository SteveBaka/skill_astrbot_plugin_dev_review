# Scheduled Tasks (Cron)

Execute logic on a schedule or wake up the AI. AI tasks trigger the generation of a `CronMessageEvent`.

Accessed via `self.context.cron_manager`.

## Register Python Function (Basic Job)

```python
await cron_mgr.add_basic_job(
    name="任务名",
    cron_expression="*/5 * * * *",
    handler=self.your_method,
    payload={"key": "value"},
    persistent=False,
    description="任务描述",
    handler_params={"extra": "data"},
    enabled=True,
)
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `name` | str | Unique identifier |
| `cron_expression` | str | Standard cron (`minute hour day month weekday`) |
| `handler` | Callable | Async handler function |
| `payload` | dict | Context data |
| `persistent` | bool | Persist (survives restarts) |
| `description` | str | Description (v4.22.2) |
| `handler_params` | dict | Extra parameters (v4.22.2) |
| `enabled` | bool | Whether enabled (v4.22.2) |

> **Timezone (v4.27.3+ #9579/#9581)**: cron jobs inherit AstrBot's configured
> timezone (Dashboard → 设置 shows the effective AstrBot time). No per-job
> timezone param needed — the cron expression is evaluated in the system/AstrBot
> timezone.

> **Agent steps (v4.28.0+ #9801)**: profile / system `max_agent_step` now applies to
> **scheduled-task and background-task agents**, not only interactive tool loops.
> Active cron jobs (`add_active_job`) can fail or stop earlier if the step budget is low.
> Failures are recorded when the runner ends in an error state (#9987 on 4.28.1).

> **Plugin filtering in cron agents (v4.29.0+ #10163)**: the woke agent now honors the
> session's `plugin_set`, so a cron job's **hooks and LLM tools** are filtered by the same
> policy as an interactive turn. Source: `cron/manager.py` reads
> `cfg.get("plugin_set", ["*"])` and sets `cron_event.plugins_name`
> (`None` when the set is `["*"]`).
>
> | Session `plugin_set` | Plugins whose hooks/tools run |
> |---|---|
> | `["allowed"]` | `allowed` + reserved |
> | `[]` | reserved only |
> | `["*"]` / absent | everything |
>
> Consequence for plugins: on 4.29+ a plugin scheduled/managed by a profile that does not
> include you in `plugin_set` will see its scheduled-task hooks go silent — this is not a
> bug in your plugin. On 4.28.x the filter was not applied to cron agents.

> **Dashboard (v4.28+)**: Agent Runner settings are **embedded in each profile**, not a
> standalone model-provider page. Logs / traces / conversations live under **Data & Logs**.

## Register AI Wake-up (Active Agent Job)

```python
await cron_mgr.add_active_job(
    name="AI 定时任务",
    cron_expression="0 8 * * *",
    payload={"session": "UMO", "note": "指令"},
    run_once=False,
    description="每日早报",
)
```

## Maintenance Methods

- `delete_job(job_id: str)`: Delete a job
- `list_jobs(job_type=None) -> list[CronJob]`: List jobs
- `update_job(job_id, **kwargs) -> CronJob | None`: Update a job

## Cron Expression Quick Reference

| Expression | Meaning |
|------------|---------|
| `*/5 * * * *` | Every 5 minutes |
| `0 9 * * *` | Every day at 9:00 |
| `0 */2 * * *` | Every 2 hours |
| `0 9 * * 1` | Every Monday at 9:00 |
| `0 0 1 * *` | 1st of every month at 0:00 |
