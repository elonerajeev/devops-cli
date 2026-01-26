"""Meeting management commands for admin."""

from pathlib import Path
from datetime import datetime

import typer
from rich.prompt import Prompt, Confirm
from devops_cli.config.manager import config_manager
from devops_cli.commands.admin.base import (
    header,
    success,
    info,
    error,
    warning,
    create_table,
    console,
    handle_duplicate,
    handle_duplicate_batch,
    get_meetings_template,
    validate_meetings_yaml,
    load_meetings_yaml,
)

app = typer.Typer(help="Manage daily meeting links and times")

@app.command("set")
def set_meeting(
    meeting_id: str = typer.Argument(..., help="Meeting ID (standup, afternoon, evening)"),
    name: str = typer.Option(None, "--name", "-n", help="Display name of the meeting"),
    time: str = typer.Option(None, "--time", "-t", help="Time in HH:MM format"),
    link: str = typer.Option(None, "--link", "-l", help="Google Meet / Zoom link")
):
    """Set meeting details."""
    config = config_manager.meetings
    meetings = config.get("meetings", {})

    # Check for duplicate (only if meeting has existing data)
    exists = meeting_id in meetings and any(meetings[meeting_id].values())
    action = handle_duplicate("Meeting", meeting_id, exists)

    if action == "cancel":
        info("Cancelled")
        return
    elif action == "skip":
        info(f"Keeping existing meeting '{meeting_id}'")
        return

    if meeting_id not in meetings:
        meetings[meeting_id] = {}

    if name:
        meetings[meeting_id]["name"] = name
    if time:
        meetings[meeting_id]["time"] = time
    if link:
        meetings[meeting_id]["link"] = link

    config["meetings"] = meetings
    if config_manager.save_meetings(config):
        success(f"Meeting '{meeting_id}' updated successfully.")
    else:
        error(f"Failed to save meeting configuration.")

@app.command("list")
def list_meetings():
    """List all configured meetings."""
    header("Configured Meetings")
    
    meetings = config_manager.meetings.get("meetings", {})
    if not meetings:
        info("No meetings configured.")
        return
        
    table = create_table("", [("ID", "cyan"), ("Name", ""), ("Time", "yellow"), ("Link", "dim")])
    
    # Sort by time
    sorted_meetings = sorted(meetings.items(), key=lambda x: x[1].get("time", "00:00"))
    
    for m_id, data in sorted_meetings:
        table.add_row(m_id, data.get("name", ""), data.get("time", ""), data.get("link", "-"))
        
    console.print(table)

@app.command("remove")
def remove_meeting(meeting_id: str = typer.Argument(..., help="Meeting ID to remove")):
    """Remove a meeting configuration."""
    config = config_manager.meetings
    meetings = config.get("meetings", {})

    if meeting_id in meetings:
        del meetings[meeting_id]
        config["meetings"] = meetings
        config_manager.save_meetings(config)
        success(f"Meeting '{meeting_id}' removed.")
    else:
        error(f"Meeting '{meeting_id}' not found.")


@app.command("meetings-import")
def import_meetings(
    file: str = typer.Option(..., "--file", "-f", help="Path to YAML file with meetings"),
    skip_existing: bool = typer.Option(
        True,
        "--skip-existing/--overwrite-existing",
        help="Skip existing meetings (default) or overwrite them",
    ),
):
    """Import meetings from a YAML file."""
    header("Import Meetings from YAML")

    file_path = Path(file)

    if not file_path.exists():
        error(f"File not found: {file}")
        info("Create a template with: devops admin meetings-export-template --output meetings.yaml")
        return

    info(f"Loading meetings from: {file}")
    console.print()

    data = load_meetings_yaml(file_path)

    if not data:
        error("Could not load YAML file")
        return

    is_valid, error_msg = validate_meetings_yaml(data)
    if not is_valid:
        error(f"Validation failed: {error_msg}")
        return

    meetings_to_import = data["meetings"]
    config = config_manager.meetings
    existing_meetings = config.get("meetings", {})

    # Analyze what will be imported
    new_meetings = []
    existing_list = []

    for meeting_id in meetings_to_import:
        if meeting_id in existing_meetings and any(existing_meetings[meeting_id].values()):
            existing_list.append(meeting_id)
        else:
            new_meetings.append(meeting_id)

    info(f"Found {len(meetings_to_import)} meetings to import:")
    for meeting_id in meetings_to_import:
        status = "(new)" if meeting_id in new_meetings else "(exists - will skip)" if skip_existing else "(exists - will overwrite)"
        console.print(f"  - {meeting_id} {status}")

    console.print()

    if existing_list and skip_existing:
        warning(f"Skipping {len(existing_list)} existing meetings: {', '.join(existing_list)}")
        console.print()

    if not Confirm.ask("Proceed with import?", default=False):
        info("Cancelled")
        return

    imported = 0
    skipped = 0

    for meeting_id, meeting_config in meetings_to_import.items():
        exists = meeting_id in existing_meetings and any(existing_meetings.get(meeting_id, {}).values())
        action = handle_duplicate_batch("Meeting", meeting_id, exists, skip_existing)

        if action == "skip":
            skipped += 1
            continue

        existing_meetings[meeting_id] = meeting_config
        imported += 1
        success(f"Imported: {meeting_id}")

    config["meetings"] = existing_meetings
    config_manager.save_meetings(config)

    console.print()
    info("Import Summary:")
    info(f"  Imported: {imported} meetings")
    if skipped > 0:
        info(f"  Skipped: {skipped} meetings (already existed)")


@app.command("meetings-export-template")
def export_meetings_template(
    output: str = typer.Option(
        "meetings-template.yaml", "--output", "-o", help="Output file path"
    ),
):
    """Export a template YAML file for bulk meeting registration."""
    header("Export Meetings Template")

    output_path = Path(output)

    if output_path.exists():
        warning(f"File already exists: {output}")
        if not Confirm.ask("Overwrite?"):
            info("Cancelled")
            return

    template = get_meetings_template()

    try:
        with open(output_path, "w") as f:
            f.write(template)

        success(f"Template exported to: {output}")
        console.print()
        info("Next steps:")
        info(f"  1. Edit '{output}' with your meetings")
        info(f"  2. Run: devops admin meetings-import --file {output}")
        console.print()

    except IOError as e:
        error(f"Failed to write template: {e}")