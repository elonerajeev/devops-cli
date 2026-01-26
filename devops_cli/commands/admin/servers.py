"""Server management commands for admin."""

import os
import tempfile
import subprocess
from datetime import datetime

import typer
import yaml
from rich.prompt import Prompt, Confirm

from devops_cli.commands.admin.base import (
    console,
    load_servers_config,
    save_servers_config,
    load_teams_config,
    success,
    error,
    warning,
    info,
    header,
    create_table,
)

app = typer.Typer()


@app.command("server-add")
def add_server():
    """Add a new server for SSH access (interactive)."""
    header("Add New Server")

    name = Prompt.ask("Server name (e.g., web-1, api-prod)")
    host = Prompt.ask("Hostname or IP")
    user = Prompt.ask("SSH user", default="deploy")
    port = int(Prompt.ask("SSH port", default="22"))
    key_path = Prompt.ask("SSH key path", default="~/.ssh/id_rsa")

    tags_input = Prompt.ask("Tags (comma-separated, e.g., web,production)", default="")
    tags = [t.strip() for t in tags_input.split(",") if t.strip()]

    config = load_servers_config()

    config["servers"][name] = {
        "host": host,
        "user": user,
        "port": port,
        "key": key_path,
        "tags": tags,
        "added_at": datetime.now().isoformat(),
    }

    # Team access
    teams_config = load_teams_config()
    teams = list(teams_config.get("teams", {}).keys())
    if teams:
        selected_teams = Prompt.ask(
            "Teams with access (comma-separated)", default="default"
        )
        config["servers"][name]["teams"] = [
            t.strip() for t in selected_teams.split(",")
        ]

    save_servers_config(config)

    success(f"Server '{name}' added!")
    info("\nDevelopers can now use:")
    info(f"  devops ssh connect {name}")
    info(f"  devops ssh run 'command' --server {name}")


@app.command("server-list")
def list_servers():
    """List all configured servers."""
    config = load_servers_config()
    servers = config.get("servers", {})

    if not servers:
        warning("No servers configured")
        info("Add a server: devops admin server-add")
        return

    header("Configured Servers")

    table = create_table(
        "", [("Name", "cyan"), ("Host", ""), ("User", "dim"), ("Tags", "yellow")]
    )

    for name, server in servers.items():
        table.add_row(
            name,
            server.get("host", "-"),
            server.get("user", "-"),
            ", ".join(server.get("tags", [])),
        )

    console.print(table)
    info(f"\nTotal: {len(servers)} servers")


@app.command("server-remove")
def remove_server(
    name: str = typer.Argument(..., help="Server name to remove"),
):
    """Remove a server."""
    config = load_servers_config()

    if name not in config.get("servers", {}):
        error(f"Server '{name}' not found")
        return

    if not Confirm.ask(f"Remove server '{name}'?"):
        info("Cancelled")
        return

    del config["servers"][name]
    save_servers_config(config)
    success(f"Server '{name}' removed")


@app.command("server-show")
def show_server(
    name: str = typer.Argument(..., help="Server name"),
):
    """Show detailed configuration for a server."""
    config = load_servers_config()
    servers = config.get("servers", {})

    if name not in servers:
        error(f"Server '{name}' not found")
        return

    server = servers[name]
    header(f"Server: {name}")

    console.print(yaml.dump(server, default_flow_style=False))


@app.command("server-edit")
def edit_server(
    name: str = typer.Argument(..., help="Server name to edit"),
):
    """Edit a server configuration."""
    config = load_servers_config()

    if name not in config.get("servers", {}):
        error(f"Server '{name}' not found")
        return

    # Write to temp file
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        yaml.dump(config["servers"][name], f, default_flow_style=False)
        temp_file = f.name

    # Open in editor
    editor = os.environ.get("EDITOR", "nano")
    subprocess.run([editor, temp_file])

    # Read back
    with open(temp_file) as f:
        updated = yaml.safe_load(f)

    os.unlink(temp_file)

    if Confirm.ask("Save changes?"):
        config["servers"][name] = updated
        save_servers_config(config)
        success(f"Server '{name}' updated")
    else:
        info("Changes discarded")
