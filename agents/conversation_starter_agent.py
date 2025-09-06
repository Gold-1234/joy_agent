import logging
from livekit.agents import llm, Agent, AgentSession
from livekit.agents import JobContext, function_tool
from livekit import rtc
from agents.session_data import SessionData
from prompts.system_prompts import CONVERSATION_STARTER_AGENT_PROMPT, BASE_PROMPT
from .conversation_continuation_agent import ConversationContinuationAgent
from livekit.agents.voice.agent_activity import AgentActivity, _EndOfTurnInfo
from .base_agent import BaseChatAgent

logger = logging.getLogger("livekit.conversation_starter_agent")
logger.info("CONVERSATION STARTER AGENT LOADED")

class ConversationStarterAgent(BaseChatAgent):
    def __init__(self, room: rtc.Room, session_data: SessionData):
        logger.info("ConversationStarterAgent __init__ CALLED")
        super().__init__(instructions=BASE_PROMPT, room=room, session_data=session_data)
        self.room = room
        self.session_data = session_data
        p = session_data.personality or {}
        self.prompt_kwargs = {
            "user_name": session_data.user_name or "friend",
            "age": session_data.age or "",
            "interests": session_data.interests or [],
            "parental_instructions": session_data.parental_instructions or {},
            "role_identity": p.get("role_identity", "Best Friend"),
            "energy_level": "Hyperactive" if p.get("energy", 0.5) > 0.5 else "Calm",
            "humor_style": "Smart-witty" if p.get("humor", 0.5) > 0.5 else "Silly",
            "curiosity_level": "Endlessly curious" if p.get("curiosity", 0.5) > 0.5 else "Passive",
            "empathy_style": "Proactive" if p.get("empathy", 0.5) > 0.5 else "Reactive",
            "vector_chat_data": session_data.last_messages or [],
            "user_data": session_data.child_profile or {}
        }
    
    async def on_enter(self):
        logger.info("starter on_enter called")
        instructions = CONVERSATION_STARTER_AGENT_PROMPT.format(**self.prompt_kwargs)
        print(f"instructions ::: {instructions}")
        print(f"session :::: {self.session}")
        await self.update_instructions(instructions)
        
        logger.info("Updating LLM instructions and generating reply.")
        try:
            await self.session.generate_reply(instructions="Greet the kid, say hi, make the greeting feel personalised.")
            logger.info("Greeting sent.")

        except Exception as e:
            print(f"error generating greeting, {e}")

        try :
            logger.info(f"session data: {self.session_data}")
            self.session.update_agent(
            ConversationContinuationAgent(
                room=self.room,
                session_data=self.session_data,
            ))
        except Exception as e:
            logger.debug(f"error transferring agent : {e}")

    async def on_user_turn_completed(
        self, turn_ctx: llm.ChatContext, new_message: llm.ChatMessage
    ) -> None:
       
        await super().on_user_turn_completed(turn_ctx, new_message)
            

    