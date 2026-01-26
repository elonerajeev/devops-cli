"""Meeting management commands for admin."""

import typer
from rich.prompt import Prompt
from devops_cli.config.manager import config_manager
from devops_cli.commands.admin.base import header, success, info, error, create_table, console

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
