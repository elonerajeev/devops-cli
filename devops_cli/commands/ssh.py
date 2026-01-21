"""SSH commands for server management."""

import subprocess
import sys
import os
import concurrent.futures
from typing import Optional
from pathlib import Path

import typer
import paramiko
from rich.console import Console
from rich.prompt import Prompt, Confirm
from rich.live import Live
from rich.table import Table

from devops_cli.config.settings import load_config
from devops_cli.utils.output import (
    success, error, warning, info, header,
    create_table, status_badge, console as out_console
)

app = typer.Typer(help="SSH and server management commands")
console = Console()


def get_server_config(server_name: str) -> dict | None:
    """Get server configuration by name."""
    config = load_config()
    servers = config.get("servers", {})
    return servers.get(server_name)


def get_servers_by_tag(tag: str) -> dict:
    """Get all servers matching a tag."""
    config = load_config()
    servers = config.get("servers", {})
    return {
        name: srv for name, srv in servers.items()
        if tag in srv.get("tags", [])
    }


def create_ssh_client(server_config: dict) -> paramiko.SSHClient:
    """Create and connect SSH client."""
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    key_path = Path(server_config.get("key", "~/.ssh/id_rsa")).expanduser()

    connect_kwargs = {
        "hostname": server_config["host"],
        "username": server_config.get("user", "root"),
        "port": server_config.get("port", 22),
        "timeout": server_config.get("timeout", 30),
    }

    # Try key-based auth first
    if key_path.exists():
        connect_kwargs["key_filename"] = str(key_path)
    elif server_config.get("password"):
        connect_kwargs["password"] = server_config["password"]

    client.connect(**connect_kwargs)
    return client


def run_remote_command(server_name: str, server_config: dict, command: str) -> dict:
    """Run a command on a remote server."""
    try:
        client = create_ssh_client(server_config)
        stdin, stdout, stderr = client.exec_command(command, timeout=60)

        exit_code = stdout.channel.recv_exit_status()
        output = stdout.read().decode().strip()
        err_output = stderr.read().decode().strip()

        client.close()

        return {
            "server": server_name,
            "success": exit_code == 0,
            "exit_code": exit_code,
            "output": output,
            "error": err_output,
        }
    except paramiko.AuthenticationException:
        return {"server": server_name, "success": False, "error": "Authentication failed"}
    except paramiko.SSHException as e:
        return {"server": server_name, "success": False, "error": f"SSH error: {e}"}
    except Exception as e:
        return {"server": server_name, "success": False, "error": str(e)}


@app.command("list")
def list_servers(
    tag: Optional[str] = typer.Option(None, "--tag", "-t", help="Filter by tag"),
):
    """List configured servers."""
    config = load_config()
    servers = config.get("servers", {})

    if not servers:
        warning("No servers configured")
        info("\nAdd servers to your config file under 'servers:'")
        console.print("""[dim]
servers:
  web-1:
    host: web1.example.com
    user: deploy
    key: ~/.ssh/id_rsa
    port: 22
    tags: [web, production]
  staging:
    host: staging.example.com
    user: deploy
    key: ~/.ssh/id_rsa
    tags: [staging]
[/dim]""")
        return

    # Filter by tag if provided
    if tag:
        servers = {
            name: srv for name, srv in servers.items()
            if tag in srv.get("tags", [])
        }
        if not servers:
            warning(f"No servers found with tag '{tag}'")
            return

    header("Configured Servers")

    table = create_table(
        "",
        [("Name", "cyan"), ("Host", ""), ("User", "dim"), ("Port", "dim"), ("Tags", "yellow")]
    )

    for name, srv in servers.items():
        table.add_row(
            name,
            srv.get("host", ""),
            srv.get("user", "root"),
            str(srv.get("port", 22)),
            ", ".join(srv.get("tags", []))
        )

    console.print(table)


@app.command("connect")
def connect_server(
    server: str = typer.Argument(..., help="Server name from config"),
):
    """Open interactive SSH session to a server."""
    server_config = get_server_config(server)

    if not server_config:
        error(f"Server '{server}' not found in configuration")
        info("Run 'devops ssh list' to see available servers")
        return

    host = server_config["host"]
    user = server_config.get("user", "root")
    port = server_config.get("port", 22)
    key_path = Path(server_config.get("key", "~/.ssh/id_rsa")).expanduser()

    info(f"Connecting to {server} ({user}@{host}:{port})...")

    # Build SSH command
    ssh_cmd = ["ssh"]

    if key_path.exists():
        ssh_cmd.extend(["-i", str(key_path)])

    ssh_cmd.extend(["-p", str(port), f"{user}@{host}"])

    # Execute interactive SSH
    try:
        subprocess.run(ssh_cmd)
    except KeyboardInterrupt:
        console.print("\n")
        info("Connection closed")


@app.command("run")
def run_command(
    command: str = typer.Argument(..., help="Command to run"),
    server: Optional[str] = typer.Option(None, "--server", "-s", help="Server name"),
    tag: Optional[str] = typer.Option(None, "--tag", "-t", help="Run on all servers with tag"),
    parallel: bool = typer.Option(True, "--parallel/--sequential", help="Run in parallel"),
):
    """Run a command on remote server(s)."""
    if not server and not tag:
        error("Specify either --server or --tag")
        return

    # Get target servers
    if server:
        server_config = get_server_config(server)
        if not server_config:
            error(f"Server '{server}' not found")
            return
        servers = {server: server_config}
    else:
        servers = get_servers_by_tag(tag)
        if not servers:
            error(f"No servers found with tag '{tag}'")
            return

    header(f"Running command on {len(servers)} server(s)")
    info(f"Command: {command}")
    console.print()

    results = []

    if parallel and len(servers) > 1:
        # Run in parallel
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = {
                executor.submit(run_remote_command, name, cfg, command): name
                for name, cfg in servers.items()
            }

            for future in concurrent.futures.as_completed(futures):
                result = future.result()
                results.append(result)
                _print_result(result)
    else:
        # Run sequentially
        for name, cfg in servers.items():
            result = run_remote_command(name, cfg, command)
            results.append(result)
            _print_result(result)

    # Summary
    console.print()
    succeeded = sum(1 for r in results if r.get("success"))
    failed = len(results) - succeeded

    if failed == 0:
        success(f"All {succeeded} server(s) completed successfully")
    else:
        warning(f"{succeeded} succeeded, {failed} failed")


def _print_result(result: dict):
    """Print a single command result."""
    server = result["server"]

    if result.get("success"):
        console.print(f"[bold green]✓ {server}[/]")
        if result.get("output"):
            for line in result["output"].split("\n")[:20]:
                console.print(f"  {line}")
            if result["output"].count("\n") > 20:
                console.print(f"  [dim]... ({result['output'].count(chr(10)) - 20} more lines)[/]")
    else:
        console.print(f"[bold red]✗ {server}[/]")
        console.print(f"  [red]{result.get('error', 'Unknown error')}[/]")

    console.print()


@app.command("upload")
def upload_file(
    local_path: str = typer.Argument(..., help="Local file path"),
    remote_path: str = typer.Argument(..., help="Remote destination path"),
    server: Optional[str] = typer.Option(None, "--server", "-s", help="Server name"),
    tag: Optional[str] = typer.Option(None, "--tag", "-t", help="Upload to all servers with tag"),
):
    """Upload a file to remote server(s)."""
    local_file = Path(local_path).expanduser()

    if not local_file.exists():
        error(f"Local file not found: {local_file}")
        return

    if not server and not tag:
        error("Specify either --server or --tag")
        return

    # Get target servers
    if server:
        server_config = get_server_config(server)
        if not server_config:
            error(f"Server '{server}' not found")
            return
        servers = {server: server_config}
    else:
        servers = get_servers_by_tag(tag)
        if not servers:
            error(f"No servers found with tag '{tag}'")
            return

    header(f"Uploading to {len(servers)} server(s)")
    info(f"Local: {local_file}")
    info(f"Remote: {remote_path}")
    console.print()

    for name, cfg in servers.items():
        try:
            client = create_ssh_client(cfg)
            sftp = client.open_sftp()

            sftp.put(str(local_file), remote_path)

            sftp.close()
            client.close()
            success(f"{name}: Upload complete")
        except Exception as e:
            error(f"{name}: {e}")


@app.command("download")
def download_file(
    remote_path: str = typer.Argument(..., help="Remote file path"),
    local_path: str = typer.Argument(..., help="Local destination path"),
    server: str = typer.Option(..., "--server", "-s", help="Server name"),
):
    """Download a file from remote server."""
    server_config = get_server_config(server)

    if not server_config:
        error(f"Server '{server}' not found")
        return

    local_file = Path(local_path).expanduser()
    local_file.parent.mkdir(parents=True, exist_ok=True)

    info(f"Downloading from {server}...")
    info(f"Remote: {remote_path}")
    info(f"Local: {local_file}")

    try:
        client = create_ssh_client(server_config)
        sftp = client.open_sftp()

        sftp.get(remote_path, str(local_file))

        sftp.close()
        client.close()
        success(f"Downloaded to {local_file}")
    except Exception as e:
        error(f"Download failed: {e}")


@app.command("ping")
def ping_servers(
    tag: Optional[str] = typer.Option(None, "--tag", "-t", help="Filter by tag"),
):
    """Check connectivity to all configured servers."""
    config = load_config()
    servers = config.get("servers", {})

    if not servers:
        warning("No servers configured")
        return

    if tag:
        servers = get_servers_by_tag(tag)
        if not servers:
            warning(f"No servers with tag '{tag}'")
            return

    header(f"Pinging {len(servers)} server(s)")

    table = create_table(
        "",
        [("Server", "cyan"), ("Host", ""), ("Status", ""), ("Message", "dim")]
    )

    def check_server(name: str, cfg: dict) -> tuple:
        try:
            client = create_ssh_client(cfg)
            client.close()
            return name, cfg["host"], "healthy", "Connected"
        except paramiko.AuthenticationException:
            return name, cfg["host"], "warning", "Auth failed"
        except Exception as e:
            return name, cfg["host"], "unhealthy", str(e)[:30]

    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = [
            executor.submit(check_server, name, cfg)
            for name, cfg in servers.items()
        ]

        for future in concurrent.futures.as_completed(futures):
            name, host, status, msg = future.result()
            table.add_row(name, host, status_badge(status), msg)

    console.print(table)


@app.command("exec")
def exec_script(
    script: str = typer.Argument(..., help="Local script file to execute"),
    server: Optional[str] = typer.Option(None, "--server", "-s", help="Server name"),
    tag: Optional[str] = typer.Option(None, "--tag", "-t", help="Run on all servers with tag"),
):
    """Execute a local script on remote server(s)."""
    script_path = Path(script).expanduser()

    if not script_path.exists():
        error(f"Script not found: {script_path}")
        return

    if not server and not tag:
        error("Specify either --server or --tag")
        return

    # Read script content
    script_content = script_path.read_text()

    # Get target servers
    if server:
        server_config = get_server_config(server)
        if not server_config:
            error(f"Server '{server}' not found")
            return
        servers = {server: server_config}
    else:
        servers = get_servers_by_tag(tag)
        if not servers:
            error(f"No servers found with tag '{tag}'")
            return

    header(f"Executing script on {len(servers)} server(s)")
    info(f"Script: {script_path.name}")
    console.print()

    # Determine interpreter from shebang or extension
    if script_content.startswith("#!"):
        first_line = script_content.split("\n")[0]
        interpreter = first_line[2:].strip()
    elif script_path.suffix == ".py":
        interpreter = "python3"
    else:
        interpreter = "bash"

    for name, cfg in servers.items():
        try:
            client = create_ssh_client(cfg)

            # Upload script to temp location
            sftp = client.open_sftp()
            remote_script = f"/tmp/{script_path.name}"
            sftp.putfo(script_path.open("rb"), remote_script)
            sftp.chmod(remote_script, 0o755)
            sftp.close()

            # Execute script
            stdin, stdout, stderr = client.exec_command(f"{interpreter} {remote_script}")
            exit_code = stdout.channel.recv_exit_status()
            output = stdout.read().decode().strip()
            err_output = stderr.read().decode().strip()

            # Cleanup
            client.exec_command(f"rm -f {remote_script}")
            client.close()

            if exit_code == 0:
                console.print(f"[bold green]✓ {name}[/]")
                if output:
                    for line in output.split("\n")[:10]:
                        console.print(f"  {line}")
            else:
                console.print(f"[bold red]✗ {name}[/] (exit code: {exit_code})")
                if err_output:
                    console.print(f"  [red]{err_output[:200]}[/]")

        except Exception as e:
            console.print(f"[bold red]✗ {name}[/]")
            console.print(f"  [red]{e}[/]")

        console.print()


@app.command("copy-id")
def copy_ssh_key(
    server: str = typer.Argument(..., help="Server name"),
    key: str = typer.Option("~/.ssh/id_rsa.pub", "--key", "-k", help="Public key to copy"),
):
    """Copy SSH public key to a server for passwordless login."""
    server_config = get_server_config(server)

    if not server_config:
        error(f"Server '{server}' not found")
        return

    key_path = Path(key).expanduser()

    if not key_path.exists():
        error(f"Public key not found: {key_path}")
        info("Generate one with: ssh-keygen -t rsa -b 4096")
        return

    public_key = key_path.read_text().strip()

    host = server_config["host"]
    user = server_config.get("user", "root")
    port = server_config.get("port", 22)

    info(f"Copying SSH key to {server} ({user}@{host})")

    # Use ssh-copy-id if available, otherwise manual
    password = Prompt.ask("Enter password for remote server", password=True)

    try:
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(host, port=port, username=user, password=password)

        # Add key to authorized_keys
        command = f'mkdir -p ~/.ssh && chmod 700 ~/.ssh && echo "{public_key}" >> ~/.ssh/authorized_keys && chmod 600 ~/.ssh/authorized_keys'
        stdin, stdout, stderr = client.exec_command(command)
        exit_code = stdout.channel.recv_exit_status()

        client.close()

        if exit_code == 0:
            success("SSH key copied successfully!")
            info("You can now connect without a password")
        else:
            error(f"Failed: {stderr.read().decode()}")
    except Exception as e:
        error(f"Failed to copy key: {e}")
