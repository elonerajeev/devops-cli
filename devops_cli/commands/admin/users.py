"""User management commands for admin."""

from pathlib import Path
from datetime import datetime
from typing import Optional

import typer
import yaml
from rich.prompt import Confirm

from devops_cli.commands.admin.base import (
    console,
    auth,
    load_users_yaml,
    validate_users_yaml,
    get_users_template,
    success,
    error,
    warning,
    info,
    header,
    create_table,
)

app = typer.Typer()


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
    """Register a new user and generate access token."""
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


def deactivate_user(
    email: str = typer.Argument(..., help="User email to deactivate"),
):
    """Deactivate a user (prevents login but keeps record)."""
    if auth.deactivate_user(email):
        success(f"User '{email}' deactivated")
        info("User cannot login until reactivated")
    else:
        error(f"User '{email}' not found")


def activate_user(
    email: str = typer.Argument(..., help="User email to activate"),
):
    """Reactivate a deactivated user."""
    if auth.activate_user(email):
        success(f"User '{email}' activated")
    else:
        error(f"User '{email}' not found")


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


def import_users(
    file: str = typer.Option(..., "--file", "-f", help="Path to YAML file with users"),
    skip_existing: bool = typer.Option(
        True, "--skip-existing/--fail-existing", help="Skip users that already exist"
    ),
):
    """Import users from a YAML file (bulk registration)."""
    header("Import Users from YAML")

    file_path = Path(file)

    if not file_path.exists():
        error(f"File not found: {file}")
        info(
            "Create a template with: devops admin users-export-template --output users.yaml"
        )
        return

    info(f"Loading users from: {file}")
    console.print()

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


def export_users_template(
    output: str = typer.Option(
        "users-template.yaml", "--output", "-o", help="Output file path"
    ),
):
    """Export a template YAML file for bulk user registration."""
    header("Export Users Template")

    output_path = Path(output)

    if output_path.exists():
        warning(f"File already exists: {output}")
        if not Confirm.ask("Overwrite?"):
            info("Cancelled")
            return

    template = get_users_template()

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


def export_users(
    output: str = typer.Option("users.yaml", "--output", "-o", help="Output file path"),
):
    """Export current users to a YAML file (without tokens)."""
    header("Export Users")

    users = auth.list_users()

    if not users:
        warning("No users registered")
        info("Add users with: devops admin user-add")
        return

    output_path = Path(output)

    if output_path.exists():
        warning(f"File already exists: {output}")
        if not Confirm.ask("Overwrite?"):
            info("Cancelled")
            return

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
