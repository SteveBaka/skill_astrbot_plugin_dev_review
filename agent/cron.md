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
