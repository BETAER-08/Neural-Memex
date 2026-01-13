import asyncio
import logging
import signal
import sys
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.style import Style
from rich import print as rprint
from sentence_transformers import SentenceTransformer

from src.core.config import settings
from src.db.db_client import db_client
from src.services.indexer import AsyncIndexer
from src.services.watcher import DirectoryWatcher

app = typer.Typer(
    help="Neural-Memex: Local Semantic File System Daemon",
    add_completion=False,
    no_args_is_help=True
)
console = Console()

# Bauhaus Styles
STYLE_BORDER = Style(color="black", bold=True)
STYLE_HEADER = Style(color="blue", bold=True)
STYLE_ROW_EVEN = Style(color="black")
STYLE_ROW_ODD = Style(color="dim")


async def _run_daemon():
    """Async entry point for the daemon."""
    indexer = AsyncIndexer()
    watcher = DirectoryWatcher(indexer)

    # Start services
    watcher.start()
    indexer_task = asyncio.create_task(indexer.start())
    
    # Graceful shutdown handler
    stop_event = asyncio.Event()

    def handle_signal():
        stop_event.set()

    loop = asyncio.get_running_loop()
    loop.add_signal_handler(signal.SIGINT, handle_signal)
    loop.add_signal_handler(signal.SIGTERM, handle_signal)

    rprint(Panel(
        f"[bold blue]Neural-Memex Daemon[/bold blue]\n"
        f"Watching: {settings.WATCH_DIRECTORIES}\n"
        f"DB Path: {settings.DB_PATH}",
        title="System Online",
        border_style="bold red"
    ))

    # Wait for stop signal
    await stop_event.wait()
    
    rprint("[bold yellow]Shutting down...[/bold yellow]")
    watcher.stop()
    await indexer.stop()
    indexer_task.cancel()
    try:
        await indexer_task
    except asyncio.CancelledError:
        pass


@app.command()
def start():
    """Starts the background monitoring daemon."""
    try:
        asyncio.run(_run_daemon())
    except KeyboardInterrupt:
        pass


@app.command()
def search(query: str):
    """Semantically search your files."""
    
    # Load model just for search (could be optimized to use a running server, but this is simple)
    with console.status("[bold yellow]Loading Neural Engine...[/bold yellow]"):
        model = SentenceTransformer(settings.MODEL_NAME)
        embedding = model.encode(query).tolist()
        
    collection = db_client.get_collection()
    
    results = collection.query(
        query_embeddings=[embedding],
        n_results=10,
        include=["metadatas", "distances", "documents"]
    )
    
    table = Table(
        title=f"Search Results: '{query}'",
        show_header=True,
        header_style=STYLE_HEADER,
        border_style=STYLE_BORDER,
        box=None
    )
    
    table.add_column("Score", justify="right", style="magenta")
    table.add_column("File", style="bold cyan")
    table.add_column("Path", style="dim")
    
    count = 0
    if results["ids"]:
        for i in range(len(results["ids"][0])):
            distance = results["distances"][0][i]
            metadata = results["metadatas"][0][i]
            
            # Simple similarity score conversion (distance is likely l2 or cosine distance)
            score = f"{1 - distance:.3f}" 
            
            table.add_row(score, metadata["filename"], metadata["path"])
            count += 1

    if count == 0:
        rprint(Panel("No relevant files found.", border_style="bold red"))
    else:
        console.print(table)


if __name__ == "__main__":
    app()
