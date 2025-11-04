
import os
import yaml
from dotenv import load_dotenv
from typing import List, Tuple
from langchain_ollama import ChatOllama
from langchain_ollama import OllamaEmbeddings
from langchain_chroma import Chroma
from langchain_core.prompts import ChatPromptTemplate, PromptTemplate
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.runnables import RunnableLambda
from langchain_core.output_parsers import StrOutputParser

PROMPT_FILE = os.path.join(os.path.dirname(__file__), '..', 'prompts.yaml')
CONFIG_FILE = os.path.join(os.path.dirname(__file__), '..', 'config.yaml')

class CodeRetrievalAgent:
    def __init__(self):
        # Load environment variables from .env file
        load_dotenv()

        # Load Configs and Prompts
        with open(CONFIG_FILE, 'r') as f:
            self.config = yaml.safe_load(f)
        self.prompts = self._load_prompts()

        # Initialize LLM and Embeddings (using Ollama)
        print("🤖 Initializing Ollama models...")
        OLLAMA_CHAT_MODEL = os.getenv("OLLAMA_CHAT_MODEL")
        OLLAMA_EMBED_MODEL = os.getenv("OLLAMA_EMBED_MODEL")
        self.llm = ChatOllama(model=OLLAMA_CHAT_MODEL, temperature=0)
        self.embeddings = OllamaEmbeddings(model=OLLAMA_EMBED_MODEL)

        # Initialize Vector Store and Retriever
        VECTOR_STORE_PATH = os.getenv("VECTOR_STORE_PATH")
        if not os.path.exists(VECTOR_STORE_PATH):
            raise FileNotFoundError(f"Vector store not found at '{VECTOR_STORE_PATH}'. Please run data_ingestion.py first.")
        self.vector_store = Chroma(
            persist_directory=VECTOR_STORE_PATH,
            embedding_function=self.embeddings
        )
        retriever_k = self.config['retriever']['search_k']
        self.retriever = self.vector_store.as_retriever(search_kwargs={"k": retriever_k})

        # 1. Define prompt for condensing question
        condense_question_prompt = PromptTemplate.from_template(
            self.prompts.get('condense_question_prompt_template')
        )

        # 2. Define prompt for answering with context
        answer_prompt = ChatPromptTemplate.from_template(
            self.prompts.get('retrieval_prompt_template_with_history')
        )

        # 3. Chain to condense question based on history
        standalone_question_chain = (
            condense_question_prompt
            | self.llm
            | StrOutputParser()
        )

        def log_and_get_docs(question):
            print(f"\n--- 1. STANDALONE QUESTION ---\n{question}\n")
            docs = self.retriever.invoke(question)
            print(f"--- 2. RETRIEVED {len(docs)} DOCUMENTS ---")
            return docs

        def format_and_log_context(docs):
            context = "\n\n".join([doc.page_content for doc in docs])
            print(f"--- 3. FINAL CONTEXT FOR LLM ---\n{context[:500]}...\n")
            return context

        # 4. Full conversational RAG chain
        # This single chain now handles everything from history to final answer.
        self.conversational_qa_chain = (
            {
                "context": standalone_question_chain 
                           | RunnableLambda(log_and_get_docs) 
                           | RunnableLambda(format_and_log_context),
                "input": lambda x: x["input"] # Pass the original question through for the final prompt
            }
            | answer_prompt
            | self.llm
            | StrOutputParser()
        )
        print("✅ Agent ready.")


    def _load_prompts(self):
        """Loads prompt templates from the YAML file."""
        try:
            with open(PROMPT_FILE, 'r') as f:
                return yaml.safe_load(f)
        except Exception as e:
            raise Exception(f"Error loading YAML prompts: {e}")




    def query(self, question: str, history: List[Tuple[str, str]]):
        # Gradio's ChatInterface with type="messages" passes a list of ChatMessage objects.
        # We need to format this into the string expected by our condense_question_prompt.
        chat_history_for_prompt = []
        print("\n\n--- NEW QUERY RECEIVED ---")
        print(f"Original Question: {question}")
        for message in history:
            if isinstance(message, HumanMessage):
                chat_history_for_prompt.append(f"Human: {message.content}")
            elif isinstance(message, AIMessage):
                chat_history_for_prompt.append(f"AI: {message.content}")

        # Invoke the single, efficient chain.
        answer = self.conversational_qa_chain.invoke({
            "input": question,
            "chat_history": "\n".join(chat_history_for_prompt)
        })
        print(f"--- 4. FINAL ANSWER ---\n{answer}\n")
        return answer