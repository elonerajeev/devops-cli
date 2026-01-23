"""Log viewing and tailing commands."""

import subprocess
import sys
import os
from typing import Optional
from pathlib import Path

import typer
from rich.console import Console
from rich.syntax import Syntax

from devops_cli.config.settings import load_config
from devops_cli.utils.output import (
    success, error, warning, info, header, console as out_console
)

app = typer.Typer(help="View and tail logs from various sources")
console = Console()


def tail_docker_logs(container: str, lines: int, follow: bool):
    """Tail logs from a Docker container."""
    cmd = ["docker", "logs", "--tail", str(lines)]
    if follow:
        cmd.append("-f")
    cmd.append(container)

    try:
        if follow:
            process = subprocess.Popen(cmd, stdout=sys.stdout, stderr=sys.stderr)
            process.wait()
        else:
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0:
                console.print(result.stdout)
                if result.stderr:
                    console.print(result.stderr, style="dim")
            else:
                error(f"Failed to get logs: {result.stderr}")
    except FileNotFoundError:
        error("Docker is not installed")
    except KeyboardInterrupt:
        console.print("\n")
        info("Stopped tailing logs")


def tail_file_logs(path: str, lines: int, follow: bool):
    """Tail logs from a file."""
    file_path = Path(path).expanduser()

    if not file_path.exists():
        error(f"Log file not found: {file_path}")
        return

    cmd = ["tail", f"-n{lines}"]
    if follow:
        cmd.append("-f")
    cmd.append(str(file_path))

    try:
        if follow:
            process = subprocess.Popen(cmd, stdout=sys.stdout, stderr=sys.stderr)
            process.wait()
        else:
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0:
                console.print(result.stdout)
            else:
                error(f"Failed to read logs: {result.stderr}")
    except KeyboardInterrupt:
        console.print("\n")
        info("Stopped tailing logs")


def tail_journald_logs(unit: str, lines: int, follow: bool):
    """Tail logs from systemd journal."""
    cmd = ["journalctl", "-u", unit, "-n", str(lines), "--no-pager"]
    if follow:
        cmd.append("-f")

    try:
        if follow:
            process = subprocess.Popen(cmd, stdout=sys.stdout, stderr=sys.stderr)
            process.wait()
        else:
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0:
                console.print(result.stdout)
            else:
                error(f"Failed to get logs: {result.stderr}")
    except FileNotFoundError:
        error("journalctl not available (not a systemd system)")
    except KeyboardInterrupt:
        console.print("\n")
        info("Stopped tailing logs")


def tail_kubernetes_logs(pod: str, namespace: str, container: Optional[str], lines: int, follow: bool):
    """Tail logs from a Kubernetes pod."""
    cmd = ["kubectl", "logs", f"--tail={lines}"]
    if namespace:
        cmd.extend(["-n", namespace])
    if follow:
        cmd.append("-f")
    if container:
        cmd.extend(["-c", container])
    cmd.append(pod)

    try:
        if follow:
            process = subprocess.Popen(cmd, stdout=sys.stdout, stderr=sys.stderr)
            process.wait()
        else:
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0:
                console.print(result.stdout)
            else:
                error(f"Failed to get logs: {result.stderr}")
    except FileNotFoundError:
        error("kubectl not installed")
    except KeyboardInterrupt:
        console.print("\n")
        info("Stopped tailing logs")


@app.command("tail")
def tail_logs(
    service: str = typer.Argument(..., help="Service name (from config) or container/file path"),
    lines: int = typer.Option(100, "--lines", "-n", help="Number of lines to show"),
    follow: bool = typer.Option(False, "--follow", "-f", help="Follow log output"),
):
    """Tail logs from a configured service or directly from a source."""
    config = load_config()
    log_sources = config.get("logs", {}).get("sources", {})

    # Check if service is configured
    if service in log_sources:
        source = log_sources[service]
        source_type = source.get("type", "docker")
        header(f"Logs: {service}")

        if source_type == "docker":
            tail_docker_logs(source["container"], lines, follow)
        elif source_type == "file":
            tail_file_logs(source["path"], lines, follow)
        elif source_type == "journald":
            tail_journald_logs(source["unit"], lines, follow)
        elif source_type == "kubernetes":
            tail_kubernetes_logs(
                source["pod"],
                source.get("namespace", "default"),
                source.get("container"),
                lines,
                follow
            )
        else:
            error(f"Unknown log source type: {source_type}")
    else:
        # Try direct Docker container name
        info(f"Service '{service}' not in config, trying as Docker container...")
        tail_docker_logs(service, lines, follow)


@app.command("docker")
def docker_logs(
    container: str = typer.Argument(..., help="Docker container name or ID"),
    lines: int = typer.Option(100, "--lines", "-n", help="Number of lines"),
    follow: bool = typer.Option(False, "--follow", "-f", help="Follow log output"),
    since: Optional[str] = typer.Option(None, "--since", "-s", help="Show logs since (e.g., 1h, 30m)"),
):
    """View Docker container logs."""
    cmd = ["docker", "logs", "--tail", str(lines)]
    if follow:
        cmd.append("-f")
    if since:
        cmd.extend(["--since", since])
    cmd.append(container)

    try:
        header(f"Docker Logs: {container}")
        if follow:
            process = subprocess.Popen(cmd, stdout=sys.stdout, stderr=sys.stderr)
            process.wait()
        else:
            result = subprocess.run(cmd, capture_output=True, text=True)
            console.print(result.stdout)
            if result.stderr:
                console.print(result.stderr, style="dim")
    except FileNotFoundError:
        error("Docker is not installed")
    except KeyboardInterrupt:
        console.print("\n")
        info("Stopped")


@app.command("file")
def file_logs(
    path: str = typer.Argument(..., help="Path to log file"),
    lines: int = typer.Option(100, "--lines", "-n", help="Number of lines"),
    follow: bool = typer.Option(False, "--follow", "-f", help="Follow log output"),
    grep: Optional[str] = typer.Option(None, "--grep", "-g", help="Filter lines matching pattern"),
):
    """View logs from a file.

    Security: Uses subprocess with list arguments to avoid shell injection.
    Pipes are created manually instead of using shell=True.
    """
    file_path = Path(path).expanduser().resolve()

    if not file_path.exists():
        error(f"File not found: {file_path}")
        return

    # Security: Validate file path doesn't escape to unexpected locations
    if not str(file_path).startswith(str(Path.home())) and not str(file_path).startswith("/var/log"):
        warning(f"Reading file outside home/logs directory: {file_path}")

    header(f"File Logs: {file_path.name}")

    # Build tail command
    tail_cmd = ["tail", f"-n{lines}"]
    if follow:
        tail_cmd.append("-f")
    tail_cmd.append(str(file_path))

    try:
        if grep:
            # Use subprocess pipes instead of shell=True
            # tail | grep pattern
            tail_proc = subprocess.Popen(
                tail_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            grep_cmd = ["grep", "--color=always", grep]

            if follow:
                grep_proc = subprocess.Popen(
                    grep_cmd,
                    stdin=tail_proc.stdout,
                    stdout=sys.stdout,
                    stderr=sys.stderr
                )
                tail_proc.stdout.close()  # Allow tail to receive SIGPIPE
                grep_proc.wait()
            else:
                grep_proc = subprocess.Popen(
                    grep_cmd,
                    stdin=tail_proc.stdout,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE
                )
                tail_proc.stdout.close()
                output, _ = grep_proc.communicate()
                console.print(output.decode('utf-8', errors='replace'))
        else:
            if follow:
                process = subprocess.Popen(tail_cmd, stdout=sys.stdout, stderr=sys.stderr)
                process.wait()
            else:
                result = subprocess.run(tail_cmd, capture_output=True, text=True)
                console.print(result.stdout)
    except KeyboardInterrupt:
        console.print("\n")
        info("Stopped")
    except FileNotFoundError as e:
        error(f"Command not found: {e.filename}")


@app.command("k8s")
def kubernetes_logs(
    pod: str = typer.Argument(..., help="Pod name"),
    namespace: str = typer.Option("default", "--namespace", "-n", help="Kubernetes namespace"),
    container: Optional[str] = typer.Option(None, "--container", "-c", help="Container name"),
    lines: int = typer.Option(100, "--tail", "-t", help="Number of lines"),
    follow: bool = typer.Option(False, "--follow", "-f", help="Follow log output"),
    previous: bool = typer.Option(False, "--previous", "-p", help="Previous container instance"),
):
    """View Kubernetes pod logs."""
    cmd = ["kubectl", "logs", f"--tail={lines}"]
    if namespace:
        cmd.extend(["-n", namespace])
    if follow:
        cmd.append("-f")
    if container:
        cmd.extend(["-c", container])
    if previous:
        cmd.append("--previous")
    cmd.append(pod)

    try:
        header(f"K8s Logs: {pod}")
        info(f"Namespace: {namespace}")
        console.print()

        if follow:
            process = subprocess.Popen(cmd, stdout=sys.stdout, stderr=sys.stderr)
            process.wait()
        else:
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0:
                console.print(result.stdout)
            else:
                error(result.stderr)
    except FileNotFoundError:
        error("kubectl not installed")
    except KeyboardInterrupt:
        console.print("\n")
        info("Stopped")


@app.command("journald")
def journald_logs(
    unit: str = typer.Argument(..., help="Systemd unit name"),
    lines: int = typer.Option(100, "--lines", "-n", help="Number of lines"),
    follow: bool = typer.Option(False, "--follow", "-f", help="Follow log output"),
    since: Optional[str] = typer.Option(None, "--since", "-s", help="Show logs since (e.g., '1 hour ago')"),
    priority: Optional[str] = typer.Option(None, "--priority", "-p", help="Filter by priority (e.g., err, warning)"),
):
    """View systemd journal logs for a unit."""
    cmd = ["journalctl", "-u", unit, "-n", str(lines), "--no-pager"]
    if follow:
        cmd.append("-f")
    if since:
        cmd.extend(["--since", since])
    if priority:
        cmd.extend(["-p", priority])

    try:
        header(f"Journal Logs: {unit}")

        if follow:
            process = subprocess.Popen(cmd, stdout=sys.stdout, stderr=sys.stderr)
            process.wait()
        else:
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0:
                console.print(result.stdout)
            else:
                error(result.stderr)
    except FileNotFoundError:
        error("journalctl not available")
    except KeyboardInterrupt:
        console.print("\n")
        info("Stopped")


@app.command("list")
def list_sources():
    """List configured log sources."""
    config = load_config()
    sources = config.get("logs", {}).get("sources", {})

    if not sources:
        warning("No log sources configured")
        info("\nAdd sources to your config file under 'logs.sources:'")
        console.print("""[dim]
logs:
  sources:
    api:
      type: docker
      container: api-container
    nginx:
      type: file
      path: /var/log/nginx/access.log
    backend:
      type: kubernetes
      pod: backend-pod
      namespace: default
    myservice:
      type: journald
      unit: myservice.service
[/dim]""")
        return

    header("Configured Log Sources")

    from devops_cli.utils.output import create_table

    table = create_table(
        "",
        [("Name", "cyan"), ("Type", "yellow"), ("Source", "dim")]
    )

    for name, source in sources.items():
        source_type = source.get("type", "unknown")

        if source_type == "docker":
            source_info = source.get("container", "")
        elif source_type == "file":
            source_info = source.get("path", "")
        elif source_type == "kubernetes":
            source_info = f"{source.get('namespace', 'default')}/{source.get('pod', '')}"
        elif source_type == "journald":
            source_info = source.get("unit", "")
        else:
            source_info = str(source)

        table.add_row(name, source_type, source_info)

    console.print(table)
    info("\nUse 'devops logs tail <name>' to view logs")


@app.command("multi")
def multi_logs(
    services: str = typer.Argument(..., help="Comma-separated service names"),
    lines: int = typer.Option(20, "--lines", "-n", help="Lines per service"),
):
    """View logs from multiple services at once."""
    config = load_config()
    log_sources = config.get("logs", {}).get("sources", {})

    service_list = [s.strip() for s in services.split(",")]

    for service in service_list:
        if service not in log_sources:
            warning(f"Service '{service}' not configured, skipping")
            continue

        source = log_sources[service]
        source_type = source.get("type", "docker")

        header(f"{service}")

        if source_type == "docker":
            tail_docker_logs(source["container"], lines, follow=False)
        elif source_type == "file":
            tail_file_logs(source["path"], lines, follow=False)

        console.print()
