"""Application management commands for admin."""

import os
import tempfile
import subprocess
from datetime import datetime

import typer
import yaml
from rich.prompt import Prompt, Confirm

from devops_cli.commands.admin.base import (
    console,
    load_apps_config,
    save_apps_config,
    load_aws_config,
    load_teams_config,
    success,
    error,
    warning,
    info,
    header,
    create_table,
)

app = typer.Typer()


@app.command("app-add")
def add_app():
    """Add a new application (interactive)."""
    header("Add New Application")

    # Basic info
    app_name = Prompt.ask("Application name (e.g., api, backend, worker)")
    app_type = Prompt.ask(
        "Application type",
        choices=["lambda", "kubernetes", "docker", "custom"],
        default="custom",
    )
    description = Prompt.ask("Description", default=f"{app_name} application")

    config = load_apps_config()

    app_config = {
        "name": app_name,
        "type": app_type,
        "description": description,
        "added_at": datetime.now().isoformat(),
    }

    # Type-specific configuration
    if app_type == "lambda":
        app_config["lambda"] = {
            "function_name": Prompt.ask("Lambda Function name", default=app_name),
            "region": Prompt.ask("AWS Region", default="us-east-1"),
        }
        app_config["logs"] = {
            "type": "cloudwatch",
            "log_group": Prompt.ask(
                "CloudWatch Log Group", default=f"/aws/lambda/{app_name}"
            ),
        }

    elif app_type == "kubernetes":
        app_config["kubernetes"] = {
            "namespace": Prompt.ask("Kubernetes Namespace", default="default"),
            "deployment": Prompt.ask("Deployment name", default=app_name),
            "container": Prompt.ask("Container name (optional)", default=""),
        }
        app_config["logs"] = {
            "type": "cloudwatch",
            "log_group": Prompt.ask("CloudWatch Log Group (K8s logs)"),
        }

    elif app_type == "docker":
        app_config["docker"] = {
            "container": Prompt.ask("Container name", default=app_name),
        }
        app_config["logs"] = {
            "type": "cloudwatch",
            "log_group": Prompt.ask("CloudWatch Log Group (Docker logs)"),
        }

    elif app_type == "custom":
        log_type = "cloudwatch"
        app_config["logs"] = {"type": log_type}
        app_config["logs"]["log_group"] = Prompt.ask("CloudWatch Log Group")
        app_config["logs"]["region"] = Prompt.ask("AWS Region", default="us-east-1")

    # Health check
    if Confirm.ask("Configure health check?", default=True):
        health_type = Prompt.ask(
            "Health check type",
            choices=["http", "tcp", "command", "none"],
            default="http",
        )

        if health_type == "http":
            app_config["health"] = {
                "type": "http",
                "url": Prompt.ask("Health check URL"),
                "expected_status": int(
                    Prompt.ask("Expected status code", default="200")
                ),
            }
        elif health_type == "tcp":
            app_config["health"] = {
                "type": "tcp",
                "host": Prompt.ask("Host"),
                "port": int(Prompt.ask("Port")),
            }
        elif health_type == "command":
            app_config["health"] = {
                "type": "command",
                "command": Prompt.ask("Health check command"),
            }

    # AWS Role for access
    aws_config = load_aws_config()
    roles = list(aws_config.get("roles", {}).keys())
    if roles:
        app_config["aws_role"] = Prompt.ask(
            "AWS role for access",
            choices=roles + ["none"],
            default=roles[0] if roles else "none",
        )
        if app_config["aws_role"] == "none":
            del app_config["aws_role"]

    # Team access
    teams_config = load_teams_config()
    teams = list(teams_config.get("teams", {}).keys())
    if teams:
        selected_teams = Prompt.ask(
            "Teams with access (comma-separated)", default="default"
        )
        app_config["teams"] = [t.strip() for t in selected_teams.split(",")]

    # Save
    config["apps"][app_name] = app_config
    save_apps_config(config)

    success(f"Application '{app_name}' added!")
    info("\nDevelopers can now use:")
    info(f"  devops app logs {app_name}")
    info(f"  devops app logs {app_name} --follow")
    if app_config.get("health"):
        info(f"  devops app health {app_name}")


@app.command("app-list")
def list_apps():
    """List all configured applications."""
    config = load_apps_config()
    apps = config.get("apps", {})

    if not apps:
        warning("No applications configured")
        info("Add an app: devops admin app-add")
        return

    header("Configured Applications")

    table = create_table(
        "", [("Name", "cyan"), ("Type", ""), ("Log Source", "dim"), ("Teams", "dim")]
    )

    for name, app_cfg in apps.items():
        app_type = app_cfg.get("type", "unknown")
        log_type = app_cfg.get("logs", {}).get("type", "-")
        teams = ", ".join(app_cfg.get("teams", ["default"]))

        table.add_row(name, app_type, log_type, teams[:20])

    console.print(table)
    info(f"\nTotal: {len(apps)} applications")


@app.command("app-show")
def show_app(
    name: str = typer.Argument(..., help="Application name"),
):
    """Show detailed configuration for an application."""
    config = load_apps_config()
    apps = config.get("apps", {})

    if name not in apps:
        error(f"Application '{name}' not found")
        return

    app_cfg = apps[name]
    header(f"Application: {name}")

    console.print(yaml.dump(app_cfg, default_flow_style=False))


@app.command("app-remove")
def remove_app(
    name: str = typer.Argument(..., help="Application name to remove"),
):
    """Remove an application."""
    config = load_apps_config()

    if name not in config.get("apps", {}):
        error(f"Application '{name}' not found")
        return

    if not Confirm.ask(f"Remove application '{name}'?"):
        info("Cancelled")
        return

    del config["apps"][name]
    save_apps_config(config)
    success(f"Application '{name}' removed")


@app.command("app-edit")
def edit_app(
    name: str = typer.Argument(..., help="Application name to edit"),
):
    """Edit an application configuration."""
    config = load_apps_config()

    if name not in config.get("apps", {}):
        error(f"Application '{name}' not found")
        return

    # Write to temp file
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        yaml.dump(config["apps"][name], f, default_flow_style=False)
        temp_file = f.name

    # Open in editor
    editor = os.environ.get("EDITOR", "nano")
    subprocess.run([editor, temp_file])

    # Read back
    with open(temp_file) as f:
        updated = yaml.safe_load(f)

    os.unlink(temp_file)

    if Confirm.ask("Save changes?"):
        config["apps"][name] = updated
        save_apps_config(config)
        success(f"Application '{name}' updated")
    else:
        info("Changes discarded")
