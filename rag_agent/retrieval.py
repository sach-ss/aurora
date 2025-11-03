
import os
import yaml
from typing import List, Tuple
from langchain_ollama import ChatOllama
from langchain_ollama import OllamaEmbeddings
from langchain_chroma import Chroma
from langchain_core.prompts import ChatPromptTemplate, PromptTemplate
from langchain_core.runnables import RunnablePassthrough

PROMPT_FILE = os.path.join(os.path.dirname(__file__), '..', 'prompts.yaml')
VECTOR_STORE_PATH = "vector_store"
OLLAMA_CHAT_MODEL = "gemma:2b" # <-- Switched to Gemma 2B
OLLAMA_EMBED_MODEL = "nomic-embed-text" # Local embedding model



class CodeRetrievalAgent:
    def __init__(self):
        # Load Prompts
        self.prompts = self._load_prompts()

        # Initialize LLM and Embeddings (using Ollama)
        print("🤖 Initializing Ollama models...")
        self.llm = ChatOllama(model=OLLAMA_CHAT_MODEL, temperature=0)
        self.embeddings = OllamaEmbeddings(model=OLLAMA_EMBED_MODEL)

        # Initialize Vector Store and Retriever
        if not os.path.exists(VECTOR_STORE_PATH):
            raise FileNotFoundError(f"Vector store not found at '{VECTOR_STORE_PATH}'. Please run data_ingestion.py first.")
        self.vector_store = Chroma(
            persist_directory=VECTOR_STORE_PATH,
            embedding_function=self.embeddings
        )
        self.retriever = self.vector_store.as_retriever(search_kwargs={"k": 50})

        # Define the LCEL RAG chain
        prompt = ChatPromptTemplate.from_template(
            self.prompts.get('retrieval_prompt', "Answer the following question using the provided context.\n\nContext:\n{context}\n\nQuestion: {input}")
        )
        self.qa_chain = (
            {
                "input": RunnablePassthrough(),
                "context": (lambda x: x["input"]) | self.retriever | (lambda docs: "\n\n".join([doc.page_content for doc in docs]))
            }
            | prompt
            | self.llm
        )

        # Mermaid chain for dependency graph
        self.mermaid_prompt = PromptTemplate.from_template(
            self.prompts.get('mermaid_prompt_template', "")
        )
        self.mermaid_chain = self.mermaid_prompt | self.llm
        print("✅ Agent ready.")


    def _load_prompts(self):
        """Loads prompt templates from the YAML file."""
        try:
            with open(PROMPT_FILE, 'r') as f:
                return yaml.safe_load(f)
        except Exception as e:
            raise Exception(f"Error loading YAML prompts: {e}")




    def query(self, question: str, history: List[Tuple[str, str]]):
        # For now, history is not used. You can extend this for chat memory.
        result = self.qa_chain.invoke({"input": question})
        answer = result.content if hasattr(result, 'content') else str(result)
        return answer, []


    def generate_graph_mermaid(self):
        """Generates a dependency graph in Mermaid syntax using the LLM."""
        print(f"Generating Mermaid dependency graph...")
        
        all_docs = self.vector_store.similarity_search(query="function class module", k=50)
        context_text = "\n---\n".join([doc.page_content for doc in all_docs])

        response = self.mermaid_chain.invoke({"context": context_text})
        mermaid_string = response.content
        print(f"Mermaid dependency graph raw output:\n"+mermaid_string)
        return mermaid_string