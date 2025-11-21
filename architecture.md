
```mermaid
graph TD
    subgraph "User Interface (Gradio)"
        A[app.py - Main Entry]
        B[Ingest Tab]
        C[Chat Tab]
        D[Visualization Tab]
    end

    subgraph "Backend Services"
        E[ingest.py]
        F[chat.py]
        G[Google Gemini API]
        H[SQLite Database]
        I[knowledge_graph.json]
        J[File System]
        K[Google AI File Search Store]
    end

    A --> B
    A --> C
    C --> D

    B --> E
    C --> F

    E -- "Scans Files" --> J
    E -- "Uploads Files" --> K
    E -- Creates --> I

    F -- "Interacts with (for Chat and RAG)" --> G
    F -- "Manages Chat History in" --> H
    F -- "Reads for Visualization from" --> I

    G -- Uses --> K
```

This diagram illustrates the architecture of the Aurora Codex application.

*   The **User Interface** is built with Gradio and is divided into several tabs.
*   `app.py` is the main entry point that launches the UI.
*   The **Ingest Tab** uses `ingest.py` to:
    *   Scan the local **File System**.
    *   Upload files to the **Google AI File Search Store**.
    *   Create the **knowledge_graph.json** by analyzing Python files.
*   The **Chat Tab** is powered by `chat.py`, which:
    *   Communicates with the **Google Gemini API** to get chat responses, using the **File Search Store** for Retrieval-Augmented Generation (RAG).
    *   Manages the conversation history in a **SQLite Database**.
    *   Reads the **knowledge_graph.json** to generate visualizations.
*   The **Visualization Tab** displays the diagrams created by `chat.py`.
