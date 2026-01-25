"""Security commands for local codebase scanning."""

import typer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import box
from pathlib import Path

from devops_cli.utils.security_scanner import run_local_scan
from devops_cli.utils.output import header, success, info, warning

app = typer.Typer(help="Security scanning for the local codebase")
console = Console()

@app.command("scan")
def security_scan(
    path: str = typer.Argument(".", help="Directory to scan"),
    show_all: bool = typer.Option(False, "--all", "-a", help="Show all findings including low severity")
):
    """
    Run a local security scan on the codebase. 
    
    Checks for hardcoded secrets, AWS keys, and other sensitive information.
    """
    header(f"Security Scan: {Path(path).absolute()}")
    
    with console.status("[bold green]Scanning for secrets and vulnerabilities..."):
        results = run_local_scan(path)
    
    secrets = results["secrets"]
    
    if not secrets:
        success("No security issues found in the local codebase!")
        return

    # Results table
    table = Table(
        title="[bold red]Security Findings[/bold red]",
        box=box.ROUNDED,
        show_header=True,
        header_style="bold red"
    )
    table.add_column("Type", style="cyan")
    table.add_column("Finding", style="white")
    table.add_column("Location", style="dim")
    table.add_column("Severity", justify="center")

    for s in secrets:
        table.add_row(
            s["type"].capitalize(),
            s["message"],
            f"{s['file']}:{s['line']}",
            f"[bold red]{s['severity'].upper()}[/bold red]"
        )

    console.print(table)
    
    # Summary panel
    console.print()
    summary = results["summary"]
    console.print(Panel(
        f"[bold red]Critical:[/bold red] {summary['critical']}\n"
        f"[bold orange3]High:[/bold orange3] {summary['high']}\n"
        f"[bold yellow]Medium:[/bold yellow] {summary['medium']}\n"
        f"[bold blue]Low:[/bold blue] {summary['low']}",
        title="Scan Summary",
        border_style="red",
        padding=(1, 2)
    ))
    
    warning("\n[bold]Remediation:[/bold]")
    info("1. Remove hardcoded secrets and use environment variables.")
    info("2. Invalidate any leaked keys immediately.")
    info("3. Use 'devops secrets set' to store secrets securely.")

if __name__ == "__main__":
    app()
