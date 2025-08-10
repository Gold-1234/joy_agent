import logging
from datetime import datetime
from livekit.agents import Agent, function_tool, RunContext
from prompts import system_prompts
from .assistant_agent import AssistantAgent
from .session_data import SessionData
from tools.supabase_tools import SupabaseHelper, save_user_data_to_backend
from dateutil.parser import parse
from livekit.agents import ChatContext, ChatMessage

class IntakeAgent(Agent):
    def __init__(self):
        # The __init__ is simple. The prompt is the agent's main "brain".
        super().__init__(
            instructions=system_prompts.INTAKE_AGENT_PROMPT
        )
        self.db_helper = SupabaseHelper()

    async def on_enter(self) -> any:
        greeting = await self.session.generate_reply(
            instructions=system_prompts.INTAKE_GREETING_PROMPT
        )
        yield greeting

    # --- DATA COLLECTION TOOLS (NOW SIMPLIFIED) ---
    @function_tool()
    async def record_name(self, context: RunContext[SessionData], name: str):
        """Use th432`is tool to record the user's name."""
        context.userdata.user_name = name
        return "Name recorded."

    @function_tool()
    async def record_city(self, context: RunContext[SessionData], city: str):
        """Use this tool to record the user's city."""
        context.userdata.city = city
        return "City recorded."

    @function_tool()
    async def record_interests(self, context: RunContext[SessionData], interests: list[str]):
        """Use this tool to record the user's interests."""
        context.userdata.interests = interests
        return "Interests recorded."

    # --- UTILITY TOOLS (AS REQUIRED BY PROMPT) ---
    @function_tool()
    async def calculate_and_record_age(self, context: RunContext[SessionData], dob: str):
        """
        Takes the user's date of birth as a string (e.g., "May 5th, 2015"),
        calculates their age in years, and saves both the DOB and the age.
        """
        try:
            birth_date = parse(dob)
        except (ValueError, TypeError):
            return "I'm sorry, I couldn't understand that date. Could you please try again?"

        today = datetime.today()
        age = today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))
        
        context.userdata.dob = dob
        context.userdata.age = age
        
        logging.info(f"Successfully parsed DOB: {dob}, Age: {age}")
        return f"Date of birth recorded, and age calculated as {age} years."

    @function_tool()
    async def get_fun_fact(self, context: RunContext[SessionData], city: str):
        """Use this tool to get a fun, kid-friendly fact about a city."""
        messages = [ChatMessage(role="user", content=[f"Tell me one short, fun fact about {city} for a child."])]
        context = ChatContext(messages=messages)
        llm_stream = await self.session.llm.chat(history=context)

        fact = "".join([c.text async for c in llm_stream])
        return fact
        
    # --- FINAL WORKFLOW TOOLS ---
    @function_tool()
    async def create_user(self, context: RunContext[SessionData]):
        """Call this tool ONLY after collecting all required information to save the user's profile."""
        ud: SessionData = context.userdata
        logging.info(f"Saving user data for user: {ud.user_name}")

        user_data_payload = {
            "device_id": ud.device_id, "name": ud.user_name, "age": ud.age,
            "city": ud.city, "interests": ud.interests, "birthday": ud.dob
        }
        try:
        # This function will now raise an exception if the backend returns an error
            await save_user_data_to_backend(user_data_payload)
        
            logging.info("Profile created successfully in backend.")
            return "User profile successfully saved to the database."
        except Exception as e:
            logging.error(f"Failed to create user profile via backend: {e}")
            return "An internal error occurred while trying to save the profile. Please inform the user that there was a problem and we will try again later."

    @function_tool()
    async def transfer_to_assistant(self, context: RunContext[SessionData]):
        """Call this tool as the very final step to transfer to the main assistant."""
        logging.info("Transferring to AssistantAgent.")
        
        ud: SessionData = context.userdata
        child_profile = await self.db_helper.fetch_child_profile(ud.device_id)
        dynamic_prompt = system_prompts.create_assistant_prompt(
            child_profile=child_profile,
            chat_history=self.session.history,
            session_data=ud
        )
        return AssistantAgent(instructions=dynamic_prompt, chat_ctx=self.session.history)