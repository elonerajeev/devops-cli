"""Autocompletion utilities for Typer commands."""

from typing import List
import typer
from devops_cli.config.manager import config_manager


def complete_app_name(ctx: typer.Context, incomplete: str) -> List[str]:
    """Autocomplete application names."""
    try:
        names = config_manager.get_all_app_names()
        return [name for name in names if name.startswith(incomplete)]
    except Exception:
        return []


def complete_server_name(ctx: typer.Context, incomplete: str) -> List[str]:
    """Autocomplete server names."""
    try:
        names = config_manager.get_all_server_names()
        return [name for name in names if name.startswith(incomplete)]
    except Exception:
        return []


def complete_website_name(ctx: typer.Context, incomplete: str) -> List[str]:
    """Autocomplete website names."""
    try:
        names = config_manager.get_all_website_names()
        return [name for name in names if name.startswith(incomplete)]
    except Exception:
        return []


def complete_aws_role(ctx: typer.Context, incomplete: str) -> List[str]:
    """Autocomplete AWS role names."""
    try:
        roles = config_manager.aws.get("roles", {}).keys()
        return [role for role in roles if role.startswith(incomplete)]
    except Exception:
        return []


def complete_server_tag(ctx: typer.Context, incomplete: str) -> List[str]:
    """Autocomplete server tags."""
    try:
        servers = config_manager.servers.get("servers", {})
        tags = set()
        for srv in servers.values():
            for tag in srv.get("tags", []):
                if tag.startswith(incomplete):
                    tags.add(tag)
        return list(tags)
    except Exception:
        return []
