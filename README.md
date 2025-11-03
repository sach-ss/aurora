# 🌌 Aurora  
**Conversational RAG-based Coding Assistant for Impact Analysis**

---

[![Python](https://img.shields.io/badge/Python-3.10+-blue?logo=python&logoColor=white)](https://www.python.org/)
[![Ollama](https://img.shields.io/badge/Ollama-Local_LLMs-black?logo=ollama)](https://ollama.com)
[![Gradio](https://img.shields.io/badge/Frontend-Gradio-orange?logo=gradio)](https://gradio.app)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Status](https://img.shields.io/badge/Build-Passing-success.svg)]()

---

Aurora is a **local conversational RAG assistant** designed to perform **impact analysis** on codebases.  
It uses **Ollama LLMs** (Gemma 2B + Nomic Embeddings) and **Gradio UI** to let you chat with your code locally — no cloud dependency.

---

## 🚀 Steps to Run Locally  

Follow these steps to get the application running on your PC.

---

### 🧩 **Step 1: Install Ollama**  
Go to [ollama.com](https://ollama.com) and download the application for Windows.  

Run the installer — Ollama will start automatically in the background.

---

### 🤖 **Step 2: Download the Local Models**  
Open your terminal (Command Prompt or PowerShell).  

Run the following commands to pull the models (Gemma 2B for chat, Nomic for embeddings):

```bash
ollama pull gemma:2b
```

```bash
ollama pull nomic-embed-text
```

---

### 🗂️ **Step 3: Set Up Your Python Project**  
Create your main project folder (e.g., `code-partner-rag-app`).  

Inside it, create the following folders:
- `rag_agent`
- `my_project_code`

Copy all the code files above into their correct locations.  

> ⚠️ **Important:** Place the code files you want to analyze into the `my_project_code` folder.

---

### 🧱 **Step 4: Install Python Dependencies**  
Open your terminal in the project folder (`code-partner-rag-app`).  

It’s recommended to use a Python virtual environment:

```bash
python -m venv venv
source venv/Scripts/activate
```

Install all required dependencies:

```bash
pip install -r requirements.txt
```

---

### 🧮 **Step 5: Ingest Your Code (Create Vector Store)**  
Ensure Ollama is running in the background, then execute:

```bash
python data_ingestion.py
```

This reads your project files, generates embeddings, and stores them in the `vector_store` folder.  
Run this again only if you **add or modify** files in `my_project_code`.

---

### 💻 **Step 6: Run the Gradio App!**  
Start the web interface with:

```bash
python app.py
```

Your terminal will show:  
- **Local URL:** `http://127.0.0.1:7860`  
- **Public URL:** `https://xxxxx.gradio.live`  

Open either in your browser to chat with your code! 🧠

---

## 🧠 Tech Stack  
- **Backend:** Python, LangChain, FAISS, Ollama  
- **Frontend:** Gradio  
- **Embeddings:** Nomic Embed  
- **LLM:** Gemma 2B  

---

## 📂 Project Structure  

```
code-partner-rag-app/
├── rag_agent/
│   ├── data_ingestion.py
│   ├── app.py
│   └── ...
├── my_project_code/
│   └── your_source_files.py
├── vector_store/
│   └── ...
├── requirements.txt
└── README.md
```

---

## 📜 License  
This project is licensed under the **MIT License** — see the [LICENSE](LICENSE) file for details.

---

## ✨ Acknowledgments  
- [Ollama](https://ollama.com) for local LLM support  
- [Nomic](https://nomic.ai) for open embeddings  
- [Gradio](https://gradio.app) for the intuitive web interface  

---

> 💡 *“Aurora turns your codebase into a conversational partner — analyze, query, and explore your projects with AI.”*
