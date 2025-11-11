import gradio as gr
import os
import time
import yaml
from dotenv import load_dotenv
from google import genai
from google.genai import types

# --- Configuration ---
def load_config():
    """Loads configuration from .env and prompts.yaml."""
    load_dotenv()
    google_api_key = os.getenv("GOOGLE_API_KEY")
    if not google_api_key:
        raise ValueError("GOOGLE_API_KEY not found in .env file")
    
    with open("prompts.yaml", "r") as f:
        prompts = yaml.safe_load(f)
    return google_api_key, prompts

# --- Gemini Client Initialization ---
try:
    GOOGLE_API_KEY, PROMPTS = load_config()
    client = genai.Client(api_key=GOOGLE_API_KEY)
except (ValueError, FileNotFoundError) as e:
    print(f"Error initializing the application: {e}")
    # Exit or handle gracefully if running in a context that allows it
    exit()


# # --- Clean up old stores ---
# print("--- Cleaning up old File Search Stores ---")
# store_to_keep_display_name = "aurora-code-analysis-store"
# try:
#     for store_item in client.file_search_stores.list():
#         if store_item.display_name != store_to_keep_display_name:
#             print(f"Deleting store: {store_item.display_name} ({store_item.name})")
#             client.file_search_stores.delete(name=store_item.name, config={'force': True})
#         else:
#             print(f"Keeping store: {store_item.display_name}")
# except Exception as e:
#     print(f"An error occurred during store cleanup: {e}")
# print("--- Cleanup Complete ---")


# --- File Search Store Management ---
def get_or_create_store():
    """Gets the file search store or creates it if it doesn't exist."""
    print("--- Initializing File Search Store ---")
    store_display_name = "aurora-code-analysis-store"
    
    # Check if the store already exists
    for store in client.file_search_stores.list():
        if store.display_name == store_display_name:
            print(f"Found existing store: {store.name}")
            return store

    # If not found, create a new one
    print(f"Store not found, creating a new one: {store_display_name}")
    return client.file_search_stores.create(config={'display_name': store_display_name})

store = get_or_create_store()

# --- Core Functions ---
def ingest_files(directory_path):
    """
    Finds all files in a directory, uploads them to the file search store, 
    yields progress, and waits for completion.
    """
    if not directory_path or not os.path.isdir(directory_path):
        yield "Please provide a valid directory path."
        return

    yield f"Scanning directory: {directory_path}"
    print(f"Scanning directory: {directory_path}")

    # Find all files in the directory
    all_files = []
    # A list of common directories to ignore
    ignored_dirs = ['.git', '__pycache__', 'venv', 'node_modules', '.idea', '.vscode', '.gradio']
    for root, dirs, files in os.walk(directory_path):
        # Remove ignored directories from the search
        dirs[:] = [d for d in dirs if d not in ignored_dirs]
        for file in files:
            all_files.append(os.path.join(root, file))

    if not all_files:
        yield "No files found in the specified directory."
        return

    yield f"Found {len(all_files)} files. Ingesting... This may take a few minutes."
    print(f"Ingesting {len(all_files)} files...")

    # Process one file at a time
    for file_path in all_files:
        file_name = os.path.basename(file_path)
        yield f"Uploading `{file_name}`..."
        print(f"Uploading: {file_name} from {file_path}")
        
        try:
            upload_config = {'display_name': file_name}
            
            # Get file extension and map to mime type
            file_ext = os.path.splitext(file_name)[1].lower()
            mime_type_map = {
                '.md': 'text/markdown',
                '.mdx': 'text/markdown',
                '.py': 'text/x-python',
                '.java': 'text/x-java-source',
                '.js': 'text/javascript',
                '.ts': 'text/typescript',
                '.yaml': 'text/plain',
                '.yml': 'text/plain',
                # Add other file types here as needed
            }
            
            if file_ext in mime_type_map:
                upload_config['mime_type'] = mime_type_map[file_ext]
            
            # This call should return a long-running operation
            operation = client.file_search_stores.upload_to_file_search_store(
                file_search_store_name=store.name,
                file=file_path, 
                config=upload_config
            )
            
            # Wait for the current file's operation to complete before proceeding
            yield f"Indexing `{file_name}`..."
            while not operation.done:
                time.sleep(4)
                operation = client.operations.get(operation)
            
            yield f"✅ Indexed `{file_name}`"
        except Exception as e:
            yield f"❌ Error indexing `{file_name}`: {e}"
            print(f"Error indexing {file_name}: {e}")


    yield f"✅ Ingestion complete for {len(all_files)} files. You can now use the Chat tab."

def delete_store():
    """Deletes the existing file search store and creates a new one."""
    global store
    store_display_name = "aurora-code-analysis-store"
    deleted_message = f"No store with display name '{store_display_name}' found to delete."

    try:
        print("--- Deleting File Search Store ---")
        for store_item in client.file_search_stores.list():
            if store_item.display_name == store_display_name:
                print(f"Deleting store: {store_item.display_name} ({store_item.name})")
                client.file_search_stores.delete(name=store_item.name, config={'force': True})
                deleted_message = f"✅ Store '{store_item.display_name}' deleted."
                break 
    except Exception as e:
        error_message = f"An error occurred during store deletion: {e}"
        print(error_message)
        return error_message

    # Re-create a new store
    store = get_or_create_store()
    recreate_message = f"A new store '{store.display_name}' has been created."
    
    return f"{deleted_message}\n{recreate_message}"

def chat_fn(message, history, chat_session):
    """
    Handles the chat interaction, using the file search store as a tool.
    """
    if not chat_session:
        print("--- Starting New Chat Session ---")
        chat_session = None # Ensure any previous session object is discarded
        # Configure the tools for the chat session
        tool_config = types.GenerateContentConfig(
            tools=[
                types.Tool(
                    file_search=types.FileSearch(
                        file_search_store_names=[store.name]
                    )
                )
            ],
            system_instruction=PROMPTS.get("chat_prompt")
        )
        # Start a chat session with the tool config
        chat_session = client.chats.create(
            model="gemini-2.5-flash", 
            config=tool_config
        )

    # Send the user's message to the existing chat session
    response = chat_session.send_message(message)
    response_text = response.text
    
    # Add citations from grounding metadata
    try:
        # Grounding metadata is nested in the first candidate
        grounding = response.candidates[0].grounding_metadata
        if grounding and grounding.grounding_chunks:
            sources = {chunk.retrieved_context.title for chunk in grounding.grounding_chunks}
            if sources:
                citations = "\n\n**Sources:**\n" + "\n".join(f"- `{source}`" for source in sorted(list(sources)))
                response_text += citations
    except (AttributeError, IndexError):
        # This can happen if there are no candidates or no grounding metadata.
        pass

    return response_text, chat_session

# --- Gradio UI ---
with gr.Blocks(theme=gr.themes.Soft()) as demo:
    gr.Markdown("<h1 style='text-align: center;'>Aurora Codex</h1>")

    with gr.Tab("Ingest Codebase"):
        gr.Markdown("## Step 1: Provide Local Codebase Path")
        gr.Markdown("Enter the local path to your codebase. The tool will scan this directory and create a searchable index of your files.")
        local_repo_path = gr.Textbox(label="Local Codebase Path", placeholder="e.g., /path/to/my/local/repo")
        with gr.Row():
            ingest_button = gr.Button("🚀 Ingest Files", variant="primary")
            delete_store_button = gr.Button("🗑️ Delete Store", variant="stop")
        ingest_status = gr.Markdown()

        ingest_button.click(
            fn=ingest_files,
            inputs=[local_repo_path],
            outputs=[ingest_status],
            show_progress="hidden"
        )
        delete_store_button.click(
            fn=delete_store,
            inputs=[],
            outputs=[ingest_status]
        )

    with gr.Tab("Chat"):
        gr.Markdown("## Step 2: Chat With Your Codebase")
        gr.Markdown("Ask questions about your code. For example: 'What does the `ingest_files` function do?' or 'Where is the Gemini API key configured?'")
        
        # State to hold the chat session object across turns
        chat_session_state = gr.State(None)
        
        chatbot = gr.Chatbot(height=600, type="messages", label="Chat with Aurora")
        chat_interface = gr.ChatInterface(
            fn=chat_fn,
            type="messages",
            chatbot=chatbot,
            additional_inputs=[chat_session_state],
            additional_outputs=[chat_session_state],
            examples=[
                ["Summarize the purpose of the main application file."],
                ["What are the main dependencies in requirements.txt?"],
                ["Explain the `chat_fn` function and its parameters."],
            ]
        )

if __name__ == "__main__":
    demo.launch()
