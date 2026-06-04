from astrbot.api import logger
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.provider import ProviderRequest, LLMResponse
from astrbot.api.star import Context, Star


class LLMHookPlugin(Star):
    """LLM hook plugin demonstrating request/response interception."""

    def __init__(self, context: Context):
        super().__init__(context)
        self.enabled = True

    @filter.on_llm_request()
    async def on_llm_request(self, event: AstrMessageEvent, req: ProviderRequest):
        """Inject extra instructions before LLM request"""
        if not self.enabled:
            return

        injection = "Please answer concisely and professionally."
        if req.system_prompt:
            req.system_prompt += f"\n{injection}"
        else:
            req.system_prompt = injection
        logger.debug(f"Injected system prompt: {injection}")

    @filter.on_llm_response()
    async def on_llm_response(self, event: AstrMessageEvent, resp: LLMResponse):
        """Log LLM response after it returns"""
        if resp.completion_text:
            logger.info(f"LLM response length: {len(resp.completion_text)} chars")

    @filter.command("toggle_hook")
    async def toggle_hook(self, event: AstrMessageEvent):
        """Toggle hook on/off"""
        self.enabled = not self.enabled
        status = "enabled" if self.enabled else "disabled"
        yield event.plain_result(f"LLM hook {status}")

    async def terminate(self):
        """Clean up resources"""
