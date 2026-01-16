import signal
import sys
import subprocess
import random
import os
from datetime import datetime
from pathlib import Path
from typing import Annotated, List

import typer
import httpx
import uvicorn
from rich import box
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
    uvicorn.run("src.server:app", host="127.0.0.1", port=8000, reload=False, loop="asyncio")


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


@app.command()
def inspire():
    """Serendipity: Rediscover a random memory from your Neural-Journal."""
    if not JOURNAL_DIR.exists():
        rprint(Panel(
            "[bold red]No memories recorded yet.[/bold red]\n"
            "Start your journey with [bold]memex log[/bold].",
            title="Neural Empty",
            border_style="bold red"
        ))
        return

    # Get all .md files
    files = list(JOURNAL_DIR.glob("*.md"))
    
    if not files:
        rprint(Panel(
            "[bold red]No memories recorded yet.[/bold red]\n"
            "Start your journey with [bold]memex log[/bold].",
            title="Neural Empty",
            border_style="bold red"
        ))
        return

    # Randomly select one
    random_file = random.choice(files)
    
    try:
        with open(random_file, "r", encoding="utf-8") as f:
            content = f.read()
            
        md = Markdown(content)
        rprint(Panel(
            md,
            title=f"[bold magenta]✨ Random Memory: {random_file.name}[/bold magenta]",
            border_style="bold magenta"
        ))
    except Exception as e:
        rprint(f"[bold red]Error:[/bold red] Failed to recall memory: {e}")
        raise typer.Exit(code=1)


@app.command()
def sync():
    """Backup your Neural-Journal to GitHub."""
    if not JOURNAL_DIR.exists():
         rprint(Panel("No journal directory found to sync.", border_style="bold red"))
         raise typer.Exit(code=1)

    try:
        # Check if it is a git repo
        if not (JOURNAL_DIR / ".git").exists():
             rprint("[bold yellow]Initializing Git Repository...[/bold yellow]")
             subprocess.run(["git", "init"], cwd=JOURNAL_DIR, check=True)

        with console.status("[bold green]Syncing to Neural-Cloud (GitHub)...[/bold green]"):
            subprocess.run(["git", "add", "."], cwd=JOURNAL_DIR, check=True)
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            subprocess.run(["git", "commit", "-m", f"Neural-Memex Sync: {timestamp}"], cwd=JOURNAL_DIR, check=False) # check=False in case of no changes
            # Note: This assumes 'origin' remote is configured.
            subprocess.run(["git", "push", "origin", "main"], cwd=JOURNAL_DIR, check=False) 
            
        rprint(Panel(
            f"Synced at {timestamp}",
            title="[bold green]Neural-Sync Complete[/bold green]",
            border_style="bold green"
        ))

    except Exception as e:
        rprint(f"[bold red]Error:[/bold red] Sync failed: {e}")
        raise typer.Exit(code=1)

@app.command()
def status():
    """System Dashboard: Monitor Neural-Memex health and knowledge stats."""
    
    # Health Check
    try:
        response = httpx.get("http://127.0.0.1:8000/health", timeout=2.0)
        is_online = response.status_code == 200
    except:
        is_online = False

    status_str = "[bold green]🟢 Online[/bold green]" if is_online else "[bold red]🔴 Offline[/bold red]"

    # Stats Calculation
    total_memories = 0
    total_size_kb = 0.0

    if JOURNAL_DIR.exists():
        files = list(JOURNAL_DIR.glob("*.md"))
        total_memories = len(files)
        total_size_bytes = sum(f.stat().st_size for f in files)
        total_size_kb = total_size_bytes / 1024

    # UI Construction
    table = Table(
        show_header=False,
        box=box.SIMPLE,
        border_style=STYLE_BORDER
    )
    
    table.add_row("System Status", status_str)
    table.add_row("Total Memories", f"[bold cyan]{total_memories}[/bold cyan]")
    table.add_row("Knowledge Size", f"[bold yellow]{total_size_kb:.1f} KB[/bold yellow]")

    console.print(table)
    console.print("[dim]Tip: Run 'memex sync' to backup[/dim]")


if __name__ == "__main__":
    app()
