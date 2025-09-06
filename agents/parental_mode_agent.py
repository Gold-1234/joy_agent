import logging
from livekit.agents import Agent, RunContext, llm, AgentSession
from livekit.rtc import Room
from agents.session_data import SessionData
from prompts.system_prompts import PARENTAL_PREFERENCE_AGENT_PROMPT
from livekit.agents.llm import ChatMessage
from tools.supabase_tools import SupabaseHelper
from tools.parental_agent_tools import PARENTAL_RULE_TOOLS
import asyncio

logger = logging.getLogger("livekit.parental_mode_agent")

class ParentalModeAgent(Agent):
    def __init__(self, room: Room, session_data: SessionData):
        super().__init__(
            instructions=PARENTAL_PREFERENCE_AGENT_PROMPT,
            tools=PARENTAL_RULE_TOOLS,
        )
        self.room = room
        self.session_data = session_data
        self.supabase = SupabaseHelper()
        self.device_id = session_data.device_id

    async def on_enter(self):
        logger.info(f"ParentalModeAgent started for device_id: {self.device_id}")
        
        updated_prompt = PARENTAL_PREFERENCE_AGENT_PROMPT.format(
            device_id=self.device_id,
            conversation_logs=self.session_data.last_messages,
            child_profile=self.session_data.child_profile
        )
        await self.update_instructions(updated_prompt)

        await self.session.say(
            text="Hello! I'm now in Parent mode. I can help you set parental preferences like bedtime, restricted topics, language filters, and more. What would you like to configure?"
        )

    async def on_user_turn_completed(self, turn_ctx: llm.ChatContext, new_message: llm.ChatMessage):
        await super().on_user_turn_completed(turn_ctx, new_message)
        if "exit parent mode" in new_message.text_content.lower() or "child mode" in new_message.text_content.lower():
            self.session_data.parent_mode = False
            from agents.conversation_starter_agent import ConversationStarterAgent
            logger.info("Parent mode ended. Switching back to ConversationStarterAgent.")
            await self.session.update_agent(
                ConversationStarterAgent(room=self.room, session_data=self.session_data)
            )
            return

        await self.session.generate_reply(
            instructions=f"Respond to the parent's last message politely and helpfully. Use device_id: {self.device_id} for all tool calls (e.g., {{'device_id': '{self.device_id}', 'time': '9:00 PM'}} for set_bedtime, or {{'device_id': '{self.device_id}', 'rules': {{'bedtime': '9:00 PM', 'restricted_topics': ['violence']}}}} for set_parental_rules)."
        )