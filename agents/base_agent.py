import json
import logging
import asyncio
from livekit.agents import JobContext, llm, stt, tts, AgentSession, ChatContext
from livekit import rtc
from .intake_agent import IntakeAgent
from .assistant_agent import AssistantAgent
from .. import config
from ..tools.supabase_tools import SupabaseHelper
from livekit.plugins.openai import LLM as OpenAI_LLM, TTS as OpenAI_TTS
from livekit.plugins.deepgram import STT as Deepgram_STT
from dataclasses import dataclass, field
from typing import Dict, Any
from .session_data import SessionData


logging.basicConfig(level=logging.INFO)



class BaseAgent:
    def __init__(self):
        self.db_helper = SupabaseHelper()
        self.llm = OpenAI_LLM(api_key=config.OPENAI_API_KEY)
        self.stt = Deepgram_STT(api_key=config.DEEPGRAM_API_KEY)
        self.tts = OpenAI_TTS(api_key=config.OPENAI_API_KEY)

    async def process_job(self, ctx: JobContext):
        logging.info("Processing job...")

        # 1. Create an asyncio.Event to signal when the job is done
        shutdown_event = asyncio.Event()

        # 2. Define a callback to be called when the job is shutting down
        def on_shutdown(reason):
            logging.info(f"Job is shutting down: {reason}")
            shutdown_event.set()

        ctx.add_participant_entrypoint(self._handle_participant)
        ctx.add_shutdown_callback(on_shutdown)
        await ctx.connect()
        logging.info("Agent connected to the room")
        await shutdown_event.wait()

    async def _handle_participant(self, ctx: JobContext, participant: rtc.RemoteParticipant):
        logging.info(f"Handling participant: {participant.identity} - {participant.metadata}")
        print(participant)
        metadata_str = participant.metadata
        if not metadata_str:
            logging.warning(f"Participant {participant.identity} has no metadata, skipping.")
            return

        try:
            metadata = json.loads(metadata_str or "{}")
            session_data = SessionData(
                is_new_user=metadata.get("isNewUser", False),
                device_id=participant.identity,
                child_profile=metadata
            )
        except json.JSONDecodeError:
            logging.error(f"Failed to parse metadata for participant {participant.identity}")
            return

        # active_agent = None
        # if metadata.get("isNewUser", False):
        #     logging.info(f"Routing to IntakeAgent for new user: {participant.identity}")
        #     active_agent = IntakeAgent(llm=self.llm, stt=self.stt, tts=self.tts, device_id=participant.identity)
        # else:
        #     logging.info(f"Routing to AssistantAgent for returning user: {metadata.get('name')}")
        #     active_agent = AssistantAgent(llm=self.llm, stt=self.stt, tts=self.tts, child_profile=metadata)

        # if active_agent:
        #     await active_agent.start(ctx)

        session = AgentSession[SessionData](
            userdata=session_data,
            llm=self.llm,
            stt=self.stt,
            tts=self.tts
        )

        if session_data.is_new_user:
            logging.info(f"Routing to intage agent for new user : {participant.identity}")
            active_agent = IntakeAgent()
        else :
            logging.info(f"Returning to assistant agent for returning user : {participant.identity}")
            active_agent = AssistantAgent()
            
        await session.start(agent=active_agent, room=ctx.room)