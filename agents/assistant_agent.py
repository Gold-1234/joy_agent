from livekit.agents import llm, ChatContext, Agent
from prompts import system_prompts
from openai import AsyncOpenAI
from .session_data import SessionData
import logging
from tools.supabase_tools import SupabaseHelper
import config
from tools.langchain_tools import LangChainAgentHelper
from livekit.agents.llm import ChatMessage 


class AssistantAgent(Agent):
    def __init__(self, instructions: str, session_data: SessionData, chat_ctx : ChatContext | None = None):
        super().__init__(
        instructions=instructions, chat_ctx=chat_ctx
        )
        self.db_helper = SupabaseHelper()
        self.session_data = session_data
        self.lc_agent_helper = LangChainAgentHelper(
            supabase_client=self.db_helper.client, 
            system_prompt=instructions
        )
        
        # self.openai_client = AsyncOpenAI()
    async def on_enter(self) -> any:
        greeting = await self.session.generate_reply(
            instructions="Greet the kid, and ask them how's there day going?"
        )
        yield greeting

    async def llm_node(self, chat_ctx: llm.ChatContext, tools, model_settings):
        print(f"running llm node")
        # 1. Get the last item from the history
        last_item = chat_ctx.items[-1]
        print(f"last item :::: {last_item}")
        # 2. Check if it's a ChatMessage and if its role is 'user'
        if not isinstance(last_item, ChatMessage) or last_item.role != 'user':
            return # Do nothing if the last item isn't a user message

        # 3. Extract the text content
        user_message_text : str = last_item.content[0]
        if not user_message_text:
            return
        
        self.session_data.chat_history.append({
            "role": "user",
            "content": user_message_text
        })

        
        # # 4. Save the user message to your database
        # await self.lc_agent_helper.add_message(
        #     user_message_text,
        #     {"role": "user", "device_id": self.session_data.device_id}
        # )

        # 5. Get the response, passing BOTH the message and the history
        final_answer = await self.lc_agent_helper.get_response(
            user_message_text, 
            chat_ctx.items # Pass the full list of chat items
        )

        self.session_data.chat_history.append({
            "role": "assistant",
            "content": final_answer
        })


        print(f"final answer : {final_answer}")

        yield final_answer


    async def on_user_turn_completed(self, turn_ctx, new_message: llm.ChatMessage):
        # The only job of this hook is to save the user's message to the database
        print("user turn completed")
        user_message_content = new_message.content[0]
        if not user_message_content:
            return

        # await self.lc_agent_helper.add_message(
        #     user_message_content, 
        #     {"role": "user", "device_id": self.session_data.device_id}
        # )
        logging.info("Saved user message to LangChain vector store.")


    async def on_session_end(self):
        print("session completed, running on session end")
        if self.session_data.chat_history:
            # Flatten messages into one big text or store individually
            combined_text = "\n".join(
                [f"{msg['role']}: {msg['content']}" for msg in self.session_data.chat_history]
            )
            if len(combined_text) > 300 : 
                await self.lc_agent_helper.add_message(
                    combined_text,
                    {"role": "conversation_history", "device_id": self.session_data.device_id, "messages": self.session_data.chat_history }
                )
                logging.info("Saved full conversation history to DB.")
            else:
                logging.info(f"Text length ({len(combined_text)}) is below threshold, not saving.")
            self.session_data.chat_history.clear()

    # async def _get_embedding(self, text: llm.ChatMessage) -> list[float] | None :

    #     """Helper function to create text embeddings for conversations"""
    #     try:
    #         text = text.text_content.replace("\n", " ")
    #         response = await self.openai_client.embeddings.create(
    #         input=[text], model="text-embedding-3-small")

    #         return response.data[0].embedding

    #     except Exception as e :
    #         logging.error(f"Error creating embedding: {e}")
    #         return None


    # async def on_user_turn_completed(self, turn_ctx :ChatContext, new_message: llm.ChatMessage) -> None:
    #     "on completing user turn agent needs to decide whether it needs to chat or need to retrieve past conversations for the given query. If chat use .chat() else do a rag_retrival using tool"
        
            
    # async def rag_retrieval(self, turn_ctx :ChatContext, new_message: llm.ChatMessage) -> None:
        # logging.info(f"User turn completed with: {new_message}")

        # if not new_message:
        #     return
        # user_embedding = await self._get_embedding(new_message)
        # if not user_embedding:  
        #     return
        # print(f"user_embedding : {user_embedding}")
        # ud: SessionData = self.session.userdata
        # ud.chat_history.append({"role": "user", "content": new_message.text_content})
        # # await self.db_helper.log_conversation(child_id=ud.device_id, role="user", content=new_message.text_content, embedding=user_embedding)

        # rag_context = await self.db_helper.get_rag_context(ud.device_id, user_embedding)

        # logging.info(f"Retrieved RAG context: {rag_context[:100]}...")
        # if rag_context:
        #     turn_ctx.add_message(
        #     role="system",
        #     content=f"REMINDER/CONTEXT: Here are some relevant things you've talked about with the user before, use this to inform your response:\n{rag_context}"
        # )