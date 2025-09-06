import logging
import json
from livekit.agents import Agent, JobContext, RunContext, function_tool, llm
from livekit.agents.llm import ChatMessage, ChatContext
from livekit.plugins.openai import LLM as OpenAI_LLM
from livekit.rtc import Room
from .user_agent import UserAgent
from .parental_mode_agent import ParentalModeAgent
from .session_data import SessionData
from tools.supabase_tools import SupabaseHelper
import config
from prompts.system_prompts import ROUTER_AGENT_PROMPT
from livekit import rtc

logger = logging.getLogger("livekit.router")
logger.info("ROUTER AGENT RUNNING")

class RouterAgent(Agent):
    def __init__(self, room: rtc.Room, session_data: SessionData):
        logger.info("ConversationStarterAgent __init__ CALLED")
        super().__init__(instructions=ROUTER_AGENT_PROMPT, tools=[
                self.route_to_user_agent,
                self.route_to_parental_agent,
                self.route_to_conversation_agent,
            ])
        self.room = room
        self.session_data = session_data
        
    @function_tool()
    async def route_to_user_agent(self, context: RunContext[SessionData]):
        logger.info("Routing to User Agent...")
        handoff = UserAgent(
            room=self.room,
            session_data=self.session_data,
        )
        self.session.update_agent(handoff)
        return "User Agent selected."

    @function_tool()
    async def route_to_parental_agent(self, context: RunContext[SessionData]):
        """
        Routes the conversation to the Parental Agent.
        """
        logger.info("Routing to Parental Agent...")
        handoff = ParentalModeAgent(room=self.room, session_data=self.session_data)
        await self.session.update_agent(handoff)
        return "Parental Agent selected."

    @function_tool()
    async def route_to_conversation_agent(self, context: RunContext[SessionData]):
        from .conversation_starter_agent import ConversationStarterAgent

        logger.info("Routing to Conversation Agent...")
        handoff = ConversationStarterAgent(
            room=self.room,
            session_data=self.session_data,
        )
        context.session.update_agent(handoff)
        return "Conversation Agent selected."

    async def on_user_turn_completed(self, ctx: llm.ChatContext, new_message: llm.ChatMessage):
        logger.info(f"Processing user message: {new_message.text_content}")
        
        # Create a chat context for intent classification
        chat_context = ChatContext(messages=[
            ChatMessage(
                role="system",
                content=ROUTER_AGENT_PROMPT.format(
                    device_id=self.session_data.device_id
                )
            ),
            ChatMessage(
                role="user",
                content=new_message.text_content
            )
        ])

        try:
            # Use LLM to classify intent and call the appropriate tool
            response = await self.llm.chat(chat_context)
            if response.choices and response.choices[0].tool_calls:
                tool_call = response.choices[0].tool_calls[0]
                tool_name = tool_call.function_name
                logger.info(f"LLM selected tool: {tool_name}")
                
                if tool_name == "route_to_user_agent":
                    await self.route_to_user_agent(context=RunContext(session=self.session))
                elif tool_name == "route_to_parental_agent":
                    await self.route_to_parental_agent(context=RunContext(session=self.session))
                elif tool_name == "route_to_conversation_agent":
                    await self.route_to_conversation_agent(context=RunContext(session=self.session))
                else:
                    logger.warning(f"Unknown tool: {tool_name}, defaulting to Conversation Agent")
                    await self.route_to_conversation_agent(context=RunContext(session=self.session))
            else:
                # Default to Conversation Agent if no tool is called
                logger.info("No tool called, defaulting to Conversation Agent")
                await self.route_to_conversation_agent(context=RunContext(session=self.session))
        except Exception as e:
            logger.error(f"Error processing user message: {e}")
            await self.session.say(
                text="Sorry, I couldn't process your request. Let's start a conversation instead."
            )
            await self.route_to_conversation_agent(context=RunContext(session=self.session))