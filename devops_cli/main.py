"""Main entry point for the DevOps CLI.

Uses lazy loading to improve startup performance - command modules are only
imported when their commands are actually invoked.
"""

import sys
import importlib
from typing import Optional, Callable

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich import box

from devops_cli import __version__

# Command module registry: name -> (module_path, help_text)
COMMAND_MODULES = {
    "git": ("devops_cli.commands.git", "Git & CI/CD operations"),
    "health": ("devops_cli.commands.health", "Health checks for services"),
    "logs": ("devops_cli.commands.logs", "View and tail logs"),
    "deploy": ("devops_cli.commands.deploy", "Deployment commands"),
    "ssh": ("devops_cli.commands.ssh", "SSH and server management"),
    "secrets": ("devops_cli.commands.secrets", "Secrets and env management"),
    "aws": ("devops_cli.commands.aws_logs", "AWS logs (CloudWatch)"),
    "admin": (
        "devops_cli.commands.admin",
        "Admin: Configure apps, servers, AWS (for Cloud Engineers)",
    ),
    "app": (
        "devops_cli.commands.app",
        "Applications: View logs, health for configured apps",
    ),
    "website": (
        "devops_cli.commands.website",
        "Websites: View info and health for configured websites",
    ),
    "auth": (
        "devops_cli.commands.auth",
        "Authentication: Login/logout for CLI access",
    ),
    "monitor": (
        "devops_cli.commands.monitor",
        "Real-time monitoring dashboard for websites, apps, servers",
    ),
    "dashboard": (
        "devops_cli.commands.dashboard",
        "Web Dashboard - Beautiful browser-based monitoring UI",
    ),
    "security": (
        "devops_cli.commands.security",
        "Security: Local codebase scanning",
    ),
}

# Module cache to avoid re-importing
_module_cache: dict = {}


def _get_module(module_path: str):
    """Get a module, loading it lazily if needed."""
    if module_path not in _module_cache:
        _module_cache[module_path] = importlib.import_module(module_path)
    return _module_cache[module_path]


def _get_invoked_command() -> Optional[str]:
    """Get the command being invoked from sys.argv."""
    if len(sys.argv) > 1:
        cmd = sys.argv[1]
        # Skip options
        if not cmd.startswith("-"):
            return cmd
    return None


# Create main app
app = typer.Typer(
    name="devops",
    help="DevOps CLI - Powerful tools for your startup workflows",
    add_completion=True,
    no_args_is_help=True,
)

console = Console()


# Built-in commands that don't need module loading
BUILTIN_COMMANDS = {"version", "init", "status", "doctor", "--help", "-h", "--version"}


def _register_commands():
    """Register command modules - load only what's needed."""
    invoked_cmd = _get_invoked_command()

    # If invoking a built-in command, just register stubs for subcommands
    # This makes built-in commands very fast
    if invoked_cmd in BUILTIN_COMMANDS or invoked_cmd is None:
        # Check if we need help display
        needs_full_help = invoked_cmd is None or "--help" in sys.argv or "-h" in sys.argv

        if needs_full_help:
            # For help display, load all modules
            for name, (module_path, help_text) in COMMAND_MODULES.items():
                module = _get_module(module_path)
                app.add_typer(module.app, name=name, help=help_text)
        else:
            # For built-in commands, register stubs only
            for name, (mod_path, mod_help) in COMMAND_MODULES.items():
                stub = typer.Typer(help=mod_help)
                app.add_typer(stub, name=name, help=mod_help)

    # If a specific command module is being invoked, only load that module
    elif invoked_cmd in COMMAND_MODULES:
        module_path, help_text = COMMAND_MODULES[invoked_cmd]
        module = _get_module(module_path)
        app.add_typer(module.app, name=invoked_cmd, help=help_text)

        # Register other commands as stubs (for help text display)
        for name, (mod_path, mod_help) in COMMAND_MODULES.items():
            if name != invoked_cmd:
                stub = typer.Typer(help=mod_help)
                app.add_typer(stub, name=name, help=mod_help)
    else:
        # Unknown command - load all modules to let Typer handle the error
        for name, (module_path, help_text) in COMMAND_MODULES.items():
            module = _get_module(module_path)
            app.add_typer(module.app, name=name, help=help_text)


# Register commands with lazy loading
_register_commands()


@app.command()
def version():
    """Show CLI version."""
    console.print(f"[bold cyan]DevOps CLI[/] v{__version__}")


@app.command()
def init():
    """Initialize CLI configuration."""
    from devops_cli.config.settings import init_config
    from devops_cli.utils.output import success, info

    config_path = init_config()
    success(f"Configuration initialized at: {config_path}")
    info("Edit this file to configure your servers, services, and credentials.")


@app.command()
def status():
    """Show quick status overview of all systems."""
    from devops_cli.utils.config_validator import ConfigValidator

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
    warnings_list = []

    # Check Python version
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
        warnings_list.append("Run 'devops admin init' to initialize")

    # Check auth directory permissions
    auth_dir = config_dir / "auth"
    if auth_dir.exists():
        import stat

        mode = auth_dir.stat().st_mode
        if mode & stat.S_IRWXO == 0:  # No 'other' permissions
            console.print("[green]✓[/green] Auth directory permissions secure")
        else:
            console.print("[yellow]![/yellow] Auth directory permissions too open")
            warnings_list.append("Run: chmod 700 ~/.devops-cli/auth")

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
    elif warnings_list:
        console.print(
            Panel(
                "\n".join([f"[yellow]•[/yellow] {w}" for w in warnings_list]),
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
    try:
        app()
    except KeyboardInterrupt:
        console.print("\n[yellow]Aborted by user.[/yellow]")
        sys.exit(0)
    except FileNotFoundError as e:
        console.print()
        console.print(Panel(
            f"[red]Error:[/] File not found: [bold]{e.filename}[/]\n\n"
            "This usually means the CLI has not been initialized or a configuration file is missing.",
            title="[bold red]File Not Found[/bold red]",
            border_style="red",
            box=box.ROUNDED,
        ))
        sys.exit(1)
    except PermissionError as e:
        console.print()
        console.print(Panel(
            f"[red]Error:[/] Permission denied: [bold]{e.filename}[/]\n\n"
            "The CLI does not have permission to access this file or directory.",
            title="[bold red]Permission Denied[/bold red]",
            border_style="red",
            box=box.ROUNDED,
        ))
        sys.exit(1)
    except Exception as e:
        # For other unhandled exceptions, show a beautiful error panel
        console.print()
        console.print(Panel(
            f"[red]An unexpected error occurred:[/]\n\n"
            f"[bold white]{str(e)}[/bold white]\n\n"
            f"[dim]Type: {type(e).__name__}[/dim]\n\n"
            "If this persists, please run [cyan]devops doctor[/cyan] or report the issue.",
            title="[bold red]Unexpected Error[/bold red]",
            border_style="red",
            box=box.ROUNDED,
        ))
        # In debug mode or for specific complex errors, we might want to see the traceback
        # but for general use, the panel is much cleaner.
        sys.exit(1)
