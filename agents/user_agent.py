import logging
from datetime import datetime
from dateutil.parser import parse
from livekit.agents import Agent, function_tool, RunContext, JobContext
from livekit.agents import llm, AgentSession
from livekit.rtc import Room
from prompts import system_prompts
from .session_data import SessionData
from tools.supabase_tools import SupabaseHelper, save_user_data_to_backend
from .base_agent import BaseChatAgent
logger = logging.getLogger("livekit.user_agent")

class UserAgent(BaseChatAgent):
    def __init__(self, room: Room, session_data: SessionData, session: AgentSession):
        super().__init__(instructions=system_prompts.USER_AGENT_PROMPT)
        self.room = room
        self.session = session
        self.session_data = session_data
        self.db_helper = SupabaseHelper()

    async def on_enter(self):
        logging.info("User agent activated.")
        await self.session.generate_reply(
            user_input="Hi, how are you? It's great to see you."
        )

    @function_tool()
    async def record_name(self, context: RunContext[SessionData], name: str):
        context.userdata.user_name = (name or "").strip()
        return "Name recorded."


    async def on_user_message(self, ctx: JobContext, message: llm.ChatMessage):
        """
        Keep the flow going while the LLM uses tools to collect fields.
        The USER_AGENT_PROMPT should guide the model to call tools as needed.
        """
        logger.debug("UserAgent received user message, continuing onboarding.")
        await self.session.llm.chat(
            instructions="Acknowledge and ask the next shortest question you need. Use tools when appropriate."
        )

    @function_tool()
    async def record_city(self, context: RunContext[SessionData], city: str) -> str:
        """Use this tool to record the user's city."""
        context.userdata.city = (city or "").strip()
        return "City recorded."

    @function_tool()
    async def record_interests(self, context: RunContext[SessionData], interests: list[str]) -> str:
        """Use this tool to record the user's interests."""
        # Normalize to a clean list of strings
        context.userdata.interests = [i.strip() for i in (interests or []) if i and i.strip()]
        return "Interests recorded."

    @function_tool()
    async def calculate_and_record_age(self, context: RunContext[SessionData], dob: str) -> str:
        """
        Takes the user's date of birth as a string (e.g., "May 5th, 2015"),
        calculates their age in years, and saves DOB + age.
        """
        try:
            birth_date = parse(dob, fuzzy=True)
        except Exception:
            return "I couldn't understand that date. Please try again like 'May 5, 2015'."

        today = datetime.today()
        age = today.year - birth_date.year - (
            (today.month, today.day) < (birth_date.month, birth_date.day)
        )

        context.userdata.dob = birth_date.date().isoformat()
        context.userdata.age = int(age)

        logging.info(f"DOB parsed: {context.userdata.dob}; Age: {context.userdata.age}")
        return f"Date of birth recorded; age calculated as {age}."

    # ------------------------
    # Utility tools
    # ------------------------
    @function_tool()
    async def get_fun_fact(self, context: RunContext[SessionData], city: str) -> str:
        """
        Get one short, kid-friendly fun fact about a city.
        """
        prompt = f"Tell one short, kid-friendly fun fact about {city}. Keep it to one sentence."
        # In v1, call the LLM via context.session.llm.chat(...)
        stream = await context.session.llm.chat(instructions=prompt)
        fact = "".join([chunk.text async for chunk in stream])
        return fact.strip()

    # (If this was meant to be different, keep it; otherwise, it's a duplicate of get_fun_fact)
    # @function_tool()
    # async def register_toy_personality(...): ...

    # ------------------------
    # Persistence / finalization
    # ------------------------
    @function_tool()
    async def create_user(self, context: RunContext[SessionData]) -> str:
        """
        Call this tool ONLY after collecting all required information
        to save the user's profile.
        """
        ud: SessionData = context.userdata
        logging.info(f"Saving user data for device: {ud.device_id}, name: {ud.user_name}")

        payload = {
            "device_id": ud.device_id,
            "name": ud.user_name,
            "age": ud.age,
            "city": ud.city,
            "interests": ud.interests,
            "birthday": ud.dob,
        }

        try:
            await save_user_data_to_backend(payload)
            logging.info("Profile created successfully in backend.")
            return "User profile saved."
        except Exception as e:
            logging.error(f"Failed to create user profile via backend: {e}")
            return (
                "There was a problem saving the profile. Please tell the user we’ll try again later."
            )

    @function_tool()
    async def transfer_to_assistant(self, context: RunContext[SessionData]):
        from conversation_starter_agent import ConversationStarterAgent
        logger.info("Transferring to ConversationStarterAgent.")
        next_agent = ConversationStarterAgent(
            room=context.session.room,           
            session_data=context.userdata,       
        )
        return next_agent
