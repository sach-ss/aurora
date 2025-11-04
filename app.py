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
            answer = agent.query(message, history)
        except ValueError as e:
            # Handle the common Ollama memory error gracefully
            if "unable to load full model on GPU" in str(e):
                return "❌ **Ollama Model Error:** The chat model (Gemma 2B) failed to load due to insufficient system memory. Please ensure the Ollama server is running and system resources are available."
            return f"❌ An error occurred during the LLM call: {e}"
        except Exception as e:
            return f"❌ An unexpected error occurred: {e}"

        return answer

    # 3. Create the Gradio App with gr.Blocks and Tabs
    with gr.Blocks(theme="soft", title="🤖 Code Partner AI") as demo:
        gr.Markdown("# 🤖 Code Partner AI (Local Gemma 2B Edition)")
        
        with gr.Tabs():
            # Chat Interface Tab
            with gr.TabItem("Chat Agent"):
                gr.ChatInterface(
                    fn=query_agent,
                    examples=[
                        "What is the overall architecture of this project?",
                        "Explain the purpose of the main function in the entrypoint file.",
                        "How is database connectivity handled in this application?",
                    ],
                    type="messages"
                )

    # Launch the app!
    print("\n---")
    print("✅ Gradio App running. Make sure Ollama is active.")
    print("---")
    # Share=True creates a public link for easy testing from other devices
    demo.launch(share=False) 

except Exception as e:
    print(f"❌ An error occurred during initialization or launch: {e}", file=sys.stderr)
    print("Please ensure Ollama is running and you have run 'python data_ingestion.py'.")