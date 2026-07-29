import datetime
from astrbot.api import logger
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star


class DailyReportPlugin(Star):
    """Scheduled task plugin demonstrating cron job registration and management."""

    def __init__(self, context: Context):
        super().__init__(context)
        self.cron_mgr = context.cron_manager

    async def initialize(self):
        """Register scheduled tasks"""
        try:
            await self.cron_mgr.add_basic_job(
                name="daily_report",
                cron_expression="0 9 * * *",
                handler=self._daily_handler,
                persistent=True,
                description="Daily report at 9:00 AM",
                enabled=True,
            )
            logger.info("Daily report cron job registered")
        except Exception as e:
            logger.error(f"Failed to register cron job: {e}")

    async def _daily_handler(self, payload: dict = None):
        """Scheduled task handler"""
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        logger.info(f"Executing daily report: {now}")

    @staticmethod
    def _job_attr(job, *names, default=""):
        for n in names:
            if hasattr(job, n):
                return getattr(job, n)
            if isinstance(job, dict) and n in job:
                return job[n]
        return default

    async def _list_jobs_safe(self):
        """list_jobs may be sync or async depending on AstrBot version."""
        result = self.cron_mgr.list_jobs()
        if hasattr(result, "__await__"):
            result = await result
        return result or []

    async def _delete_job_safe(self, name: str):
        result = self.cron_mgr.delete_job(name)
        if hasattr(result, "__await__"):
            await result

    @filter.command("cron_list")
    async def list_jobs(self, event: AstrMessageEvent):
        """List all scheduled tasks"""
        try:
            jobs = await self._list_jobs_safe()
        except Exception as e:
            yield event.plain_result(f"List failed: {e}")
            return
        if not jobs:
            yield event.plain_result("No scheduled tasks")
            return

        lines = ["Scheduled tasks:"]
        for job in jobs:
            name = self._job_attr(job, "name", "id", default="?")
            expr = self._job_attr(job, "cron_expression", "cron", "expression", default="?")
            enabled = self._job_attr(job, "enabled", default=True)
            lines.append(f"- {name} | {expr} | {'enabled' if enabled else 'disabled'}")
        yield event.plain_result("\n".join(lines))

    @filter.command("cron_delete")
    async def delete_job(self, event: AstrMessageEvent):
        """Delete a scheduled task by name. Usage: /cron_delete <name>"""
        # message_str may still contain the command token depending on platform
        raw = event.message_str.strip()
        parts = raw.split(None, 1)
        if raw.lower().startswith("cron_delete"):
            name = parts[1].strip() if len(parts) > 1 else ""
        else:
            name = raw
        if not name:
            yield event.plain_result("Usage: /cron_delete <task_name>")
            return
        try:
            await self._delete_job_safe(name)
            yield event.plain_result(f"Deleted task: {name}")
        except Exception as e:
            yield event.plain_result(f"Delete failed: {e}")

    async def terminate(self):
        """Clean up scheduled tasks"""
        try:
            await self._delete_job_safe("daily_report")
            logger.info("Daily report cron job cleaned up")
        except Exception as e:
            logger.warning(f"Error cleaning up cron job: {e}")
