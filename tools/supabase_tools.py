import aiohttp
from supabase import create_client, Client
import config
import logging


class SupabaseHelper:
    def __init__(self):
        self.client: Client = create_client(config.SUPABASE_URL, config.SUPABASE_KEY)

    async def fetch_child_profile(self, device_id: str):
        """Fetches the child's profile using the device_id."""
        try:
            response = self.client.table('child_profiles').select("*").eq('device_id', device_id).single().execute()
            return response.data
        except Exception as e:
            print(f"Error fetching child profile: {e}")
            return None

    async def fetch_toy_personality(self, child_id: str):
        """Fetches the toy's personality for a given child."""
        try:
            # Fetch the latest personality record for the child
            response = self.client.table('toy_personality').select("*").eq('child_id', child_id).order('last_updated', desc=True).limit(1).single().execute()
            return response.data
        except Exception:
            # Return a default personality if none exists
            return {'energy': 0.5, 'humor': 0.5, 'curiosity': 0.5, 'empathy': 0.5, 'role_identity': 'Best Friend'}

    async def fetch_parental_rules(self, child_id: str):
        """Fetches parental rules for a given child."""
        try:
            response = self.client.table('parental_rules').select("*").eq('child_id', child_id).single().execute()
            return response.data
        except Exception:
            return {} # Return empty dict if no rules are set

    async def log_conversation(self, child_id: str, role: str, content: str, embedding: list):
        """Logs a single message turn to the conversations table with its embedding."""
        try:
            print(f"saving conversation to db :::: {content}")
            self.client.table('conversation_logs').insert({
                'child_id': child_id,
                'role': role,
                'content': content,
                'embedding': embedding,
                
            }).execute()
        except Exception as e:
            print(f"Error logging conversation: {e}")

    async def get_rag_context(self, child_id: str, embedding: list, match_threshold: float = 0.78, match_count: int = 5):
        """Retrieves relevant past conversation snippets for RAG."""
        try:
            response = self.client.rpc('match_conversations', {
                'query_embedding': embedding,
                'p_child_id': child_id,
                'match_threshold': match_threshold,
                'match_count': match_count
            }).execute()
            return "\n".join([f"- {item['role']}: {item['content']}" for item in response.data])
        except Exception as e:
            print(f"Error fetching RAG context: {e}")
            return ""

# This function communicates with the secure Node.js backend
async def save_user_data_to_backend(user: dict):
    print("requesting to save user")
    url = f"{config.BACKEND_URL}/save-user-data"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {config.AGENT_AUTH_TOKEN}"
    }
    print(f"url:{url}")
    data_to_send = {
        "deviceId": user.get("device_id"),
        "name": user.get("name"),
        "age": user.get("age"),
        "city": user.get("city"),
        "birthday": user.get("birthday"),
        "interests": user.get("interests")
    }
    print(f"data : {data_to_send}")
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
        