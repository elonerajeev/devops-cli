"""Core admin commands: init, status, export/import, templates, validation."""

import os
import shutil
from pathlib import Path
from datetime import datetime
from typing import Optional

import typer
import yaml
from rich.prompt import Prompt, Confirm

from devops_cli.commands.admin.base import (
    console,
    auth,
    ADMIN_CONFIG_DIR,
    TEMPLATES_DIR,
    ensure_admin_dirs,
    load_apps_config,
    save_apps_config,
    load_servers_config,
    save_servers_config,
    load_aws_config,
    save_aws_config,
    load_teams_config,
    save_teams_config,
    load_websites_config,
    save_websites_config,
    success,
    error,
    warning,
    info,
    header,
    create_table,
)

app = typer.Typer()


# ==================== Initialize ====================


def admin_init():
    """Initialize admin configuration for a new organization."""
    header("DevOps CLI - Admin Setup")

    ensure_admin_dirs()

    org_name = Prompt.ask("Organization/Company name")
    aws_region = Prompt.ask("Default AWS region", default="us-east-1")

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
                "apps": ["*"],
                "servers": ["*"],
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


# ==================== Export/Import ====================


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

    if not include_secrets:
        if "roles" in config["aws"]:
            for role in config["aws"]["roles"].values():
                role.pop("credentials", None)

    with open(output, "w") as f:
        yaml.dump(config, f, default_flow_style=False)

    success(f"Configuration exported to {output}")

    if not include_secrets:
        info("Sensitive data was excluded. Use --include-secrets to include.")


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

    roles = aws_config.get("roles", {})
    if roles:
        console.print(f"[green]✓[/] AWS Roles: {len(roles)} configured")
        for name in roles:
            console.print(f"    - {name}")
    else:
        console.print("[yellow]![/] AWS Roles: None configured")

    apps = apps_config.get("apps", {})
    if apps:
        console.print(f"[green]✓[/] Applications: {len(apps)} configured")
        for name in apps:
            console.print(f"    - {name}")
    else:
        console.print("[yellow]![/] Applications: None configured")

    servers = servers_config.get("servers", {})
    if servers:
        console.print(f"[green]✓[/] Servers: {len(servers)} configured")
        for name in servers:
            console.print(f"    - {name}")
    else:
        console.print("[yellow]![/] Servers: None configured")

    websites = load_websites_config()
    if websites:
        console.print(f"[green]✓[/] Websites: {len(websites)} configured")
        for name in websites:
            console.print(f"    - {name}")
    else:
        console.print("[yellow]![/] Websites: None configured")

    teams = teams_config.get("teams", {})
    if teams:
        console.print(f"[green]✓[/] Teams: {len(teams)} configured")
        for name in teams:
            console.print(f"    - {name}")
    else:
        console.print("[yellow]![/] Teams: None configured")

    console.print()

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
    """Manage YAML configuration templates."""
    if not TEMPLATES_DIR.exists():
        error(f"Templates directory not found: {TEMPLATES_DIR}")
        return

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
            "meetings": ("Daily team meetings", "devops admin meeting set"),
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
        header("Copying All Templates")
        console.print()

        copied = 0
        for tf in template_files:
            name = tf.stem.replace("-template", "")
            dest_file = output_path / f"{name}.yaml"

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


# ==================== Config Validation ====================


def validate_config(
    file: str = typer.Argument(..., help="YAML config file to validate"),
    config_type: Optional[str] = typer.Option(
        None, "--type", "-t", help="Config type (auto-detected if not specified)"
    ),
):
    """Validate a YAML configuration file before importing."""
    from devops_cli.config.validator import (
        validate_config_file,
        detect_config_type,
        ConfigType,
    )

    file_path = Path(file)

    if not file_path.exists():
        error(f"File not found: {file}")
        return

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

    result = validate_config_file(file_path, cfg_type)

    console.print(result.get_summary())

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

        if cfg_type == ConfigType.AWS_CREDENTIALS:
            console.print()
            warning("Remember to delete this file after import for security!")
    else:
        console.print()
        console.print(
            "[red bold]✗ Configuration has errors - fix them before importing[/]"
        )
