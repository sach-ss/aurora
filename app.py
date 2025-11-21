import gradio as gr
from gradio.components import ChatMessage
import os
import yaml
from dotenv import load_dotenv
from google import genai

from ingest import get_or_create_store, create_ingest_ui
from chat import init_db, create_chat_ui

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

store = get_or_create_store(client, STORE_DISPLAY_NAME)
init_db(DB_NAME) # Initialize the database on startup

# --- Gradio UI ---
css = """
.conversation-list-container {
    max-height: 300px;
    overflow-y: auto;
    border: 1px solid #e0e0e0;
    border-radius: 8px;
}
#visualization-output {
    min-height: 600px;
    overflow: auto;
}
"""
with gr.Blocks(theme=gr.themes.Ocean(), css=css) as demo:
    gr.Markdown("<h1 style='text-align: center;'>Aurora Codex</h1>")

    # Create the Ingest tab by calling the function from ingest.py
    create_ingest_ui(client, store, CONFIG)

    # Create the Chat tab by calling the function from chat.py
    create_chat_ui(client, store, PROMPTS, CONFIG)

if __name__ == "__main__":
    demo.launch()
