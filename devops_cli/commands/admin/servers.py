"""Server management commands for admin."""

import os
import tempfile
import subprocess
from datetime import datetime

import typer
import yaml
from rich.prompt import Prompt, Confirm

from pathlib import Path

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
    handle_duplicate,
    handle_duplicate_batch,
    get_servers_template,
    validate_servers_yaml,
    load_servers_yaml,
)

app = typer.Typer()


@app.command("server-add")
def add_server():
    """Add a new server for SSH access (interactive)."""
    header("Add New Server")

    name = Prompt.ask("Server name (e.g., web-1, api-prod)")

    config = load_servers_config()

    # Check for duplicate
    exists = name in config.get("servers", {})
    action = handle_duplicate("Server", name, exists)

    if action == "cancel":
        info("Cancelled")
        return
    elif action == "skip":
        info(f"Keeping existing server '{name}'")
        return

    host = Prompt.ask("Hostname or IP")
    user = Prompt.ask("SSH user", default="deploy")
    port = int(Prompt.ask("SSH port", default="22"))
    key_path = Prompt.ask("SSH key path", default="~/.ssh/id_rsa")

    tags_input = Prompt.ask("Tags (comma-separated, e.g., web,production)", default="")
    tags = [t.strip() for t in tags_input.split(",") if t.strip()]

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


@app.command("servers-import")
def import_servers(
    file: str = typer.Option(..., "--file", "-f", help="Path to YAML file with servers"),
    skip_existing: bool = typer.Option(
        True,
        "--skip-existing/--overwrite-existing",
        help="Skip existing servers (default) or overwrite them",
    ),
):
    """Import servers from a YAML file."""
    header("Import Servers from YAML")

    file_path = Path(file)

    if not file_path.exists():
        error(f"File not found: {file}")
        info("Create a template with: devops admin servers-export-template --output servers.yaml")
        return

    info(f"Loading servers from: {file}")
    console.print()

    data = load_servers_yaml(file_path)

    if not data:
        error("Could not load YAML file")
        return

    is_valid, error_msg = validate_servers_yaml(data)
    if not is_valid:
        error(f"Validation failed: {error_msg}")
        return

    servers_to_import = data["servers"]
    config = load_servers_config()

    if "servers" not in config:
        config["servers"] = {}

    # Analyze what will be imported
    new_servers = []
    existing_servers = []

    for server_name in servers_to_import:
        if server_name in config["servers"]:
            existing_servers.append(server_name)
        else:
            new_servers.append(server_name)

    info(f"Found {len(servers_to_import)} servers to import:")
    for server_name in servers_to_import:
        status = "(new)" if server_name in new_servers else "(exists - will skip)" if skip_existing else "(exists - will overwrite)"
        console.print(f"  - {server_name} {status}")

    console.print()

    if existing_servers and skip_existing:
        warning(f"Skipping {len(existing_servers)} existing servers: {', '.join(existing_servers)}")
        console.print()

    if not Confirm.ask("Proceed with import?", default=False):
        info("Cancelled")
        return

    imported = 0
    skipped = 0

    for server_name, server_config in servers_to_import.items():
        action = handle_duplicate_batch("Server", server_name, server_name in config["servers"], skip_existing)

        if action == "skip":
            skipped += 1
            continue

        # Add timestamp
        server_config["added_at"] = datetime.now().isoformat()
        config["servers"][server_name] = server_config
        imported += 1
        success(f"Imported: {server_name}")

    save_servers_config(config)

    console.print()
    info("Import Summary:")
    info(f"  Imported: {imported} servers")
    if skipped > 0:
        info(f"  Skipped: {skipped} servers (already existed)")


@app.command("servers-export-template")
def export_servers_template(
    output: str = typer.Option(
        "servers-template.yaml", "--output", "-o", help="Output file path"
    ),
):
    """Export a template YAML file for bulk server registration."""
    header("Export Servers Template")

    output_path = Path(output)

    if output_path.exists():
        warning(f"File already exists: {output}")
        if not Confirm.ask("Overwrite?"):
            info("Cancelled")
            return

    template = get_servers_template()

    try:
        with open(output_path, "w") as f:
            f.write(template)

        success(f"Template exported to: {output}")
        console.print()
        info("Next steps:")
        info(f"  1. Edit '{output}' with your servers")
        info(f"  2. Run: devops admin servers-import --file {output}")
        console.print()

    except IOError as e:
        error(f"Failed to write template: {e}")
