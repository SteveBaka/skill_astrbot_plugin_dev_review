import aiohttp
from astrbot.api import logger
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star
from pydantic import Field
from pydantic.dataclasses import dataclass
from astrbot.core.agent.tool import FunctionTool
from astrbot.core.agent.run_context import ContextWrapper
from astrbot.core.astr_agent_context import AstrAgentContext


@dataclass
class WeatherTool(FunctionTool[AstrAgentContext]):
    """LLM Tool for weather queries. AI can call this automatically."""

    name: str = "get_weather"
    description: str = "Get current weather for a specified city"
    parameters: dict = Field(
        default_factory=lambda: {
            "type": "object",
            "properties": {
                "city": {
                    "type": "string",
                    "description": "City name, e.g. Beijing, Shanghai",
                }
            },
            "required": ["city"],
        }
    )

    async def call(
        self, context: ContextWrapper[AstrAgentContext], **kwargs
    ) -> str:
        city = kwargs.get("city", "")
        if not city:
            return "Error: Missing 'city' parameter"

        try:
            async with aiohttp.ClientSession() as session:
                url = f"https://wttr.in/{city}?format=3"
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    if resp.status != 200:
                        return f"Error: Weather service returned {resp.status}"
                    text = await resp.text()
                    return text.strip()
        except aiohttp.ClientError as e:
            logger.error(f"Weather query network error: {e}")
            return f"Error: Network request failed: {e}"
        except Exception as e:
            logger.error(f"Weather query unknown error: {e}")
            return f"Error: Query failed: {e}"


class WeatherPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        self.context.add_llm_tools(WeatherTool())

    async def initialize(self):
        logger.info("Weather plugin loaded, WeatherTool registered to global tool pool")

    @filter.command("weather")
    async def weather_cmd(self, event: AstrMessageEvent):
        """Query weather manually. Usage: /weather <city>"""
        city = event.message_str.strip()
        if not city:
            yield event.plain_result("Usage: /weather <city_name>")
            return

        tool = WeatherTool()
        result = await tool.call(ContextWrapper(None), city=city)
        yield event.plain_result(result)

    async def terminate(self):
        logger.info("Weather plugin unloaded")
