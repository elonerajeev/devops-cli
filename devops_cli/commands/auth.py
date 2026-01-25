"""Authentication commands for developers.

Commands:
    devops auth login   - Login with email and token
    devops auth logout  - Logout current session
    devops auth status  - Check authentication status
    devops auth whoami  - Show current user info
"""

import typer
from rich.console import Console
from rich.prompt import Prompt
from getpass import getpass

from devops_cli.auth import AuthManager
from devops_cli.utils.output import success, error, warning, info, header, print_panel

app = typer.Typer(help="Authentication - Login/logout for CLI access")
console = Console()


@app.command("login")
def login(
    email: str = typer.Option(None, "--email", "-e", help="Your email address"),
    token: str = typer.Option(
        None, "--token", "-t", help="Your access token (hidden input if not provided)"
    ),
):
    """Login to DevOps CLI with your credentials.

    You need an access token from your Cloud Engineer/Admin.
    Session is valid for 8 hours.

    Example:
        devops auth login
        devops auth login --email john@company.com
    """
    auth = AuthManager()

    # Check if already logged in
    session = auth.get_current_session()
    if session:
        warning(f"Already logged in as {session['email']}")
        info("Use 'devops auth logout' to switch accounts")
        return

    header("DevOps CLI Login")
    console.print()

    # Get email
    if not email:
        email = Prompt.ask("[cyan]Email[/]")

    if not email:
        error("Email is required")
        return

    # Get token (hidden input for security)
    if not token:
        console.print("[cyan]Token[/]: ", end="")
        try:
            token = getpass("")
        except (KeyboardInterrupt, EOFError):
            console.print()
            return

    if not token:
        error("Token is required")
        return

    # Attempt login
    try:
        if auth.login(email, token):
            console.print()
            success(f"Welcome, {email}!")
            info("Session valid for 8 hours")
            console.print()
            info("You can now use all CLI commands")
        else:
            console.print()
            error("Invalid email or token")
            info("Contact your admin if you forgot your token")
    except ValueError as e:
        console.print()
        error(str(e))


@app.command("logout")
def logout():
    """Logout from current session."""
    auth = AuthManager()

    session = auth.get_current_session()
    if not session:
        warning("Not logged in")
        return

    email = session.get("email")
    auth.logout()
    success(f"Logged out: {email}")


@app.command("status")
def status():
    """Check authentication status."""
    auth = AuthManager()
    session = auth.get_current_session()

    if session:
        from datetime import datetime

        expires = datetime.fromisoformat(session["expires_at"])
        remaining = expires - datetime.now()
        hours = int(remaining.total_seconds() // 3600)
        minutes = int((remaining.total_seconds() % 3600) // 60)

        content = [
            "[green]Authenticated[/]",
            "",
            f"[bold]User:[/] {session['email']}",
            f"[bold]Name:[/] {session.get('name', '-')}",
            f"[bold]Role:[/] {session.get('role', 'developer')}",
            f"[bold]Session expires in:[/] {hours}h {minutes}m",
        ]
        print_panel("\n".join(content), title="Auth Status", style="green")
    else:
        content = [
            "[red]Not authenticated[/]",
            "",
            "Run [cyan]devops auth login[/] to authenticate",
        ]
        print_panel("\n".join(content), title="Auth Status", style="red")


@app.command("whoami")
def whoami():
    """Show current user information."""
    auth = AuthManager()
    session = auth.get_current_session()

    if session:
        console.print(
            f"[cyan]{session['email']}[/] ({session.get('role', 'developer')})"
        )
    else:
        error("Not logged in")


@app.command("refresh")
def refresh():
    """Refresh session to extend expiration time."""
    auth = AuthManager()

    if not auth.is_authenticated():
        error("Not logged in")
        return

    if auth.refresh_session():
        success("Session refreshed (valid for 8 more hours)")
    else:
        error("Failed to refresh session")
