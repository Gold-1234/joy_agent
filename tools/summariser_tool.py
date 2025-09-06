from openai import OpenAI
import config
import logging
from tools.supabase_tools import SupabaseHelper

client = OpenAI(api_key=config.OPENAI_API_KEY)
db = SupabaseHelper()

async def summarize_last_sessions(session_texts: list[str]) -> list[str]:
    """
    Summarizes the last 5 session transcripts into 2 lines each.
    
    :param session_texts: List of session transcripts (most recent last)
    :return: List of 2-line summaries
    """
    summaries = []
    
    for i, text in enumerate(session_texts[-5:]):  # Take last 5 sessions
        prompt = f"""
        Summarize the following session in **2 concise lines** focusing on:
        - Main topics the child talked about
        - Child's mood or preferences
        - Anything notable for personalization
        Session Transcript:
        {text}
        """
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a friendly AI assistant."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.5
        )
        summary_text = response.choices[0].message.content.strip()
        summaries.append(summary_text)

    
    return summaries


async def archive_nth_last_session(db, child_id: str, n: int):
    print("archiving last session")
    db = SupabaseHelper()

    session_res = db.client.table("conversation_logs") \
        .select("id, content") \
        .eq("child_id", child_id) \
        .order("created_at", desc=True) \
        .range(n-1, n-1) \
        .execute()
    
    print(f"response from archive :: {session_res}")

    if not session_res.data:
        return None  

    session = session_res.data[0]
    session_id = session["id"]
    session_text = session["content"]

    # Summarize with OpenAI
    prompt = f"""
    Summarize the following session in **2 concise lines** focusing on:
    - Main topics the child talked about
    - Child's mood or preferences
    - Anything notable for personalization
    Session Transcript:
    {session_text}
    """
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are a friendly AI assistant."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.5
    )
    summary_text = response.choices[0].message.content.strip()

    # Update the same row to store the summary
    res = db.client.table("conversation_logs") \
        .update({
            "content": summary_text,
        }) \
        .eq("id", session_id) \
        .execute()
    
    print(f"updated summary for conversation :: {res}")

    return summary_text