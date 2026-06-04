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

    @filter.command("cron_list")
    async def list_jobs(self, event: AstrMessageEvent):
        """List all scheduled tasks"""
        jobs = self.cron_mgr.list_jobs()
        if not jobs:
            yield event.plain_result("No scheduled tasks")
            return

        lines = ["Scheduled tasks:"]
        for job in jobs:
            lines.append(f"- {job.name} | {job.cron_expression} | {'enabled' if job.enabled else 'disabled'}")
        yield event.plain_result("\n".join(lines))

    @filter.command("cron_delete")
    async def delete_job(self, event: AstrMessageEvent):
        """Delete a scheduled task by name. Usage: /cron_delete <name>"""
        name = event.message_str.strip()
        if not name:
            yield event.plain_result("Usage: /cron_delete <task_name>")
            return
        try:
            self.cron_mgr.delete_job(name)
            yield event.plain_result(f"Deleted task: {name}")
        except Exception as e:
            yield event.plain_result(f"Delete failed: {e}")

    async def terminate(self):
        """Clean up scheduled tasks"""
        try:
            self.cron_mgr.delete_job("daily_report")
            logger.info("Daily report cron job cleaned up")
        except Exception as e:
            logger.warning(f"Error cleaning up cron job: {e}")
