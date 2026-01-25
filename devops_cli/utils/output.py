"""Pretty output utilities using Rich."""

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn

console = Console()


def success(message: str) -> None:
    """Print success message."""
    console.print(f"[bold green]✓[/] {message}")


def error(message: str) -> None:
    """Print error message."""
    console.print(f"[bold red]✗[/] {message}")


def warning(message: str) -> None:
    """Print warning message."""
    console.print(f"[bold yellow]![/] {message}")


def info(message: str) -> None:
    """Print info message."""
    console.print(f"[bold blue]→[/] {message}")


def header(title: str) -> None:
    """Print a section header."""
    console.print(f"\n[bold cyan]{title}[/]")
    console.print("[dim]" + "─" * len(title) + "[/]")


def create_table(title: str, columns: list[tuple[str, str]]) -> Table:
    """Create a styled table."""
    table = Table(title=title, show_header=True, header_style="bold magenta")
    for col_name, col_style in columns:
        table.add_column(col_name, style=col_style)
    return table


def status_badge(status: str) -> str:
    """Return colored status badge."""
    status_colors = {
        "running": "[bold green]● RUNNING[/]",
        "healthy": "[bold green]● HEALTHY[/]",
        "success": "[bold green]● SUCCESS[/]",
        "passed": "[bold green]● PASSED[/]",
        "stopped": "[bold red]● STOPPED[/]",
        "unhealthy": "[bold red]● UNHEALTHY[/]",
        "failed": "[bold red]● FAILED[/]",
        "error": "[bold red]● ERROR[/]",
        "pending": "[bold yellow]● PENDING[/]",
        "warning": "[bold yellow]● WARNING[/]",
        "unknown": "[dim]● UNKNOWN[/]",
    }
    return status_colors.get(status.lower(), f"[dim]● {status.upper()}[/]")


def print_panel(content: str, title: str = "", style: str = "blue") -> None:
    """Print content in a panel."""
    console.print(Panel(content, title=title, border_style=style))


def spinner(message: str):
    """Return a spinner context manager."""
    return Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
        transient=True,
    )
