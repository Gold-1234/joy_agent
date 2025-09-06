from livekit.agents import function_tool
from livekit import rtc
from .supabase_tools import SupabaseHelper
from agents.session_data import SessionData
from agents.user_interests_agent import UserInterestAgent
from openai import OpenAI
from config import OPENAI_API_KEY
import logging

db = SupabaseHelper()
agent = UserInterestAgent()
client = OpenAI(api_key=OPENAI_API_KEY) 

logger = logging.getLogger('livekit.router')

async def exit_session(session_data: SessionData):
	logger.info(f"Chat : {session_data.chat_history}")
	await agent.process_message(user_id=session_data.device_id,message=session_data.chat_history)
	
	chat_history = session_data.chat_history

	text_to_embed = " ".join([m['content'] for m in chat_history])
	logger.info(f"Text to embed : {text_to_embed}")
	response = client.embeddings.create(
		input=[text_to_embed],
		model="text-embedding-3-small"
	)
	embedding_vector = response.data[0].embedding
	print(embedding_vector)

	result = await db.log_conversation(child_id=session_data.device_id, content=session_data.chat_history, embedding=embedding_vector)
	
	return result

async def get_data(message: str, session_data: SessionData):
    print(f"message : {message}")

    response = client.embeddings.create(
        input=[message],
        model="text-embedding-3-small"
    )
    embedding = response.data[0].embedding

    result = await db.get_rag_context(child_id=session_data.device_id, embedding=embedding)

    # Ensure it's a text string the LLM can read
    if isinstance(result, list):
        result = "\n".join([r["content"] for r in result if "content" in r])
    
    print(f"result from RAG retrieval ::: {result}")
    return result

async def generate_query_summary(chat_history: list) -> str:
    """
    Generates a concise query summary from chat history for RAG retrieval.
    This function acts as a query synthesizer to improve retrieval quality.
    """
    # A specific prompt to guide the LLM to act as a query synthesizer.
    system_prompt = """
    You are a query synthesizer. Your task is to analyze the provided chat history and
    generate a single, concise search query that captures the user's intent. The goal is to
    find relevant information from a knowledge base about a past conversation.

    Instructions:
    - Focus on the most recent user turn and the topic they are trying to recall.
    - Ignore conversational filler like "hey," "remind me," "search about it."
    - Synthesize the core topic into a clear, targeted query.
    - Output ONLY the synthesized query string, with no extra text or explanations.
    """
    
    messages = [{"role": "system", "content": system_prompt}]
    for msg in chat_history:
        messages.append({"role": msg['role'], "content": msg['content']})

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            temperature=0.0
        )
        summary = response.choices[0].message.content.strip()
        print(f"Synthesized query for RAG: {summary}")
        return summary
    except Exception as e:
        print(f"Error generating query summary: {e}")
        return chat_history[-1]['content']

