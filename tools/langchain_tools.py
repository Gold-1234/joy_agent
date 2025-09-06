import logging
from langchain_community.vectorstores import SupabaseVectorStore
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain.agents import AgentExecutor, create_openai_tools_agent, Tool
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import AIMessage, HumanMessage
from .supabase_tools import SupabaseHelper
import config

class LangChainAgentHelper:
    def __init__(self, supabase_client, system_prompt: str):
        self.llm = ChatOpenAI(model="gpt-4o", temperature=0.7, api_key=config.OPENAI_API_KEY)
        self.embeddings = OpenAIEmbeddings(model="text-embedding-3-small", api_key=config.OPENAI_API_KEY)
        self.vector_store = SupabaseVectorStore(
            client=supabase_client,
            table_name="conversations",
            query_name="match_conversation",
            embedding=self.embeddings,
        )
        
        retriever = self.vector_store.as_retriever()

        # 2. Create the RAG Tool
        rag_tool = Tool(
            name="ConversationHistorySearch",
            func=retriever.invoke,
            description="Use this to search the conversation history for specific facts, details, or context from the user's past conversations. Use this if the user asks a question about something they've said before.",
        )
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            MessagesPlaceholder(variable_name="chat_history"),
            ("human", "{input}"),
            MessagesPlaceholder(variable_name="agent_scratchpad"),
        ])

        # 4. Create the LangChain Agent
        agent = create_openai_tools_agent(self.llm, [rag_tool], prompt)
        self.agent_executor = AgentExecutor(agent=agent, tools=[rag_tool], verbose=True)


    async def get_response(self, user_message: str, chat_history: list):
        """Gets a response from the agent, which decides to use RAG or not."""

        lc_chat_history = []
        for msg in chat_history:
            if msg.role == 'user':
                # Ensure content is a string, not a list
                content_text = msg.content[0] if isinstance(msg.content, list) else msg.content
                lc_chat_history.append(HumanMessage(content=content_text))
            elif msg.role == 'assistant':
                content_text = msg.content[0] if isinstance(msg.content, list) else msg.content
                lc_chat_history.append(AIMessage(content=content_text))

        # Invoke the agent with the properly formatted history
        response = await self.agent_executor.ainvoke({
            "input": user_message,
            "chat_history": lc_chat_history
        })
        
        return response["output"]

    async def add_message(self, text: str, metadata: dict):
        """Adds a new message to the vector store."""
        await self.vector_store.aadd_texts([text], [metadata])
        logging.info(f"Added '{metadata['role']}' message to vector store.")