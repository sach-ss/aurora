import sqlite3
from datetime import datetime
import tempfile
import json
import os
from gradio.components import ChatMessage
import gradio as gr
from google.genai import types


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

# --- Database Management ---
def init_db(db_name):
    """Initializes the SQLite database and creates the history table if it doesn't exist."""
    print(f"--- Initializing Database: {db_name} ---")
    try:
        with sqlite3.connect(db_name, detect_types=sqlite3.PARSE_DECLTYPES) as conn:
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


def add_chat_history(db_name, conversation_id, query, response):
    """Adds a new chat interaction to the history database."""
    try:
        with sqlite3.connect(db_name, detect_types=sqlite3.PARSE_DECLTYPES) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO chat_history (conversation_id, timestamp, query, response) VALUES (?, ?, ?, ?)",
                (conversation_id, datetime.now(), query, response)
            )
            conn.commit()
    except sqlite3.Error as e:
        print(f"Error adding to chat history: {e}")


def get_conversations(db_name):
    """Retrieves a list of unique conversation IDs and their first query as the title."""
    try:
        with sqlite3.connect(db_name, detect_types=sqlite3.PARSE_DECLTYPES) as conn:
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


def delete_conversation_from_db(db_name, conversation_id):
    """Deletes all messages for a given conversation_id from the database."""
    try:
        with sqlite3.connect(db_name, detect_types=sqlite3.PARSE_DECLTYPES) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM chat_history WHERE conversation_id = ?",
                (conversation_id,)
            )
            conn.commit()
        print(f"Deleted conversation: {conversation_id}")
        return True
    except sqlite3.Error as e:
        print(f"Error deleting conversation {conversation_id}: {e}")
        return False


def load_conversation_from_db(db_name, conversation_id):
    """Loads a past conversation from the database."""
    try:
        with sqlite3.connect(db_name, detect_types=sqlite3.PARSE_DECLTYPES) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT query, response FROM chat_history WHERE conversation_id = ? ORDER BY timestamp ASC",
                (conversation_id,)
            )
            return cursor.fetchall()
    except sqlite3.Error as e:
        print(f"Error loading conversation: {e}")
        return []


def generate_report(conversation_id, db_name):
    """Generates a markdown report from a conversation and returns the file path."""
    from gradio import update as gr_update # Local import
    if not conversation_id:
        return gr_update(value=None, visible=False)

    history = load_conversation_from_db(db_name, conversation_id)
    if not history:
        return gr_update(value=None, visible=False)

    # Create the report content
    report_content = f"# Impact Analysis Report\n\n"
    report_content += f"**Conversation ID:** `{conversation_id}`\n"
    report_content += f"**Generated on:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
    report_content += "---\n\n"

    all_sources = set()

    for i, (query, response) in enumerate(history):
        report_content += f"### Interaction {i+1}\n\n"
        report_content += f"**User Query:**\n```\n{query}\n```\n\n"
        report_content += f"**Aurora's Response:**\n{response}\n\n"
        
        # Extract sources from the response
        if "**Sources:**" in response:
            sources_part = response.split("**Sources:**")[1]
            sources = [line.split('`')[1] for line in sources_part.strip().split('\n') if '`' in line]
            all_sources.update(sources)
        report_content += "---\n\n"

    # Create a temporary file to store the report
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.md', encoding='utf-8') as temp_file:
        temp_file.write(report_content)
        return gr_update(value=temp_file.name, visible=True)


def generate_visualization(conversation_id, db_name, config, show_neighbors=False):
    """
    Generates a Mermaid diagram by filtering the knowledge graph based on the current conversation.
    """
    if not conversation_id:
        return "```mermaid\ngraph TD;\n  A[No conversation selected.];\n```"

    # 1. Load the full knowledge graph
    graph_file_path = config.get("knowledge_graph", {}).get("graph_file_path")
    if not graph_file_path or not os.path.exists(graph_file_path):
        return "```mermaid\ngraph TD;\n  A[Knowledge graph not found. Please build it on the Ingest page.];\n```"
    
    with open(graph_file_path, 'r', encoding='utf-8') as f:
        knowledge_graph = json.load(f)

    # 2. Identify relevant entities from the chat conversation
    history = load_conversation_from_db(db_name, conversation_id)
    if not history:
        return "```mermaid\ngraph TD;\n  A[Could not load conversation history.];\n```"

    all_text = "".join([q + r for q, r in history])
    all_node_ids = {node['id'] for node in knowledge_graph['nodes']}
    
    # Find nodes mentioned in the conversation
    mentioned_nodes = {node_id for node_id in all_node_ids if node_id in all_text}

    if not mentioned_nodes:
        return "```mermaid\ngraph TD;\n  A[No specific code entities found in this conversation to visualize.];\n```"

    # 3. Build the subgraph based on whether to include neighbors
    if show_neighbors:
        # Expanded view: include mentioned nodes and their direct neighbors
        subgraph_nodes = set(mentioned_nodes)
        subgraph_edges = []
        for edge in knowledge_graph['edges']:
            source, target = edge['source'], edge['target']
            if source in mentioned_nodes or target in mentioned_nodes:
                subgraph_nodes.add(source)
                subgraph_nodes.add(target)
                subgraph_edges.append(edge)
    else:
        # Focused view: include only edges between mentioned nodes.
        subgraph_nodes = set(mentioned_nodes)
        subgraph_edges = [
            edge for edge in knowledge_graph['edges']
            if edge['source'] in subgraph_nodes and edge['target'] in subgraph_nodes
        ]
        # The nodes for the subgraph are only those that are part of the filtered edges.
        subgraph_nodes = {node for edge in subgraph_edges for node in (edge['source'], edge['target'])}

    # 4. Convert the subgraph to Mermaid syntax
    mermaid_string = "graph TD;\n"
    # Create safe IDs for mermaid (replace dots, etc.)
    safe_ids = {node_id: node_id.replace('.', '_').replace('-', '_') for node_id in subgraph_nodes}

    for node_id in sorted(list(subgraph_nodes)):
        # Highlight the nodes that were directly mentioned in the chat
        if node_id in mentioned_nodes:
            mermaid_string += f'  {safe_ids[node_id]}["`{node_id}`"];\n'
            mermaid_string += f'  style {safe_ids[node_id]} fill:#0b5394,stroke:#fff,stroke-width:2px,color:#fff;\n'
        else:
            mermaid_string += f'  {safe_ids[node_id]}["{node_id}"];\n'

    for edge in subgraph_edges:
        source, target = edge['source'], edge['target']
        if source in safe_ids and target in safe_ids:
            mermaid_string += f"  {safe_ids[source]} -->|{edge['type']}| {safe_ids[target]};\n"

    return f"```mermaid\n{mermaid_string}\n```"

# --- Core Chat Logic ---
def chat_fn(message, history, chat_session, conversation_id_state, client, store, prompts, config):
    """
    Handles the chat interaction, using the file search store as a tool.
    """
    db_name = config["database_name"]
    new_conversation_started = False

    # If conversation_id is missing, it's a new conversation.
    if not conversation_id_state:
        new_conversation_started = True
        # Generate a new conversation ID for this new session
        conversation_id_state = f"conv_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        print(f"New conversation started with ID: {conversation_id_state}")

    # If the backend chat session doesn't exist (e.g., after loading a convo), create it.
    if not chat_session:
        chat_session = None  # Ensure any previous session object is discarded

        # Convert Gradio's ChatMessage history to Gemini's Content format before creating the session
        gemini_history = []
        if history:
            for msg in history:
                # The Gemini API uses 'model' for the assistant's role
                if isinstance(msg, dict):
                    role = 'model' if msg['role'] == 'assistant' else msg['role']
                    content = msg['content']
                else:  # It's a ChatMessage object
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
            system_instruction=prompts.get("chat_prompt")
        )
        # Start a chat session with the tool config
        chat_session = client.chats.create(  # type: ignore
            history=gemini_history,
            model=config["gemini_model"]["chat_model_name"],
            config=tool_config
        )

    # Send the user's message to the existing chat session
    try:
        response = chat_session.send_message(message)
        response_text = response.text
    except Exception as e:
        print(f"Error during chat session: {e}")
        error_message = (
            "I'm sorry, but I encountered an error while processing your request. "
            "This could be due to a temporary issue with the service. Please try again in a moment."
        )
        return error_message, chat_session, conversation_id_state, new_conversation_started

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
        add_chat_history(db_name, conversation_id_state, message, response_text)

    return response_text, chat_session, conversation_id_state, new_conversation_started


def _get_conversation_controls_updates(visible: bool, report_file_value=None):
    """Helper to generate gr.update dictionaries for conversation-specific controls."""
    # Returns a tuple of gr.update objects in the order they appear in conversation_controls
    return (
        gr.update(visible=visible),  # delete_conversation_button
        gr.update(visible=visible),  # generate_report_button
        gr.update(visible=visible if report_file_value else False, value=report_file_value), # report_file
        gr.update(visible=visible),  # visualize_button
        gr.update(visible=visible)   # visualize_neighbors_checkbox
    )

def load_conversation(conversation_id, db_name):
    """Loads a past conversation from the database into the chat window."""
    from gradio import update as gr_update # Local import to avoid circular dependency issues
    if not conversation_id:
        return [], None, None, gr_update(value=None), *_get_conversation_controls_updates(False)

    print(f"Loading conversation: {conversation_id}")
    history = load_conversation_from_db(db_name, conversation_id)

    if not history:
        # Handle case where history is not found or there was a DB error
        return [], None, None, gr_update(value=conversation_id), *_get_conversation_controls_updates(True)

    # Reconstruct Gradio's chatbot history format for type="messages"
    chat_history_formatted = []
    for query, response in history:
        chat_history_formatted.extend([ChatMessage(role="user", content=query), ChatMessage(role="assistant", content=response)])

    # When loading a conversation, we must start a new backend chat session
    # because the session object cannot be serialized and stored.
    # The context is rebuilt by Gradio's history.
    return chat_history_formatted, None, conversation_id, gr_update(value=conversation_id), *_get_conversation_controls_updates(True)


# --- UI Wrapper Functions ---
def chat_wrapper(message, history, assess_criticality, chat_session, conversation_id_state, client, store, prompts, config, refresh_conversation_list_fn):
    """
    Wrapper function to manage history for the custom chat UI.
    It calls the main chat_fn and handles history updates.
    """
    # Append the user's message to the history for display
    history.append(ChatMessage(role="user", content=message))

    # If the user wants a criticality assessment, append the instruction to the message
    final_message = message
    if assess_criticality:
        final_message += "\n\nPlease also provide a detailed criticality assessment for the identified impacts, prioritizing them from most to least critical."
    
    # Get the bot's response by calling the core chat logic
    response_text, new_chat_session, new_conversation_id, new_convo_started = chat_fn(
        final_message, history, chat_session, conversation_id_state, client, store, prompts, config
    )
    
    # Append the bot's response to the history
    history.append(ChatMessage(role="assistant", content=response_text))
    
    # If a new conversation was started, refresh the list
    conversation_list_update = refresh_conversation_list_fn() if new_convo_started else gr.update()

    # Return all the updated states, clearing the input textbox
    return history, "", new_chat_session, new_conversation_id, conversation_list_update

def get_formatted_conversations(db_name):
    """Fetches and formats conversations for the gr.Radio component."""
    convos = get_conversations(db_name)
    # Format for gr.Radio: list of (label, value) tuples
    return [(f"{title[:40]}..." if len(title) > 40 else title, conv_id) for conv_id, title in convos]

def create_chat_ui(client, store, prompts, config):
    """Creates the Gradio UI for the Chat tab."""
    db_name = config["database_name"]

    with gr.Tab("Chat") as chat_tab:
        with gr.Row():
            with gr.Sidebar():
                new_chat_button = gr.Button("➕ New Chat", variant="primary")
                refresh_convos_button = gr.Button("🔄 Refresh", variant="secondary")
                conversation_list = gr.Radio(
                    choices=get_formatted_conversations(db_name),
                    # Note: The 'height' parameter is not standard. CSS is used instead.
                    label="Past Conversations",
                    interactive=True,
                    show_label=False,
                    elem_classes=["conversation-list-container"]
                )
                with gr.Group(): # Group controls for easier update
                    delete_conversation_button = gr.Button("🗑️ Delete Selected", variant="stop", visible=False, elem_id="delete_conversation_button")
                    generate_report_button = gr.Button("📄 Generate Report", variant="secondary", visible=False, elem_id="generate_report_button")
                    report_file = gr.File(label="Download Report", visible=False, interactive=False, elem_id="report_file")
                    visualize_button = gr.Button("🎨 Visualize Impact", variant="secondary", visible=False, elem_id="visualize_button")
                    visualize_neighbors_checkbox = gr.Checkbox(label="Show Neighbors", value=False, visible=False, scale=1, elem_id="visualize_neighbors_checkbox")

            with gr.Column(scale=4):
                chat_session_state = gr.State(None)
                conversation_id_state = gr.State(None)
                
                chatbot = gr.Chatbot(
                    height=600, type="messages", label="Chat with Aurora", show_label=True, container=True, show_copy_button=True,
                    examples=[
                        {"text": "What are the main dependencies in requirements.txt?"},
                        {"text": "Explain the `chat_fn` function and its parameters."}
                    ]
                )
                with gr.Row():
                    chat_input = gr.Textbox(show_label=False, placeholder="Enter your message...", scale=4, container=False)
                    assess_criticality_checkbox = gr.Checkbox(label="Assess Criticality", value=False, scale=1)
                    send_button = gr.Button("Send", variant="primary", scale=1)
        
        with gr.Tab("Visualization"):
            visualization_output = gr.Markdown("No visualization generated yet. Ask a question and then click 'Visualize Impact'.", elem_id="visualization-output")

        def populate_example(evt: gr.SelectData):
            """Populates the chat input with the text from the clicked example."""
            return evt.value['text']

        # --- Event Handlers ---
        refresh_fn = lambda: refresh_conversation_list(db_name)
        
        chat_wrapper_fn = lambda msg, hist, crit, sess, conv_id: chat_wrapper(msg, hist, crit, sess, conv_id, client, store, prompts, config, refresh_fn)
        send_button.click(fn=chat_wrapper_fn, inputs=[chat_input, chatbot, assess_criticality_checkbox, chat_session_state, conversation_id_state], outputs=[chatbot, chat_input, chat_session_state, conversation_id_state, conversation_list])
        chat_input.submit(fn=chat_wrapper_fn, inputs=[chat_input, chatbot, assess_criticality_checkbox, chat_session_state, conversation_id_state], outputs=[chatbot, chat_input, chat_session_state, conversation_id_state, conversation_list])

        chatbot.example_select(fn=populate_example, inputs=None, outputs=[chat_input])

        load_conversation_fn = lambda conv_id: load_conversation(conv_id, db_name)
        conversation_controls = [delete_conversation_button, generate_report_button, report_file, visualize_button, visualize_neighbors_checkbox]

        refresh_convos_button.click(fn=refresh_fn, outputs=[conversation_list] + conversation_controls)

        conversation_list.input(
            fn=load_conversation_fn,
            inputs=[conversation_list],
            outputs=[chatbot, chat_session_state, conversation_id_state, conversation_list] + conversation_controls
        )

        new_chat_button.click(
            fn=lambda: start_new_chat(db_name),
            outputs=[chatbot, chat_session_state, conversation_id_state, conversation_list] + conversation_controls,
            show_progress="hidden"
        )

        delete_conversation_fn = lambda conv_id: delete_conversation(conv_id, db_name, refresh_fn)
        delete_conversation_button.click(
            fn=delete_conversation_fn,
            inputs=[conversation_id_state],
            outputs=[chatbot, chat_session_state, conversation_id_state, conversation_list] + conversation_controls
        )

        generate_report_fn = lambda conv_id: generate_report(conv_id, db_name)
        generate_report_button.click(fn=generate_report_fn, inputs=[conversation_id_state], outputs=[report_file])

        visualize_fn = lambda conv_id, show_neighbors: generate_visualization(conv_id, db_name, config, show_neighbors)
        visualize_button.click(fn=visualize_fn, inputs=[conversation_id_state, visualize_neighbors_checkbox], outputs=[visualization_output], show_progress="hidden")

def start_new_chat(db_name):
    """Clears the chat interface and starts a new session."""
    # Clear chat, session, and conversation selection. Also hide controls.
    formatted_convos = get_formatted_conversations(db_name)
    # Create a new update object that both refreshes choices and clears the selection
    conversation_list_update = gr.update(choices=formatted_convos, value=None)
    return None, None, None, conversation_list_update, *_get_conversation_controls_updates(False)

def refresh_conversation_list(db_name):
    """Refreshes the list of conversations in the sidebar."""
    formatted_convos = get_formatted_conversations(db_name)
    return gr.update(choices=formatted_convos), *_get_conversation_controls_updates(False)

def delete_conversation(conversation_id, db_name, refresh_conversation_list_fn):
    """Deletes a conversation and updates the UI."""
    if not conversation_id:
        return None, None, None, gr.update(), *_get_conversation_controls_updates(False)

    success = delete_conversation_from_db(db_name, conversation_id)

    if not success:
        # If deletion fails, don't change the UI, just log the error.
        return gr.update(), gr.update(), gr.update(), gr.update(), *_get_conversation_controls_updates(True)

    # After successful deletion, clear the chat, refresh the list, and hide the button
    # We call refresh_fn() which returns a tuple of updates for the list and controls.
    conversation_list_update, *control_updates = refresh_conversation_list_fn()
    return None, None, None, conversation_list_update, *control_updates