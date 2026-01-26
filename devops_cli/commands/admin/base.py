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
