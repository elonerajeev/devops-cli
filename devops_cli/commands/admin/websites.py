"""Website management commands for admin."""

import os
import tempfile
import subprocess
from datetime import datetime

import typer
import yaml
from rich.prompt import Prompt, Confirm

from devops_cli.commands.admin.base import (
    console,
    load_websites_config,
    save_websites_config,
    get_website_config,
    add_website_to_config,
    remove_website_from_config,
    load_teams_config,
    success,
    error,
    warning,
    info,
    header,
    create_table,
)

app = typer.Typer()


@app.command("website-add")
def add_website():
    """Add a new website to monitor (interactive)."""
    header("Add New Website")

    name = Prompt.ask("Website name (e.g., frontend-prod, blog)")
    url = Prompt.ask("URL (e.g., https://example.com/health)")
    expected_status = int(Prompt.ask("Expected HTTP status code", default="200"))
    method = Prompt.ask("HTTP method", choices=["GET", "POST", "HEAD"], default="GET")
    timeout = int(Prompt.ask("Timeout in seconds", default="10"))

    websites_config = load_websites_config()

    if name in websites_config:
        error(f"Website '{name}' already exists.")
        return

    website_data = {
        "name": name,
        "url": url,
        "expected_status": expected_status,
        "method": method,
        "timeout": timeout,
        "added_at": datetime.now().isoformat(),
    }

    # Team access
    teams_config = load_teams_config()
    teams = list(teams_config.get("teams", {}).keys())
    if teams:
        selected_teams = Prompt.ask(
            "Teams with access (comma-separated)", default="default"
        )
        website_data["teams"] = [t.strip() for t in selected_teams.split(",")]

    add_website_to_config(name, url, **website_data)

    success(f"Website '{name}' added!")
    info("\nDevelopers can now use:")
    info(f"  devops website health {name}")
    info(f"  devops website info {name}")


@app.command("website-list")
def list_websites():
    """List all configured websites."""
    websites = load_websites_config()

    if not websites:
        warning("No websites configured")
        info("Add a website: devops admin website-add")
        return

    header("Configured Websites")

    table = create_table(
        "",
        [
            ("Name", "cyan"),
            ("URL", ""),
            ("Expected Status", "dim"),
            ("Method", "dim"),
            ("Teams", "dim"),
        ],
    )

    for name, website in websites.items():
        teams = ", ".join(website.get("teams", ["default"]))
        table.add_row(
            name,
            website.get("url", "-"),
            str(website.get("expected_status", "N/A")),
            website.get("method", "GET"),
            teams[:20],
        )

    console.print(table)
    info(f"\nTotal: {len(websites)} websites")


@app.command("website-show")
def show_website(
    name: str = typer.Argument(..., help="Website name"),
):
    """Show detailed configuration for a website."""
    website = get_website_config(name)

    if not website:
        error(f"Website '{name}' not found")
        return

    header(f"Website: {name}")

    console.print(yaml.dump(website, default_flow_style=False))


@app.command("website-remove")
def remove_website(
    name: str = typer.Argument(..., help="Website name to remove"),
):
    """Remove a website."""
    if not get_website_config(name):
        error(f"Website '{name}' not found")
        return

    if not Confirm.ask(f"Remove website '{name}'?"):
        info("Cancelled")
        return

    if remove_website_from_config(name):
        success(f"Website '{name}' removed")
    else:
        error(f"Failed to remove website '{name}'")


@app.command("website-edit")
def edit_website(
    name: str = typer.Argument(..., help="Website name to edit"),
):
    """Edit a website configuration."""
    websites = load_websites_config()

    if name not in websites:
        error(f"Website '{name}' not found")
        return

    # Write to temp file
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        yaml.dump(websites[name], f, default_flow_style=False)
        temp_file = f.name

    # Open in editor
    editor = os.environ.get("EDITOR", "nano")
    subprocess.run([editor, temp_file])

    # Read back
    with open(temp_file) as f:
        updated = yaml.safe_load(f)

    os.unlink(temp_file)

    if Confirm.ask("Save changes?"):
        websites[name] = updated
        save_websites_config(websites)
        success(f"Website '{name}' updated")
    else:
        info("Changes discarded")
