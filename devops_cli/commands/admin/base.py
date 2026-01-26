"""Base utilities and common imports for admin commands.

This module provides shared functionality used across all admin submodules.
"""

import os
import json
import shutil
from pathlib import Path
from datetime import datetime
from typing import Optional

import typer
import yaml
from rich.console import Console
from rich.prompt import Prompt, Confirm
from rich.panel import Panel
from rich import box

from devops_cli.config.loader import (
    ADMIN_CONFIG_DIR,
    AWS_CONFIG_FILE,
    TEAMS_CONFIG_FILE,
    SECRETS_DIR,
    ensure_admin_dirs,
    load_apps_config,
    save_apps_config,
    load_servers_config,
    save_servers_config,
    load_aws_config,
    save_aws_config,
    load_teams_config,
    save_teams_config,
    get_aws_credentials_template,
    import_aws_credentials_from_yaml,
    get_aws_roles_template,
    validate_aws_roles_yaml,
    load_aws_roles_yaml,
    get_users_template,
    validate_users_yaml,
    load_users_yaml,
    # Apps YAML functions
    get_apps_template,
    validate_apps_yaml,
    load_apps_yaml,
    # Servers YAML functions
    get_servers_template,
    validate_servers_yaml,
    load_servers_yaml,
    # Teams YAML functions
    get_teams_template,
    validate_teams_yaml,
    load_teams_yaml,
    # Websites YAML functions
    get_websites_template,
    validate_websites_yaml,
    load_websites_yaml,
    # Repos YAML functions
    get_repos_template,
    validate_repos_yaml,
    load_repos_yaml,
    # Meetings YAML functions
    get_meetings_template,
    validate_meetings_yaml,
    load_meetings_yaml,
)
from devops_cli.config.settings import load_config
from devops_cli.config.repos import (
    load_repos,
    save_repos,
    get_repo_config,
    add_repo,
    remove_repo,
    fetch_repo_from_github,
    discover_org_repos,
    discover_user_repos,
    validate_github_token,
    validate_repo_name,
)
from devops_cli.config.aws_credentials import (
    save_aws_credentials,
    load_aws_credentials,
    delete_aws_credentials,
    credentials_exist,
    get_credentials_info,
    validate_aws_credentials,
    import_from_dict,
)
from devops_cli.config.websites import (
    load_websites_config,
    save_websites_config,
    get_website_config,
    add_website as add_website_to_config,
    remove_website as remove_website_from_config,
)
from devops_cli.utils.output import (
    success,
    error,
    warning,
    info,
    header,
    create_table,
)
from devops_cli.auth import AuthManager

# Templates directory location
TEMPLATES_DIR = Path(__file__).parent.parent.parent / "config" / "templates"

# Shared console and auth manager
console = Console()
auth = AuthManager()

# Commands that don't require admin auth (first-time setup)
INIT_COMMANDS = ["init"]


def check_admin_access(ctx: typer.Context):
    """Check if user has admin access. Called before admin commands."""
    # Get the command being run
    command_name = ctx.invoked_subcommand

    # Skip auth check for init command (first-time setup)
    if command_name in INIT_COMMANDS:
        return

    # Check if CLI is initialized
    if not ADMIN_CONFIG_DIR.exists():
        console.print()
        console.print(
            Panel(
                "[yellow]CLI not initialized yet.[/yellow]\n\n"
                "Run [cyan]devops admin init[/cyan] first to set up the CLI.",
                title="[bold]Setup Required[/bold]",
                border_style="yellow",
                box=box.ROUNDED,
            )
        )
        raise typer.Exit(0)

    # Check if any users exist (if not, allow first admin setup)
    users = auth.list_users()

    if not users:
        # No users yet - this is first-time setup, allow user-add only
        if command_name == "user-add":
            return
        console.print()
        console.print(
            Panel(
                "[yellow]No admin users registered yet.[/yellow]\n\n"
                "Create the first admin user:\n"
                "  [cyan]devops admin user-add --email admin@company.com --role admin[/cyan]",
                title="[bold]First Admin Setup[/bold]",
                border_style="yellow",
                box=box.ROUNDED,
            )
        )
        raise typer.Exit(0)

    # Check if current user is authenticated
    session = auth.get_current_session()
    if not session:
        console.print()
        console.print(
            Panel(
                "[red]Authentication required.[/red]\n\n"
                "Admin commands require you to be logged in.\n\n"
                "Run: [cyan]devops auth login[/cyan]",
                title="[bold]Login Required[/bold]",
                border_style="red",
                box=box.ROUNDED,
            )
        )
        raise typer.Exit(1)

    # Check if user has admin role
    if session.get("role") != "admin":
        console.print()
        console.print(
            Panel(
                f"[red]Access denied.[/red]\n\n"
                f"You are logged in as: [cyan]{session.get('email')}[/cyan] (role: {session.get('role')})\n\n"
                "Admin commands require [bold]admin[/bold] role.\n"
                "Contact your administrator for access.",
                title="[bold]Admin Access Required[/bold]",
                border_style="red",
                box=box.ROUNDED,
            )
        )
        raise typer.Exit(1)


def handle_duplicate(
    resource_type: str,
    name: str,
    exists: bool
) -> str:
    """
    Handle duplicate resource detection with interactive menu.

    Args:
        resource_type: Type of resource (e.g., "App", "Server", "Team")
        name: Name of the resource
        exists: Whether the resource already exists

    Returns:
        "overwrite" - User chose to overwrite existing
        "skip" - User chose to skip (keep existing)
        "cancel" - User chose to cancel operation
        "create" - Resource doesn't exist, proceed with creation
    """
    if not exists:
        return "create"

    console.print()
    warning(f"{resource_type} '{name}' already exists.")
    console.print()
    console.print("[bold]What do you want to do?[/bold]")
    console.print("  [cyan][1][/cyan] Overwrite existing configuration")
    console.print("  [cyan][2][/cyan] Skip (keep existing)")
    console.print("  [cyan][3][/cyan] Cancel")
    console.print()

    choice = Prompt.ask(
        "Enter choice",
        choices=["1", "2", "3"],
        default="2"
    )

    if choice == "1":
        return "overwrite"
    elif choice == "2":
        return "skip"
    else:
        return "cancel"


def handle_duplicate_batch(
    resource_type: str,
    name: str,
    exists: bool,
    skip_existing: bool
) -> str:
    """
    Handle duplicate resource detection for batch imports.

    Args:
        resource_type: Type of resource (e.g., "App", "Server", "Team")
        name: Name of the resource
        exists: Whether the resource already exists
        skip_existing: If True, skip existing; if False, overwrite

    Returns:
        "overwrite" - Overwrite existing
        "skip" - Skip (keep existing)
        "create" - Resource doesn't exist, proceed with creation
    """
    if not exists:
        return "create"

    if skip_existing:
        return "skip"
    else:
        return "overwrite"
