import asyncio
import aiohttp
from supabase import create_client, Client
import config
import logging
from .agent_personality import personalities

logger = logging.getLogger("livekit.supabase_tools")

class SupabaseHelper:
    def __init__(self):
        self.client: Client = create_client(config.SUPABASE_URL, config.SUPABASE_KEY)

    async def fetch_child_profile(self, device_id: str):
        """Fetches the child's profile using the device_id."""
        try:
            def run_query():
                return self.client.table('child_profiles').select("*").eq('device_id', device_id).single().execute()

            response = await asyncio.to_thread(run_query)
            return response.data
        except Exception as e:
            logging.error(f"Error fetching child profile: {e}")
            return None

    async def fetch_toy_personality(self, child_id: str):
        """Fetches the toy's personality for a given child."""
        try:
            def run_query():
                return (self.client.table('toy_personality')
                        .select("*")
                        .eq('child_id', child_id)
                        .order('last_updated', desc=True)
                        .limit(1)
                        .single()
                        .execute())
            response = await asyncio.to_thread(run_query)
            return response.data
        except Exception:
            return {'energy': 0.5, 'humor': 0.5, 'curiosity': 0.5, 'empathy': 0.5, 'role_identity': 'Best Friend'}

    async def set_toy_personality(self, personality: str, child_id: str):
        """Sets the toy personality for a child."""
        if not personality or personality not in personalities:
            personality_data = personalities["cheerful_friend"]
        else:
            personality_data = personalities[personality]

        try:
            def run_query():
                return self.client.table('toy_personality').upsert({
                    "child_id": child_id,
                    "role_identity": personality_data["role_identity"],
                    "description": personality_data["description"],
                    "energy": personality_data["energy"],
                    "humor": personality_data["humor"],
                    "curiosity": personality_data["curiosity"],
                    "empathy": personality_data["empathy"],
                    "last_updated": "now()"
                }).execute()
            response = await asyncio.to_thread(run_query)
            return response.data
        except Exception as e:
            logging.error(f"Error setting toy personality: {e}")
            return personality_data


    async def fetch_parental_rules(self, child_id: str):
        """Fetches parental rules for a given child."""
        try:
            response = await self.client.table('parental_rules').select("*").eq('child_id', child_id).single().execute()
            print(f"response from parental rules :: {response}")
            return response.data
        except Exception:
            return {}

    async def update_parental_rule(self, device_id: str, rule: dict) -> bool:
        def run_upsert():
            return self.client.table("parental_rules").upsert(
                {"device_id": device_id, **rule},
                on_conflict="device_id"
            ).execute()
        try:
            response = await asyncio.to_thread(run_upsert)
            if response.data:
                logger.info(f"Updated parental rule for device_id: {device_id}")
                return True
            logger.error(f"Failed to update parental rule for device_id: {device_id}")
            return False
        except Exception as e:
            logger.error(f"Error updating parental rule for device_id {device_id}: {e}")
            raise
        
    async def set_interests(self, user_id: str, category: str, items: list[str]):
        """Set or update a user's interests for a category."""
        valid_categories = ["Hobbies", "Sports", "Favorite_Food", "Topics"]
        if category not in valid_categories:
            raise ValueError(f"Invalid category. Must be one of {valid_categories}")

        data = {
            "user_id": user_id,
            "category": category,
            "items": items
        }

        response = await self.client.table("user_interests").upsert(data).execute()

        if response.data:
            print("Interests set successfully:", response.data)
        else:
            print("Error setting interests:", response)

    async def get_interests(self, child_id: str):
        """Fetch all interests for a given user."""
        response = self.client.table("user_interests").select("*").eq("user_id", child_id).execute()

        if not response.data:
            return {}

        interests = {row["category"]: row["items"] for row in response.data}
        return interests

    async def log_conversation(self, child_id: str, content: list, embedding: list):
        try:
            print(f"saving conversation to db :::: {content}")
            await self.client.table('conversation_logs').insert({
                'child_id': child_id,
                'content': content,
                'embedding': embedding
            }).execute()
        except Exception as e:
            print(f"Error logging conversation: {e}")

    async def get_last_n_conversations(self, child_id: str, n: int):
        """
        Fetch the last 5 conversation messages for a child.
        Returns a list of dicts with role, content, and timestamp.
        """
        try:
            response = self.client.table('conversation_logs')\
                .select("content, created_at")\
                .eq('child_id', child_id)\
                .order('created_at', desc=True)\
                .limit(n)\
                .execute()

            if not response.data:
                return []

            return list(response.data)

        except Exception as e:
            print(f"Error fetching last 5 conversations: {e}")
            return []
        

    async def get_rag_context(self, child_id: str, embedding: list, match_threshold: float = 0.50, match_count: int = 5):
        """Retrieves relevant past conversation snippets."""
        try:
            response = self.client.rpc('match_conversations', {
                'query_embedding': embedding,
                'p_child_id': child_id,
                'match_threshold': match_threshold,
                'match_count': match_count
            }).execute()
            logger.info(f"RAG response : {response}")
            return "\n".join([f"{item['content']}" for item in response.data])
        except Exception as e:
            print(f"Error fetching RAG context: {e}")
            return ""

# Backend sync
async def save_user_data_to_backend(user: dict):
    print("requesting to save user")
    url = f"{config.BACKEND_URL}/save-user-data"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {config.AGENT_AUTH_TOKEN}"
    }
    data_to_send = {
        "deviceId": user.get("device_id"),
        "name": user.get("name"),
        "age": user.get("age"),
        "city": user.get("city"),
        "birthday": user.get("birthday"),
        "interests": user.get("interests")
    }
    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(url, json=data_to_send, headers=headers) as response:
                if response.status == 200:
                    print("Successfully saved user data to backend.")
                    return await response.json()
                else:
                    print(f"Error saving user data: {await response.text()}")
                    return None
        except Exception as e:
            print(f"Failed to connect to backend: {e}")
            return None
