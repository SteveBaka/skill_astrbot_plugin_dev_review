import time
from astrbot.api import logger
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, StarTools
from quart import jsonify


PLUGIN_NAME = "astrbot_plugin_dashboard"


class DashboardPlugin(Star):
    """Web API plugin demonstrating Dashboard page integration."""

    def __init__(self, context: Context):
        super().__init__(context)
        self.start_time = time.time()

        context.register_web_api(
            f"/{PLUGIN_NAME}/status",
            self.api_status,
            ["GET"],
            "Get plugin status",
        )
        context.register_web_api(
            f"/{PLUGIN_NAME}/stats",
            self.api_stats,
            ["GET"],
            "Get statistics",
        )

    async def initialize(self):
        """Initialize plugin"""
        self.data_dir = StarTools.get_data_dir()
        self.data_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"Dashboard plugin loaded, data dir: {self.data_dir}")

    async def api_status(self):
        """Status API"""
        uptime = int(time.time() - self.start_time)
        return jsonify({
            "status": "running",
            "uptime_seconds": uptime,
        })

    async def api_stats(self):
        """Statistics API"""
        return jsonify({
            "plugin_name": PLUGIN_NAME,
            "data_dir": str(self.data_dir),
        })

    @filter.command("dashboard")
    async def dashboard_info(self, event: AstrMessageEvent):
        """Show Dashboard info"""
        yield event.plain_result(
            f"Dashboard URL: /api/plug/{PLUGIN_NAME}/status\n"
            f"Stats URL: /api/plug/{PLUGIN_NAME}/stats"
        )

    async def terminate(self):
        """Clean up resources"""
        logger.info("Dashboard plugin unloaded")
