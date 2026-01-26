"""Website management commands for admin."""

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
    handle_duplicate,
    handle_duplicate_batch,
    get_websites_template,
    validate_websites_yaml,
    load_websites_yaml,
)

app = typer.Typer()


@app.command("website-add")
def add_website():
    """Add a new website to monitor (interactive)."""
    header("Add New Website")

    name = Prompt.ask("Website name (e.g., frontend-prod, blog)")

    websites_config = load_websites_config()

    # Check for duplicate
    exists = name in websites_config
    action = handle_duplicate("Website", name, exists)

    if action == "cancel":
        info("Cancelled")
        return
    elif action == "skip":
        info(f"Keeping existing website '{name}'")
        return

    url = Prompt.ask("URL (e.g., https://example.com/health)")
    expected_status = int(Prompt.ask("Expected HTTP status code", default="200"))
    method = Prompt.ask("HTTP method", choices=["GET", "POST", "HEAD"], default="GET")
    timeout = int(Prompt.ask("Timeout in seconds", default="10"))

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


@app.command("websites-import")
def import_websites(
    file: str = typer.Option(..., "--file", "-f", help="Path to YAML file with websites"),
    skip_existing: bool = typer.Option(
        True,
        "--skip-existing/--overwrite-existing",
        help="Skip existing websites (default) or overwrite them",
    ),
):
    """Import websites from a YAML file."""
    header("Import Websites from YAML")

    file_path = Path(file)

    if not file_path.exists():
        error(f"File not found: {file}")
        info("Create a template with: devops admin websites-export-template --output websites.yaml")
        return

    info(f"Loading websites from: {file}")
    console.print()

    data = load_websites_yaml(file_path)

    if not data:
        error("Could not load YAML file")
        return

    is_valid, error_msg = validate_websites_yaml(data)
    if not is_valid:
        error(f"Validation failed: {error_msg}")
        return

    websites_to_import = data["websites"]
    websites_config = load_websites_config()

    # Analyze what will be imported
    new_websites = []
    existing_websites = []

    for website_name in websites_to_import:
        if website_name in websites_config:
            existing_websites.append(website_name)
        else:
            new_websites.append(website_name)

    info(f"Found {len(websites_to_import)} websites to import:")
    for website_name in websites_to_import:
        status = "(new)" if website_name in new_websites else "(exists - will skip)" if skip_existing else "(exists - will overwrite)"
        console.print(f"  - {website_name} {status}")

    console.print()

    if existing_websites and skip_existing:
        warning(f"Skipping {len(existing_websites)} existing websites: {', '.join(existing_websites)}")
        console.print()

    if not Confirm.ask("Proceed with import?", default=False):
        info("Cancelled")
        return

    imported = 0
    skipped = 0

    for website_name, website_config in websites_to_import.items():
        action = handle_duplicate_batch("Website", website_name, website_name in websites_config, skip_existing)

        if action == "skip":
            skipped += 1
            continue

        # Add timestamp
        website_config["added_at"] = datetime.now().isoformat()
        websites_config[website_name] = website_config
        imported += 1
        success(f"Imported: {website_name}")

    save_websites_config(websites_config)

    console.print()
    info("Import Summary:")
    info(f"  Imported: {imported} websites")
    if skipped > 0:
        info(f"  Skipped: {skipped} websites (already existed)")


@app.command("websites-export-template")
def export_websites_template(
    output: str = typer.Option(
        "websites-template.yaml", "--output", "-o", help="Output file path"
    ),
):
    """Export a template YAML file for bulk website registration."""
    header("Export Websites Template")

    output_path = Path(output)

    if output_path.exists():
        warning(f"File already exists: {output}")
        if not Confirm.ask("Overwrite?"):
            info("Cancelled")
            return

    template = get_websites_template()

    try:
        with open(output_path, "w") as f:
            f.write(template)

        success(f"Template exported to: {output}")
        console.print()
        info("Next steps:")
        info(f"  1. Edit '{output}' with your websites")
        info(f"  2. Run: devops admin websites-import --file {output}")
        console.print()

    except IOError as e:
        error(f"Failed to write template: {e}")
