import json
import logging
import asyncio
from dataclasses import dataclass, field
from typing import Dict, Any
from .tools.supabase_tools import SupabaseHelper
from livekit.agents import JobContext, AgentSession, JobRequest, Worker, WorkerOptions
from livekit import rtc
from .agents.intake_agent import IntakeAgent
from .agents.assistant_agent import AssistantAgent
from .agents.session_data import SessionData
from agent import config
from .prompts import system_prompts
from livekit.plugins import silero, sarvam

from livekit.plugins.openai import LLM as OpenAI_LLM, TTS as OpenAI_TTS
from livekit.plugins.deepgram import STT as Deepgram_STT

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s %(message)s",
)

# These are the key lines to get more details from the agent SDK
logging.getLogger("livekit").setLevel(logging.DEBUG)
logging.getLogger("livekit.agents").setLevel(logging.DEBUG)


# --- Initialize Services (globally for the worker) ---
llm = OpenAI_LLM(api_key=config.OPENAI_API_KEY)
stt = Deepgram_STT(api_key=config.DEEPGRAM_API_KEY)
tts = OpenAI_TTS(api_key=config.OPENAI_API_KEY, voice="alloy")
vad = silero.VAD.load()
db_helper = SupabaseHelper()


# --- Define the Participant Handler ---
async def handle_participant(ctx: JobContext, participant: rtc.RemoteParticipant):
    logging.info(f"Handling participant: {participant.identity}")

    try:
        metadata = json.loads(participant.metadata or "{}")
        session_data = SessionData(
            is_new_user=metadata.get("isNewUser", False),
            device_id=participant.identity,
            child_profile=metadata
        )
    except json.JSONDecodeError:
        logging.error(f"Failed to parse metadata for participant {participant.identity}")
        return

    session = AgentSession[SessionData](
        userdata=session_data,
        llm=llm,
        stt=stt,
        tts=tts,
        vad=vad,
        
    )

    if session_data.is_new_user:
        active_agent = IntakeAgent()
    else:
        logging.info(f"Returning user detected. Fetching profile...: session data : {session_data}")
        child_profile = await db_helper.fetch_child_profile(session_data.device_id)
        print(f'user : {child_profile}')
        dynamic_prompt = system_prompts.create_assistant_prompt(child_profile=child_profile, chat_history=session.history)
        active_agent = AssistantAgent(instructions=dynamic_prompt, chat_ctx=session.history, session_data=session_data)
#  AssistantAgent(instructions=dynamic_prompt, chat_ctx=session.history, session_data=session_data)
    ctx.active_agent = active_agent
    ctx.active_session = session
    await session.start(agent=active_agent, room=ctx.room)


# --- This is the main job entrypoint ---
async def create_agent(ctx: JobRequest):
    logging.info(f"Starting agent for job {ctx.job.id}")

    shutdown_event = asyncio.Event()
    async def on_shutdown(reason):
        logging.info(f"Job is shutting down: {reason}")
        agent = getattr(ctx, "active_agent")
        if agent and hasattr(agent, "on_session_end"):
            try:
                await asyncio.shield(agent.on_session_end())
            except Exception as e:
                logging.error(f"Error in on_session_end: {e}")

        shutdown_event.set()

    ctx.add_participant_entrypoint(handle_participant)
    ctx.add_shutdown_callback(on_shutdown)
    
    await ctx.connect()
    logging.info("Agent connected to the room")
    await shutdown_event.wait()


# --- Main Worker Execution ---
async def main():
    options = WorkerOptions(
        entrypoint_fnc=create_agent,
        ws_url=config.LIVEKIT_URL,
        api_key=config.LIVEKIT_API_KEY,
        api_secret=config.LIVEKIT_API_SECRET
    )
    worker = Worker(options)
    await worker.run()

if __name__ == "__main__":
    asyncio.run(main())