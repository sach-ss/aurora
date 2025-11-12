import gradio as gr
from gradio.components import ChatMessage
import os
import sqlite3
from datetime import datetime
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

    with open("config.yaml", "r") as f:
        config = yaml.safe_load(f)

    return google_api_key, prompts, config

# --- Gemini Client Initialization ---
try:
    GOOGLE_API_KEY, PROMPTS, CONFIG = load_config()
    client = genai.Client(api_key=GOOGLE_API_KEY)
except (ValueError, FileNotFoundError) as e:
    print(f"Error initializing the application: {e}")
    # Exit or handle gracefully if running in a context that allows it
    exit()

# --- SQLite Datetime Adapters (for Python 3.12+ DeprecationWarning) ---
def adapt_datetime_iso(val):
    """Adapt datetime.datetime to timezone-naive ISO 8601 format."""
    return val.isoformat()

def convert_datetime(val):
    """Convert ISO 8601 formatted string to datetime.datetime object."""
    return datetime.fromisoformat(val.decode())

# Register the adapter and converter
sqlite3.register_adapter(datetime, adapt_datetime_iso)
sqlite3.register_converter("DATETIME", convert_datetime)


# --- Configuration Values ---
STORE_DISPLAY_NAME = CONFIG["file_search_store"]["display_name"]
DB_NAME = CONFIG["database_name"]
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

# --- Database Management ---
def init_db():
    """Initializes the SQLite database and creates the history table if it doesn't exist."""
    print(f"--- Initializing Database: {DB_NAME} ---")
    try:
        with sqlite3.connect(DB_NAME, detect_types=sqlite3.PARSE_DECLTYPES) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS chat_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    conversation_id TEXT NOT NULL,
                    timestamp DATETIME NOT NULL,
                    query TEXT NOT NULL,
                    response TEXT NOT NULL
                )
            """)
            conn.commit()
        print("Database initialized successfully.")
    except sqlite3.Error as e:
        print(f"Error initializing database: {e}")

# --- File Search Store Management ---
def get_or_create_store():
    """Gets the file search store or creates it if it doesn't exist."""
    print(f"--- Initializing File Search Store: {STORE_DISPLAY_NAME} ---")

    # Check if the store already exists
    for store in client.file_search_stores.list():
        if store.display_name == STORE_DISPLAY_NAME:
            print(f"Found existing store: {store.name}")
            return store

    # If not found, create a new one
    print(f"Store not found, creating a new one: {STORE_DISPLAY_NAME}")
    return client.file_search_stores.create(config={'display_name': STORE_DISPLAY_NAME})

store = get_or_create_store()
init_db() # Initialize the database on startup

def add_chat_history(conversation_id, query, response):
    """Adds a new chat interaction to the history database."""
    try:
        with sqlite3.connect(DB_NAME, detect_types=sqlite3.PARSE_DECLTYPES) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO chat_history (conversation_id, timestamp, query, response) VALUES (?, ?, ?, ?)",
                (conversation_id, datetime.now(), query, response)
            )
            conn.commit()
    except sqlite3.Error as e:
        print(f"Error adding to chat history: {e}")

def get_chat_history():
    """Retrieves all chat history from the database, ordered by most recent."""
    try:
        with sqlite3.connect(DB_NAME, detect_types=sqlite3.PARSE_DECLTYPES) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT conversation_id, timestamp, query, response FROM chat_history ORDER BY timestamp DESC")
            return cursor.fetchall()
    except sqlite3.Error as e:
        print(f"Error fetching chat history: {e}")
        return []

def get_conversations():
    """Retrieves a list of unique conversation IDs and their first query as the title."""
    try:
        with sqlite3.connect(DB_NAME, detect_types=sqlite3.PARSE_DECLTYPES) as conn:
            cursor = conn.cursor()
            # Use a subquery to get the first message for each conversation
            cursor.execute("""
                SELECT T1.conversation_id, T1.query
                FROM chat_history T1
                JOIN (
                    SELECT conversation_id, MIN(timestamp) AS min_ts
                    FROM chat_history
                    GROUP BY conversation_id
                ) T2 ON T1.conversation_id = T2.conversation_id AND T1.timestamp = T2.min_ts
                ORDER BY T1.timestamp DESC;
            """)
            return cursor.fetchall()
    except sqlite3.Error as e:
        print(f"Error fetching conversations: {e}")
        return []

def delete_conversation(conversation_id):
    """Deletes all messages for a given conversation_id from the database."""
    if not conversation_id:
        # This case should ideally not be hit if the button is managed correctly
        return None, None, None, gr.update(), gr.update(visible=False)

    try:
        with sqlite3.connect(DB_NAME, detect_types=sqlite3.PARSE_DECLTYPES) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM chat_history WHERE conversation_id = ?",
                (conversation_id,)
            )
            conn.commit()
        print(f"Deleted conversation: {conversation_id}")
    except sqlite3.Error as e:
        print(f"Error deleting conversation {conversation_id}: {e}")
        # If deletion fails, don't change the UI, just log the error.
        return gr.update(), gr.update(), gr.update(), gr.update(), gr.update(visible=True)

    # After successful deletion, clear the chat, refresh the list, and hide the button
    return None, None, None, refresh_conversation_list(), gr.update(visible=False)

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
    ignored_dirs = CONFIG["ingestion"]["ignored_directories"]
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
            mime_type_map = CONFIG.get("mime_type_map", {})
            file_ext = os.path.splitext(file_name)[1].lower()

            if file_ext in mime_type_map:
                upload_config['mime_type'] = mime_type_map[file_ext]
            else:
                # Default to plain text if mime type is not mapped
                upload_config['mime_type'] = 'text/plain'
            
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
    deleted_message = f"No store with display name '{STORE_DISPLAY_NAME}' found to delete."

    try:
        print("--- Deleting File Search Store ---")
        for store_item in client.file_search_stores.list():
            if store_item.display_name == STORE_DISPLAY_NAME:
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

def chat_wrapper(message, history, chat_session, conversation_id_state, conversation_list_input):
    """
    Wrapper function to manage history for the custom chat UI.
    It calls the main chat_fn and handles history updates.
    """
    # Append the user's message to the history for display
    history.append(ChatMessage(role="user", content=message))
    
    # Get the bot's response by calling the core chat logic
    response_text, new_chat_session, new_conversation_id, conversation_list_update = chat_fn(message, history, chat_session, conversation_id_state, conversation_list_input)
    
    # Append the bot's response to the history
    history.append(ChatMessage(role="assistant", content=response_text))
    
    # Return all the updated states, clearing the input textbox
    return history, "", new_chat_session, new_conversation_id, conversation_list_update

def chat_fn(message, history, chat_session, conversation_id_state, conversation_list_input):
    """
    Handles the chat interaction, using the file search store as a tool.
    """
    # --- DEBUG: Print the state of inputs ---
    print("\n--- Inside chat_fn ---")
    print(f"Message: {message}")
    # The history is now passed directly from the wrapper and is the source of truth.
    print(f"Final history used: {len(history) if history else 0} messages")
    print(f"Chat session exists: {chat_session is not None}")
    print(f"Conversation ID: {conversation_id_state}")
    # --- END DEBUG ---

    # If conversation_id is missing, it's a new conversation.
    if not conversation_id_state:
        new_conversation_started = True
        # Generate a new conversation ID for this new session
        conversation_id_state = f"conv_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        print(f"New conversation started with ID: {conversation_id_state}")
    else:
        new_conversation_started = False

    # If the backend chat session doesn't exist (e.g., after loading a convo), create it.
    if not chat_session:
        # --- DEBUG ---
        print("--- Starting New Backend Chat Session ---")
        chat_session = None # Ensure any previous session object is discarded

        # Convert Gradio's ChatMessage history to Gemini's Content format before creating the session
        gemini_history = []
        if history:
            print(f"--- Preparing {len(history)} messages for new backend session ---")
            for msg in history:
                # The Gemini API uses 'model' for the assistant's role
                # Handle both dict (from Gradio state) and ChatMessage objects (from wrapper)
                if isinstance(msg, dict):
                    role = 'model' if msg['role'] == 'assistant' else msg['role']
                    content = msg['content']
                else: # It's a ChatMessage object
                    role = 'model' if msg.role == 'assistant' else msg.role
                    content = msg.content
                gemini_history.append(types.Content(role=role, parts=[types.Part(text=content)]))


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
        chat_session = client.chats.create( # type: ignore
            history=gemini_history,
            model=CONFIG["gemini_model"]["chat_model_name"],
            config=tool_config
        )

    # Send the user's message to the existing chat session
    try:
        response = chat_session.send_message(message)
        response_text = response.text
    except Exception as e:
        print(f"Error during chat session: {e}")
        # Safe fallback response
        error_message = (
            "I'm sorry, but I encountered an error while processing your request. "
            "This could be due to a temporary issue with the service. Please try again in a moment."
        )
        return error_message, chat_session, conversation_id_state, gr.update()
    
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

    # Save the interaction to the database
    if message and response_text and conversation_id_state:
        add_chat_history(conversation_id_state, message, response_text)

    # If a new conversation was just created, refresh the list on the UI
    if new_conversation_started:
        conversation_list_update = refresh_conversation_list()
        return response_text, chat_session, conversation_id_state, conversation_list_update
    else:
        return response_text, chat_session, conversation_id_state, gr.update()

def load_conversation(conversation_id):
    """Loads a past conversation from the database into the chat window."""
    if not conversation_id:
        return [], None, None, gr.update(value=None), gr.update(visible=False)

    print(f"Loading conversation: {conversation_id}")
    try:
        with sqlite3.connect(DB_NAME, detect_types=sqlite3.PARSE_DECLTYPES) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT query, response FROM chat_history WHERE conversation_id = ? ORDER BY timestamp ASC",
                (conversation_id,)
            )
            history = cursor.fetchall()
    except sqlite3.Error as e:
        print(f"Error loading conversation: {e}")
        return [], None, None, gr.update(value=conversation_id), gr.update(visible=True)

    # Reconstruct Gradio's chatbot history format for type="messages"
    chat_history_formatted = []
    for query, response in history:
        chat_history_formatted.extend([ChatMessage(role="user", content=query), ChatMessage(role="assistant", content=response)])

    # When loading a conversation, we must start a new backend chat session
    # because the session object cannot be serialized and stored.
    # The context is rebuilt by Gradio's history.
    return chat_history_formatted, None, conversation_id, gr.update(value=conversation_id), gr.update(visible=True)

def start_new_chat():
    """Clears the chat interface and starts a new session."""
    return None, None, None, gr.update(value=None), gr.update(visible=False)

def refresh_conversation_list():
    """Refreshes the list of conversations in the sidebar."""
    convos = get_conversations()
    # Format for gr.Radio: list of (label, value) tuples
    formatted_convos = [(f"{title[:40]}..." if len(title) > 40 else title, conv_id) for conv_id, title in convos]
    return gr.update(choices=formatted_convos)

# --- Gradio UI ---
with gr.Blocks(theme=gr.themes.Ocean()) as demo:
    gr.Markdown("<h1 style='text-align: center;'>Aurora Codex</h1>")

    with gr.Tab("Ingest Codebase"):
        gr.Markdown("## Provide Local Codebase Path")
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
        with gr.Row():
            with gr.Column(scale=1):
                gr.Markdown("## Conversations")
                new_chat_button = gr.Button("➕ New Chat", variant="primary")
                refresh_convos_button = gr.Button("🔄 Refresh")
                conversation_list = gr.Radio(
                    label="Past Conversations",
                    interactive=True,
                    elem_classes=["conversation-list"]
                )
                delete_conversation_button = gr.Button("🗑️ Delete Selected", variant="stop", visible=False)

            with gr.Column(scale=4):
                gr.Markdown("## Chat With Your Codebase")
                # State to hold the chat session object and current conversation ID
                chat_session_state = gr.State(None)
                conversation_id_state = gr.State(None)
                
                chatbot = gr.Chatbot(height=600, type="messages", label="Chat with Aurora", show_label=False)
                with gr.Row():
                    chat_input = gr.Textbox(
                        show_label=False,
                        placeholder="Enter your message...",
                        scale=4,
                        container=False
                    )
                    send_button = gr.Button("Send", variant="primary", scale=1)
                gr.Examples(
                    examples=[
                        "What are the main dependencies in requirements.txt?",
                        "Explain the `chat_fn` function and its parameters."
                    ],
                    inputs=[chat_input]
                )

        # --- Event Handlers ---
        # Handle sending a message
        send_button.click(
            fn=chat_wrapper,
            inputs=[chat_input, chatbot, chat_session_state, conversation_id_state, conversation_list],
            outputs=[chatbot, chat_input, chat_session_state, conversation_id_state, conversation_list]
        )
        chat_input.submit(fn=chat_wrapper, inputs=[chat_input, chatbot, chat_session_state, conversation_id_state, conversation_list], outputs=[chatbot, chat_input, chat_session_state, conversation_id_state, conversation_list])

        # Load conversations on startup and when the tab is selected
        demo.load(fn=refresh_conversation_list, outputs=[conversation_list])
        refresh_convos_button.click(fn=refresh_conversation_list, outputs=[conversation_list])

        # Handle selecting a conversation from the list
        conversation_list.input(
            fn=load_conversation,
            inputs=[conversation_list],
            outputs=[chatbot, chat_session_state, conversation_id_state, conversation_list, delete_conversation_button]
        )

        # Handle starting a new chat
        new_chat_button.click(fn=start_new_chat, outputs=[chatbot, chat_session_state, conversation_id_state, conversation_list, delete_conversation_button])

        # Handle deleting a conversation
        delete_conversation_button.click(
            fn=delete_conversation,
            inputs=[conversation_id_state],
            outputs=[chatbot, chat_session_state, conversation_id_state, conversation_list, delete_conversation_button]
        )

if __name__ == "__main__":
    demo.launch()
