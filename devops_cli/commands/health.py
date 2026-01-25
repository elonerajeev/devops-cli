"""Health check commands for services."""

import socket
import subprocess
import time
import concurrent.futures
from typing import Optional

import typer
import requests
from rich.console import Console
from rich.table import Table

from devops_cli.config.settings import load_config
from devops_cli.utils.output import (
    success,
    error,
    warning,
    info,
    header,
    create_table,
    status_badge,
)

app = typer.Typer(help="Health checks for services")
console = Console()


def check_http(
    url: str, method: str = "GET", expected_status: int = 200, timeout: int = 10
) -> dict:
    """Check HTTP endpoint health."""
    start = time.time()
    try:
        resp = requests.request(method, url, timeout=timeout)
        latency = (time.time() - start) * 1000  # ms

        is_healthy = resp.status_code == expected_status
        return {
            "healthy": is_healthy,
            "status_code": resp.status_code,
            "latency_ms": round(latency, 2),
            "message": (
                "OK"
                if is_healthy
                else f"Expected {expected_status}, got {resp.status_code}"
            ),
        }
    except requests.Timeout:
        return {"healthy": False, "message": "Timeout", "latency_ms": timeout * 1000}
    except requests.ConnectionError:
        return {"healthy": False, "message": "Connection refused"}
    except Exception as e:
        return {"healthy": False, "message": str(e)}


def check_tcp(host: str, port: int, timeout: int = 5) -> dict:
    """Check TCP port connectivity."""
    start = time.time()
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        result = sock.connect_ex((host, port))
        sock.close()
        latency = (time.time() - start) * 1000

        if result == 0:
            return {
                "healthy": True,
                "latency_ms": round(latency, 2),
                "message": "Port open",
            }
        else:
            return {"healthy": False, "message": "Port closed"}
    except socket.timeout:
        return {"healthy": False, "message": "Timeout"}
    except socket.gaierror:
        return {"healthy": False, "message": "DNS resolution failed"}
    except Exception as e:
        return {"healthy": False, "message": str(e)}


def check_command(command: str, timeout: int = 30) -> dict:
    """Check by running a command (exit 0 = healthy).

    Security: Uses shlex.split() to safely parse command string into list,
    avoiding shell injection vulnerabilities.
    """
    import shlex

    start = time.time()
    try:
        # Safely split command string into list to avoid shell injection
        cmd_list = shlex.split(command)
        if not cmd_list:
            return {"healthy": False, "message": "Empty command"}

        result = subprocess.run(
            cmd_list, capture_output=True, text=True, timeout=timeout
        )
        latency = (time.time() - start) * 1000

        is_healthy = result.returncode == 0
        return {
            "healthy": is_healthy,
            "latency_ms": round(latency, 2),
            "message": (
                "OK"
                if is_healthy
                else result.stderr[:100] or f"Exit code: {result.returncode}"
            ),
        }
    except subprocess.TimeoutExpired:
        return {"healthy": False, "message": "Command timeout"}
    except ValueError as e:
        return {"healthy": False, "message": f"Invalid command syntax: {str(e)}"}
    except FileNotFoundError:
        return {"healthy": False, "message": "Command not found"}
    except Exception as e:
        return {"healthy": False, "message": str(e)}


def check_docker_container(container: str) -> dict:
    """Check if a Docker container is running and healthy."""
    try:
        result = subprocess.run(
            [
                "docker",
                "inspect",
                "--format",
                "{{.State.Status}}:{{.State.Health.Status}}",
                container,
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )

        if result.returncode != 0:
            return {"healthy": False, "message": "Container not found"}

        output = result.stdout.strip()
        parts = output.split(":")
        status = parts[0]
        health = parts[1] if len(parts) > 1 and parts[1] else "none"

        if status != "running":
            return {"healthy": False, "message": f"Container {status}"}
        if health == "unhealthy":
            return {"healthy": False, "message": "Container unhealthy"}

        return {"healthy": True, "message": f"Running ({health})"}
    except FileNotFoundError:
        return {"healthy": False, "message": "Docker not installed"}
    except Exception as e:
        return {"healthy": False, "message": str(e)}


def run_service_check(name: str, config: dict) -> dict:
    """Run a health check based on service configuration."""
    check_type = config.get("type", "http")

    if check_type == "http":
        return check_http(
            url=config["url"],
            method=config.get("method", "GET"),
            expected_status=config.get("expected_status", 200),
            timeout=config.get("timeout", 10),
        )
    elif check_type == "tcp":
        return check_tcp(
            host=config["host"], port=config["port"], timeout=config.get("timeout", 5)
        )
    elif check_type == "command":
        return check_command(config["command"], timeout=config.get("timeout", 30))
    elif check_type == "docker":
        return check_docker_container(config["container"])
    else:
        return {"healthy": False, "message": f"Unknown check type: {check_type}"}


@app.command("check")
def check_all(
    service: Optional[str] = typer.Argument(None, help="Specific service to check"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show detailed output"),
):
    """Run health checks on all configured services."""
    config = load_config()
    services = config.get("services", {})

    if not services:
        warning("No services configured for health checks")
        info("Add services to your config file under 'services:'")
        info("\nExample:")
        console.print("""[dim]
services:
  api:
    type: http
    url: https://api.example.com/health
    expected_status: 200
  database:
    type: tcp
    host: localhost
    port: 5432
  redis:
    type: docker
    container: redis
[/dim]""")
        return

    # Filter to specific service if provided
    if service:
        if service not in services:
            error(f"Service '{service}' not found in configuration")
            return
        services = {service: services[service]}

    header("Health Check Results")

    table = create_table(
        "",
        [("Service", "cyan"), ("Status", ""), ("Latency", "dim"), ("Details", "dim")],
    )

    all_healthy = True
    results = {}

    # Run checks in parallel
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        future_to_service = {
            executor.submit(run_service_check, name, svc_config): name
            for name, svc_config in services.items()
        }

        for future in concurrent.futures.as_completed(future_to_service):
            name = future_to_service[future]
            try:
                result = future.result()
                results[name] = result

                status = "healthy" if result["healthy"] else "unhealthy"
                latency = (
                    f"{result.get('latency_ms', '-')} ms"
                    if result.get("latency_ms")
                    else "-"
                )

                table.add_row(
                    name, status_badge(status), latency, result.get("message", "")[:40]
                )

                if not result["healthy"]:
                    all_healthy = False
            except Exception as e:
                table.add_row(name, status_badge("error"), "-", str(e)[:40])
                all_healthy = False

    console.print(table)

    # Summary
    console.print()
    if all_healthy:
        success(f"All {len(services)} services are healthy")
    else:
        unhealthy = sum(1 for r in results.values() if not r.get("healthy", False))
        error(f"{unhealthy}/{len(services)} services are unhealthy")


@app.command("ping")
def ping_url(
    url: str = typer.Argument(..., help="URL to ping"),
    count: int = typer.Option(5, "--count", "-c", help="Number of pings"),
):
    """Ping a URL and show latency statistics."""
    header(f"Pinging: {url}")

    latencies = []
    for i in range(count):
        result = check_http(url, timeout=10)
        if result["healthy"]:
            latency = result["latency_ms"]
            latencies.append(latency)
            console.print(f"  [{i+1}] {latency:.1f} ms - [green]OK[/]")
        else:
            console.print(f"  [{i+1}] [red]FAILED[/] - {result['message']}")
        time.sleep(0.5)

    if latencies:
        console.print()
        info(f"Min: {min(latencies):.1f} ms")
        info(f"Max: {max(latencies):.1f} ms")
        info(f"Avg: {sum(latencies)/len(latencies):.1f} ms")
        success(f"Success: {len(latencies)}/{count}")
    else:
        error("All requests failed")


@app.command("port")
def check_port(
    host: str = typer.Argument(..., help="Host to check"),
    port: int = typer.Argument(..., help="Port number"),
):
    """Check if a TCP port is open."""
    info(f"Checking {host}:{port}...")
    result = check_tcp(host, port)

    if result["healthy"]:
        success(f"Port {port} is open on {host}")
        info(f"Latency: {result['latency_ms']} ms")
    else:
        error(f"Port {port} is closed on {host}: {result['message']}")


@app.command("docker")
def check_docker_services(
    all_containers: bool = typer.Option(
        False, "--all", "-a", help="Show all containers"
    ),
):
    """Check Docker container health status."""
    try:
        cmd = ["docker", "ps", "--format", "{{.Names}}\t{{.Status}}\t{{.Ports}}"]
        if all_containers:
            cmd.insert(2, "-a")

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)

        if result.returncode != 0:
            error("Failed to get Docker containers")
            return

        lines = [l for l in result.stdout.strip().split("\n") if l]
        if not lines:
            info("No Docker containers found")
            return

        header("Docker Containers")

        table = create_table(
            "", [("Container", "cyan"), ("Status", ""), ("Ports", "dim")]
        )

        for line in lines:
            parts = line.split("\t")
            name = parts[0]
            status = parts[1] if len(parts) > 1 else ""
            ports = parts[2] if len(parts) > 2 else ""

            # Determine health
            if "Up" in status:
                if "unhealthy" in status.lower():
                    badge = status_badge("unhealthy")
                elif "healthy" in status.lower():
                    badge = status_badge("healthy")
                else:
                    badge = status_badge("running")
            else:
                badge = status_badge("stopped")

            table.add_row(name, badge, ports[:40])

        console.print(table)

    except FileNotFoundError:
        error("Docker is not installed")
    except Exception as e:
        error(f"Error: {e}")


@app.command("watch")
def watch_health(
    interval: int = typer.Option(
        30, "--interval", "-i", help="Check interval in seconds"
    ),
):
    """Continuously watch service health (Ctrl+C to stop)."""
    config = load_config()
    services = config.get("services", {})

    if not services:
        warning("No services configured")
        return

    info(f"Watching {len(services)} services every {interval}s (Ctrl+C to stop)")
    console.print()

    try:
        while True:
            table = Table(show_header=True, header_style="bold")
            table.add_column("Service", style="cyan")
            table.add_column("Status")
            table.add_column("Latency", style="dim")
            table.add_column("Time", style="dim")

            current_time = time.strftime("%H:%M:%S")

            for name, svc_config in services.items():
                result = run_service_check(name, svc_config)
                status = "healthy" if result["healthy"] else "unhealthy"
                latency = (
                    f"{result.get('latency_ms', '-')} ms"
                    if result.get("latency_ms")
                    else "-"
                )
                table.add_row(name, status_badge(status), latency, current_time)

            console.clear()
            console.print(table)
            console.print(f"\n[dim]Next check in {interval}s (Ctrl+C to stop)[/]")
            time.sleep(interval)

    except KeyboardInterrupt:
        console.print("\n")
        info("Stopped watching")
