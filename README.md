# 🌌 Aurora
**Conversational Coding Assistant for Impact Analysis using Gemini**

---

[![Python](https://img.shields.io/badge/Python-3.10+-blue?logo=python&logoColor=white)](https://www.python.org/)
[![Gemini](https://img.shields.io/badge/Gemini_API-Google-4285F4?logo=google)](https://ai.google.dev/)
[![Gradio](https://img.shields.io/badge/Frontend-Gradio-orange?logo=gradio)](https://gradio.app)
[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)

---

Aurora is a **conversational assistant** designed to perform **impact analysis** on codebases.
It uses the **Google Gemini API** (defaulting to the fast `gemini-2.5-flash` model) with its native file search capabilities and a **Gradio UI** to let you chat with your code.

---

## 🚀 Steps to Run Locally

Follow these steps to get the application running.

---

### 🧩 **Step 1: Get a Google API Key**
1.  **Go to Google AI Studio:** Open your browser and navigate to [https://aistudio.google.com/app/apikey](https://aistudio.google.com/app/apikey).
2.  **Sign In:** Use your Google account to sign in.
3.  **Create API Key:** Click the **"Create API key"** button. You may be prompted to create a new Google Cloud project; this is a standard step.
4.  **Copy Your Key:** A window will appear with your new API key. Copy this key to your clipboard.

> **⚠️ Important:** Treat your API key like a password. Never share it publicly or commit it to a Git repository.

### 🗂️ **Step 2: Set Up Your Project**
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

### 🧱 **Step 3: Install Python Dependencies**
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

### 💻 **Step 4: Run the Gradio App!**
Start the web interface.

```bash
python app.py
```

Your terminal will show:
- **Local URL:** `http://127.0.0.1:7860`
- **Public URL:** `https://xxxxx.gradio.live`

Open either in your browser.

---

### **Step 5: Ingest and Chat**
1.  **Ingest Codebase:** In the "Ingest Codebase" tab, upload all relevant code files (`.py`, `.js`, `.ts`, `.md`, etc.). The tool will create a searchable index of your codebase.
2.  **Chat With Your Codebase:** Once ingestion is complete, switch to the "Chat" tab and start asking questions about your code.

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
├── prompts.yaml            # <-- All LLM prompts
├── requirements.txt
└── README.md
```

---

## 📝 Notes
*   The file search store name is hardcoded as `"aurora-code-analysis-store"`. If you want to use a different name, you'll need to modify `app.py`.

---

## 📜 License
This project is licensed under the **Apache License 2.0**. See the `LICENSE` file for details.

---

## ✨ Acknowledgments
- Google for the Gemini API
- Gradio for the intuitive web interface

---

> 💡 *“Aurora turns your codebase into a conversational partner — analyze, query, and explore your projects with the power of Gemini.”*
