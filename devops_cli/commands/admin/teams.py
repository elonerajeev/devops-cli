"""Team management commands for admin."""

import os
import tempfile
import subprocess
from datetime import datetime
from typing import Optional

import typer
import yaml
from rich.prompt import Prompt, Confirm

from devops_cli.commands.admin.base import (
    console,
    load_teams_config,
    save_teams_config,
    success,
    error,
    warning,
    info,
    header,
    create_table,
)

app = typer.Typer()


@app.command("team-add")
def add_team(
    name: str = typer.Option(..., "--name", "-n", prompt="Team name", help="Team name"),
    description: Optional[str] = typer.Option(
        None, "--desc", "-d", help="Team description"
    ),
):
    """Add a new team."""
    config = load_teams_config()

    apps_access = Prompt.ask(
        "Apps access (comma-separated names, or * for all)", default="*"
    )
    servers_access = Prompt.ask(
        "Servers access (comma-separated names/tags, or * for all)", default="*"
    )

    apps_list = (
        [a.strip() for a in apps_access.split(",")] if apps_access != "*" else ["*"]
    )
    servers_list = (
        [s.strip() for s in servers_access.split(",")]
        if servers_access != "*"
        else ["*"]
    )

    config["teams"][name] = {
        "name": name,
        "description": description or f"Team {name}",
        "apps": apps_list,
        "servers": servers_list,
        "created_at": datetime.now().isoformat(),
    }

    save_teams_config(config)
    success(f"Team '{name}' created")


@app.command("team-list")
def list_teams():
    """List all teams."""
    config = load_teams_config()
    teams = config.get("teams", {})

    if not teams:
        warning("No teams configured")
        return

    header("Teams")

    table = create_table(
        "", [("Name", "cyan"), ("Apps Access", ""), ("Servers Access", "dim")]
    )

    for name, team in teams.items():
        apps = ", ".join(team.get("apps", []))[:30]
        servers = ", ".join(team.get("servers", []))[:30]
        table.add_row(name, apps, servers)

    console.print(table)


@app.command("team-remove")
def remove_team(
    name: str = typer.Argument(..., help="Team name to remove"),
):
    """Remove a team."""
    config = load_teams_config()

    if name not in config.get("teams", {}):
        error(f"Team '{name}' not found")
        return

    if name == "default":
        error("Cannot remove the default team")
        return

    if not Confirm.ask(f"Remove team '{name}'?"):
        info("Cancelled")
        return

    del config["teams"][name]
    save_teams_config(config)
    success(f"Team '{name}' removed")


@app.command("team-show")
def show_team(
    name: str = typer.Argument(..., help="Team name"),
):
    """Show detailed configuration for a team."""
    config = load_teams_config()
    teams = config.get("teams", {})

    if name not in teams:
        error(f"Team '{name}' not found")
        return

    team = teams[name]
    header(f"Team: {name}")

    console.print(yaml.dump(team, default_flow_style=False))


@app.command("team-edit")
def edit_team(
    name: str = typer.Argument(..., help="Team name to edit"),
):
    """Edit a team configuration."""
    config = load_teams_config()

    if name not in config.get("teams", {}):
        error(f"Team '{name}' not found")
        return

    # Write to temp file
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        yaml.dump(config["teams"][name], f, default_flow_style=False)
        temp_file = f.name

    # Open in editor
    editor = os.environ.get("EDITOR", "nano")
    subprocess.run([editor, temp_file])

    # Read back
    with open(temp_file) as f:
        updated = yaml.safe_load(f)

    os.unlink(temp_file)

    if Confirm.ask("Save changes?"):
        config["teams"][name] = updated
        save_teams_config(config)
        success(f"Team '{name}' updated")
    else:
        info("Changes discarded")
