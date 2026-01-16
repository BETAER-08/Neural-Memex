import signal
import sys
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Annotated, List

import typer
import httpx
import uvicorn
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.markdown import Markdown
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
STYLE_ROW_ODD = Style(dim=True)

JOURNAL_DIR = Path.home() / "Documents" / "Memex_Journal"


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



@app.command()
def log(content: Annotated[List[str], typer.Argument(help="Content of your journal entry.")]):
    """Log a new entry into your Neural-Journal."""
    if not content:
        rprint("[bold red]Error:[/bold red] Journal entry cannot be empty.")
        raise typer.Exit(code=1)

    # Ensure Journal Directory Exists
    if not JOURNAL_DIR.exists():
        JOURNAL_DIR.mkdir(parents=True, exist_ok=True)

    today_str = datetime.now().strftime("%Y-%m-%d")
    timestamp_str = datetime.now().strftime("%H:%M:%S")
    journal_file = JOURNAL_DIR / f"{today_str}.md"

    entry_text = " ".join(content)
    formatted_entry = f"\n## [{timestamp_str}] Log\n{entry_text}\n"

    try:
        with open(journal_file, "a", encoding="utf-8") as f:
            f.write(formatted_entry)
        
        rprint(Panel(
            f"[italic]{entry_text}[/italic]",
            title=f"[bold green]Saved to Memory ({today_str}.md)[/bold green]",
            border_style="bold yellow"
        ))
    except Exception as e:
        rprint(f"[bold red]Error:[/bold red] Failed to write journal entry: {e}")
        raise typer.Exit(code=1)


@app.command()
def read_today():
    """Read today's Neural-Journal entries."""
    today_str = datetime.now().strftime("%Y-%m-%d")
    journal_file = JOURNAL_DIR / f"{today_str}.md"

    if not journal_file.exists():
        rprint(Panel(
            "[dim]No entries for today yet. Start writing with [bold]memex log[/bold]![/dim]",
            title=f"Journal: {today_str}",
            border_style="bold red"
        ))
        return

    try:
        with open(journal_file, "r", encoding="utf-8") as f:
            content = f.read()
        
        md = Markdown(content)
        rprint(Panel(
            md,
            title=f"Journal: {today_str}",
            border_style="bold blue"
        ))
    except Exception as e:
        rprint(f"[bold red]Error:[/bold red] Failed to read journal entry: {e}")
        raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
