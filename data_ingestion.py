import os
from langchain_community.document_loaders import DirectoryLoader, TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.embeddings import OllamaEmbeddings
from langchain_chroma import Chroma
from dotenv import load_dotenv

load_dotenv()

# --- Configuration ---
SOURCE_DIRECTORY = "./my_project_code" # Folder containing your source code
CHROMA_PATH = "vector_store"
OLLAMA_EMBED_MODEL = "nomic-embed-text" # Local embedding model
CHUNK_SIZE = 1000
CHUNK_OVERLAP = 200 

def load_documents(directory: str):
    """Loads all text documents (including code) from the specified directory."""
    print(f"📂 Loading documents from {directory}...")
    loader = DirectoryLoader(
        path=directory, 
        glob="**/*.*", 
        loader_cls=TextLoader,
        # --- CRITICAL FIX: Specify UTF-8 Encoding ---
        loader_kwargs={"encoding": "utf-8"}, 
        # ---------------------------------------------
        # --- CRITICAL FIX: Exclude binary and cache files ---
        exclude=[
            "**/*.md", "**/*.txt", "**/*.log", 
            "**/*.jpg", "**/*.jpeg", "**/*.png",
            "**/*.pyc",  # Exclude compiled Python bytecode
            "**/__pycache__/**" # Exclude all files in cache directories
        ]
        # ---------------------------------------------
    )
    documents = loader.load()
    print(f"✅ Loaded {len(documents)} documents.")
    return documents

def split_text(documents):
    """Splits the loaded documents into smaller, manageable chunks."""
    print(f"✂️ Splitting documents into chunks...")
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=["\n\n", "\n", " ", ""]
    )
    chunks = text_splitter.split_documents(documents)
    print(f"✅ Created {len(chunks)} chunks.")
    return chunks

def create_database(chunks):
    """Generates embeddings using Ollama and saves them to Chroma."""
    
    print(f"🧠 Generating embeddings with {OLLAMA_EMBED_MODEL} and building ChromaDB...")
    
    # Use OllamaEmbeddings
    embeddings = OllamaEmbeddings(model=OLLAMA_EMBED_MODEL)
    
    vector_store = Chroma.from_documents(
        documents=chunks,
        embedding=embeddings,
        persist_directory=CHROMA_PATH
    )
    
    vector_store.persist()
    print(f"✅ ChromaDB saved successfully to {CHROMA_PATH}")


def main():
    """Main function to run the indexing process."""
    if not os.path.exists(SOURCE_DIRECTORY):
        print(f"❌ Error: Source directory '{SOURCE_DIRECTORY}' not found.")
        print("Please create it and place your project code inside (e.g., 'my_project_code/main.py').")
        return

    print("---")
    print("Make sure Ollama is running and you have pulled the embedding model:")
    print(f"ollama pull {OLLAMA_EMBED_MODEL}")
    print("---")
    
    documents = load_documents(SOURCE_DIRECTORY)
    if documents:
        chunks = split_text(documents)
        create_database(chunks)


if __name__ == "__main__":
    main()