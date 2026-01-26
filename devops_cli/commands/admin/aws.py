"""AWS role and credentials management commands for admin."""

import json
from pathlib import Path
from datetime import datetime
from typing import Optional

import typer
import yaml
from rich.prompt import Prompt, Confirm

from devops_cli.commands.admin.base import (
    console,
    ADMIN_CONFIG_DIR,
    SECRETS_DIR,
    load_aws_config,
    save_aws_config,
    get_aws_roles_template,
    validate_aws_roles_yaml,
    load_aws_roles_yaml,
    get_aws_credentials_template,
    import_aws_credentials_from_yaml,
    save_aws_credentials,
    load_aws_credentials,
    delete_aws_credentials,
    credentials_exist,
    get_credentials_info,
    validate_aws_credentials,
    import_from_dict,
    success,
    error,
    warning,
    info,
    header,
    create_table,
    handle_duplicate,
)

app = typer.Typer()


# ==================== AWS Role Management ====================


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

    # Check for duplicate
    exists = name in config.get("roles", {})
    action = handle_duplicate("AWS Role", name, exists)

    if action == "cancel":
        info("Cancelled")
        return
    elif action == "skip":
        info(f"Keeping existing AWS role '{name}'")
        return

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


def import_aws_roles(
    file: str = typer.Option(
        ..., "--file", "-f", help="Path to YAML file with AWS roles"
    ),
    merge: bool = typer.Option(
        True, "--merge/--replace", help="Merge with existing or replace all"
    ),
):
    """Import AWS roles from a YAML file."""
    header("Import AWS Roles from YAML")

    file_path = Path(file)

    if not file_path.exists():
        error(f"File not found: {file}")
        info(
            "Create a template with: devops admin aws-roles-export-template --output aws-roles.yaml"
        )
        return

    info(f"Loading roles from: {file}")
    console.print()

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

    for name, role in roles_to_import.items():
        console.print(f"  - {name}: {role.get('role_arn', 'N/A')[:50]}...")

    console.print()

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


def export_aws_roles_template(
    output: str = typer.Option(
        "aws-roles-template.yaml", "--output", "-o", help="Output file path"
    ),
):
    """Export a template YAML file for AWS roles."""
    header("Export AWS Roles Template")

    output_path = Path(output)

    if output_path.exists():
        warning(f"File already exists: {output}")
        if not Confirm.ask("Overwrite?"):
            info("Cancelled")
            return

    template = get_aws_roles_template()

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


def export_aws_roles(
    output: str = typer.Option(
        "aws-roles.yaml", "--output", "-o", help="Output file path"
    ),
):
    """Export current AWS roles to a YAML file."""
    header("Export AWS Roles")

    config = load_aws_config()
    roles = config.get("roles", {})

    if not roles:
        warning("No AWS roles configured")
        info("Add roles with: devops admin aws-add-role")
        return

    output_path = Path(output)

    if output_path.exists():
        warning(f"File already exists: {output}")
        if not Confirm.ask("Overwrite?"):
            info("Cancelled")
            return

    export_data = {"aws_roles": {}}

    for name, role in roles.items():
        export_data["aws_roles"][name] = {
            "role_arn": role.get("role_arn"),
            "region": role.get("region"),
            "external_id": role.get("external_id"),
            "description": role.get("description"),
        }

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


# ==================== AWS Credentials Management ====================


def configure_aws_credentials(
    access_key: Optional[str] = typer.Option(
        None, "--access-key", "-k", help="AWS Access Key ID"
    ),
    secret_key: Optional[str] = typer.Option(
        None, "--secret-key", "-s", help="AWS Secret Access Key"
    ),
    region: Optional[str] = typer.Option(None, "--region", "-r", help="AWS Region"),
    description: Optional[str] = typer.Option(
        None, "--desc", "-d", help="Description for these credentials"
    ),
    skip_validation: bool = typer.Option(
        False, "--skip-validation", help="Skip AWS API validation (for CI/CD)"
    ),
):
    """Configure AWS credentials for CloudWatch log access."""
    header("Configure AWS Credentials")

    if credentials_exist():
        warning("AWS credentials already configured")
        if not Confirm.ask("Replace existing credentials?"):
            info("Cancelled")
            return

    if not access_key:
        access_key = Prompt.ask("AWS Access Key ID")
    if not secret_key:
        secret_key = Prompt.ask("AWS Secret Access Key", password=True)
    if not region:
        region = Prompt.ask("Default AWS Region", default="us-east-1")

    if not skip_validation:
        info("Validating credentials...")
        is_valid, error_msg = validate_aws_credentials(access_key, secret_key, region)
        if not is_valid:
            error(f"Validation failed: {error_msg}")
            console.print()
            info("Use --skip-validation to skip this check (not recommended)")
            return
        success("Credentials validated!")

    if save_aws_credentials(access_key, secret_key, region, description):
        success("AWS credentials configured!")
        console.print()
        info("Credentials are stored encrypted at:")
        info("  ~/.devops-cli/.aws_credentials.enc")
        console.print()
        info("Developers can now use:")
        info("  devops aws cloudwatch <log-group>")
        info("  devops app logs <app-name>")
    else:
        error("Failed to save credentials")


def show_aws_credentials():
    """Show configured AWS credentials (masked)."""
    if not credentials_exist():
        warning("No AWS credentials configured")
        info("Configure with: devops admin aws-configure")
        return

    header("AWS Credentials")

    creds_info = get_credentials_info()
    if creds_info:
        console.print(f"[bold]Access Key:[/] {creds_info['access_key_masked']}")
        console.print(f"[bold]Region:[/] {creds_info['region']}")
        console.print(f"[bold]Description:[/] {creds_info['description']}")
        console.print()
        info("Credentials are stored encrypted at:")
        info("  ~/.devops-cli/.aws_credentials.enc")
    else:
        error("Failed to load credentials")


def test_aws_credentials():
    """Test AWS credentials and permissions."""
    if not credentials_exist():
        warning("No AWS credentials configured")
        info("Configure with: devops admin aws-configure")
        return

    header("Testing AWS Credentials")

    creds = load_aws_credentials()
    if not creds:
        error("Could not load credentials")
        return

    info("Testing connection to AWS...")
    console.print()

    is_valid, error_msg = validate_aws_credentials(
        creds["access_key"], creds["secret_key"], creds["region"]
    )

    if is_valid:
        success("AWS credentials are valid!")
        console.print()
        info("Developers can now access AWS logs")
    else:
        error(f"Validation failed: {error_msg}")
        console.print()
        info("Please reconfigure with: devops admin aws-configure")


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


def import_aws_credentials(
    file: str = typer.Option(
        ..., "--file", "-f", help="Path to YAML file with AWS credentials"
    ),
    skip_validation: bool = typer.Option(
        False, "--skip-validation", help="Skip AWS API validation (for CI/CD)"
    ),
):
    """Import AWS credentials from a YAML file."""
    header("Import AWS Credentials from YAML")

    file_path = Path(file)

    if not file_path.exists():
        error(f"File not found: {file}")
        info(
            "Create a template with: devops admin aws-export-template --output aws-credentials.yaml"
        )
        return

    if credentials_exist():
        warning("AWS credentials already configured")
        if not Confirm.ask("Replace existing credentials?"):
            info("Cancelled")
            return

    info(f"Loading credentials from: {file}")
    console.print()

    creds, err = import_aws_credentials_from_yaml(file_path)

    if err:
        error(f"Failed to load credentials: {err}")
        return

    console.print(f"  Access Key: {creds['access_key'][:4]}****")
    console.print(f"  Region: {creds['region']}")
    console.print(f"  Description: {creds.get('description', 'N/A')}")
    console.print()

    if not skip_validation:
        info("Validating credentials...")
        is_valid, error_msg = validate_aws_credentials(
            creds["access_key"], creds["secret_key"], creds["region"]
        )
        if not is_valid:
            error(f"Validation failed: {error_msg}")
            console.print()
            info("Use --skip-validation to skip this check (not recommended)")
            return
        success("Credentials validated!")

    if import_from_dict(creds):
        success("AWS credentials imported!")
        console.print()
        info("Credentials are stored encrypted at:")
        info("  ~/.devops-cli/.aws_credentials.enc")
        console.print()
        info("Developers can now use:")
        info("  devops aws cloudwatch <log-group>")
        info("  devops app logs <app-name>")
    else:
        error("Failed to save credentials")


def export_aws_template(
    output: str = typer.Option(
        "aws-credentials-template.yaml", "--output", "-o", help="Output file path"
    ),
):
    """Export a template YAML file for AWS credentials."""
    header("Export AWS Credentials Template")

    output_path = Path(output)

    if output_path.exists():
        warning(f"File already exists: {output}")
        if not Confirm.ask("Overwrite?"):
            info("Cancelled")
            return

    template = get_aws_credentials_template()

    try:
        with open(output_path, "w") as f:
            f.write(template)

        success(f"Template exported to: {output}")
        console.print()
        warning("SECURITY: Never commit this file to version control!")
        console.print()
        info("Next steps:")
        info(f"  1. Edit '{output}' with your AWS credentials")
        info(f"  2. Run: devops admin aws-import --file {output}")
        info(f"  3. Delete '{output}' after importing")
        console.print()

    except IOError as e:
        error(f"Failed to write template: {e}")
