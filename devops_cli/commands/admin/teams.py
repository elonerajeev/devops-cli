"""Team management commands for admin."""

import os
import tempfile
import subprocess
from datetime import datetime
from typing import Optional

import typer
import yaml
from rich.prompt import Prompt, Confirm

from pathlib import Path

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
    handle_duplicate,
    handle_duplicate_batch,
    get_teams_template,
    validate_teams_yaml,
    load_teams_yaml,
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

    # Check for duplicate
    exists = name in config.get("teams", {})
    action = handle_duplicate("Team", name, exists)

    if action == "cancel":
        info("Cancelled")
        return
    elif action == "skip":
        info(f"Keeping existing team '{name}'")
        return

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


@app.command("teams-import")
def import_teams(
    file: str = typer.Option(..., "--file", "-f", help="Path to YAML file with teams"),
    skip_existing: bool = typer.Option(
        True,
        "--skip-existing/--overwrite-existing",
        help="Skip existing teams (default) or overwrite them",
    ),
):
    """Import teams from a YAML file."""
    header("Import Teams from YAML")

    file_path = Path(file)

    if not file_path.exists():
        error(f"File not found: {file}")
        info("Create a template with: devops admin teams-export-template --output teams.yaml")
        return

    info(f"Loading teams from: {file}")
    console.print()

    data = load_teams_yaml(file_path)

    if not data:
        error("Could not load YAML file")
        return

    is_valid, error_msg = validate_teams_yaml(data)
    if not is_valid:
        error(f"Validation failed: {error_msg}")
        return

    teams_to_import = data["teams"]
    config = load_teams_config()

    if "teams" not in config:
        config["teams"] = {}

    # Analyze what will be imported
    new_teams = []
    existing_teams = []

    for team_name in teams_to_import:
        if team_name in config["teams"]:
            existing_teams.append(team_name)
        else:
            new_teams.append(team_name)

    info(f"Found {len(teams_to_import)} teams to import:")
    for team_name in teams_to_import:
        status = "(new)" if team_name in new_teams else "(exists - will skip)" if skip_existing else "(exists - will overwrite)"
        console.print(f"  - {team_name} {status}")

    console.print()

    if existing_teams and skip_existing:
        warning(f"Skipping {len(existing_teams)} existing teams: {', '.join(existing_teams)}")
        console.print()

    if not Confirm.ask("Proceed with import?", default=False):
        info("Cancelled")
        return

    imported = 0
    skipped = 0

    for team_name, team_config in teams_to_import.items():
        action = handle_duplicate_batch("Team", team_name, team_name in config["teams"], skip_existing)

        if action == "skip":
            skipped += 1
            continue

        # Add timestamp
        team_config["created_at"] = datetime.now().isoformat()
        config["teams"][team_name] = team_config
        imported += 1
        success(f"Imported: {team_name}")

    save_teams_config(config)

    console.print()
    info("Import Summary:")
    info(f"  Imported: {imported} teams")
    if skipped > 0:
        info(f"  Skipped: {skipped} teams (already existed)")


@app.command("teams-export-template")
def export_teams_template(
    output: str = typer.Option(
        "teams-template.yaml", "--output", "-o", help="Output file path"
    ),
):
    """Export a template YAML file for bulk team registration."""
    header("Export Teams Template")

    output_path = Path(output)

    if output_path.exists():
        warning(f"File already exists: {output}")
        if not Confirm.ask("Overwrite?"):
            info("Cancelled")
            return

    template = get_teams_template()

    try:
        with open(output_path, "w") as f:
            f.write(template)

        success(f"Template exported to: {output}")
        console.print()
        info("Next steps:")
        info(f"  1. Edit '{output}' with your teams")
        info(f"  2. Run: devops admin teams-import --file {output}")
        console.print()

    except IOError as e:
        error(f"Failed to write template: {e}")
