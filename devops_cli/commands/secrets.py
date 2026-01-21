"""Secrets management commands."""

import os
import json
import base64
import hashlib
import getpass
from typing import Optional
from pathlib import Path
from datetime import datetime

import typer
from rich.console import Console
from rich.prompt import Prompt, Confirm
from rich.table import Table

from devops_cli.config.settings import load_config
from devops_cli.utils.output import (
    success, error, warning, info, header,
    create_table, console as out_console
)

app = typer.Typer(help="Secrets and environment variable management")
console = Console()

# Default paths
SECRETS_DIR = Path.home() / ".devops-cli" / "secrets"
ENV_FILE = ".env"


def get_encryption_key(password: str) -> bytes:
    """Derive encryption key from password."""
    return hashlib.pbkdf2_hmac(
        'sha256',
        password.encode(),
        b'devops-cli-salt',  # In production, use random salt stored with data
        100000,
        dklen=32
    )


def simple_encrypt(data: str, password: str) -> str:
    """Simple XOR encryption (for demo - use cryptography lib in production)."""
    key = get_encryption_key(password)
    encrypted = bytes([ord(c) ^ key[i % len(key)] for i, c in enumerate(data)])
    return base64.b64encode(encrypted).decode()


def simple_decrypt(encrypted_data: str, password: str) -> str:
    """Simple XOR decryption."""
    key = get_encryption_key(password)
    data = base64.b64decode(encrypted_data)
    decrypted = ''.join([chr(b ^ key[i % len(key)]) for i, b in enumerate(data)])
    return decrypted


def load_env_file(path: Path) -> dict:
    """Load environment variables from a file."""
    env_vars = {}
    if path.exists():
        with open(path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, _, value = line.partition('=')
                    # Remove quotes if present
                    value = value.strip().strip('"').strip("'")
                    env_vars[key.strip()] = value
    return env_vars


def save_env_file(path: Path, env_vars: dict, comments: list = None):
    """Save environment variables to a file."""
    with open(path, 'w') as f:
        if comments:
            for comment in comments:
                f.write(f"# {comment}\n")
            f.write("\n")

        for key, value in sorted(env_vars.items()):
            # Quote values with spaces
            if ' ' in value or '"' in value:
                value = f'"{value}"'
            f.write(f"{key}={value}\n")


@app.command("init")
def init_secrets():
    """Initialize secrets management."""
    SECRETS_DIR.mkdir(parents=True, exist_ok=True)

    # Create .env.example if .env exists
    env_path = Path(ENV_FILE)
    if env_path.exists():
        env_vars = load_env_file(env_path)
        example_path = Path(".env.example")

        with open(example_path, 'w') as f:
            f.write("# Environment Variables\n")
            f.write("# Copy this file to .env and fill in the values\n\n")
            for key in sorted(env_vars.keys()):
                f.write(f"{key}=\n")

        success(f"Created {example_path} from {env_path}")

    success("Secrets management initialized")
    info(f"Secrets directory: {SECRETS_DIR}")


@app.command("set")
def set_secret(
    key: str = typer.Argument(..., help="Secret key name"),
    value: Optional[str] = typer.Option(None, "--value", "-v", help="Secret value (will prompt if not provided)"),
    env: str = typer.Option("default", "--env", "-e", help="Environment (dev, staging, prod)"),
    file: Optional[str] = typer.Option(None, "--file", "-f", help="Add to specific .env file"),
):
    """Set a secret value."""
    if value is None:
        value = Prompt.ask(f"Enter value for {key}", password=True)

    if file:
        # Add to specific .env file
        env_path = Path(file)
        env_vars = load_env_file(env_path) if env_path.exists() else {}
        env_vars[key] = value
        save_env_file(env_path, env_vars)
        success(f"Set {key} in {file}")
    else:
        # Store in encrypted secrets store
        secrets_file = SECRETS_DIR / f"{env}.secrets"
        secrets = {}

        if secrets_file.exists():
            password = Prompt.ask("Enter secrets password", password=True)
            try:
                encrypted = secrets_file.read_text()
                decrypted = simple_decrypt(encrypted, password)
                secrets = json.loads(decrypted)
            except Exception:
                error("Failed to decrypt secrets. Wrong password?")
                return
        else:
            password = Prompt.ask("Create new secrets password", password=True)
            confirm = Prompt.ask("Confirm password", password=True)
            if password != confirm:
                error("Passwords don't match")
                return

        secrets[key] = {
            "value": value,
            "updated": datetime.now().isoformat(),
        }

        encrypted = simple_encrypt(json.dumps(secrets), password)
        SECRETS_DIR.mkdir(parents=True, exist_ok=True)
        secrets_file.write_text(encrypted)

        success(f"Secret '{key}' saved to {env} environment")


@app.command("get")
def get_secret(
    key: str = typer.Argument(..., help="Secret key name"),
    env: str = typer.Option("default", "--env", "-e", help="Environment"),
    show: bool = typer.Option(False, "--show", "-s", help="Show value (default: masked)"),
):
    """Get a secret value."""
    secrets_file = SECRETS_DIR / f"{env}.secrets"

    if not secrets_file.exists():
        error(f"No secrets found for environment '{env}'")
        return

    password = Prompt.ask("Enter secrets password", password=True)

    try:
        encrypted = secrets_file.read_text()
        decrypted = simple_decrypt(encrypted, password)
        secrets = json.loads(decrypted)
    except Exception:
        error("Failed to decrypt secrets")
        return

    if key not in secrets:
        error(f"Secret '{key}' not found")
        return

    secret = secrets[key]
    value = secret["value"]

    if show:
        console.print(f"{key}={value}")
    else:
        masked = value[:2] + "*" * (len(value) - 4) + value[-2:] if len(value) > 4 else "****"
        console.print(f"{key}={masked}")
        info("Use --show to reveal the full value")


@app.command("list")
def list_secrets(
    env: str = typer.Option("default", "--env", "-e", help="Environment"),
    file: Optional[str] = typer.Option(None, "--file", "-f", help="List from .env file"),
):
    """List all secrets (keys only, not values)."""
    if file:
        # List from .env file
        env_path = Path(file)
        if not env_path.exists():
            error(f"File not found: {file}")
            return

        env_vars = load_env_file(env_path)
        header(f"Environment Variables: {file}")

        table = create_table("", [("Key", "cyan"), ("Value", "dim")])

        for key, value in sorted(env_vars.items()):
            masked = value[:3] + "***" if len(value) > 3 else "***"
            table.add_row(key, masked)

        console.print(table)
        info(f"Total: {len(env_vars)} variables")
    else:
        # List from encrypted store
        secrets_file = SECRETS_DIR / f"{env}.secrets"

        if not secrets_file.exists():
            warning(f"No secrets found for environment '{env}'")
            return

        password = Prompt.ask("Enter secrets password", password=True)

        try:
            encrypted = secrets_file.read_text()
            decrypted = simple_decrypt(encrypted, password)
            secrets = json.loads(decrypted)
        except Exception:
            error("Failed to decrypt secrets")
            return

        header(f"Secrets: {env}")

        table = create_table("", [("Key", "cyan"), ("Updated", "dim")])

        for key, data in sorted(secrets.items()):
            updated = data.get("updated", "unknown")[:19]
            table.add_row(key, updated)

        console.print(table)
        info(f"Total: {len(secrets)} secrets")


@app.command("delete")
def delete_secret(
    key: str = typer.Argument(..., help="Secret key to delete"),
    env: str = typer.Option("default", "--env", "-e", help="Environment"),
):
    """Delete a secret."""
    secrets_file = SECRETS_DIR / f"{env}.secrets"

    if not secrets_file.exists():
        error(f"No secrets found for environment '{env}'")
        return

    password = Prompt.ask("Enter secrets password", password=True)

    try:
        encrypted = secrets_file.read_text()
        decrypted = simple_decrypt(encrypted, password)
        secrets = json.loads(decrypted)
    except Exception:
        error("Failed to decrypt secrets")
        return

    if key not in secrets:
        error(f"Secret '{key}' not found")
        return

    if not Confirm.ask(f"Delete secret '{key}'?"):
        info("Cancelled")
        return

    del secrets[key]

    encrypted = simple_encrypt(json.dumps(secrets), password)
    secrets_file.write_text(encrypted)

    success(f"Secret '{key}' deleted")


@app.command("export")
def export_secrets(
    output: str = typer.Option(".env", "--output", "-o", help="Output file"),
    env: str = typer.Option("default", "--env", "-e", help="Environment"),
    append: bool = typer.Option(False, "--append", "-a", help="Append to existing file"),
):
    """Export secrets to .env file."""
    secrets_file = SECRETS_DIR / f"{env}.secrets"

    if not secrets_file.exists():
        error(f"No secrets found for environment '{env}'")
        return

    password = Prompt.ask("Enter secrets password", password=True)

    try:
        encrypted = secrets_file.read_text()
        decrypted = simple_decrypt(encrypted, password)
        secrets = json.loads(decrypted)
    except Exception:
        error("Failed to decrypt secrets")
        return

    output_path = Path(output)

    if append and output_path.exists():
        existing = load_env_file(output_path)
        for key, data in secrets.items():
            existing[key] = data["value"]
        env_vars = existing
    else:
        env_vars = {key: data["value"] for key, data in secrets.items()}

    save_env_file(output_path, env_vars, [
        f"Generated by devops-cli on {datetime.now().isoformat()}",
        f"Environment: {env}",
    ])

    success(f"Exported {len(secrets)} secrets to {output}")
    warning("Remember: Never commit .env files to git!")


@app.command("import")
def import_secrets(
    file: str = typer.Argument(".env", help="File to import from"),
    env: str = typer.Option("default", "--env", "-e", help="Environment to import to"),
):
    """Import secrets from .env file."""
    file_path = Path(file)

    if not file_path.exists():
        error(f"File not found: {file}")
        return

    env_vars = load_env_file(file_path)

    if not env_vars:
        warning("No variables found in file")
        return

    secrets_file = SECRETS_DIR / f"{env}.secrets"

    if secrets_file.exists():
        password = Prompt.ask("Enter secrets password", password=True)
        try:
            encrypted = secrets_file.read_text()
            decrypted = simple_decrypt(encrypted, password)
            secrets = json.loads(decrypted)
        except Exception:
            error("Failed to decrypt existing secrets")
            return
    else:
        password = Prompt.ask("Create new secrets password", password=True)
        confirm = Prompt.ask("Confirm password", password=True)
        if password != confirm:
            error("Passwords don't match")
            return
        secrets = {}

    # Import variables
    now = datetime.now().isoformat()
    for key, value in env_vars.items():
        secrets[key] = {"value": value, "updated": now}

    encrypted = simple_encrypt(json.dumps(secrets), password)
    SECRETS_DIR.mkdir(parents=True, exist_ok=True)
    secrets_file.write_text(encrypted)

    success(f"Imported {len(env_vars)} secrets to {env} environment")


@app.command("env")
def manage_env(
    action: str = typer.Argument(..., help="Action: show, edit, validate"),
    file: str = typer.Option(".env", "--file", "-f", help="Env file path"),
):
    """Manage .env files."""
    file_path = Path(file)

    if action == "show":
        if not file_path.exists():
            error(f"File not found: {file}")
            return

        env_vars = load_env_file(file_path)
        header(f"Environment: {file}")

        for key, value in sorted(env_vars.items()):
            # Mask sensitive values
            if any(s in key.lower() for s in ['password', 'secret', 'token', 'key', 'api']):
                masked = value[:2] + "*" * min(len(value) - 2, 10) if len(value) > 2 else "***"
                console.print(f"[cyan]{key}[/]={masked}")
            else:
                console.print(f"[cyan]{key}[/]={value}")

    elif action == "edit":
        import subprocess
        editor = os.environ.get("EDITOR", "nano")

        if not file_path.exists():
            if Confirm.ask(f"File {file} doesn't exist. Create it?"):
                file_path.touch()
            else:
                return

        subprocess.run([editor, str(file_path)])
        success(f"Edited {file}")

    elif action == "validate":
        if not file_path.exists():
            error(f"File not found: {file}")
            return

        env_vars = load_env_file(file_path)
        issues = []

        for key, value in env_vars.items():
            if not value:
                issues.append(f"{key}: Empty value")
            if ' ' in key:
                issues.append(f"{key}: Key contains spaces")

        if issues:
            warning(f"Found {len(issues)} issue(s):")
            for issue in issues:
                console.print(f"  [yellow]![/] {issue}")
        else:
            success(f"Validated {len(env_vars)} variables - all good!")

    else:
        error(f"Unknown action: {action}")
        info("Valid actions: show, edit, validate")


@app.command("sync")
def sync_env_files(
    source: str = typer.Argument(..., help="Source .env file"),
    target: str = typer.Argument(..., help="Target .env file"),
):
    """Sync keys between .env files (adds missing keys with empty values)."""
    source_path = Path(source)
    target_path = Path(target)

    if not source_path.exists():
        error(f"Source file not found: {source}")
        return

    source_vars = load_env_file(source_path)
    target_vars = load_env_file(target_path) if target_path.exists() else {}

    missing = []
    for key in source_vars:
        if key not in target_vars:
            target_vars[key] = ""
            missing.append(key)

    if missing:
        save_env_file(target_path, target_vars)
        success(f"Added {len(missing)} missing keys to {target}")
        for key in missing:
            info(f"  + {key}")
    else:
        info("Files are already in sync")


@app.command("generate")
def generate_secret(
    key: Optional[str] = typer.Option(None, "--key", "-k", help="Save with this key name"),
    length: int = typer.Option(32, "--length", "-l", help="Secret length"),
    env: str = typer.Option("default", "--env", "-e", help="Environment to save to"),
    type: str = typer.Option("random", "--type", "-t", help="Type: random, uuid, hex"),
):
    """Generate a random secret value."""
    import secrets
    import uuid

    if type == "random":
        # Alphanumeric
        alphabet = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
        value = ''.join(secrets.choice(alphabet) for _ in range(length))
    elif type == "uuid":
        value = str(uuid.uuid4())
    elif type == "hex":
        value = secrets.token_hex(length // 2)
    else:
        error(f"Unknown type: {type}")
        return

    console.print(f"[green]Generated:[/] {value}")

    if key:
        # Save the secret
        if Confirm.ask(f"Save as '{key}' in {env} environment?"):
            # Reuse set_secret logic
            secrets_file = SECRETS_DIR / f"{env}.secrets"
            secrets_data = {}

            if secrets_file.exists():
                password = Prompt.ask("Enter secrets password", password=True)
                try:
                    encrypted = secrets_file.read_text()
                    decrypted = simple_decrypt(encrypted, password)
                    secrets_data = json.loads(decrypted)
                except Exception:
                    error("Failed to decrypt secrets")
                    return
            else:
                password = Prompt.ask("Create secrets password", password=True)

            secrets_data[key] = {
                "value": value,
                "updated": datetime.now().isoformat(),
            }

            encrypted = simple_encrypt(json.dumps(secrets_data), password)
            SECRETS_DIR.mkdir(parents=True, exist_ok=True)
            secrets_file.write_text(encrypted)

            success(f"Saved as '{key}'")
