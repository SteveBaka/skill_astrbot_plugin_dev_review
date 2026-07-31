import datetime
from astrbot.api import logger
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star


class DailyReportPlugin(Star):
    """Scheduled task plugin demonstrating cron job registration and management."""

    def __init__(self, context: Context):
        super().__init__(context)
        self.cron_mgr = context.cron_manager

    JOB_NAME = "daily_report"

    async def initialize(self):
        """Register scheduled tasks (idempotent).

        Core API (v4.26.x): add_basic_job always inserts a new DB row with a new
        job_id; delete_job expects job_id (UUID), NOT the human name. Using
        name as job_id does not remove prior rows — every reload/reinstall with
        persistent=True stacks duplicate "daily_report" entries. Deduplicate by
        name → delete each job_id → add once.
        """
        try:
            removed = await self._delete_jobs_by_name(self.JOB_NAME)
            if removed:
                logger.info(f"Removed {removed} existing cron job(s) named {self.JOB_NAME}")
            await self.cron_mgr.add_basic_job(
                name=self.JOB_NAME,
                cron_expression="0 9 * * *",
                handler=self._daily_handler,
                persistent=True,
                description="Daily report at 9:00 AM",
                enabled=True,
            )
            logger.info("Daily report cron job registered (idempotent by name)")
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

    async def _delete_job_by_id(self, job_id: str):
        """delete_job requires job_id (UUID), not display name."""
        result = self.cron_mgr.delete_job(job_id)
        if hasattr(result, "__await__"):
            await result

    async def _delete_jobs_by_name(self, name: str) -> int:
        """Delete every job whose .name matches (may be multiple duplicates)."""
        jobs = await self._list_jobs_safe()
        n = 0
        for job in jobs:
            jname = self._job_attr(job, "name", default="")
            jid = self._job_attr(job, "job_id", "id", default="")
            if jname == name and jid:
                try:
                    await self._delete_job_by_id(str(jid))
                    n += 1
                except Exception as e:
                    logger.warning(f"Failed to delete cron job {jid}: {e}")
        return n

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
            name = self._job_attr(job, "name", default="?")
            jid = self._job_attr(job, "job_id", "id", default="?")
            expr = self._job_attr(job, "cron_expression", "cron", "expression", default="?")
            enabled = self._job_attr(job, "enabled", default=True)
            lines.append(
                f"- {name} | id={jid} | {expr} | {'enabled' if enabled else 'disabled'}"
            )
        yield event.plain_result("\n".join(lines))

    @filter.command("cron_delete")
    async def delete_job(self, event: AstrMessageEvent):
        """Delete scheduled tasks by name (all duplicates) or by job_id.

        Usage: /cron_delete <name_or_job_id>
        """
        raw = event.message_str.strip()
        parts = raw.split(None, 1)
        if raw.lower().startswith("cron_delete"):
            target = parts[1].strip() if len(parts) > 1 else ""
        else:
            target = raw
        if not target:
            yield event.plain_result(
                "Usage: /cron_delete <task_name|job_id>\n"
                "Tip: name deletes all jobs with that name; job_id deletes one row."
            )
            return
        try:
            jobs = await self._list_jobs_safe()
            ids = []
            for job in jobs:
                jname = str(self._job_attr(job, "name", default=""))
                jid = str(self._job_attr(job, "job_id", "id", default=""))
                if target == jid or target == jname:
                    if jid:
                        ids.append(jid)
            if not ids:
                yield event.plain_result(f"No job matched: {target}")
                return
            for jid in ids:
                await self._delete_job_by_id(jid)
            yield event.plain_result(f"Deleted {len(ids)} job(s) matching: {target}")
        except Exception as e:
            yield event.plain_result(f"Delete failed: {e}")

    async def terminate(self):
        """Clean up scheduled tasks by name (all duplicates)."""
        try:
            n = await self._delete_jobs_by_name(self.JOB_NAME)
            logger.info(f"Cleaned up {n} daily_report cron job(s)")
        except Exception as e:
            logger.warning(f"Error cleaning up cron job: {e}")
