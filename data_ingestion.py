import os
import yaml
import shutil
from langchain_community.document_loaders import DirectoryLoader, TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_ollama import OllamaEmbeddings
from langchain_chroma import Chroma
from dotenv import load_dotenv

# --- Configuration Loading ---
load_dotenv()
with open("config.yaml", 'r') as f:
    config = yaml.safe_load(f)

SOURCE_DIRECTORY = os.getenv("SOURCE_DIRECTORY")
CHROMA_PATH = os.getenv("VECTOR_STORE_PATH")
OLLAMA_EMBED_MODEL = os.getenv("OLLAMA_EMBED_MODEL")
CHUNK_SIZE = config['text_splitter']['chunk_size']
CHUNK_OVERLAP = config['text_splitter']['chunk_overlap']

def load_documents(directory: str):
    """Loads all text documents (including code) from the specified directory."""
    print(f"📂 Loading documents from {directory}...")
    loader = DirectoryLoader(
        path=directory, 
        glob="**/*.*", 
        loader_cls=TextLoader,
        loader_kwargs={"encoding": "utf-8"}, 
        exclude=[
            "**/.*",              # Exclude hidden files and directories (e.g., .git, .vscode)
            "**/*.md", "**/*.txt", "**/*.log", "**/*.json", "**/*.lock",
            "**/*.jpg", "**/*.jpeg", "**/*.png", "**/*.gif", "**/*.svg",
            # Common dependency and build artifact directories
            "**/node_modules/**", # JavaScript
            "**/__pycache__/**", # Python
            "**/target/**",       # Java/Rust
            "**/build/**",        # C++/CMake/Gradle
            "**/dist/**",         # Python/JavaScript
        ]
        # ---------------------------------------------
    )
    documents = loader.load()
    print(f"✅ Loaded {len(documents)} documents.")
    return documents

def split_text(documents):
    """Splits the loaded documents into chunks using language-specific separators."""
    print(f"✂️ Splitting documents into chunks...")
    
    # Mapping file extensions to languages supported by RecursiveCharacterTextSplitter
    language_map = {
        ".py": "python", ".js": "js", ".java": "java", ".c": "c", ".cpp": "cpp",
        ".go": "go", ".rb": "ruby", ".rs": "rust", ".ts": "ts", ".html": "html",
        ".md": "markdown", ".tex": "latex"
    }

    chunks = []
    for doc in documents:
        file_extension = os.path.splitext(doc.metadata.get("source", ""))[1]
        language = language_map.get(file_extension)
        
        splitter = RecursiveCharacterTextSplitter.from_language(
            language=language, chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP
        ) if language else RecursiveCharacterTextSplitter(chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP)
        
        chunks.extend(splitter.split_documents([doc]))

    print(f"✅ Created {len(chunks)} chunks from {len(documents)} documents.")
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
    
    print(f"✅ ChromaDB saved successfully to {CHROMA_PATH}")


def main():
    """Main function to run the indexing process."""
    if not os.path.exists(SOURCE_DIRECTORY):
        print(f"❌ Error: Source directory '{SOURCE_DIRECTORY}' not found.")
        print("Please create it and place your project code inside (e.g., 'my_project_code/main.py').")
        return

    # If the database already exists, delete it to ensure a fresh start
    if os.path.exists(CHROMA_PATH):
        print(f"⚠️ Found existing ChromaDB at '{CHROMA_PATH}'. Deleting it to re-ingest data.")
        shutil.rmtree(CHROMA_PATH)
        print(f"✅ Deleted existing database.")

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