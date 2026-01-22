"""Dashboard command for starting the web interface.

Usage:
    devops dashboard start           # Start on default port 3000
    devops dashboard start --port 8080
    devops dashboard start --host 0.0.0.0
"""

import typer
from rich.console import Console
from rich.panel import Panel
from rich import box

app = typer.Typer(help="Web Dashboard - Beautiful monitoring interface")
console = Console()


@app.command("start")
def start_dashboard(
    port: int = typer.Option(3000, "--port", "-p", help="Port to run the dashboard on"),
    host: str = typer.Option("127.0.0.1", "--host", "-h", help="Host to bind to"),
    reload: bool = typer.Option(False, "--reload", "-r", help="Enable auto-reload for development"),
):
    """Start the web dashboard server.

    The dashboard provides:
    - Real-time monitoring view
    - Application management
    - Server status
    - User management (admin only)

    Example:
        devops dashboard start
        devops dashboard start --port 8080
        devops dashboard start --host 0.0.0.0  # Allow external access
    """
    # Check dependencies
    try:
        import uvicorn
        import fastapi
    except ImportError:
        console.print()
        console.print(Panel(
            "[red]Missing dependencies for dashboard.[/red]\n\n"
            "Install with:\n"
            "  [cyan]pip install fastapi uvicorn jinja2 python-multipart[/cyan]",
            title="[bold]Installation Required[/bold]",
            border_style="red",
            box=box.ROUNDED
        ))
        raise typer.Exit(1)

    # Display startup info
    console.print()
    console.print(Panel(
        f"[bold green]Starting DevOps CLI Dashboard[/bold green]\n\n"
        f"[cyan]URL:[/cyan]     http://{host}:{port}\n"
        f"[cyan]Host:[/cyan]    {host}\n"
        f"[cyan]Port:[/cyan]    {port}\n"
        f"[cyan]Reload:[/cyan]  {'Enabled' if reload else 'Disabled'}\n\n"
        f"[dim]Press Ctrl+C to stop[/dim]",
        title="[bold]Web Dashboard[/bold]",
        border_style="green",
        box=box.ROUNDED
    ))
    console.print()

    # Open browser automatically (optional)
    if host in ["127.0.0.1", "localhost"]:
        try:
            import webbrowser
            import threading

            def open_browser():
                import time
                time.sleep(1.5)  # Wait for server to start
                webbrowser.open(f"http://{host}:{port}")

            threading.Thread(target=open_browser, daemon=True).start()
        except Exception:
            pass

    # Run the dashboard
    from devops_cli.dashboard import run_dashboard
    run_dashboard(host=host, port=port, reload=reload)


@app.command("info")
def dashboard_info():
    """Show dashboard information and requirements."""
    console.print()
    console.print(Panel(
        "[bold]DevOps CLI Web Dashboard[/bold]\n\n"
        "[cyan]Features:[/cyan]\n"
        "  - Real-time monitoring status\n"
        "  - Application health checks\n"
        "  - Server management\n"
        "  - User management (admin)\n"
        "  - Mobile-friendly design\n\n"
        "[cyan]Requirements:[/cyan]\n"
        "  - fastapi\n"
        "  - uvicorn\n"
        "  - jinja2\n"
        "  - python-multipart\n\n"
        "[cyan]Install:[/cyan]\n"
        "  pip install fastapi uvicorn jinja2 python-multipart\n\n"
        "[cyan]Usage:[/cyan]\n"
        "  devops dashboard start\n"
        "  devops dashboard start --port 8080",
        title="[bold]Dashboard Info[/bold]",
        border_style="cyan",
        box=box.ROUNDED
    ))


@app.callback(invoke_without_command=True)
def dashboard_callback(ctx: typer.Context):
    """Web Dashboard for DevOps CLI."""
    if ctx.invoked_subcommand is None:
        # Default to start command
        start_dashboard(port=3000, host="127.0.0.1", reload=False)
