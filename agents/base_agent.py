from livekit.agents import Agent, llm, AgentSession
import logging
from livekit import rtc
from .session_data import SessionData
import asyncio

logger = logging.getLogger("livekit.BASE_AGENT")
logger.info("BASE_AGENT")


class BaseChatAgent(Agent):
    def __init__(self, room: rtc.room, session_data: SessionData, instructions="", **kwargs):
        super().__init__(instructions=instructions, **kwargs)
        self.room = room
        self.session_data = session_data
        self._exit_timer = None
        
    async def _exit_after_timeout(self, seconds: int):
            try:
                await asyncio.sleep(seconds)
                logger.info(f"No user activity for {seconds}s. Closing session...")
                await self.session.aclose()  # ends agent session
                # await self.room.disconnect()
            except asyncio.CancelledError:
                pass

    async def on_user_turn_completed(
        self, turn_ctx: llm.ChatContext, new_message: llm.ChatMessage
    ) -> None:
        logger.info(f"chat_history after user turn completed :: {self.session_data.chat_history}")
        logger.info(f"User turn completed : {new_message}")

        text = new_message.content[0]
        self.session_data.chat_history.append({"role": "user", "content": text})

        logger.info(f"chat :: {self.chat_ctx}")
        last_item = self.chat_ctx.items[-1]

        if "parent mode" in text.lower() or "parental mode" in text.lower() or "parent" in text.lower():
            logger.info("Switching to ParentalModeAgent...")
            from agents.parental_mode_agent import ParentalModeAgent
            self.session.update_agent(
                ParentalModeAgent(room=self.room, session_data=self.session_data)
            )
            logger.info("Handoff to ParentalModeAgent completed.")

        if last_item.type == "message":
            if last_item.role == "assistant":
                text = last_item.text_content
                if text:
                    self.session_data.chat_history.append({"role": "assistant", "content": text})
                    logger.info(f"Saved assistant msg: {text}")
        else:
            pass
        if self._exit_timer and not self._exit_timer.done():
            self._exit_timer.cancel()

        # start a new exit timer
        self._exit_timer = asyncio.create_task(self._exit_after_timeout(60))  # 60s timeout

        
        
            