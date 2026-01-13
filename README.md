# Neural-Memex

**Neural-Memex** is a local background daemon that transforms your filesystem into a semantic knowledge base. It watches your directories in real-time, embeds text files using a local Large Language Model (LLM), and stores them in a Vector Database for "meaning-based" retrieval.

Designed for privacy and performance on **Fedora Linux**, fully offline.

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Python](https://img.shields.io/badge/python-3.10%2B-blue)
![Style](https://img.shields.io/badge/style-Bauhaus-orange)

## ✨ Features

- **📂 Real-time Indexing**: Automatically detects file creation and modification using `watchdog`.
- **🧠 Local Intelligence**: Uses `sentence-transformers/all-MiniLM-L6-v2` for high-speed, offline embeddings.
- **⚡ Async Architecture**: Non-blocking Producer-Consumer pattern ensures your system stays responsive.
- **🎨 Bauhaus CLI**: A beautiful, strict grid-based Command Line Interface built with `rich`.
- **🔍 Vector Search**: Find files by describing what they contain, not just keywords (e.g., "Authentication logic" finds `auth_service.py`).
- **🐧 Systemd Ready**: Includes a service file for seamless background operation.

## 🛠️ Architecture

- **Language**: Python 3.10+
- **Database**: `chromadb` (Persistent Vector Store)
- **Concurrency**: `asyncio` + `asyncio.Queue`
- **CLI**: `typer`

## 🚀 Installation

### Prerequisites
- Python 3.10 or higher
- Linux (Fedora/Debian/Arch etc.)

### Setup

1.  **Clone the repository** (if you haven't already):
    ```bash
    git clone https://github.com/yourusername/neural-memex.git
    cd neural-memex
    ```

2.  **Create a Virtual Environment**:
    ```bash
    python3 -m venv .venv
    source .venv/bin/activate
    ```

3.  **Install Dependencies**:
    ```bash
    pip install .
    ```

## 📖 Usage

### Start the Daemon
Running the start command initializes the file watcher and the async indexer. By default, it watches `~/Documents`.

```bash
python src/cli.py start
```
*Keep this running in a terminal, or see Systemd Integration below.*

### Semantic Search
Open a new terminal to query your indexed files.

```bash
# Example: Find all files related to user login
python src/cli.py search "login authentication security"
```

## ⚙️ Configuration

The system uses `pydantic-settings`. Defaults are defined in `src/core/config.py`.

Key settings:
- `MEMEX_WATCH_DIRECTORIES`: List of paths to watch (Default: `["~/Documents"]`)
- `MEMEX_MODEL_NAME`: HuggingFace model name (Default: `all-MiniLM-L6-v2`)
- `MEMEX_DB_PATH`: Location of ChromaDB (Default: `~/.neural_memex/chroma_db`)

## 🖥️ Systemd Integration

Run Neural-Memex as a user-level background service.

1.  **Link the Service File**:
    ```bash
    mkdir -p ~/.config/systemd/user/
    ln -s $(pwd)/systemd/neural-memex.service ~/.config/systemd/user/
    ```

2.  **Reload & Start**:
    ```bash
    systemctl --user daemon-reload
    systemctl --user enable --now neural-memex
    ```

3.  **Check Status**:
    ```bash
    systemctl --user status neural-memex
    ```

## 📜 License

MIT License
