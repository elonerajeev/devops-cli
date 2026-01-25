"""Admin commands for Cloud Engineers to configure the CLI.

This module provides commands for cloud engineers/DevOps to:
- Add/remove applications (EC2, ECS, Lambda, etc.)
- Add/remove servers for SSH access
- Configure AWS IAM roles and credentials
- Manage team access and permissions
- Set up log sources and health checks

Developers use the configured resources without needing to know the underlying details.

SECURITY: All admin commands (except init) require admin role authentication.
"""

import os
import json
import shutil
from pathlib import Path
from datetime import datetime
from typing import Optional

import typer
import yaml
from rich.console import Console
from rich.prompt import Prompt, Confirm
from rich.panel import Panel
from rich import box

from devops_cli.config.loader import (
    ADMIN_CONFIG_DIR,
    AWS_CONFIG_FILE,
    TEAMS_CONFIG_FILE,
    SECRETS_DIR,
    ensure_admin_dirs,
    load_apps_config,
    save_apps_config,
    load_servers_config,
    save_servers_config,
    load_aws_config,
    save_aws_config,
    load_teams_config,
    save_teams_config,
    get_aws_credentials_template,
    import_aws_credentials_from_yaml,
    get_aws_roles_template,
    validate_aws_roles_yaml,
    load_aws_roles_yaml,
    get_users_template,
    validate_users_yaml,
    load_users_yaml,
)
from devops_cli.config.settings import load_config
from devops_cli.config.repos import (
    load_repos,
    save_repos,
    get_repo_config,
    add_repo,
    remove_repo,
    fetch_repo_from_github,
    discover_org_repos,
    discover_user_repos,
    validate_github_token,
    validate_repo_name,
)
from devops_cli.config.aws_credentials import (
    save_aws_credentials,
    load_aws_credentials,
    delete_aws_credentials,
    credentials_exist,
    get_credentials_info,
    validate_aws_credentials,
    import_from_dict,
)
from devops_cli.config.websites import (
    load_websites_config,
    save_websites_config,
    get_website_config,
    add_website as add_website_to_config,
    remove_website as remove_website_from_config,
)
from devops_cli.utils.output import (
    success,
    error,
    warning,
    info,
    header,
    create_table,
)
from devops_cli.auth import AuthManager

# Templates directory location
TEMPLATES_DIR = Path(__file__).parent.parent / "config" / "templates"

app = typer.Typer(help="Admin commands for Cloud Engineers to configure the CLI")
console = Console()
auth = AuthManager()

# Commands that don't require admin auth (first-time setup)
INIT_COMMANDS = ["init"]


def check_admin_access(ctx: typer.Context):
    """Check if user has admin access. Called before admin commands."""
    # Get the command being run
    command_name = ctx.invoked_subcommand

    # Skip auth check for init command (first-time setup)
    if command_name in INIT_COMMANDS:
        return

    # Check if CLI is initialized
    if not ADMIN_CONFIG_DIR.exists():
        console.print()
        console.print(
            Panel(
                "[yellow]CLI not initialized yet.[/yellow]\n\n"
                "Run [cyan]devops admin init[/cyan] first to set up the CLI.",
                title="[bold]Setup Required[/bold]",
                border_style="yellow",
                box=box.ROUNDED,
            )
        )
        raise typer.Exit(0)

    # Check if any users exist (if not, allow first admin setup)
    users = auth.list_users()

    if not users:
        # No users yet - this is first-time setup, allow user-add only
        if command_name == "user-add":
            return
        console.print()
        console.print(
            Panel(
                "[yellow]No admin users registered yet.[/yellow]\n\n"
                "Create the first admin user:\n"
                "  [cyan]devops admin user-add --email admin@company.com --role admin[/cyan]",
                title="[bold]First Admin Setup[/bold]",
                border_style="yellow",
                box=box.ROUNDED,
            )
        )
        raise typer.Exit(0)

    # Check if current user is authenticated
    session = auth.get_current_session()
    if not session:
        console.print()
        console.print(
            Panel(
                "[red]Authentication required.[/red]\n\n"
                "Admin commands require you to be logged in.\n\n"
                "Run: [cyan]devops auth login[/cyan]",
                title="[bold]🔐 Login Required[/bold]",
                border_style="red",
                box=box.ROUNDED,
            )
        )
        raise typer.Exit(1)

    # Check if user has admin role
    if session.get("role") != "admin":
        console.print()
        console.print(
            Panel(
                f"[red]Access denied.[/red]\n\n"
                f"You are logged in as: [cyan]{session.get('email')}[/cyan] (role: {session.get('role')})\n\n"
                "Admin commands require [bold]admin[/bold] role.\n"
                "Contact your administrator for access.",
                title="[bold]🚫 Admin Access Required[/bold]",
                border_style="red",
                box=box.ROUNDED,
            )
        )
        raise typer.Exit(1)


@app.callback()
def admin_callback(ctx: typer.Context):
    """Verify admin access before running admin commands."""
    check_admin_access(ctx)


# ==================== Initialize ====================


@app.command("init")
def admin_init():
    """Initialize admin configuration for a new organization."""
    header("DevOps CLI - Admin Setup")

    ensure_admin_dirs()

    # Organization name
    org_name = Prompt.ask("Organization/Company name")

    # AWS Region
    aws_region = Prompt.ask("Default AWS region", default="us-east-1")

    # Create initial configs
    aws_config = {
        "organization": org_name,
        "default_region": aws_region,
        "roles": {},
        "created_at": datetime.now().isoformat(),
        "created_by": os.getenv("USER", "admin"),
    }
    save_aws_config(aws_config)

    apps_config = {
        "organization": org_name,
        "apps": {},
    }
    save_apps_config(apps_config)

    servers_config = {
        "organization": org_name,
        "servers": {},
    }
    save_servers_config(servers_config)

    websites_config = {
        "organization": org_name,
        "websites": {},
    }
    save_websites_config(websites_config)

    teams_config = {
        "organization": org_name,
        "teams": {
            "default": {
                "name": "Default Team",
                "apps": ["*"],  # Access to all apps
                "servers": ["*"],  # Access to all servers
            }
        },
    }
    save_teams_config(teams_config)

    success(f"Admin configuration initialized for '{org_name}'")
    info(f"\nConfig directory: {ADMIN_CONFIG_DIR}")
    info("\nNext steps:")
    info("  1. Add AWS role: devops admin aws add-role")
    info("  2. Add an app:   devops admin app add")
    info("  3. Add a server: devops admin server add")


# ==================== AWS Role Management ====================


@app.command("aws-add-role")
def add_aws_role(
    name: str = typer.Option(
        ..., "--name", "-n", prompt="Role name (e.g., dev-readonly)", help="Role name"
    ),
    role_arn: str = typer.Option(
        ..., "--arn", "-a", prompt="IAM Role ARN", help="IAM Role ARN to assume"
    ),
    region: Optional[str] = typer.Option(None, "--region", "-r", help="AWS region"),
    external_id: Optional[str] = typer.Option(
        None, "--external-id", help="External ID for role assumption"
    ),
    description: Optional[str] = typer.Option(
        None, "--desc", "-d", help="Role description"
    ),
):
    """Add an AWS IAM role for accessing resources."""
    config = load_aws_config()

    if "roles" not in config:
        config["roles"] = {}

    config["roles"][name] = {
        "role_arn": role_arn,
        "region": region or config.get("default_region", "us-east-1"),
        "external_id": external_id,
        "description": description or f"AWS role for {name}",
        "added_at": datetime.now().isoformat(),
    }

    save_aws_config(config)
    success(f"AWS role '{name}' added")
    info(f"Role ARN: {role_arn}")

    info("\nDevelopers can now use: devops aws --role " + name)


@app.command("aws-list-roles")
def list_aws_roles():
    """List configured AWS roles."""
    config = load_aws_config()
    roles = config.get("roles", {})

    if not roles:
        warning("No AWS roles configured")
        info("Add a role: devops admin aws-add-role")
        return

    header("AWS Roles")

    table = create_table(
        "",
        [("Name", "cyan"), ("Region", ""), ("Role ARN", "dim"), ("Description", "dim")],
    )

    for name, role in roles.items():
        table.add_row(
            name,
            role.get("region", "-"),
            role.get("role_arn", "-")[:50] + "...",
            role.get("description", "-")[:30],
        )

    console.print(table)


@app.command("aws-remove-role")
def remove_aws_role(
    name: str = typer.Argument(..., help="Role name to remove"),
):
    """Remove an AWS role."""
    config = load_aws_config()

    if name not in config.get("roles", {}):
        error(f"Role '{name}' not found")
        return

    if not Confirm.ask(f"Remove AWS role '{name}'?"):
        info("Cancelled")
        return

    del config["roles"][name]
    save_aws_config(config)
    success(f"AWS role '{name}' removed")


@app.command("aws-roles-import")
def import_aws_roles(
    file: str = typer.Option(
        ..., "--file", "-f", help="Path to YAML file with AWS roles"
    ),
    merge: bool = typer.Option(
        True, "--merge/--replace", help="Merge with existing or replace all"
    ),
):
    """Import AWS roles from a YAML file.

    The YAML file should have the following format:

        aws_roles:
          dev-readonly:
            role_arn: arn:aws:iam::123456789012:role/DevOpsReadOnly
            region: us-east-1
            external_id: optional-external-id
            description: Read-only access for development

    Example:
        devops admin aws-roles-import --file aws-roles.yaml
        devops admin aws-roles-import --file aws-roles.yaml --replace
    """
    header("Import AWS Roles from YAML")

    file_path = Path(file)

    # Check if file exists
    if not file_path.exists():
        error(f"File not found: {file}")
        info(
            "Create a template with: devops admin aws-roles-export-template --output aws-roles.yaml"
        )
        return

    info(f"Loading roles from: {file}")
    console.print()

    # Load and validate
    data = load_aws_roles_yaml(file_path)

    if not data:
        error("Could not load YAML file")
        return

    is_valid, error_msg = validate_aws_roles_yaml(data)
    if not is_valid:
        error(f"Validation failed: {error_msg}")
        return

    roles_to_import = data["aws_roles"]
    role_count = len(roles_to_import)

    info(f"Found {role_count} roles to import")
    console.print()

    # Show what will be imported
    for name, role in roles_to_import.items():
        console.print(f"  - {name}: {role.get('role_arn', 'N/A')[:50]}...")

    console.print()

    # Load existing config
    config = load_aws_config()

    if "roles" not in config:
        config["roles"] = {}

    existing_count = len(config["roles"])

    if not merge and existing_count > 0:
        warning(f"This will replace {existing_count} existing roles")
        if not Confirm.ask("Continue?"):
            info("Cancelled")
            return
        config["roles"] = {}

    # Import roles
    imported = 0
    updated = 0

    for name, role_data in roles_to_import.items():
        if name in config["roles"]:
            updated += 1
        else:
            imported += 1

        config["roles"][name] = {
            "role_arn": role_data["role_arn"],
            "region": role_data["region"],
            "external_id": role_data.get("external_id"),
            "description": role_data.get("description", f"AWS role for {name}"),
            "added_at": datetime.now().isoformat(),
        }

    save_aws_config(config)

    success("AWS roles imported successfully!")
    console.print()
    if imported > 0:
        info(f"  Added: {imported} new roles")
    if updated > 0:
        info(f"  Updated: {updated} existing roles")
    console.print()
    info("Developers can now use: devops aws --role <role-name>")


@app.command("aws-roles-export-template")
def export_aws_roles_template(
    output: str = typer.Option(
        "aws-roles-template.yaml", "--output", "-o", help="Output file path"
    ),
):
    """Export a template YAML file for AWS roles.

    This generates a template file with example roles that you can edit
    and then import with 'aws-roles-import'.

    Example:
        devops admin aws-roles-export-template
        devops admin aws-roles-export-template --output my-roles.yaml
    """
    header("Export AWS Roles Template")

    output_path = Path(output)

    # Check if file exists
    if output_path.exists():
        warning(f"File already exists: {output}")
        if not Confirm.ask("Overwrite?"):
            info("Cancelled")
            return

    # Get template content
    template = get_aws_roles_template()

    # Write template
    try:
        with open(output_path, "w") as f:
            f.write(template)

        success(f"Template exported to: {output}")
        console.print()
        info("Next steps:")
        info(f"  1. Edit '{output}' with your AWS roles")
        info(f"  2. Run: devops admin aws-roles-import --file {output}")
        console.print()

    except IOError as e:
        error(f"Failed to write template: {e}")


@app.command("aws-roles-export")
def export_aws_roles(
    output: str = typer.Option(
        "aws-roles.yaml", "--output", "-o", help="Output file path"
    ),
):
    """Export current AWS roles to a YAML file.

    This exports your configured roles (without credentials) for backup or sharing.

    Example:
        devops admin aws-roles-export
        devops admin aws-roles-export --output backup-roles.yaml
    """
    header("Export AWS Roles")

    config = load_aws_config()
    roles = config.get("roles", {})

    if not roles:
        warning("No AWS roles configured")
        info("Add roles with: devops admin aws-add-role")
        return

    output_path = Path(output)

    # Check if file exists
    if output_path.exists():
        warning(f"File already exists: {output}")
        if not Confirm.ask("Overwrite?"):
            info("Cancelled")
            return

    # Prepare export data
    export_data = {"aws_roles": {}}

    for name, role in roles.items():
        export_data["aws_roles"][name] = {
            "role_arn": role.get("role_arn"),
            "region": role.get("region"),
            "external_id": role.get("external_id"),
            "description": role.get("description"),
        }

    # Write to file
    try:
        with open(output_path, "w") as f:
            f.write(f"# AWS Roles Export - {datetime.now().isoformat()}\n")
            f.write(
                "# Re-import with: devops admin aws-roles-import --file "
                + output
                + "\n\n"
            )
            yaml.dump(export_data, f, default_flow_style=False, sort_keys=False)

        success(f"Exported {len(roles)} roles to: {output}")

    except IOError as e:
        error(f"Failed to write file: {e}")


@app.command("aws-set-credentials")
def set_aws_credentials(
    role_name: str = typer.Argument(..., help="Role name to set credentials for"),
    access_key: Optional[str] = typer.Option(
        None, "--access-key", "-k", help="AWS Access Key ID"
    ),
    secret_key: Optional[str] = typer.Option(
        None, "--secret-key", "-s", help="AWS Secret Access Key"
    ),
):
    """Set AWS credentials for a role (for cross-account access)."""
    config = load_aws_config()

    if role_name not in config.get("roles", {}):
        error(
            f"Role '{role_name}' not found. Add it first with: devops admin aws-add-role"
        )
        return

    if not access_key:
        access_key = Prompt.ask("AWS Access Key ID")
    if not secret_key:
        secret_key = Prompt.ask("AWS Secret Access Key", password=True)

    # Store credentials securely using project's encryption helper
    from devops_cli.config.aws_credentials import _get_or_create_encryption_key
    from cryptography.fernet import Fernet

    try:
        key = _get_or_create_encryption_key()
        fernet = Fernet(key)

        creds_data = json.dumps(
            {
                "access_key": access_key,
                "secret_key": secret_key,
                "updated_at": datetime.now().isoformat(),
            }
        )

        creds_file = ADMIN_CONFIG_DIR / f".aws_creds_{role_name}.enc"
        encrypted = fernet.encrypt(creds_data.encode())
        creds_file.write_bytes(encrypted)
        creds_file.chmod(0o600)

        success(f"Credentials saved for role '{role_name}'")
        warning("Credentials are encrypted and stored locally.")
    except Exception as e:
        error(f"Failed to save encrypted credentials: {e}")


# ==================== Application Management ====================


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
        # K8s logs can be routed to CloudWatch, but for now we keep it simple
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
        log_type = "cloudwatch"  # Restricted to cloudwatch as requested
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

    for name, app in apps.items():
        app_type = app.get("type", "unknown")
        log_type = app.get("logs", {}).get("type", "-")
        teams = ", ".join(app.get("teams", ["default"]))

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

    app = apps[name]
    header(f"Application: {name}")

    console.print(yaml.dump(app, default_flow_style=False))


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
    import subprocess

    config = load_apps_config()

    if name not in config.get("apps", {}):
        error(f"Application '{name}' not found")
        return

    # Write to temp file
    import tempfile

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


# ==================== Website Management ====================


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
    import subprocess

    websites = load_websites_config()

    if name not in websites:
        error(f"Website '{name}' not found")
        return

    # Write to temp file
    import tempfile

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


# ==================== Server Management ====================


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
    import subprocess
    import tempfile

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


# ==================== Team Management ====================


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
    import subprocess
    import tempfile

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


# ==================== Export/Import ====================


@app.command("export")
def export_config(
    output: str = typer.Option(
        "devops-config.yaml", "--output", "-o", help="Output file"
    ),
    include_secrets: bool = typer.Option(
        False, "--include-secrets", help="Include sensitive data"
    ),
):
    """Export configuration for sharing or backup."""
    config = {
        "exported_at": datetime.now().isoformat(),
        "aws": load_aws_config(),
        "apps": load_apps_config(),
        "servers": load_servers_config(),
        "websites": load_websites_config(),
        "teams": load_teams_config(),
    }

    # Remove sensitive data unless explicitly requested
    if not include_secrets:
        if "roles" in config["aws"]:
            for role in config["aws"]["roles"].values():
                role.pop("credentials", None)

    with open(output, "w") as f:
        yaml.dump(config, f, default_flow_style=False)

    success(f"Configuration exported to {output}")

    if not include_secrets:
        info("Sensitive data was excluded. Use --include-secrets to include.")


@app.command("import")
def import_config(
    input_file: str = typer.Argument(..., help="Config file to import"),
    merge: bool = typer.Option(
        True, "--merge/--replace", help="Merge with existing or replace"
    ),
):
    """Import configuration from file."""
    if not Path(input_file).exists():
        error(f"File not found: {input_file}")
        return

    with open(input_file) as f:
        imported = yaml.safe_load(f)

    if not Confirm.ask(f"Import configuration from {input_file}?"):
        info("Cancelled")
        return

    if merge:
        # Merge with existing
        if "aws" in imported:
            aws_config = load_aws_config()
            aws_config.update(imported["aws"])
            save_aws_config(aws_config)

        if "apps" in imported:
            apps_config = load_apps_config()
            apps_config["apps"].update(imported["apps"].get("apps", {}))
            save_apps_config(apps_config)

        if "servers" in imported:
            servers_config = load_servers_config()
            servers_config["servers"].update(imported["servers"].get("servers", {}))
            save_servers_config(servers_config)

        if "websites" in imported:
            websites_config = load_websites_config()
            websites_config.update(imported.get("websites", {}))
            save_websites_config(websites_config)

        if "teams" in imported:
            teams_config = load_teams_config()
            teams_config["teams"].update(imported["teams"].get("teams", {}))
            save_teams_config(teams_config)

        success("Configuration merged")
    else:
        # Replace all
        if "aws" in imported:
            save_aws_config(imported["aws"])
        if "apps" in imported:
            save_apps_config({"apps": imported["apps"]})
        if "servers" in imported:
            save_servers_config({"servers": imported["servers"]})
        if "websites" in imported:
            save_websites_config(imported.get("websites", {}))
        if "teams" in imported:
            save_teams_config(imported["teams"])

        success("Configuration replaced")


# ==================== Status ====================


@app.command("status")
def admin_status():
    """Show admin configuration status."""
    header("Admin Configuration Status")

    aws_config = load_aws_config()
    apps_config = load_apps_config()
    servers_config = load_servers_config()
    teams_config = load_teams_config()

    org = aws_config.get("organization", "Not configured")
    console.print(f"[bold]Organization:[/] {org}")
    console.print()

    # AWS
    roles = aws_config.get("roles", {})
    if roles:
        console.print(f"[green]✓[/] AWS Roles: {len(roles)} configured")
        for name in roles:
            console.print(f"    - {name}")
    else:
        console.print("[yellow]![/] AWS Roles: None configured")

    # Apps
    apps = apps_config.get("apps", {})
    if apps:
        console.print(f"[green]✓[/] Applications: {len(apps)} configured")
        for name in apps:
            console.print(f"    - {name}")
    else:
        console.print("[yellow]![/] Applications: None configured")

    # Servers
    servers = servers_config.get("servers", {})
    if servers:
        console.print(f"[green]✓[/] Servers: {len(servers)} configured")
        for name in servers:
            console.print(f"    - {name}")
    else:
        console.print("[yellow]![/] Servers: None configured")

    # Websites
    websites = load_websites_config()
    if websites:
        console.print(f"[green]✓[/] Websites: {len(websites)} configured")
        for name in websites:
            console.print(f"    - {name}")
    else:
        console.print("[yellow]![/] Websites: None configured")

    # Teams
    teams = teams_config.get("teams", {})
    if teams:
        console.print(f"[green]✓[/] Teams: {len(teams)} configured")
        for name in teams:
            console.print(f"    - {name}")
    else:
        console.print("[yellow]![/] Teams: None configured")

    console.print()

    # Users
    try:
        users = auth.list_users()
        if users:
            console.print(f"[green]✓[/] Users: {len(users)} registered")
            for u in users:
                status = (
                    "[green]active[/]" if u.get("active", True) else "[red]inactive[/]"
                )
                console.print(f"    - {u['email']} ({status})")
        else:
            console.print("[yellow]![/] Users: None registered")
    except Exception:
        console.print("[yellow]![/] Users: Auth not initialized")

    console.print()
    info("Config directory: " + str(ADMIN_CONFIG_DIR))


# ==================== Templates Management ====================


@app.command("templates")
def manage_templates(
    list_templates: bool = typer.Option(
        False, "--list", "-l", help="List available templates"
    ),
    copy_all: bool = typer.Option(
        False, "--copy", "-c", help="Copy all templates to current directory"
    ),
    copy_template: Optional[str] = typer.Option(
        None, "--copy-template", "-t", help="Copy specific template"
    ),
    show_path: bool = typer.Option(
        False, "--path", "-p", help="Show templates directory path"
    ),
    output_dir: str = typer.Option(
        ".", "--output", "-o", help="Output directory for copied templates"
    ),
):
    """Manage YAML configuration templates.

    Templates are pre-configured YAML files with example values and documentation.
    Copy them, fill in your actual values, and import them.

    Examples:
        devops admin templates --list              # List all templates
        devops admin templates --copy              # Copy all to current dir
        devops admin templates -t apps             # Copy only apps template
        devops admin templates --path              # Show templates location
    """
    if not TEMPLATES_DIR.exists():
        error(f"Templates directory not found: {TEMPLATES_DIR}")
        return

    # List available templates
    template_files = list(TEMPLATES_DIR.glob("*-template.yaml"))

    if show_path:
        header("Templates Directory")
        console.print(f"[cyan]{TEMPLATES_DIR}[/]")
        console.print()
        info("You can copy templates manually from this location.")
        return

    if list_templates or (not copy_all and not copy_template):
        header("Available Configuration Templates")
        console.print()

        table = create_table(
            "", [("Template", "cyan"), ("Description", ""), ("Import Command", "dim")]
        )

        template_info = {
            "apps": (
                "Applications (ECS, EC2, Lambda, etc.)",
                "devops admin import --file",
            ),
            "servers": ("SSH servers configuration", "devops admin import --file"),
            "websites": ("Website health monitoring", "devops admin import --file"),
            "teams": ("Team access control", "devops admin import --file"),
            "repos": ("GitHub repositories", "devops admin import --file"),
            "aws-roles": ("AWS IAM roles", "devops admin aws-roles-import --file"),
            "aws-credentials": (
                "AWS credentials (sensitive!)",
                "devops admin aws-import --file",
            ),
            "users": ("Bulk user registration", "devops admin users-import --file"),
        }

        for tf in sorted(template_files):
            name = tf.stem.replace("-template", "")
            desc, cmd = template_info.get(
                name, ("Configuration", "devops admin import --file")
            )
            table.add_row(name, desc, cmd)

        console.print(table)
        console.print()
        info("Copy templates with: devops admin templates --copy")
        info("Or copy specific: devops admin templates -t <name>")
        return

    output_path = Path(output_dir)
    if not output_path.exists():
        output_path.mkdir(parents=True, exist_ok=True)

    if copy_template:
        # Copy specific template
        template_name = (
            copy_template.lower().replace("-template", "").replace(".yaml", "")
        )
        template_file = TEMPLATES_DIR / f"{template_name}-template.yaml"

        if not template_file.exists():
            error(f"Template not found: {template_name}")
            info("Available templates:")
            for tf in template_files:
                console.print(f"  - {tf.stem.replace('-template', '')}")
            return

        dest_file = output_path / f"{template_name}.yaml"

        if dest_file.exists():
            if not Confirm.ask(f"Overwrite existing {dest_file.name}?"):
                info("Cancelled")
                return

        shutil.copy(template_file, dest_file)
        success(f"Copied: {dest_file}")
        console.print()
        info(f"Edit '{dest_file}' with your values, then import it.")
        return

    if copy_all:
        # Copy all templates
        header("Copying All Templates")
        console.print()

        copied = 0
        for tf in template_files:
            name = tf.stem.replace("-template", "")
            dest_file = output_path / f"{name}.yaml"

            # Skip if exists and user doesn't want to overwrite
            if dest_file.exists():
                console.print(f"[yellow]Skipping[/] {name}.yaml (already exists)")
                continue

            shutil.copy(tf, dest_file)
            console.print(f"[green]Copied[/] {name}.yaml")
            copied += 1

        console.print()
        if copied > 0:
            success(f"Copied {copied} templates to {output_path}")
            console.print()
            info("Next steps:")
            info("  1. Edit each YAML file with your actual values")
            info("  2. Import using the appropriate command")
            info("  3. Delete sensitive files (aws-credentials.yaml) after import!")
        else:
            warning("No new templates copied (all already exist)")
            info("Use --output to specify a different directory")


# ==================== User Management ====================


@app.command("user-add")
def add_user(
    email: str = typer.Option(
        ..., "--email", "-e", prompt="User email", help="User's email address"
    ),
    name: Optional[str] = typer.Option(
        None, "--name", "-n", help="User's display name"
    ),
    role: str = typer.Option(
        "developer", "--role", "-r", help="Role: developer or admin"
    ),
    team: str = typer.Option("default", "--team", "-t", help="Team name"),
):
    """Register a new user and generate access token.

    The token will be displayed ONCE. Share it securely with the user.
    """
    if role not in ["developer", "admin"]:
        error("Role must be 'developer' or 'admin'")
        return

    try:
        token = auth.register_user(email, name, role, team)

        success(f"User '{email}' registered!")
        console.print()
        console.print(
            "[bold yellow]ACCESS TOKEN (share this securely with the user):[/]"
        )
        console.print()
        console.print(f"[bold cyan]{token}[/]")
        console.print()
        warning("This token is shown only ONCE. Save it now!")
        console.print()
        info("User can login with: devops auth login")

    except ValueError as e:
        error(str(e))


@app.command("user-list")
def list_users():
    """List all registered users."""
    users = auth.list_users()

    if not users:
        warning("No users registered")
        info("Add a user: devops admin user-add")
        return

    header("Registered Users")

    table = create_table(
        "",
        [
            ("Email", "cyan"),
            ("Name", ""),
            ("Role", ""),
            ("Team", ""),
            ("Status", ""),
            ("Last Login", "dim"),
        ],
    )

    for user in users:
        status_str = (
            "[green]Active[/]" if user.get("active", True) else "[red]Inactive[/]"
        )
        last_login = user.get("last_login", "-")
        if last_login and last_login != "-":
            from datetime import datetime

            try:
                dt = datetime.fromisoformat(last_login)
                last_login = dt.strftime("%Y-%m-%d %H:%M")
            except Exception:
                pass

        table.add_row(
            user["email"],
            user.get("name", "-"),
            user.get("role", "developer"),
            user.get("team", "default"),
            status_str,
            last_login or "-",
        )

    console.print(table)
    info(f"\nTotal: {len(users)} users")


@app.command("user-remove")
def remove_user(
    email: str = typer.Argument(..., help="User email to remove"),
):
    """Remove a user permanently."""
    if not Confirm.ask(f"Remove user '{email}' permanently?"):
        info("Cancelled")
        return

    if auth.remove_user(email):
        success(f"User '{email}' removed")
    else:
        error(f"User '{email}' not found")


@app.command("user-deactivate")
def deactivate_user(
    email: str = typer.Argument(..., help="User email to deactivate"),
):
    """Deactivate a user (prevents login but keeps record)."""
    if auth.deactivate_user(email):
        success(f"User '{email}' deactivated")
        info("User cannot login until reactivated")
    else:
        error(f"User '{email}' not found")


@app.command("user-activate")
def activate_user(
    email: str = typer.Argument(..., help="User email to activate"),
):
    """Reactivate a deactivated user."""
    if auth.activate_user(email):
        success(f"User '{email}' activated")
    else:
        error(f"User '{email}' not found")


@app.command("user-reset-token")
def reset_user_token(
    email: str = typer.Argument(..., help="User email to reset token for"),
):
    """Generate a new token for a user (invalidates old token)."""
    if not Confirm.ask(
        f"Generate new token for '{email}'? (old token will stop working)"
    ):
        info("Cancelled")
        return

    try:
        token = auth.reset_token(email)

        success(f"New token generated for '{email}'!")
        console.print()
        console.print("[bold yellow]NEW ACCESS TOKEN:[/]")
        console.print()
        console.print(f"[bold cyan]{token}[/]")
        console.print()
        warning("Share this securely with the user. Old token no longer works.")

    except ValueError as e:
        error(str(e))


@app.command("users-import")
def import_users(
    file: str = typer.Option(..., "--file", "-f", help="Path to YAML file with users"),
    skip_existing: bool = typer.Option(
        True, "--skip-existing/--fail-existing", help="Skip users that already exist"
    ),
):
    """Import users from a YAML file (bulk registration).

    The YAML file should have the following format:

        users:
          - email: admin@company.com
            name: Admin User
            role: admin
            team: default

          - email: dev@company.com
            name: Developer
            role: developer
            team: backend

    Tokens will be generated and displayed after import.
    Share tokens securely with each user!

    Example:
        devops admin users-import --file users.yaml
        devops admin users-import --file users.yaml --fail-existing
    """
    header("Import Users from YAML")

    file_path = Path(file)

    # Check if file exists
    if not file_path.exists():
        error(f"File not found: {file}")
        info(
            "Create a template with: devops admin users-export-template --output users.yaml"
        )
        return

    info(f"Loading users from: {file}")
    console.print()

    # Load and validate
    data = load_users_yaml(file_path)

    if not data:
        error("Could not load YAML file")
        return

    is_valid, error_msg = validate_users_yaml(data)
    if not is_valid:
        error(f"Validation failed: {error_msg}")
        return

    users_to_import = data["users"]
    user_count = len(users_to_import)

    info(f"Found {user_count} users to import")
    console.print()

    # Check for existing users
    existing_users = {u["email"] for u in auth.list_users()}
    new_users = [u for u in users_to_import if u["email"] not in existing_users]
    duplicate_users = [u for u in users_to_import if u["email"] in existing_users]

    if duplicate_users:
        if skip_existing:
            warning(f"Skipping {len(duplicate_users)} existing users:")
            for u in duplicate_users:
                console.print(f"  - {u['email']}")
            console.print()
        else:
            error(
                f"Found {len(duplicate_users)} existing users. Use --skip-existing to skip them."
            )
            for u in duplicate_users:
                console.print(f"  - {u['email']}")
            return

    if not new_users:
        warning("No new users to import (all already exist)")
        return

    info(f"Will import {len(new_users)} new users:")
    for u in new_users:
        console.print(f"  - {u['email']} ({u['role']})")
    console.print()

    if not Confirm.ask("Proceed with import?"):
        info("Cancelled")
        return

    # Import users and collect tokens
    console.print()
    results = []

    for user in new_users:
        try:
            token = auth.register_user(
                email=user["email"],
                name=user.get("name"),
                role=user["role"],
                team=user.get("team", "default"),
            )
            results.append({"email": user["email"], "token": token, "success": True})
            success(f"Registered: {user['email']}")

        except ValueError as e:
            results.append({"email": user["email"], "error": str(e), "success": False})
            error(f"Failed: {user['email']} - {e}")

    console.print()

    # Summary
    successful = [r for r in results if r["success"]]
    failed = [r for r in results if not r["success"]]

    header("Import Summary")

    if successful:
        console.print(f"[green]Successfully registered: {len(successful)} users[/]")
        console.print()
        console.print(
            "[bold yellow]ACCESS TOKENS (share these securely with each user):[/]"
        )
        console.print()

        table = create_table("", [("Email", "cyan"), ("Token", "")])

        for r in successful:
            table.add_row(r["email"], r["token"])

        console.print(table)
        console.print()
        warning("Tokens are shown only ONCE. Save them now!")

    if failed:
        console.print()
        console.print(f"[red]Failed to register: {len(failed)} users[/]")
        for r in failed:
            console.print(f"  - {r['email']}: {r['error']}")


@app.command("users-export-template")
def export_users_template(
    output: str = typer.Option(
        "users-template.yaml", "--output", "-o", help="Output file path"
    ),
):
    """Export a template YAML file for bulk user registration.

    This generates a template file with example users that you can edit
    and then import with 'users-import'.

    Example:
        devops admin users-export-template
        devops admin users-export-template --output my-users.yaml
    """
    header("Export Users Template")

    output_path = Path(output)

    # Check if file exists
    if output_path.exists():
        warning(f"File already exists: {output}")
        if not Confirm.ask("Overwrite?"):
            info("Cancelled")
            return

    # Get template content
    template = get_users_template()

    # Write template
    try:
        with open(output_path, "w") as f:
            f.write(template)

        success(f"Template exported to: {output}")
        console.print()
        info("Next steps:")
        info(f"  1. Edit '{output}' with your users")
        info(f"  2. Run: devops admin users-import --file {output}")
        console.print()

    except IOError as e:
        error(f"Failed to write template: {e}")


@app.command("users-export")
def export_users(
    output: str = typer.Option("users.yaml", "--output", "-o", help="Output file path"),
):
    """Export current users to a YAML file (without tokens).

    This exports your registered users for backup or documentation.
    Tokens are NOT included for security reasons.

    Example:
        devops admin users-export
        devops admin users-export --output backup-users.yaml
    """
    header("Export Users")

    users = auth.list_users()

    if not users:
        warning("No users registered")
        info("Add users with: devops admin user-add")
        return

    output_path = Path(output)

    # Check if file exists
    if output_path.exists():
        warning(f"File already exists: {output}")
        if not Confirm.ask("Overwrite?"):
            info("Cancelled")
            return

    # Prepare export data
    export_data = {"users": []}

    for user in users:
        export_data["users"].append(
            {
                "email": user["email"],
                "name": user.get("name"),
                "role": user.get("role", "developer"),
                "team": user.get("team", "default"),
            }
        )

    # Write to file
    try:
        with open(output_path, "w") as f:
            f.write(f"# Users Export - {datetime.now().isoformat()}\n")
            f.write("# NOTE: Tokens are NOT included for security.\n")
            f.write("# To re-import, users will get NEW tokens.\n\n")
            yaml.dump(export_data, f, default_flow_style=False, sort_keys=False)

        success(f"Exported {len(users)} users to: {output}")
        warning("Tokens are NOT included in export for security reasons")

    except IOError as e:
        error(f"Failed to write file: {e}")


@app.command("audit-logs")
def view_audit_logs(
    limit: int = typer.Option(
        50, "--limit", "-l", help="Number of log entries to show"
    ),
):
    """View authentication audit logs."""
    logs = auth.get_audit_logs(limit)

    if not logs:
        info("No audit logs found")
        return

    header("Audit Logs")

    for log in logs:
        # Color code by event type
        if "FAILED" in log or "BLOCKED" in log:
            console.print(f"[red]{log}[/]")
        elif "SUCCESS" in log or "REGISTERED" in log:
            console.print(f"[green]{log}[/]")
        elif "REMOVED" in log or "DEACTIVATED" in log:
            console.print(f"[yellow]{log}[/]")
        else:
            console.print(f"[dim]{log}[/]")

    console.print()
    info(f"Showing last {len(logs)} entries")


# ==================== Repository Management ====================


@app.command("repo-discover")
def discover_repos(
    source: str = typer.Option(
        ...,
        "--source",
        "-s",
        prompt="Source type (org/user)",
        help="Discover from org or user repos",
    ),
    name: str = typer.Option(
        ...,
        "--name",
        "-n",
        prompt="Organization or username",
        help="GitHub organization or username",
    ),
):
    """Auto-discover all repositories from GitHub org or user.

    This will fetch all repo details automatically from GitHub API.
    """
    config = load_config()
    token = config.get("github", {}).get("token")

    if not token:
        error("GitHub token not configured")
        info("Set GITHUB_TOKEN env var or add to config: devops init")
        return

    # Validate token
    is_valid, err_msg = validate_github_token(token)
    if not is_valid:
        error(f"GitHub token validation failed: {err_msg}")
        info("Please check your token at: https://github.com/settings/tokens")
        info("Required scope: 'repo'")
        return

    header(f"Discovering repositories from {source}: {name}")

    # Fetch repos from GitHub
    if source.lower() in ["org", "organization"]:
        repos = discover_org_repos(name, token)
    elif source.lower() == "user":
        repos = discover_user_repos(name, token)
    else:
        error("Source must be 'org' or 'user'")
        return

    if not repos:
        warning("No repositories found or access denied")
        info("Make sure your GitHub token has 'repo' scope")
        return

    success(f"Found {len(repos)} repositories!")
    console.print()

    # Show repos in a table
    table = create_table(
        "Discovered Repositories",
        [
            ("Name", "cyan"),
            ("Owner", ""),
            ("Visibility", "yellow"),
            ("Language", "dim"),
        ],
    )

    for repo in repos[:20]:  # Show first 20
        visibility = "[red]private[/]" if repo["private"] else "[green]public[/]"
        table.add_row(
            repo["name"], repo["owner"], visibility, repo.get("language", "Unknown")
        )

    console.print(table)

    if len(repos) > 20:
        console.print(f"\n... and {len(repos) - 20} more")

    console.print()

    # Ask which repos to add
    add_all = Confirm.ask(
        "Add all discovered repositories to configuration?", default=False
    )

    if add_all:
        # Add all repos
        existing_repos = load_repos()
        added_count = 0

        for repo in repos:
            repo_name = repo["name"]

            # Use owner/repo as unique key if repo name conflicts
            if repo_name in existing_repos:
                repo_name = f"{repo['owner']}/{repo['name']}"

            existing_repos[repo_name] = {
                "owner": repo["owner"],
                "repo": repo["name"],
                "description": repo["description"],
                "default_branch": repo["default_branch"],
                "visibility": repo["visibility"],
                "private": repo["private"],
                "language": repo.get("language"),
                "url": repo["url"],
                "created_at": repo.get("created_at"),
                "added_at": datetime.now().isoformat(),
                "auto_discovered": True,
            }
            added_count += 1

        save_repos(existing_repos)
        success(f"Added {added_count} repositories to configuration!")
        info("\nDevelopers can now use: devops git repos")

    else:
        # Interactive selection
        info("Add repositories individually with: devops admin repo-add")
        info("Example: devops admin repo-add --name myrepo --owner myorg --repo myrepo")


@app.command("repo-add")
def add_repository(
    name: str = typer.Option(
        None, "--name", "-n", help="Friendly name for the repo (e.g., backend)"
    ),
    owner: str = typer.Option(None, "--owner", "-o", help="GitHub owner/org"),
    repo: str = typer.Option(None, "--repo", "-r", help="Repository name"),
    auto_fetch: bool = typer.Option(
        True, "--auto-fetch/--no-fetch", help="Auto-fetch details from GitHub"
    ),
):
    """Add a specific repository to configuration.

    If auto-fetch is enabled, repo details (description, default branch, etc.)
    will be fetched automatically from GitHub.
    """
    config = load_config()
    token = config.get("github", {}).get("token")

    # Interactive prompts if not provided
    if not name:
        name = Prompt.ask("Repository friendly name (e.g., backend, frontend)")
    if not owner:
        owner = Prompt.ask("GitHub owner/organization")
    if not repo:
        repo = Prompt.ask("Repository name", default=name)

    # Validate repository name
    is_valid, err_msg = validate_repo_name(name)
    if not is_valid:
        error(f"Invalid repository name: {err_msg}")
        return

    # Check if repo already exists
    existing_repos = load_repos()
    if name in existing_repos:
        error(f"Repository '{name}' already exists in configuration")
        info(f"Use: devops admin repo-show {name}")
        return

    if not token and auto_fetch:
        warning(
            "GitHub token not configured. Will add repo without auto-fetching details."
        )
        auto_fetch = False
    elif token and auto_fetch:
        # Validate token
        is_valid, err_msg = validate_github_token(token)
        if not is_valid:
            warning(f"GitHub token validation failed: {err_msg}")
            warning("Will add repo without auto-fetching details.")
            auto_fetch = False

    header(f"Adding repository: {owner}/{repo}")

    repo_config = {
        "owner": owner,
        "repo": repo,
        "added_at": datetime.now().isoformat(),
    }

    # Auto-fetch details from GitHub
    if auto_fetch and token:
        info("Fetching repository details from GitHub...")
        github_data = fetch_repo_from_github(owner, repo, token)

        if github_data and "error" not in github_data:
            # Success
            repo_config.update(
                {
                    "description": github_data.get("description", "No description"),
                    "default_branch": github_data.get("default_branch", "main"),
                    "visibility": github_data.get("visibility", "private"),
                    "private": github_data.get("private", True),
                    "language": github_data.get("language"),
                    "url": github_data.get("url"),
                    "created_at": github_data.get("created_at"),
                    "auto_fetched": True,
                }
            )
            success("Repository details fetched from GitHub!")
            console.print()
            console.print(f"  Description: {repo_config['description']}")
            console.print(f"  Default Branch: {repo_config['default_branch']}")
            console.print(f"  Language: {repo_config.get('language', 'Unknown')}")
            console.print(f"  Visibility: {repo_config['visibility']}")
        elif github_data and "error" in github_data:
            # Error from GitHub API
            error(f"GitHub API error: {github_data.get('message', 'Unknown error')}")
            if github_data.get("error") == "rate_limit":
                info("GitHub rate limit exceeded. Try again later or use manual entry.")
            if not Confirm.ask("Add repository anyway (without GitHub data)?"):
                info("Cancelled")
                return
            # Add minimal config
            repo_config["default_branch"] = Prompt.ask("Default branch", default="main")
            repo_config["description"] = Prompt.ask(
                "Description (optional)", default=""
            )
        else:
            # Repository not found
            error("Could not fetch repo details from GitHub")
            info("Repository might not exist or token lacks access")
            if not Confirm.ask("Add repository anyway (without GitHub data)?"):
                info("Cancelled")
                return
            # Add minimal config
            repo_config["default_branch"] = Prompt.ask("Default branch", default="main")
            repo_config["description"] = Prompt.ask(
                "Description (optional)", default=""
            )
    else:
        # Manual entry
        repo_config["default_branch"] = Prompt.ask("Default branch", default="main")
        repo_config["description"] = Prompt.ask("Description (optional)", default="")

    # Save
    add_repo(
        name,
        owner,
        repo,
        **{k: v for k, v in repo_config.items() if k not in ["owner", "repo"]},
    )

    success(f"Repository '{name}' added!")
    console.print()
    info("Developers can now use:")
    info(f"  devops git pipeline --repo {name}")
    info(f"  devops git pr --repo {name}")
    info(f"  devops git prs --repo {name}")


@app.command("repo-list")
def list_repositories():
    """List all configured repositories."""
    repos = load_repos()

    if not repos:
        warning("No repositories configured")
        info("Discover repos: devops admin repo-discover")
        info("Or add manually: devops admin repo-add")
        return

    header("Configured Repositories")

    table = create_table(
        "",
        [
            ("Name", "cyan"),
            ("Owner/Repo", ""),
            ("Branch", "dim"),
            ("Language", "dim"),
            ("Visibility", "yellow"),
        ],
    )

    for name, repo in repos.items():
        owner_repo = f"{repo['owner']}/{repo['repo']}"
        branch = repo.get("default_branch", "main")
        language = repo.get("language", "Unknown")
        repo.get("visibility", "unknown")

        vis_color = (
            "[red]private[/]" if repo.get("private", True) else "[green]public[/]"
        )

        table.add_row(name, owner_repo[:40], branch, language, vis_color)

    console.print(table)
    info(f"\nTotal: {len(repos)} repositories")
    console.print()
    info("View details: devops admin repo-show <name>")


@app.command("repo-show")
def show_repository(
    name: str = typer.Argument(..., help="Repository name"),
):
    """Show detailed configuration for a repository."""
    repo = get_repo_config(name)

    if not repo:
        error(f"Repository '{name}' not found")
        info("List repos: devops admin repo-list")
        return

    header(f"Repository: {name}")
    console.print()
    console.print(yaml.dump(repo, default_flow_style=False))


@app.command("repo-remove")
def remove_repository(
    name: str = typer.Argument(..., help="Repository name to remove"),
):
    """Remove a repository from configuration."""
    if not get_repo_config(name):
        error(f"Repository '{name}' not found")
        return

    if not Confirm.ask(f"Remove repository '{name}' from configuration?"):
        info("Cancelled")
        return

    if remove_repo(name):
        success(f"Repository '{name}' removed")
    else:
        error(f"Failed to remove repository '{name}'")


@app.command("repo-refresh")
def refresh_repository(
    name: str = typer.Argument(..., help="Repository name to refresh"),
):
    """Refresh repository details from GitHub (updates description, branch, etc.)."""
    config = load_config()
    token = config.get("github", {}).get("token")

    if not token:
        error("GitHub token not configured")
        return

    repo = get_repo_config(name)
    if not repo:
        error(f"Repository '{name}' not found")
        return

    owner = repo["owner"]
    repo_name = repo["repo"]

    header(f"Refreshing: {owner}/{repo_name}")

    # Fetch latest data from GitHub
    github_data = fetch_repo_from_github(owner, repo_name, token)

    if not github_data:
        error("Could not fetch repository details from GitHub")
        info("Repository might not exist or token lacks access")
        return

    # Update repo config
    repos = load_repos()
    repos[name].update(
        {
            "description": github_data.get("description", "No description"),
            "default_branch": github_data.get("default_branch", "main"),
            "visibility": github_data.get("visibility", "private"),
            "private": github_data.get("private", True),
            "language": github_data.get("language"),
            "url": github_data.get("url"),
            "created_at": github_data.get("created_at"),
            "last_refreshed": datetime.now().isoformat(),
        }
    )

    save_repos(repos)

    success(f"Repository '{name}' refreshed from GitHub!")
    console.print()
    console.print(f"  Description: {github_data['description']}")
    console.print(f"  Default Branch: {github_data['default_branch']}")
    console.print(f"  Language: {github_data.get('language', 'Unknown')}")
    console.print(f"  Visibility: {github_data['visibility']}")


@app.command("repo-edit")
def edit_repository(
    name: str = typer.Argument(..., help="Repository name to edit"),
):
    """Edit a repository configuration."""
    import subprocess
    import tempfile

    repo = get_repo_config(name)
    if not repo:
        error(f"Repository '{name}' not found")
        return

    # Write to temp file
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        yaml.dump(repo, f, default_flow_style=False)
        temp_file = f.name

    # Open in editor
    editor = os.environ.get("EDITOR", "nano")
    subprocess.run([editor, temp_file])

    # Read back
    with open(temp_file) as f:
        updated = yaml.safe_load(f)

    os.unlink(temp_file)

    if Confirm.ask("Save changes?"):
        repos = load_repos()
        repos[name] = updated
        save_repos(repos)
        success(f"Repository '{name}' updated")
    else:
        info("Changes discarded")


# ==================== AWS Credentials Management ====================


@app.command("aws-configure")
def configure_aws_credentials(
    access_key: Optional[str] = typer.Option(
        None, "--access-key", "-k", help="AWS Access Key ID"
    ),
    secret_key: Optional[str] = typer.Option(
        None, "--secret-key", "-s", help="AWS Secret Access Key"
    ),
    region: Optional[str] = typer.Option(None, "--region", "-r", help="AWS Region"),
    from_file: Optional[str] = typer.Option(
        None, "--from-file", "-f", help="Import from YAML file instead"
    ),
):
    """Configure AWS credentials for CloudWatch log access.

    These credentials will be stored securely (encrypted) and used for all AWS operations.
    They should have READ-ONLY CloudWatch Logs permissions.

    Required IAM Permissions:
    - logs:DescribeLogGroups
    - logs:FilterLogEvents
    - logs:GetLogEvents
    - ec2:DescribeInstances (optional, for EC2 info)

    You can also import from a YAML file:
        devops admin aws-configure --from-file aws-credentials.yaml
    """
    # If --from-file is provided, delegate to aws-import
    if from_file:
        import_aws_credentials(file=from_file, skip_validation=False)
        return

    header("Configure AWS Credentials")

    info("These credentials will be used for CloudWatch log access.")
    info("Ensure they have READ-ONLY permissions.")
    console.print()

    # Interactive prompts if not provided
    if not access_key:
        access_key = Prompt.ask("AWS Access Key ID")

    if not secret_key:
        secret_key = Prompt.ask("AWS Secret Access Key", password=True)

    if not region:
        region = Prompt.ask("AWS Region", default="ap-south-1")

    # Validate format
    if not access_key.startswith("AKIA"):
        error("Invalid Access Key format. Should start with 'AKIA'")
        return

    if len(secret_key) < 20:
        error("Invalid Secret Key. Too short.")
        return

    info("Validating credentials with AWS...")
    console.print()

    # Test credentials
    is_valid, error_msg = validate_aws_credentials(access_key, secret_key, region)

    if not is_valid:
        error(f"Credential validation failed: {error_msg}")
        info("\nPlease check:")
        info("  1. Access Key and Secret Key are correct")
        info("  2. IAM user has CloudWatch Logs read permissions")
        info("  3. Region is correct")
        return

    success("✓ Credentials validated successfully!")
    console.print()

    # Save credentials
    description = Prompt.ask(
        "Description (optional)", default="DevOps CLI CloudWatch Access"
    )

    if save_aws_credentials(access_key, secret_key, region, description):
        success("AWS credentials saved securely!")
        console.print()
        info("Credentials are encrypted and stored at:")
        info("  ~/.devops-cli/.aws_credentials.enc")
        console.print()
        info("Developers can now use:")
        info("  devops aws cloudwatch <log-group>")
        info("  devops app logs <app-name>")
    else:
        error("Failed to save credentials")


@app.command("aws-show")
def show_aws_credentials():
    """Show configured AWS credentials (masked)."""
    if not credentials_exist():
        warning("No AWS credentials configured")
        info("Configure with: devops admin aws-configure")
        return

    header("AWS Credentials")

    creds_info = get_credentials_info()
    if creds_info:
        console.print(f"[bold]Region:[/] {creds_info['region']}")
        console.print(f"[bold]Access Key:[/] {creds_info['access_key_preview']}")
        console.print(f"[bold]Description:[/] {creds_info['description']}")
        console.print()
        info("Credentials are stored encrypted at:")
        info("  ~/.devops-cli/.aws_credentials.enc")
    else:
        error("Failed to load credentials")


@app.command("aws-test")
def test_aws_credentials():
    """Test AWS credentials and permissions."""
    if not credentials_exist():
        warning("No AWS credentials configured")
        info("Configure with: devops admin aws-configure")
        return

    header("Testing AWS Credentials")

    creds = load_aws_credentials()
    if not creds:
        error("Failed to load credentials")
        return

    info(f"Region: {creds['region']}")
    info(
        f"Testing with Access Key: {creds['access_key'][:4]}...{creds['access_key'][-4:]}"
    )
    console.print()

    is_valid, error_msg = validate_aws_credentials(
        creds["access_key"], creds["secret_key"], creds["region"]
    )

    if is_valid:
        success("✓ Credentials are valid!")
        success("✓ CloudWatch Logs access confirmed!")
        console.print()
        info("Developers can now access AWS logs")
    else:
        error(f"Validation failed: {error_msg}")
        console.print()
        info("Please reconfigure with: devops admin aws-configure")


@app.command("aws-remove")
def remove_aws_credentials():
    """Remove stored AWS credentials."""
    if not credentials_exist():
        warning("No AWS credentials configured")
        return

    if not Confirm.ask("Remove AWS credentials?"):
        info("Cancelled")
        return

    if delete_aws_credentials():
        success("AWS credentials removed")
        info("Configure again with: devops admin aws-configure")
    else:
        error("Failed to remove credentials")


@app.command("aws-import")
def import_aws_credentials(
    file: str = typer.Option(
        ..., "--file", "-f", help="Path to YAML file with AWS credentials"
    ),
    skip_validation: bool = typer.Option(
        False, "--skip-validation", help="Skip AWS API validation (for CI/CD)"
    ),
):
    """Import AWS credentials from a YAML file.

    The YAML file should have the following format:

        aws_credentials:
          access_key: AKIAXXXXXXXXXXXXXXXXXX
          secret_key: your-secret-access-key
          region: ap-south-1
          description: DevOps CLI AWS Access

    Credentials are validated and then encrypted for secure storage.
    The input YAML file is NOT stored by the CLI - delete it after import!

    Example:
        devops admin aws-import --file aws-credentials.yaml
        devops admin aws-import --file creds.yaml --skip-validation
    """
    header("Import AWS Credentials from YAML")

    file_path = Path(file)

    # Check if file exists
    if not file_path.exists():
        error(f"File not found: {file}")
        info(
            "Create a template with: devops admin aws-export-template --output aws-credentials.yaml"
        )
        return

    info(f"Loading credentials from: {file}")
    console.print()

    # Import and validate
    if skip_validation:
        warning("Skipping AWS API validation")
        console.print()

    success_result, error_msg, credentials = import_aws_credentials_from_yaml(
        file_path, skip_validation=skip_validation
    )

    if not success_result:
        error(f"Import failed: {error_msg}")
        console.print()
        info("Check your YAML file format and credentials")
        info("Generate a template with: devops admin aws-export-template")
        return

    if not skip_validation:
        success("Credentials validated successfully with AWS!")
        console.print()

    # Check if credentials already exist
    if credentials_exist():
        warning("Existing AWS credentials will be replaced")
        if not Confirm.ask("Continue?"):
            info("Cancelled")
            return
        console.print()

    # Save credentials (encrypted)
    if import_from_dict(credentials):
        success("AWS credentials imported and encrypted successfully!")
        console.print()

        # Show masked info
        console.print(f"[bold]Region:[/] {credentials['region']}")
        masked_key = (
            f"{credentials['access_key'][:4]}...{credentials['access_key'][-4:]}"
        )
        console.print(f"[bold]Access Key:[/] {masked_key}")
        console.print(f"[bold]Description:[/] {credentials.get('description', 'N/A')}")
        console.print()

        warning(f"SECURITY: Delete the input file '{file}' now!")
        console.print()
        info("Credentials are stored encrypted at:")
        info("  ~/.devops-cli/.aws_credentials.enc")
        console.print()
        info("Developers can now use:")
        info("  devops aws cloudwatch <log-group>")
        info("  devops app logs <app-name>")
    else:
        error("Failed to save credentials")


@app.command("aws-export-template")
def export_aws_template(
    output: str = typer.Option(
        "aws-credentials-template.yaml", "--output", "-o", help="Output file path"
    ),
):
    """Export a template YAML file for AWS credentials.

    This generates a template file with placeholder values that you can edit
    with your actual AWS credentials, then import with 'aws-import'.

    Example:
        devops admin aws-export-template
        devops admin aws-export-template --output my-aws-creds.yaml
    """
    header("Export AWS Credentials Template")

    output_path = Path(output)

    # Check if file exists
    if output_path.exists():
        warning(f"File already exists: {output}")
        if not Confirm.ask("Overwrite?"):
            info("Cancelled")
            return

    # Get template content
    template = get_aws_credentials_template()

    # Write template
    try:
        with open(output_path, "w") as f:
            f.write(template)

        success(f"Template exported to: {output}")
        console.print()
        info("Next steps:")
        info(f"  1. Edit '{output}' with your AWS credentials")
        info(f"  2. Run: devops admin aws-import --file {output}")
        info(f"  3. Delete '{output}' after successful import")
        console.print()
        warning("Never commit credential files to version control!")

    except IOError as e:
        error(f"Failed to write template: {e}")


# ==================== Config Validation ====================


@app.command("validate")
def validate_config(
    file: str = typer.Argument(..., help="YAML config file to validate"),
    config_type: Optional[str] = typer.Option(
        None, "--type", "-t", help="Config type (auto-detected if not specified)"
    ),
):
    """Validate a YAML configuration file before importing.

    Checks structure, required fields, and secret references.
    Helps ensure your config is correct before importing.

    Examples:
        devops admin validate apps.yaml
        devops admin validate servers.yaml --type servers
        devops admin validate aws-credentials.yaml
    """
    from devops_cli.config.validator import (
        validate_config_file,
        detect_config_type,
        ConfigType,
    )

    file_path = Path(file)

    if not file_path.exists():
        error(f"File not found: {file}")
        return

    # Detect config type
    if config_type:
        try:
            cfg_type = ConfigType(config_type.lower())
        except ValueError:
            error(f"Invalid config type: {config_type}")
            info(
                "Valid types: apps, servers, websites, teams, repos, aws_roles, aws_credentials, users"
            )
            return
    else:
        cfg_type = detect_config_type(file_path)
        if not cfg_type:
            error("Could not detect config type from filename or content")
            info("Please specify --type explicitly")
            info("Example: devops admin validate myfile.yaml --type apps")
            return

    header(f"Validating Configuration: {file}")
    info(f"Type: {cfg_type.value}\n")

    # Validate
    result = validate_config_file(file_path, cfg_type)

    # Display results
    console.print(result.get_summary())

    # Show import command if valid
    if result.valid:
        console.print()
        console.print("[green bold]✓ Configuration is ready to import![/]")
        console.print()
        info("To import this configuration, run:")

        if cfg_type == ConfigType.AWS_CREDENTIALS:
            info(f"  devops admin aws-import --file {file}")
        elif cfg_type == ConfigType.AWS_ROLES:
            info(f"  devops admin aws-roles-import --file {file}")
        elif cfg_type == ConfigType.USERS:
            info(f"  devops admin users-import --file {file}")
        else:
            info(f"  devops admin import --file {file}")

        # Security reminder for sensitive configs
        if cfg_type == ConfigType.AWS_CREDENTIALS:
            console.print()
            warning("Remember to delete this file after import for security!")
    else:
        console.print()
        console.print(
            "[red bold]✗ Configuration has errors - fix them before importing[/]"
        )
