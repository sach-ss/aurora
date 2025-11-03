import gradio as gr
from dotenv import load_dotenv
from rag_agent.retrieval import CodeRetrievalAgent
from typing import List, Tuple
import sys

# Load environment variables (if any)
load_dotenv()

try:
    # 1. Initialize our RAG agent
    agent = CodeRetrievalAgent()

    # 2. Define the chat function for Gradio
    def query_agent(message: str, history: List[Tuple[str, str]]):
        print(f"Received query: {message}")
        
        try:
            # Call the agent's query method
            answer, sources = agent.query(message, history)
        except ValueError as e:
            # Handle the common Ollama memory error gracefully
            if "unable to load full model on GPU" in str(e):
                return "❌ **Ollama Model Error:** The chat model (Gemma 2B) failed to load due to insufficient system memory. Please ensure the Ollama server is running and system resources are available."
            return f"❌ An error occurred during the LLM call: {e}"
        except Exception as e:
            return f"❌ An unexpected error occurred: {e}"

        response = answer
        
        if sources:
            response += "\n\n---\n"
            response += "### 📚 Relevant Code Context\n"
            
            # 1. Group sources by filename for clear presentation
            source_map = {}
            for doc in sources:
                source_file = doc.metadata.get('source', 'N/A')
                # Extract line number if available (e.g., from TextLoader)
                start_line = doc.metadata.get('lines', {}).get('from', 'Unknown')
                
                # Clean up the path for display
                clean_path = source_file.replace('./my_project_code/', '')
                
                # Use the start_line as the key for uniqueness within the file
                source_key = (clean_path, start_line)
                
                if source_key not in source_map:
                    source_map[source_key] = doc.page_content

            # 2. Format the sources into a Markdown list
            for (file_name, line), content in source_map.items():
                response += f"**File:** `{file_name}` (Line {line})\n"
                
                # Use a Markdown blockquote to display the snippet
                # Clean up content by stripping leading/trailing whitespace and tabs
                snippet = content.strip()
                response += f"> ```python\n> {snippet}\n> ```\n\n"
                
        return response

    # 3. Define the graph function
    def render_graph():
        mermaid_code = agent.generate_graph_mermaid()
        return mermaid_code

    # 4. Create the Gradio App with gr.Blocks and Tabs
    with gr.Blocks(theme="soft", title="🤖 Code Partner AI") as demo:
        gr.Markdown("# 🤖 Code Partner AI (Local Gemma 2B Edition)")
        
        with gr.Tabs():
            # Chat Interface Tab
            with gr.TabItem("Chat Agent"):
                gr.ChatInterface(
                    fn=query_agent,
                    examples=[
                        "What is the function of the vector_store in the app?",
                        "Explain the purpose of the function 'create_database' in data_ingestion.py",
                    ],
                    type="messages"
                )
            
            # Dependency Graph Tab
            with gr.TabItem("Dependency Graph"):
                with gr.Column():
                    gr.Markdown("Click the button to generate and display the code dependency graph.")
                    graph_btn = gr.Button("🚀 Generate Graph")
                    graph_output = gr.Markdown(label="Generated Graph")
                
                graph_btn.click(fn=render_graph, inputs=None, outputs=graph_output)

    # Launch the app!
    print("\n---")
    print("✅ Gradio App running. Make sure Ollama is active.")
    print("---")
    # Share=True creates a public link for easy testing from other devices
    demo.launch(share=False) 

except Exception as e:
    print(f"❌ An error occurred during initialization or launch: {e}", file=sys.stderr)
    print("Please ensure Ollama is running and you have run 'python data_ingestion.py'.")