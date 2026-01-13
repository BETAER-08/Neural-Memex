import signal
import sys
import subprocess
from typing import Annotated

import typer
import httpx
import uvicorn
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.style import Style
from rich import print as rprint

app = typer.Typer(
    help="Neural-Memex: Local Semantic File System Daemon (Client)",
    add_completion=False,
    no_args_is_help=True
)
console = Console()

# Bauhaus Styles
STYLE_BORDER = Style(color="black", bold=True)
STYLE_HEADER = Style(color="blue", bold=True)
STYLE_ROW_EVEN = Style(color="black")
STYLE_ROW_ODD = Style(color="dim")


@app.command()
def start():
    """Starts the background monitoring daemon (FastAPI Server)."""
    rprint(Panel(
        f"[bold blue]Starting Neural-Memex Daemon...[/bold blue]\n"
        f"Server: http://127.0.0.1:8000",
        title="System Startup",
        border_style="bold red"
    ))
    # We run uvicorn directly. 
    # In a real 'daemon' mode this might detach, but for now we block.
    uvicorn.run("src.server:app", host="127.0.0.1", port=8000, reload=False)


@app.command()
def search(query: str):
    """Semantically search your files via the running Daemon."""
    
    DAEMON_URL = "http://127.0.0.1:8000/search"
    
    with console.status("[bold yellow]Querying Neural Engine...[/bold yellow]"):
        try:
            response = httpx.post(DAEMON_URL, json={"query": query}, timeout=10.0)
            response.raise_for_status()
            results = response.json()
        except httpx.ConnectError:
            rprint("[bold red]Error:[/bold red] Could not connect to Neural-Memex Daemon.")
            rprint("Please run [green]memex start[/green] in another terminal.")
            raise typer.Exit(code=1)
        except Exception as e:
            rprint(f"[bold red]Error:[/bold red] Request failed: {e}")
            raise typer.Exit(code=1)

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
    if results:
        for item in results:
            score = f"{item['score']:.3f}"
            table.add_row(score, item["filename"], item["path"])
            count += 1

    if count == 0:
        rprint(Panel("No relevant files found.", border_style="bold red"))
    else:
        console.print(table)


if __name__ == "__main__":
    app()
