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
import base64
import hashlib
from pathlib import Path
from datetime import datetime
from typing import Optional, List

import typer
import yaml
from rich.console import Console
from rich.prompt import Prompt, Confirm
from rich.table import Table
from rich.panel import Panel
from rich import box

from devops_cli.config.settings import load_config, save_config, get_config_path
from devops_cli.config.repos import (
    load_repos, save_repos, get_repo_config, add_repo, remove_repo,
    fetch_repo_from_github, discover_org_repos, discover_user_repos,
    validate_github_token, validate_repo_name
)
from devops_cli.config.aws_credentials import (
    save_aws_credentials, load_aws_credentials, delete_aws_credentials,
    credentials_exist, get_credentials_info, validate_aws_credentials
)
from devops_cli.config.websites import (
    load_websites_config, save_websites_config, get_website_config,
    add_website as add_website_to_config, remove_website as remove_website_from_config
)
from devops_cli.utils.output import (
    success, error, warning, info, header,
    create_table, status_badge, console as out_console
)
from devops_cli.auth import AuthManager

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
        console.print(Panel(
            "[yellow]CLI not initialized yet.[/yellow]\n\n"
            "Run [cyan]devops admin init[/cyan] first to set up the CLI.",
            title="[bold]Setup Required[/bold]",
            border_style="yellow",
            box=box.ROUNDED
        ))
        raise typer.Exit(0)

    # Check if any users exist (if not, allow first admin setup)
    users = auth.list_users()

    if not users:
        # No users yet - this is first-time setup, allow user-add only
        if command_name == "user-add":
            return
        console.print()
        console.print(Panel(
            "[yellow]No admin users registered yet.[/yellow]\n\n"
            "Create the first admin user:\n"
            "  [cyan]devops admin user-add --email admin@company.com --role admin[/cyan]",
            title="[bold]First Admin Setup[/bold]",
            border_style="yellow",
            box=box.ROUNDED
        ))
        raise typer.Exit(0)

    # Check if current user is authenticated
    session = auth.get_current_session()
    if not session:
        console.print()
        console.print(Panel(
            "[red]Authentication required.[/red]\n\n"
            "Admin commands require you to be logged in.\n\n"
            "Run: [cyan]devops auth login[/cyan]",
            title="[bold]🔐 Login Required[/bold]",
            border_style="red",
            box=box.ROUNDED
        ))
        raise typer.Exit(1)

    # Check if user has admin role
    if session.get("role") != "admin":
        console.print()
        console.print(Panel(
            f"[red]Access denied.[/red]\n\n"
            f"You are logged in as: [cyan]{session.get('email')}[/cyan] (role: {session.get('role')})\n\n"
            "Admin commands require [bold]admin[/bold] role.\n"
            "Contact your administrator for access.",
            title="[bold]🚫 Admin Access Required[/bold]",
            border_style="red",
            box=box.ROUNDED
        ))
        raise typer.Exit(1)


@app.callback()
def admin_callback(ctx: typer.Context):
    """Verify admin access before running admin commands."""
    check_admin_access(ctx)


# Admin config paths
ADMIN_CONFIG_DIR = Path.home() / ".devops-cli"
APPS_CONFIG_FILE = ADMIN_CONFIG_DIR / "apps.yaml"
SERVERS_CONFIG_FILE = ADMIN_CONFIG_DIR / "servers.yaml"
WEBSITES_CONFIG_FILE = ADMIN_CONFIG_DIR / "websites.yaml"
AWS_CONFIG_FILE = ADMIN_CONFIG_DIR / "aws.yaml"
TEAMS_CONFIG_FILE = ADMIN_CONFIG_DIR / "teams.yaml"
SECRETS_DIR = ADMIN_CONFIG_DIR / "secrets"


def ensure_admin_dirs():
    """Ensure admin config directories exist."""
    ADMIN_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    SECRETS_DIR.mkdir(parents=True, exist_ok=True)


def load_apps_config() -> dict:
    """Load applications configuration."""
    if APPS_CONFIG_FILE.exists():
        with open(APPS_CONFIG_FILE) as f:
            return yaml.safe_load(f) or {"apps": {}}
    return {"apps": {}}


def save_apps_config(config: dict):
    """Save applications configuration."""
    ensure_admin_dirs()
    with open(APPS_CONFIG_FILE, "w") as f:
        yaml.dump(config, f, default_flow_style=False)


def load_servers_config() -> dict:
    """Load servers configuration."""
    if SERVERS_CONFIG_FILE.exists():
        with open(SERVERS_CONFIG_FILE) as f:
            return yaml.safe_load(f) or {"servers": {}}
    return {"servers": {}}


def save_servers_config(config: dict):
    """Save servers configuration."""
    ensure_admin_dirs()
    with open(SERVERS_CONFIG_FILE, "w") as f:
        yaml.dump(config, f, default_flow_style=False)


def load_aws_config() -> dict:
    """Load AWS configuration."""
    if AWS_CONFIG_FILE.exists():
        with open(AWS_CONFIG_FILE) as f:
            return yaml.safe_load(f) or {}
    return {}


def save_aws_config(config: dict):
    """Save AWS configuration."""
    ensure_admin_dirs()
    with open(AWS_CONFIG_FILE, "w") as f:
        yaml.dump(config, f, default_flow_style=False)


def load_teams_config() -> dict:
    """Load teams configuration."""
    if TEAMS_CONFIG_FILE.exists():
        with open(TEAMS_CONFIG_FILE) as f:
            return yaml.safe_load(f) or {"teams": {}}
    return {"teams": {}}


def save_teams_config(config: dict):
    """Save teams configuration."""
    ensure_admin_dirs()
    with open(TEAMS_CONFIG_FILE, "w") as f:
        yaml.dump(config, f, default_flow_style=False)


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
    name: str = typer.Option(..., "--name", "-n", prompt="Role name (e.g., dev-readonly)", help="Role name"),
    role_arn: str = typer.Option(..., "--arn", "-a", prompt="IAM Role ARN", help="IAM Role ARN to assume"),
    region: Optional[str] = typer.Option(None, "--region", "-r", help="AWS region"),
    external_id: Optional[str] = typer.Option(None, "--external-id", help="External ID for role assumption"),
    description: Optional[str] = typer.Option(None, "--desc", "-d", help="Role description"),
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
        [("Name", "cyan"), ("Region", ""), ("Role ARN", "dim"), ("Description", "dim")]
    )

    for name, role in roles.items():
        table.add_row(
            name,
            role.get("region", "-"),
            role.get("role_arn", "-")[:50] + "...",
            role.get("description", "-")[:30]
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


@app.command("aws-set-credentials")
def set_aws_credentials(
    role_name: str = typer.Argument(..., help="Role name to set credentials for"),
    access_key: Optional[str] = typer.Option(None, "--access-key", "-k", help="AWS Access Key ID"),
    secret_key: Optional[str] = typer.Option(None, "--secret-key", "-s", help="AWS Secret Access Key"),
):
    """Set AWS credentials for a role (for cross-account access)."""
    config = load_aws_config()

    if role_name not in config.get("roles", {}):
        error(f"Role '{name}' not found. Add it first with: devops admin aws-add-role")
        return

    if not access_key:
        access_key = Prompt.ask("AWS Access Key ID")
    if not secret_key:
        secret_key = Prompt.ask("AWS Secret Access Key", password=True)

    # Store credentials securely
    creds_file = SECRETS_DIR / f"aws_{role_name}.creds"

    # Simple encryption (in production, use proper encryption)
    creds_data = json.dumps({
        "access_key": access_key,
        "secret_key": secret_key,
        "updated_at": datetime.now().isoformat(),
    })

    # Encode
    encoded = base64.b64encode(creds_data.encode()).decode()
    creds_file.write_text(encoded)
    creds_file.chmod(0o600)

    success(f"Credentials saved for role '{role_name}'")
    warning("Credentials are stored locally. For production, use IAM roles or AWS SSO.")


# ==================== Application Management ====================

@app.command("app-add")
def add_app():
    """Add a new application (interactive)."""
    header("Add New Application")

    # Basic info
    app_name = Prompt.ask("Application name (e.g., api, backend, worker)")
    app_type = Prompt.ask(
        "Application type",
        choices=["ecs", "lambda", "kubernetes", "docker", "custom"],
        default="ecs"
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
    if app_type == "ecs":
        app_config["ecs"] = {
            "cluster": Prompt.ask("ECS Cluster name"),
            "service": Prompt.ask("ECS Service name", default=app_name),
            "region": Prompt.ask("AWS Region", default="us-east-1"),
        }
        app_config["logs"] = {
            "type": "cloudwatch",
            "log_group": Prompt.ask("CloudWatch Log Group", default=f"/ecs/{app_name}"),
        }

    elif app_type == "lambda":
        app_config["lambda"] = {
            "function_name": Prompt.ask("Lambda Function name", default=app_name),
            "region": Prompt.ask("AWS Region", default="us-east-1"),
        }
        app_config["logs"] = {
            "type": "cloudwatch",
            "log_group": Prompt.ask("CloudWatch Log Group", default=f"/aws/lambda/{app_name}"),
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
        log_type = "cloudwatch" # Restricted to cloudwatch as requested
        app_config["logs"] = {"type": log_type}
        app_config["logs"]["log_group"] = Prompt.ask("CloudWatch Log Group")
        app_config["logs"]["region"] = Prompt.ask("AWS Region", default="us-east-1")

    # Health check
    if Confirm.ask("Configure health check?", default=True):
        health_type = Prompt.ask(
            "Health check type",
            choices=["http", "tcp", "command", "none"],
            default="http"
        )

        if health_type == "http":
            app_config["health"] = {
                "type": "http",
                "url": Prompt.ask("Health check URL"),
                "expected_status": int(Prompt.ask("Expected status code", default="200")),
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
            default=roles[0] if roles else "none"
        )
        if app_config["aws_role"] == "none":
            del app_config["aws_role"]

    # Team access
    teams_config = load_teams_config()
    teams = list(teams_config.get("teams", {}).keys())
    if teams:
        selected_teams = Prompt.ask(
            "Teams with access (comma-separated)",
            default="default"
        )
        app_config["teams"] = [t.strip() for t in selected_teams.split(",")]

    # Save
    config["apps"][app_name] = app_config
    save_apps_config(config)

    success(f"Application '{app_name}' added!")
    info(f"\nDevelopers can now use:")
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
        "",
        [("Name", "cyan"), ("Type", ""), ("Log Source", "dim"), ("Teams", "dim")]
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
            "Teams with access (comma-separated)",
            default="default"
        )
        website_data["teams"] = [t.strip() for t in selected_teams.split(",")]

    add_website_to_config(name, url, **website_data)

    success(f"Website '{name}' added!")
    info(f"\nDevelopers can now use:")
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
        [("Name", "cyan"), ("URL", ""), ("Expected Status", "dim"), ("Method", "dim"), ("Teams", "dim")]
    )

    for name, website in websites.items():
        teams = ", ".join(website.get("teams", ["default"]))
        table.add_row(
            name,
            website.get("url", "-"),
            str(website.get("expected_status", "N/A")),
            website.get("method", "GET"),
            teams[:20]
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
            "Teams with access (comma-separated)",
            default="default"
        )
        config["servers"][name]["teams"] = [t.strip() for t in selected_teams.split(",")]

    save_servers_config(config)

    success(f"Server '{name}' added!")
    info(f"\nDevelopers can now use:")
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
        "",
        [("Name", "cyan"), ("Host", ""), ("User", "dim"), ("Tags", "yellow")]
    )

    for name, server in servers.items():
        table.add_row(
            name,
            server.get("host", "-"),
            server.get("user", "-"),
            ", ".join(server.get("tags", []))
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


# ==================== Team Management ====================

@app.command("team-add")
def add_team(
    name: str = typer.Option(..., "--name", "-n", prompt="Team name", help="Team name"),
    description: Optional[str] = typer.Option(None, "--desc", "-d", help="Team description"),
):
    """Add a new team."""
    config = load_teams_config()

    apps_access = Prompt.ask(
        "Apps access (comma-separated names, or * for all)",
        default="*"
    )
    servers_access = Prompt.ask(
        "Servers access (comma-separated names/tags, or * for all)",
        default="*"
    )

    apps_list = [a.strip() for a in apps_access.split(",")] if apps_access != "*" else ["*"]
    servers_list = [s.strip() for s in servers_access.split(",")] if servers_access != "*" else ["*"]

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
        "",
        [("Name", "cyan"), ("Apps Access", ""), ("Servers Access", "dim")]
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


# ==================== Export/Import ====================

@app.command("export")
def export_config(
    output: str = typer.Option("devops-config.yaml", "--output", "-o", help="Output file"),
    include_secrets: bool = typer.Option(False, "--include-secrets", help="Include sensitive data"),
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
    merge: bool = typer.Option(True, "--merge/--replace", help="Merge with existing or replace"),
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
    websites_config = load_websites_config()
    websites = websites_config.get("websites", {})
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
                status = "[green]active[/]" if u.get("active", True) else "[red]inactive[/]"
                console.print(f"    - {u['email']} ({status})")
        else:
            console.print("[yellow]![/] Users: None registered")
    except Exception:
        console.print("[yellow]![/] Users: Auth not initialized")

    console.print()
    info("Config directory: " + str(ADMIN_CONFIG_DIR))


# ==================== User Management ====================

@app.command("user-add")
def add_user(
    email: str = typer.Option(..., "--email", "-e", prompt="User email", help="User's email address"),
    name: Optional[str] = typer.Option(None, "--name", "-n", help="User's display name"),
    role: str = typer.Option("developer", "--role", "-r", help="Role: developer or admin"),
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
        console.print("[bold yellow]ACCESS TOKEN (share this securely with the user):[/]")
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
        [("Email", "cyan"), ("Name", ""), ("Role", ""), ("Team", ""), ("Status", ""), ("Last Login", "dim")]
    )

    for user in users:
        status_str = "[green]Active[/]" if user.get("active", True) else "[red]Inactive[/]"
        last_login = user.get("last_login", "-")
        if last_login and last_login != "-":
            from datetime import datetime
            try:
                dt = datetime.fromisoformat(last_login)
                last_login = dt.strftime("%Y-%m-%d %H:%M")
            except:
                pass

        table.add_row(
            user["email"],
            user.get("name", "-"),
            user.get("role", "developer"),
            user.get("team", "default"),
            status_str,
            last_login or "-"
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
    if not Confirm.ask(f"Generate new token for '{email}'? (old token will stop working)"):
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


@app.command("audit-logs")
def view_audit_logs(
    limit: int = typer.Option(50, "--limit", "-l", help="Number of log entries to show"),
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
        help="Discover from org or user repos"
    ),
    name: str = typer.Option(
        ...,
        "--name",
        "-n",
        prompt="Organization or username",
        help="GitHub organization or username"
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
        warning(f"No repositories found or access denied")
        info("Make sure your GitHub token has 'repo' scope")
        return

    success(f"Found {len(repos)} repositories!")
    console.print()

    # Show repos in a table
    table = create_table(
        "Discovered Repositories",
        [("Name", "cyan"), ("Owner", ""), ("Visibility", "yellow"), ("Language", "dim")]
    )

    for repo in repos[:20]:  # Show first 20
        visibility = "[red]private[/]" if repo["private"] else "[green]public[/]"
        table.add_row(
            repo["name"],
            repo["owner"],
            visibility,
            repo.get("language", "Unknown")
        )

    console.print(table)

    if len(repos) > 20:
        console.print(f"\n... and {len(repos) - 20} more")

    console.print()

    # Ask which repos to add
    add_all = Confirm.ask("Add all discovered repositories to configuration?", default=False)

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
    name: str = typer.Option(None, "--name", "-n", help="Friendly name for the repo (e.g., backend)"),
    owner: str = typer.Option(None, "--owner", "-o", help="GitHub owner/org"),
    repo: str = typer.Option(None, "--repo", "-r", help="Repository name"),
    auto_fetch: bool = typer.Option(True, "--auto-fetch/--no-fetch", help="Auto-fetch details from GitHub"),
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
        warning("GitHub token not configured. Will add repo without auto-fetching details.")
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
            repo_config.update({
                "description": github_data.get("description", "No description"),
                "default_branch": github_data.get("default_branch", "main"),
                "visibility": github_data.get("visibility", "private"),
                "private": github_data.get("private", True),
                "language": github_data.get("language"),
                "url": github_data.get("url"),
                "created_at": github_data.get("created_at"),
                "auto_fetched": True,
            })
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
            repo_config["description"] = Prompt.ask("Description (optional)", default="")
        else:
            # Repository not found
            error("Could not fetch repo details from GitHub")
            info("Repository might not exist or token lacks access")
            if not Confirm.ask("Add repository anyway (without GitHub data)?"):
                info("Cancelled")
                return
            # Add minimal config
            repo_config["default_branch"] = Prompt.ask("Default branch", default="main")
            repo_config["description"] = Prompt.ask("Description (optional)", default="")
    else:
        # Manual entry
        repo_config["default_branch"] = Prompt.ask("Default branch", default="main")
        repo_config["description"] = Prompt.ask("Description (optional)", default="")

    # Save
    add_repo(name, owner, repo, **{k: v for k, v in repo_config.items() if k not in ["owner", "repo"]})

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
        [("Name", "cyan"), ("Owner/Repo", ""), ("Branch", "dim"), ("Language", "dim"), ("Visibility", "yellow")]
    )

    for name, repo in repos.items():
        owner_repo = f"{repo['owner']}/{repo['repo']}"
        branch = repo.get("default_branch", "main")
        language = repo.get("language", "Unknown")
        visibility = repo.get("visibility", "unknown")

        vis_color = "[red]private[/]" if repo.get("private", True) else "[green]public[/]"

        table.add_row(
            name,
            owner_repo[:40],
            branch,
            language,
            vis_color
        )

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
    repos[name].update({
        "description": github_data.get("description", "No description"),
        "default_branch": github_data.get("default_branch", "main"),
        "visibility": github_data.get("visibility", "private"),
        "private": github_data.get("private", True),
        "language": github_data.get("language"),
        "url": github_data.get("url"),
        "created_at": github_data.get("created_at"),
        "last_refreshed": datetime.now().isoformat(),
    })

    save_repos(repos)

    success(f"Repository '{name}' refreshed from GitHub!")
    console.print()
    console.print(f"  Description: {github_data['description']}")
    console.print(f"  Default Branch: {github_data['default_branch']}")
    console.print(f"  Language: {github_data.get('language', 'Unknown')}")
    console.print(f"  Visibility: {github_data['visibility']}")


# ==================== AWS Credentials Management ====================

@app.command("aws-configure")
def configure_aws_credentials(
    access_key: Optional[str] = typer.Option(None, "--access-key", "-k", help="AWS Access Key ID"),
    secret_key: Optional[str] = typer.Option(None, "--secret-key", "-s", help="AWS Secret Access Key"),
    region: Optional[str] = typer.Option(None, "--region", "-r", help="AWS Region"),
):
    """Configure AWS credentials for CloudWatch log access.

    These credentials will be stored securely (encrypted) and used for all AWS operations.
    They should have READ-ONLY CloudWatch Logs permissions.

    Required IAM Permissions:
    - logs:DescribeLogGroups
    - logs:FilterLogEvents
    - logs:GetLogEvents
    - ec2:DescribeInstances (optional, for EC2 info)
    """
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
        "Description (optional)",
        default="DevOps CLI CloudWatch Access"
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
    info(f"Testing with Access Key: {creds['access_key'][:4]}...{creds['access_key'][-4:]}")
    console.print()

    is_valid, error_msg = validate_aws_credentials(
        creds['access_key'],
        creds['secret_key'],
        creds['region']
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
