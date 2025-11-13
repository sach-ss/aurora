import os
import time
import json
import gradio as gr
import ast


def get_or_create_store(client, store_display_name):
    """Gets the file search store or creates it if it doesn't exist."""
    print(f"--- Initializing File Search Store: {store_display_name} ---")

    # Check if the store already exists
    for store in client.file_search_stores.list():
        if store.display_name == store_display_name:
            print(f"Found existing store: {store.name}")
            return store

    # If not found, create a new one
    print(f"Store not found, creating a new one: {store_display_name}")
    return client.file_search_stores.create(config={'display_name': store_display_name})


def ingest_files(directory_path, client, store, config):
    """
    Finds all files in a directory, uploads them to the file search store,
    yields progress, and waits for completion.
    """
    if not directory_path or not os.path.isdir(directory_path):
        # Return a final message if the path is invalid
        yield "❌ Error: Please provide a valid directory path."
        return

    yield f"Scanning directory: {directory_path}"
    print(f"Scanning directory: {directory_path}")

    # Find all files in the directory
    all_files = []
    ignored_dirs = config["ingestion"]["ignored_directories"]
    ignored_files = config["ingestion"].get("ignored_files", [])
    for root, dirs, files in os.walk(directory_path):
        # Remove ignored directories from the search
        dirs[:] = [d for d in dirs if d not in ignored_dirs]
        for file in files:
            if file.startswith('.'):
                continue
            if file in ignored_files:
                continue
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
            mime_type_map = config.get("mime_type_map", {})
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

    final_message = f"✅ Ingestion complete for {len(all_files)} files. You can now use the Chat tab."
    yield final_message


class CodeAnalyzer(ast.NodeVisitor):
    """
    An AST node visitor that extracts nodes (files, functions, classes)
    and edges (imports, calls) from Python code.
    """
    def __init__(self, file_name):
        self.file_name = file_name
        self.nodes = []
        self.edges = []
        self.current_scope = file_name  # Start with file-level scope

    def visit_FunctionDef(self, node):
        self.nodes.append({"id": node.name, "type": "function", "file": self.file_name})
        parent_scope = self.current_scope
        self.current_scope = node.name
        self.generic_visit(node)
        self.current_scope = parent_scope

    def visit_ClassDef(self, node):
        self.nodes.append({"id": node.name, "type": "class", "file": self.file_name})
        parent_scope = self.current_scope
        self.current_scope = node.name
        self.generic_visit(node)
        self.current_scope = parent_scope

    def visit_Import(self, node):
        for alias in node.names:
            self.edges.append({"source": self.file_name, "target": alias.name, "type": "imports"})
        self.generic_visit(node)

    def visit_ImportFrom(self, node):
        if node.module:
            self.edges.append({"source": self.file_name, "target": node.module, "type": "imports"})
        self.generic_visit(node)

    def visit_Call(self, node):
        # This is a simplified call analysis. It captures direct function names.
        if isinstance(node.func, ast.Name):
            self.edges.append({"source": self.current_scope, "target": node.func.id, "type": "calls"})
        self.generic_visit(node)


def build_knowledge_graph(directory_path, config):
    """
    Scans a directory, uses Python's AST module to extract entities and relationships
    from .py files, and builds a knowledge graph.
    """
    if not directory_path or not os.path.isdir(directory_path):
        yield "❌ Error: Please provide a valid directory path to build the graph."
        return

    yield f"Scanning directory for graph construction: {directory_path}"
    python_files = []
    ignored_dirs = config["ingestion"]["ignored_directories"]
    ignored_files = config["ingestion"].get("ignored_files", [])
    for root, dirs, files in os.walk(directory_path):
        dirs[:] = [d for d in dirs if d not in ignored_dirs]
        for file in files:
            if file.startswith('.'):
                continue
            if file in ignored_files:
                continue
            if file.endswith(".py"):
                python_files.append(os.path.join(root, file))

    if not python_files:
        yield "No Python (.py) files found to build graph."
        return

    yield f"Found {len(python_files)} Python files. Building knowledge graph..."
    knowledge_graph = {"nodes": [], "edges": []}
    existing_node_ids = set()

    for file_path in python_files:
        file_name = os.path.basename(file_path)
        yield f"Analyzing `{file_name}`..."
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()

            if not content.strip():
                yield f"Skipping empty file: `{file_name}`"
                continue

            # Add the file itself as a node
            if file_name not in existing_node_ids:
                knowledge_graph["nodes"].append({"id": file_name, "type": "file", "file": file_name})
                existing_node_ids.add(file_name)

            # Parse the code and analyze it
            tree = ast.parse(content)
            analyzer = CodeAnalyzer(file_name)
            analyzer.visit(tree)

            # Aggregate nodes and edges, avoiding duplicates
            for node in analyzer.nodes:
                if node.get("id") not in existing_node_ids:
                    knowledge_graph["nodes"].append(node)
                    existing_node_ids.add(node.get("id"))
            knowledge_graph["edges"].extend(analyzer.edges)

        except Exception as e:
            yield f"❌ Error analyzing `{file_name}`: {e}"
            print(f"Error analyzing {file_name}: {e}")

    graph_file_path = config["knowledge_graph"]["graph_file_path"]
    try:
        with open(graph_file_path, 'w', encoding='utf-8') as f:
            json.dump(knowledge_graph, f, indent=2)
        yield f"✅ Knowledge graph built successfully and saved to `{graph_file_path}`."
    except Exception as e:
        yield f"❌ Error saving knowledge graph: {e}"


def view_knowledge_graph(config):
    """
    Reads the knowledge graph from the JSON file and returns it for display.
    """
    graph_file_path = config.get("knowledge_graph", {}).get("graph_file_path")
    if not graph_file_path:
        return gr.update(visible=False), "❌ Error: `graph_file_path` not found in config.yaml."

    if not os.path.exists(graph_file_path):
        return gr.update(visible=False), f"❌ Error: Knowledge graph file not found at `{graph_file_path}`. Please build it first."

    try:
        with open(graph_file_path, 'r', encoding='utf-8') as f:
            graph_data = json.load(f)
        # Format the dictionary as a nicely indented JSON string for the gr.Code component
        json_string = json.dumps(graph_data, indent=2)
        return gr.update(value=json_string, visible=True), "✅ Knowledge graph loaded."
    except Exception as e:
        error_message = f"❌ Error reading or parsing knowledge graph file: {e}"
        return gr.update(visible=False), error_message


def create_ingest_ui(client, store, config):
    """Creates the Gradio UI for the Ingest Codebase tab."""
    with gr.Tab("Ingest Codebase"):
        gr.Markdown("## Provide Local Codebase Path")
        gr.Markdown("Enter the local path to your codebase. The tool will scan this directory and create a searchable index of your files.")
        local_repo_path = gr.Textbox(label="Local Codebase Path", placeholder="e.g., /path/to/my/local/repo")
        with gr.Row(equal_height=False):
            ingest_button = gr.Button("🚀 Ingest Files", variant="primary")
            build_graph_button = gr.Button("🕸️ Build Knowledge Graph", variant="secondary")
            view_graph_button = gr.Button("👁️ View Graph", variant="secondary")
        ingest_status = gr.Markdown()

        ingest_button.click(
            fn=lambda path, cfg: (yield from ingest_files(path, client, store, cfg)),
            inputs=[local_repo_path, gr.State(config)],
            outputs=[ingest_status],
            show_progress="hidden"
        )

        build_graph_button.click(
            fn=lambda path: (yield from build_knowledge_graph(path, config)),
            inputs=[local_repo_path],
            outputs=[ingest_status]
        )

        graph_viewer = gr.Code(label="Knowledge Graph", language="json", visible=False)

        view_graph_button.click(
            fn=lambda: view_knowledge_graph(config),
            inputs=[],
            outputs=[graph_viewer, ingest_status]
        )