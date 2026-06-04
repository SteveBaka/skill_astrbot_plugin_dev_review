import aiohttp
from astrbot.api import logger
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star
from pydantic import Field
from pydantic.dataclasses import dataclass
from astrbot.core.agent.tool import FunctionTool, ToolSet
from astrbot.core.agent.run_context import ContextWrapper
from astrbot.core.astr_agent_context import AstrAgentContext


@dataclass
class SearchWebTool(FunctionTool[AstrAgentContext]):
    """Web search tool"""

    name: str = "search_web"
    description: str = "Search web content and return summary"
    parameters: dict = Field(
        default_factory=lambda: {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search keyword",
                }
            },
            "required": ["query"],
        }
    )

    async def call(
        self, context: ContextWrapper[AstrAgentContext], **kwargs
    ) -> str:
        query = kwargs.get("query", "")
        if not query:
            return "Error: Missing 'query' parameter"

        try:
            async with aiohttp.ClientSession() as session:
                url = "https://api.duckduckgo.com/"
                params = {"q": query, "format": "json", "no_html": 1}
                async with session.get(
                    url, params=params, timeout=aiohttp.ClientTimeout(total=15)
                ) as resp:
                    if resp.status != 200:
                        return f"Error: Search service returned {resp.status}"
                    data = await resp.json()
                    abstract = data.get("AbstractText", "No summary found")
                    return abstract or "No results found"
        except aiohttp.ClientError as e:
            logger.error(f"Search network error: {e}")
            return f"Error: Network request failed: {e}"
        except Exception as e:
            logger.error(f"Search unknown error: {e}")
            return f"Error: Search failed: {e}"


class AgentPlugin(Star):
    """Agent sub-agent plugin demonstrating tool_loop_agent and multi-tool collaboration."""

    def __init__(self, context: Context):
        super().__init__(context)
        self.context.add_llm_tools(SearchWebTool())

    async def initialize(self):
        logger.info("Agent sub-agent plugin loaded")

    @filter.command("agent_search")
    async def agent_search(self, event: AstrMessageEvent):
        """Use AI Agent to search and summarize"""
        query = event.message_str.strip()
        if not query:
            yield event.plain_result("Usage: /agent_search <search_query>")
            return

        try:
            provider_id = await self.context.get_current_chat_provider_id(
                event.unified_msg_origin
            )
            resp = await self.context.tool_loop_agent(
                event=event,
                chat_provider_id=provider_id,
                prompt=f"Search and summarize: {query}",
                tools=ToolSet([SearchWebTool()]),
                system_prompt="You are a search assistant. Use search_web to find information and provide a concise summary.",
                max_steps=5,
            )
            yield event.plain_result(resp.completion_text)
        except Exception as e:
            logger.error(f"Agent search failed: {e}")
            yield event.plain_result(f"Search failed: {e}")

    async def terminate(self):
        logger.info("Agent sub-agent plugin unloaded")
