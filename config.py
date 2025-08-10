import os
from dotenv import load_dotenv

load_dotenv()

# Environment Variables
LIVEKIT_URL = os.environ.get("LIVEKIT_URL")
LIVEKIT_API_KEY = os.environ.get("LIVEKIT_API_KEY")
LIVEKIT_API_SECRET = os.environ.get("LIVEKIT_API_SECRET")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
DEEPGRAM_API_KEY = os.environ.get("DEEPGRAM_API_KEY")
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
BACKEND_URL = os.environ.get("BACKEND_URL")
AGENT_AUTH_TOKEN = os.environ.get("AGENT_AUTH_TOKEN")
POSTGRES_URL = os.environ.get("POSTGRES_URL")