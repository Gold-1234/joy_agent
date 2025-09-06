# agents/conversation_continuation_agent.py

import logging
from livekit.agents import llm, Agent, AgentSession
from livekit.agents import Worker, JobContext, function_tool
from livekit import rtc
from livekit.agents.voice.agent_activity import AgentActivity, _EndOfTurnInfo
from agents.session_data import SessionData
from prompts.system_prompts import (
    CONVERSATION_CONTINUATION_AGENT_PROMPT,
    create_assistant_prompt,
)
from typing import Optional
from tools.agent_tools import exit_session, get_data, generate_query_summary
from .router_agent import RouterAgent
from .base_agent import BaseChatAgent


logger = logging.getLogger("livekit.conversation_continuation_agent")
logger.info("CONVERSATION CONTINUATION AGENT LOADED")

class ConversationContinuationAgent(BaseChatAgent):

    def __init__(self, room: rtc.Room, session_data: SessionData):
        super().__init__(instructions=CONVERSATION_CONTINUATION_AGENT_PROMPT, room=room, session_data=session_data) 
        logger.info("Initializing ConversationContinuationAgent.")
        self.room = room
        self.session_data = session_data

    @function_tool
    async def exit(self):
        await exit_session(session_data=self.session_data)

    @function_tool

    async def extract_data(self, query: Optional[str] = None):
        """
        Retrieve past conversation memories from vector DB when session/context lacks info.
        Args:
            query: Optional query. If not given, summarize last user messages.
        """
        if not query:
            # build query from last few turns
            messages_for_rag = [
                {"role": item.role, "content": item.content[0]}
                for item in self.chat_ctx.items[-10:]
            ]
            query = await generate_query_summary(messages_for_rag)

        logger.info(f"Final RAG input: {query}")

        # Call your DB
        result = await get_data(session_data=self.session_data, message=query)

        if not result:
            return "No related past memories found."
        return result  

    async def on_enter(self):
        sd = self.session_data
        logger.info("Building full system prompt for continuation agent...")

        full_prompt = create_assistant_prompt(
            child_profile=sd.child_profile,
            personality=sd.personality,
            parental_rules=sd.parental_instructions,
            chat_history=sd.last_messages,
        )
        # full_prompt = f"{CONVERSATION_CONTINUATION_AGENT_PROMPT}\n\n{full_prompt}"
        
        logger.debug(f"Full system prompt: {full_prompt}")
        await self.update_instructions(full_prompt)
        logger.info("LLM instructions set for continuation.")
        logger.info(f"Continumm ::: {self.session}")

    async def on_user_turn_completed(
        self, turn_ctx: llm.ChatContext, new_message: llm.ChatMessage
    ) -> None:
        # logger.info(f"User turn completed : {new_message}")
        # text = new_message.content[0]
        # self.session_data.chat_history.append({"role": "user", "content": text})

        # if self.chat_ctx.items and self.chat_ctx.items[-1].role == "assistant":
        #     text = self.chat_ctx.items[-1].content[0]
        #     self.session_data.chat_history.append({"role": "assistant", "content": text})
        #     logger.info(f"Saved assistant msg: {text}")
        await super().on_user_turn_completed(turn_ctx, new_message)
        

    
        
        
 