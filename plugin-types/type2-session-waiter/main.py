from astrbot.api import logger
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star
from astrbot.core.utils.session_waiter import session_waiter, SessionController


class QuizPlugin(Star):
    """Multi-turn quiz plugin demonstrating session_waiter usage."""

    def __init__(self, context: Context):
        super().__init__(context)

    @filter.command("quiz")
    async def start_quiz(self, event: AstrMessageEvent):
        """Start a quiz game"""
        yield event.plain_result(
            "Welcome to the quiz!\n"
            "Question: What is the base class for AstrBot plugins?\n"
            "(Type your answer, or type 'quit' to exit)"
        )

        @session_waiter(timeout=30)
        async def waiter(controller: SessionController, event: AstrMessageEvent):
            answer = event.message_str.strip()

            if answer.lower() == "quit":
                await event.send(event.plain_result("Quiz exited."))
                controller.stop()
                return

            if answer in ("Star", "star"):
                await event.send(event.plain_result("Correct! The AstrBot plugin base class is Star."))
                controller.stop()
                return

            await event.send(event.plain_result("Wrong answer, try again! (type 'quit' to exit)"))
            controller.keep(timeout=30, reset_timeout=True)

        try:
            await waiter(event)
        except TimeoutError:
            yield event.plain_result("Quiz timed out!")

    async def terminate(self):
        """Clean up resources"""
