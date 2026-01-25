"""Main entry point for the DevOps CLI."""

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich import box

from devops_cli import __version__
from devops_cli.commands import (
    git,
    health,
    logs,
    deploy,
    ssh,
    secrets,
    aws_logs,
    admin,
    app as app_cmd,
    auth,
    monitor,
    dashboard,
    website,
    security,
)
from devops_cli.config.settings import init_config
from devops_cli.utils.output import success, info
from devops_cli.utils.config_validator import ConfigValidator

app = typer.Typer(
    name="devops",
    help="DevOps CLI - Powerful tools for your startup workflows",
    add_completion=True,
    no_args_is_help=True,
)

console = Console()

# Register command groups
app.add_typer(git.app, name="git", help="Git & CI/CD operations")
app.add_typer(health.app, name="health", help="Health checks for services")
app.add_typer(logs.app, name="logs", help="View and tail logs")
app.add_typer(deploy.app, name="deploy", help="Deployment commands")
app.add_typer(ssh.app, name="ssh", help="SSH and server management")
app.add_typer(secrets.app, name="secrets", help="Secrets and env management")
app.add_typer(aws_logs.app, name="aws", help="AWS logs (CloudWatch)")
app.add_typer(
    admin.app,
    name="admin",
    help="Admin: Configure apps, servers, AWS (for Cloud Engineers)",
)
app.add_typer(
    app_cmd.app, name="app", help="Applications: View logs, health for configured apps"
)
app.add_typer(
    website.app,
    name="website",
    help="Websites: View info and health for configured websites",
)
app.add_typer(auth.app, name="auth", help="Authentication: Login/logout for CLI access")
app.add_typer(
    monitor.app,
    name="monitor",
    help="Real-time monitoring dashboard for websites, apps, servers",
)
app.add_typer(
    dashboard.app,
    name="dashboard",
    help="Web Dashboard - Beautiful browser-based monitoring UI",
)
app.add_typer(
    security.app,
    name="security",
    help="Security: Local codebase scanning",
)


@app.command()
def version():
    """Show CLI version."""
    console.print(f"[bold cyan]DevOps CLI[/] v{__version__}")


@app.command()
def init():
    """Initialize CLI configuration."""
    config_path = init_config()
    success(f"Configuration initialized at: {config_path}")
    info("Edit this file to configure your servers, services, and credentials.")


@app.command()
def status():
    """Show quick status overview of all systems."""
    summary = ConfigValidator.get_config_summary()
    counts = summary["counts"]

    # Header
    console.print()
    header_text = f"[bold cyan]DevOps CLI[/bold cyan] v{__version__}"
    console.print(
        Panel(header_text, box=box.DOUBLE, border_style="cyan", padding=(0, 2))
    )

    # Check if initialized
    if not summary["initialized"]:
        console.print()
        console.print(
            Panel(
                "[yellow]CLI has not been initialized for your organization.[/yellow]\n\n"
                "[dim]For Admins/Cloud Engineers:[/dim]\n"
                "  Run [cyan]devops admin init[/cyan] to set up the CLI\n\n"
                "[dim]For Developers:[/dim]\n"
                "  Contact your Admin to set up the CLI first",
                title="[bold]Setup Required[/bold]",
                border_style="yellow",
                box=box.ROUNDED,
                padding=(1, 2),
            )
        )
        return

    # Configuration Status Table
    console.print()
    table = Table(
        title="[bold]Configuration Status[/bold]",
        box=box.ROUNDED,
        show_header=True,
        header_style="bold cyan",
        padding=(0, 1),
    )
    table.add_column("Resource", style="white")
    table.add_column("Status", justify="center")
    table.add_column("Count", justify="right")
    table.add_column("Action", style="dim")

    # Users
    if summary["users"]:
        table.add_row(
            "Users",
            "[green]✓ Configured[/green]",
            str(counts["users"]),
            "devops admin user-list",
        )
    else:
        table.add_row(
            "Users", "[yellow]! Not Set[/yellow]", "0", "devops admin user-add"
        )

    # Apps
    if summary["apps"]:
        table.add_row(
            "Applications",
            "[green]✓ Configured[/green]",
            str(counts["apps"]),
            "devops app list",
        )
    else:
        table.add_row(
            "Applications", "[yellow]! Not Set[/yellow]", "0", "devops admin app-add"
        )

    # Servers
    if summary["servers"]:
        table.add_row(
            "SSH Servers",
            "[green]✓ Configured[/green]",
            str(counts["servers"]),
            "devops ssh list",
        )
    else:
        table.add_row(
            "SSH Servers", "[yellow]! Not Set[/yellow]", "0", "devops admin server-add"
        )

    # AWS Roles
    if summary["aws_roles"]:
        table.add_row(
            "AWS Roles",
            "[green]✓ Configured[/green]",
            str(counts["aws_roles"]),
            "devops admin aws-list",
        )
    else:
        table.add_row(
            "AWS Roles", "[dim]- Optional[/dim]", "0", "devops admin aws-add-role"
        )

    # Monitoring
    if summary["monitoring"]:
        table.add_row(
            "Monitoring",
            "[green]✓ Configured[/green]",
            str(counts["monitoring_resources"]),
            "devops monitor",
        )
    else:
        table.add_row(
            "Monitoring", "[dim]- Optional[/dim]", "0", "devops monitor add-website"
        )

    console.print(table)

    # Auth status
    console.print()
    try:
        from devops_cli.auth import AuthManager

        auth_mgr = AuthManager()
        session = auth_mgr.get_current_session()
        if session:
            console.print(
                f"[green]✓[/green] Logged in as: [cyan]{session.get('email')}[/cyan] ({session.get('role')})"
            )
        else:
            console.print(
                "[yellow]![/yellow] Not logged in. Run: [cyan]devops auth login[/cyan]"
            )
    except Exception:
        console.print("[dim]Auth status unavailable[/dim]")
        # Quick help
    console.print()
    console.print("[bold]Quick Commands:[/bold]")
    console.print("  [cyan]devops app list[/cyan]       - List available applications")
    console.print("  [cyan]devops app logs <app>[/cyan] - View application logs")
    console.print(
        "  [cyan]devops monitor[/cyan]        - Real-time monitoring dashboard"
    )
    console.print("  [cyan]devops dashboard[/cyan]      - Web UI dashboard (browser)")
    console.print("  [cyan]devops --help[/cyan]         - See all commands")


@app.command()
def doctor():
    """Check CLI health and diagnose issues."""
    console.print()
    console.print(
        Panel("[bold]DevOps CLI Doctor[/bold]", box=box.DOUBLE, border_style="cyan")
    )
    console.print()

    issues = []
    warnings = []

    # Check Python version
    import sys

    py_version = (
        f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    )
    if sys.version_info >= (3, 9):
        console.print(f"[green]✓[/green] Python version: {py_version}")
    else:
        console.print(f"[red]✗[/red] Python version: {py_version} (3.9+ recommended)")
        issues.append("Upgrade Python to 3.9 or higher")

    # Check required packages
    packages = [
        ("typer", "typer"),
        ("rich", "rich"),
        ("yaml", "pyyaml"),
        ("httpx", "httpx"),
        ("boto3", "boto3"),
    ]
    for import_name, display_name in packages:
        try:
            __import__(import_name)
            console.print(f"[green]✓[/green] {display_name} installed")
        except ImportError:
            console.print(f"[red]✗[/red] {display_name} not installed")
            issues.append(f"Install {display_name}: pip install {display_name}")

    # Check config directory
    from pathlib import Path

    config_dir = Path.home() / ".devops-cli"
    if config_dir.exists():
        console.print(f"[green]✓[/green] Config directory exists: {config_dir}")
    else:
        console.print("[yellow]![/yellow] Config directory not found")
        warnings.append("Run 'devops admin init' to initialize")

    # Check auth directory permissions
    auth_dir = config_dir / "auth"
    if auth_dir.exists():
        import stat

        mode = auth_dir.stat().st_mode
        if mode & stat.S_IRWXO == 0:  # No 'other' permissions
            console.print("[green]✓[/green] Auth directory permissions secure")
        else:
            console.print("[yellow]![/yellow] Auth directory permissions too open")
            warnings.append("Run: chmod 700 ~/.devops-cli/auth")

    # Check Git
    import subprocess

    try:
        result = subprocess.run(["git", "--version"], capture_output=True, text=True)
        if result.returncode == 0:
            console.print(f"[green]✓[/green] Git installed: {result.stdout.strip()}")
        else:
            console.print("[red]✗[/red] Git not working properly")
            issues.append("Check Git installation")
    except FileNotFoundError:
        console.print("[red]✗[/red] Git not found")
        issues.append("Install Git")

    # Check AWS CLI (optional)
    try:
        result = subprocess.run(["aws", "--version"], capture_output=True, text=True)
        if result.returncode == 0:
            console.print("[green]✓[/green] AWS CLI installed")
        else:
            console.print("[dim]-[/dim] AWS CLI not configured (optional)")
    except FileNotFoundError:
        console.print("[dim]-[/dim] AWS CLI not installed (optional)")

    # Summary
    console.print()
    if issues:
        console.print(
            Panel(
                "\n".join([f"[red]•[/red] {i}" for i in issues]),
                title="[bold red]Issues Found[/bold red]",
                border_style="red",
                box=box.ROUNDED,
            )
        )
    elif warnings:
        console.print(
            Panel(
                "\n".join([f"[yellow]•[/yellow] {w}" for w in warnings]),
                title="[bold yellow]Warnings[/bold yellow]",
                border_style="yellow",
                box=box.ROUNDED,
            )
        )
    else:
        console.print("[bold green]All checks passed![/bold green]")


@app.callback()
def main():
    """
    DevOps CLI - A powerful tool for startup DevOps workflows.

    Quick commands:
    - devops status           : Check CLI status
    - devops app list         : List available applications
    - devops app logs <app>   : View application logs
    - devops monitor          : Real-time monitoring dashboard
    - devops admin init       : Initialize CLI (for admins)
    """
    pass


if __name__ == "__main__":
    app()
