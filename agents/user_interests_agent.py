import logging
import json
from livekit.agents import Agent, llm
from livekit.plugins.openai import LLM as OpenAI_LLM
from tools.supabase_tools import SupabaseHelper
from prompts.system_prompts import USER_INTEREST_AGENT_PROMPT


class UserInterestAgent(Agent):
    def __init__(self):
        super().__init__(instructions=USER_INTEREST_AGENT_PROMPT, llm=OpenAI_LLM)
        self.supabase = SupabaseHelper().client

    async def process_message(self, message: str, user_id: str):
        prompt = f"""
        You are detecting personal interests from a child (age 4–12).
        Sort the interests into one of these categories:
        - Hobbies
        - Sports
        - Favorite_Food
        - Topics

        MESSAGE: "{message}"

        Return JSON like this:
        {{
          "Hobbies": ["drawing", "lego"],
          "Sports": ["football"],
          "Favorite_Food": ["pizza"],
          "Topics": ["dinosaurs"]
        }}

        If no interests, return empty arrays.
        """

        try:
            # Build LLM chat context
            chat_ctx = llm.ChatContext()
            chat_ctx.add_message(role="user", content=prompt)

            result = await self.llm.chat(chat_ctx=chat_ctx)
            text = result.message.content[0]

            data = json.loads(text)

            # Store category → items
            for category, items in data.items():
                if items:
                    self._store_interests(user_id, category, items)

        except Exception as e:
            logging.error(f"Error extracting interests: {e}")

    def _store_interests(self, user_id: str, category: str, new_items: list[str]):
        """Insert/update interests by category for the user, avoid duplicates."""

        record = (
            self.supabase.table("user_interests")
            .select("items")
            .eq("user_id", user_id)
            .eq("category", category)
            .maybe_single()
            .execute()
        )

        existing_items = record.data["items"] if record.data else []

        # Merge without duplicates
        merged_items = list(set(existing_items + new_items))

        if record.data:
            # Update existing row
            self.supabase.table("user_interests") \
                .update({"items": merged_items}) \
                .eq("user_id", user_id) \
                .eq("category", category) \
                .execute()
        else:
            # Insert new row
            self.supabase.table("user_interests") \
                .insert({
                    "user_id": user_id,
                    "category": category,
                    "items": merged_items
                }) \
                .execute()

    def get_current_interests(self, user_id: str):
        """Fetch all categories + items for a user."""
        result = (
            self.supabase.table("user_interests")
            .select("category, items")
            .eq("user_id", user_id)
            .execute()
        )

        return {row["category"]: row["items"] for row in result.data}