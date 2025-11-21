# 🌌 Aurora Codex
**An Advanced Conversational Assistant for Codebase Impact Analysis**

---

[![Python](https://img.shields.io/badge/Python-3.12+-blue?logo=python&logoColor=white)](https://www.python.org/)
[![Gemini](https://img.shields.io/badge/Gemini_API-Google-4285F4?logo=google)](https://ai.google.dev/)
[![Gradio](https://img.shields.io/badge/Frontend-Gradio-orange?logo=gradio)](https://gradio.app)
[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)

---

Aurora Codex is an advanced, conversational AI assistant designed to perform deep impact analysis on your codebases. It leverages the **Google Gemini API** for Retrieval-Augmented Generation (RAG) and Python's native **Abstract Syntax Tree (AST)** module for static code analysis. The entire experience is delivered through a clean and interactive **Gradio** web interface.

---

## ✨ Key Features

- **Conversational Code Analysis (RAG):** Ingest any codebase and start a conversation. Ask questions about functions, dependencies, and potential impacts in natural language.
- **Static Knowledge Graph Generation:** Build a detailed structural map of your Python codebase. The tool uses AST to parse `.py` files, identify entities (functions, classes) and relationships (imports, calls), and saves this as a `knowledge_graph.json`.
- **Advanced Impact Analysis:**
  - **Criticality Assessment:** Request a prioritized analysis of impacted components, classified as High, Medium, or Low, with justifications for each.
  - **Dynamic Dependency Visualization:** Generate on-the-fly dependency graphs using Mermaid.js based on your conversation to visually understand component relationships.
- **Exportable Reports:** Download your entire impact analysis conversation as a structured Markdown report for documentation or sharing.
- **Interactive UI:**
  - A clean, themeable interface powered by Gradio.
  - Collapsible sidebar to maximize chat space.
  - Separate tabs for file ingestion, chat, and visualization.

---

## 🚀 Steps to Run Locally

Follow these steps to get the application running.

---

### 🧩 Step 1: Get a Google API Key
1.  **Go to Google AI Studio:** Open your browser and navigate to [https://aistudio.google.com/app/apikey](https://aistudio.google.com/app/apikey).
2.  **Sign In:** Use your Google account to sign in.
3.  **Create API Key:** Click the **"Create API key"** button. You may be prompted to create a new Google Cloud project; this is a standard step.
4.  **Copy Your Key:** A window will appear with your new API key. Copy this key to your clipboard.

> **⚠️ Important:** Treat your API key like a password. Never share it publicly or commit it to a Git repository.

### 🗂️ Step 2: Set Up Your Project
1.  Clone the repository from GitHub and navigate into the directory:
    ```bash
    git clone https://github.com/PushkarKashyap/aurora
    cd aurora
    ```

2.  **Configure your environment:**
    - Create a `.env` file by copying the example:
      ```bash
      # For Windows (Command Prompt)
      copy .env.example .env
      # For macOS/Linux
      # cp .env.example .env
      ```
    - Open the new `.env` file and paste your Google API key from Step 1.

---

### 🧱 Step 3: Install Python Dependencies
Open your terminal in the project folder (`aurora`).

It’s recommended to use a Python virtual environment:

```bash
python -m venv venv
venv\Scripts\activate  # On Windows
# source venv/Scripts/activate  # On macOS/Linux
```

Install all required dependencies:

```bash
pip install -r requirements.txt
```

---

### 💻 Step 4: Run the Gradio App
Start the web interface.

```bash
python app.py
```

Your terminal will show:
- **Local URL:** `http://127.0.0.1:7860`
- **Public URL:** `https://xxxxx.gradio.live`

Open either in your browser.

---

### 🔎 Step 5: Analyze Your Codebase
1.  **Ingest Files:** On the **"Ingest Codebase"** tab, provide the path to your local codebase and click **"Ingest Files"**. This creates a searchable index for the RAG functionality.
2.  **Build Knowledge Graph:** Click **"Build Knowledge Graph"**. This performs a static analysis of all `.py` files and creates a `knowledge_graph.json` file. You can view the result by clicking **"View Graph"**.
3.  **Chat & Analyze:** Switch to the **"Chat"** tab.
    - Ask questions about your code's functionality and dependencies.
    - Use the **"Assess Criticality"** checkbox for a deeper, prioritized analysis.
    - After a conversation, click **"Visualize Impact"** to see a dependency diagram in the **"Visualization"** tab.
    - Download your session as a report using the **"Generate Report"** button.

---

## ⚠️ Store Management

Over time, you may create multiple file search stores in your Google AI account. A standalone script is provided to clean these up.

To **delete all** file search stores associated with your API key, run the following command from your terminal:

```bash
python cleanup_stores.py
```

The script will ask for confirmation before proceeding with the deletion.

---

## 🧠 Tech Stack
- **Backend:** Python, Google Gemini API
- **Frontend:** Gradio
- **LLM:** Gemini 2.5 Flash (default)

---

## 📂 Project Structure

```
aurora/
├── .env                    # <-- Local environment configuration (created from example)
├── config.yaml             # <-- Application-wide configuration (e.g., store name, ignored dirs)
├── .env.example
├── .gitignore
├── app.py                  # <-- Main application entrypoint
├── chat.py                 # <-- Core chat logic and database interactions
├── ingest.py               # <-- File ingestion and indexing logic
├── prompts.yaml            # <-- All LLM prompts
├── requirements.txt
├── README.md
├── .git/                   # <-- Git version control directory
├── .gradio/                # <-- Gradio-related files (e.g., certificates)
├── data/                   # <-- Directory for data files (if any)
├── __pycache__/            # <-- Python cache files
└── venv/                   # <-- Python virtual environment
```

---

## 📝 Notes
*   The file search store name (`display_name`) can be configured in `config.yaml`.
*   The ingestion process in `ingest.py` processes files sequentially. For very large codebases, this might be slow.
*   The chat history is stored in a local SQLite database, configured via `config.yaml`.

---

## 📜 License
This project is licensed under the **Apache License 2.0**. See the `LICENSE` file for details.

---

## ✨ Acknowledgments
- Google for the Gemini API
- Gradio for the intuitive web interface

---

> 💡 *“Aurora turns your codebase into a conversational partner — analyze, query, and explore your projects with the power of Gemini.”*
