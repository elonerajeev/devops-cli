"""Application management commands for admin."""

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
    handle_duplicate,
    handle_duplicate_batch,
    get_apps_template,
    validate_apps_yaml,
    load_apps_yaml,
)

app = typer.Typer()


@app.command("app-add")
def add_app():
    """Add a new application (interactive)."""
    header("Add New Application")

    # Basic info
    app_name = Prompt.ask("Application name (e.g., api, backend, worker)")

    config = load_apps_config()

    # Check for duplicate
    exists = app_name in config.get("apps", {})
    action = handle_duplicate("App", app_name, exists)

    if action == "cancel":
        info("Cancelled")
        return
    elif action == "skip":
        info(f"Keeping existing app '{app_name}'")
        return

    app_type = Prompt.ask(
        "Application type",
        choices=["lambda", "kubernetes", "docker", "custom"],
        default="custom",
    )
    description = Prompt.ask("Description", default=f"{app_name} application")

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


@app.command("apps-import")
def import_apps(
    file: str = typer.Option(..., "--file", "-f", help="Path to YAML file with apps"),
    skip_existing: bool = typer.Option(
        True,
        "--skip-existing/--overwrite-existing",
        help="Skip existing apps (default) or overwrite them",
    ),
):
    """Import applications from a YAML file."""
    header("Import Applications from YAML")

    file_path = Path(file)

    if not file_path.exists():
        error(f"File not found: {file}")
        info("Create a template with: devops admin apps-export-template --output apps.yaml")
        return

    info(f"Loading apps from: {file}")
    console.print()

    data = load_apps_yaml(file_path)

    if not data:
        error("Could not load YAML file")
        return

    is_valid, error_msg = validate_apps_yaml(data)
    if not is_valid:
        error(f"Validation failed: {error_msg}")
        return

    apps_to_import = data["apps"]
    config = load_apps_config()

    if "apps" not in config:
        config["apps"] = {}

    # Analyze what will be imported
    new_apps = []
    existing_apps = []

    for app_name in apps_to_import:
        if app_name in config["apps"]:
            existing_apps.append(app_name)
        else:
            new_apps.append(app_name)

    info(f"Found {len(apps_to_import)} apps to import:")
    for app_name in apps_to_import:
        status = "(new)" if app_name in new_apps else "(exists - will skip)" if skip_existing else "(exists - will overwrite)"
        console.print(f"  - {app_name} {status}")

    console.print()

    if existing_apps and skip_existing:
        warning(f"Skipping {len(existing_apps)} existing apps: {', '.join(existing_apps)}")
        console.print()

    if not Confirm.ask("Proceed with import?", default=False):
        info("Cancelled")
        return

    imported = 0
    skipped = 0

    for app_name, app_config in apps_to_import.items():
        action = handle_duplicate_batch("App", app_name, app_name in config["apps"], skip_existing)

        if action == "skip":
            skipped += 1
            continue

        # Add timestamp
        app_config["added_at"] = datetime.now().isoformat()
        config["apps"][app_name] = app_config
        imported += 1
        success(f"Imported: {app_name}")

    save_apps_config(config)

    console.print()
    info("Import Summary:")
    info(f"  Imported: {imported} apps")
    if skipped > 0:
        info(f"  Skipped: {skipped} apps (already existed)")


@app.command("apps-export-template")
def export_apps_template(
    output: str = typer.Option(
        "apps-template.yaml", "--output", "-o", help="Output file path"
    ),
):
    """Export a template YAML file for bulk app registration."""
    header("Export Apps Template")

    output_path = Path(output)

    if output_path.exists():
        warning(f"File already exists: {output}")
        if not Confirm.ask("Overwrite?"):
            info("Cancelled")
            return

    template = get_apps_template()

    try:
        with open(output_path, "w") as f:
            f.write(template)

        success(f"Template exported to: {output}")
        console.print()
        info("Next steps:")
        info(f"  1. Edit '{output}' with your applications")
        info(f"  2. Run: devops admin apps-import --file {output}")
        console.print()

    except IOError as e:
        error(f"Failed to write template: {e}")
