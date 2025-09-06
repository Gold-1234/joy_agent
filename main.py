import asyncio
import json
import logging
import os
from aiohttp import web

from livekit import rtc
from livekit.agents import JobContext, JobRequest, AgentSession, Worker, WorkerOptions
from livekit.plugins import silero
from livekit.plugins.openai import LLM as OpenAI_LLM, TTS as OpenAI_TTS
from livekit.plugins.deepgram import STT as Deepgram_STT

import config
from tools.supabase_tools import SupabaseHelper
from tools.summariser_tool import summarize_last_sessions, archive_nth_last_session
from agents.session_data import SessionData
from agents.conversation_starter_agent import ConversationStarterAgent
from agents.user_agent import UserAgent
from tools.agent_personality import personalities
from agents.router_agent import RouterAgent

# --- Logging Setup ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s %(message)s",
)
logging.getLogger("livekit").setLevel(logging.DEBUG)
logging.getLogger("livekit.agents").setLevel(logging.DEBUG)
logger = logging.getLogger("main")

# --- Initialize global services ---
llm = OpenAI_LLM(api_key=config.OPENAI_API_KEY)
stt = Deepgram_STT(api_key=config.DEEPGRAM_API_KEY)
tts = OpenAI_TTS(api_key=config.OPENAI_API_KEY, voice="alloy")
vad = silero.VAD.load()
db_helper = SupabaseHelper()


async def handle_participant(ctx: JobContext, participant: rtc.RemoteParticipant):
    logger.info(f"Handling participant: {participant.identity}")
    try:
        metadata = json.loads(participant.metadata or "{}")
        logger.debug(f"Parsed metadata: {metadata}")
    except json.JSONDecodeError:
        logger.exception(f"Failed to parse metadata for participant {participant.identity}")
        metadata = {}

    device_id = participant.identity
    logger.info(f"Fetching user data for device_id: {device_id}")
    await archive_nth_last_session(db=db_helper, child_id=device_id, n=11)
    try:
        child_profile = await db_helper.fetch_child_profile(device_id) or {}
        personality = await db_helper.fetch_toy_personality(device_id) or {}
        parental_instructions = await db_helper.fetch_parental_rules(device_id) or {}
        last_sessions = await db_helper.get_last_n_conversations(device_id, 5) or []
        ctx_summaries = await summarize_last_sessions(last_sessions) or []
        preferences = await db_helper.get_interests(device_id) or {}
    except Exception:
        logger.exception("Failed to fetch data from Supabase. Using empty defaults.")
        child_profile = {}
        personality = personalities["cheerful_friend"]
        parental_instructions = {}
        last_sessions = []
        ctx_summaries = []
        preferences = {}

    # Ensure stable defaults for prompt filling
    user_name = child_profile.get("name", "friend")
    age = child_profile.get("age", None)
    city = child_profile.get("city", None)
    interests = child_profile.get("interests", []) or []
    dob = child_profile.get("birthday", None)
    chat_history=[]
    try:
        current_personality = personalities["cheerful_friend"]
        safe_personality = {
            "energy": current_personality.energy,
            "humor": current_personality.humor,
            "curiosity": current_personality.curiosity,
            "empathy": current_personality.empathy,
            "role_identity": current_personality.role_identity,
        }
    except KeyError:
        logger.error(f"Could not find {personality} personality. Using a default personality.")
        safe_personality = {"energy": 0.5, "humor": 0.5, "curiosity": 0.5, "empathy": 0.5, "role_identity": "Best Friend"}
    except AttributeError:
        logger.error("The personality object does not have the expected attributes. Using defaults.")
        safe_personality = {"energy": 0.5, "humor": 0.5, "curiosity": 0.5, "empathy": 0.5, "role_identity": "Best Friend"}

    session_data = SessionData(
        is_new_user=bool(metadata.get("isNewUser", False)),
        device_id=device_id,
        child_profile=child_profile,
        last_messages=ctx_summaries,
        parental_instructions=parental_instructions,
        preferences=preferences,
        personality=safe_personality,
        user_name=user_name,
        age=age,
        city=city,
        interests=interests,
        dob=dob,
        chat_history=chat_history
    )

    logger.info(f"SessionData successfully constructed. is_new_user: {session_data.is_new_user}")
    logger.debug(f"Full SessionData object: {session_data}")

    # ---- Build session ----
    logger.info("Initializing AgentSession...")
    session = AgentSession[SessionData](
        userdata=session_data,
        llm=llm,
        stt=stt,
        vad=vad,        
        tts=tts,
    )

    logger.info(f"Session : {session}")

    # ---- Choose initial agent ----
    if session_data.is_new_user:
        logger.info("New user detected. Starting with UserAgent.")
        active_agent = UserAgent(room=ctx.room, session_data=session_data)
    else:
        logger.info("Existing user detected. Starting with ConversationStarterAgent.")
        active_agent = ConversationStarterAgent(room=ctx.room, session_data=session_data)
    
    await session.start(room=ctx.room, agent=active_agent)

async def create_agent(ctx: JobContext):
    logger.info(f"Starting agent for job {ctx.job.id}")

    shutdown_event = asyncio.Event()

    async def on_shutdown(reason: str):
        logger.info(f"Job is shutting down: {reason}")
        shutdown_event.set()
    
    ctx.add_participant_entrypoint(handle_participant)
    ctx.add_shutdown_callback(on_shutdown)

    await ctx.connect()
    logger.info("Agent connected to the room")
    await shutdown_event.wait()


# --- HTTP Health Check ---
async def health_check(_request):
    return web.Response(text="OK")


async def run_http_server():
    app = web.Application()
    app.router.add_get("/", health_check)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 5000))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    logger.info(f"HTTP server running on port {port}")


# --- Main ---
async def run_livekit_worker():
    options = WorkerOptions(
        entrypoint_fnc=create_agent,
        ws_url=config.LIVEKIT_URL,
        api_key=config.LIVEKIT_API_KEY,
        api_secret=config.LIVEKIT_API_SECRET,
    )
    worker = Worker(options)
    await worker.run()


async def main():
    await asyncio.gather(run_livekit_worker(), run_http_server())


if __name__ == "__main__":
    asyncio.run(main())
