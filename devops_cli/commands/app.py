"""Dynamic App commands for developers.

This module provides dynamic commands that work with any application
configured by cloud engineers. No hardcoded app names - everything
is read from configuration.

Usage:
    devops app list              # List available apps
    devops app logs <app-name>   # View logs for any app
    devops app health <app-name> # Check health of any app
    devops app info <app-name>   # Show app details
"""

import re
import time
from datetime import datetime
from typing import Optional

import typer
from rich.console import Console

from devops_cli.commands.admin import load_apps_config
from devops_cli.auth import AuthManager
from devops_cli.utils.output import (
    success,
    error,
    warning,
    info,
    header,
    create_table,
    status_badge,
)
# Import utilities (moved from duplicated code)
from devops_cli.utils.time_helpers import parse_time_range
from devops_cli.utils.log_formatters import colorize_log_level, mask_secrets
from devops_cli.utils.aws_helpers import get_aws_session
from devops_cli.utils.completion import complete_app_name

app = typer.Typer(
    help="Application commands - View logs, health, and info for configured apps"
)
console = Console()
auth = AuthManager()


# Try to import boto3
try:
    import boto3
    from botocore.exceptions import ClientError, NoCredentialsError

    BOTO3_AVAILABLE = True
except ImportError:
    BOTO3_AVAILABLE = False


def get_app_config(app_name: str) -> dict | None:
    """Get application configuration by name."""
    config = load_apps_config()
    return config.get("apps", {}).get(app_name)


# ==================== List Apps ====================


@app.command("list")
def list_apps(
    type_filter: Optional[str] = typer.Option(
        None, "--type", "-t", help="Filter by app type"
    ),
):
    """List all available applications."""
    config = load_apps_config()
    apps = config.get("apps", {})

    if not apps:
        warning("No applications configured")
        info("Ask your cloud engineer to add applications using: devops admin app-add")
        return

    header("Available Applications")

    table = create_table(
        "",
        [("Name", "cyan"), ("Type", ""), ("Description", "dim"), ("Log Source", "dim")],
    )

    for name, app_config in apps.items():
        app_type = app_config.get("type", "unknown")

        # Apply filter
        if type_filter and app_type != type_filter:
            continue

        description = app_config.get("description", "-")[:30]
        log_source = app_config.get("logs", {}).get("type", "-")

        table.add_row(name, app_type, description, log_source)

    console.print(table)
    info("\nUse 'devops app logs <name>' to view logs")
    info("Use 'devops app info <name>' for details")
    info("Use 'devops app restart <name>' to restart an application")


# ==================== App Control ====================

@app.command("restart")
def app_restart(
    name: str = typer.Argument(..., help="Application name", autocompletion=complete_app_name),
):
    """Restart an application."""
    check_auth()
    app_config = get_app_config(name)

    if not app_config:
        error(f"Application '{name}' not found")
        return

    app_type = app_config.get("type", "").lower()
    identifier = app_config.get("identifier") or name
    
    header(f"Restarting {name} ({app_type})")
    
    import subprocess
    
    try:
        if app_type == "docker":
            info(f"Running: docker restart {identifier}")
            subprocess.run(["docker", "restart", identifier], check=True)
        elif app_type == "pm2":
            info(f"Running: pm2 restart {identifier}")
            subprocess.run(["pm2", "restart", identifier], check=True)
        elif app_type == "kubernetes" or app_type == "k8s":
            namespace = app_config.get("kubernetes", {}).get("namespace", "default")
            deployment = app_config.get("kubernetes", {}).get("deployment", identifier)
            info(f"Running: kubectl rollout restart deployment/{deployment} -n {namespace}")
            subprocess.run(["kubectl", "rollout", "restart", f"deployment/{deployment}", "-n", namespace], check=True)
        else:
            error(f"Restart not supported for app type: {app_type}")
            return
            
        success(f"Successfully triggered restart for {name}")
    except subprocess.CalledProcessError as e:
        error(f"Failed to restart {name}: {e}")
    except FileNotFoundError as e:
        error(f"Required tool not found: {e.filename}")


@app.command("exec")
def app_exec(
    name: str = typer.Argument(..., help="Application name", autocompletion=complete_app_name),
    command: str = typer.Option("/bin/sh", "--cmd", "-c", help="Command to run"),
):
    """Open an interactive shell in the application container/pod."""
    check_auth()
    app_config = get_app_config(name)

    if not app_config:
        error(f"Application '{name}' not found")
        return

    app_type = app_config.get("type", "").lower()
    identifier = app_config.get("identifier") or name
    
    info(f"Opening shell in {name}...")
    
    import subprocess
    
    try:
        if app_type == "docker":
            subprocess.run(["docker", "exec", "-it", identifier, command])
        elif app_type == "kubernetes" or app_type == "k8s":
            namespace = app_config.get("kubernetes", {}).get("namespace", "default")
            # Try to find a pod for this deployment
            get_pod = subprocess.run(
                ["kubectl", "get", "pods", "-n", namespace, "-l", f"app={identifier}", "-o", "jsonpath={.items[0].metadata.name}"],
                capture_output=True, text=True
            )
            pod_name = get_pod.stdout.strip()
            if not pod_name:
                error(f"No active pods found for {name}")
                return
            subprocess.run(["kubectl", "exec", "-it", pod_name, "-n", namespace, "--", command])
        else:
            error(f"Exec not supported for app type: {app_type}")
    except Exception as e:
        error(f"Failed to execute: {e}")


# ==================== App Info ====================


@app.command("info")
def app_info(
    name: str = typer.Argument(..., help="Application name", autocompletion=complete_app_name),
):
    """Show detailed information about an application."""
    app_config = get_app_config(name)

    if not app_config:
        error(f"Application '{name}' not found")
        info("Use 'devops app list' to see available applications")
        return

    header(f"Application: {name}")

    console.print(f"[bold]Type:[/] {app_config.get('type', 'unknown')}")
    console.print(f"[bold]Description:[/] {app_config.get('description', '-')}")
    console.print()

    # Type-specific info
    app_type = app_config.get("type")

    if app_type == "lambda":
        lam = app_config.get("lambda", {})
        console.print("[bold cyan]Lambda Configuration:[/]")
        console.print(f"  Function: {lam.get('function_name', '-')}")
        console.print(f"  Region: {lam.get('region', '-')}")

    elif app_type == "kubernetes":
        k8s = app_config.get("kubernetes", {})
        console.print("[bold cyan]Kubernetes Configuration:[/]")
        console.print(f"  Namespace: {k8s.get('namespace', '-')}")
        console.print(f"  Deployment: {k8s.get('deployment', '-')}")

    # Logs info
    logs = app_config.get("logs", {})
    if logs:
        console.print()
        console.print("[bold cyan]Log Configuration:[/]")
        console.print(f"  Type: {logs.get('type', '-')}")
        if logs.get("log_group"):
            console.print(f"  Log Group: {logs.get('log_group')}")

    # Health check info
    health = app_config.get("health", {})
    if health:
        console.print()
        console.print("[bold cyan]Health Check:[/]")
        console.print(f"  Type: {health.get('type', '-')}")
        if health.get("url"):
            console.print(f"  URL: {health.get('url')}")

    console.print()
    info("View logs: devops app logs " + name)
    if health:
        info("Check health: devops app health " + name)


# ==================== App Logs ====================


def check_auth():
    """Check if user is authenticated, show message if not."""
    if not auth.is_authenticated():
        error("Authentication required")
        info("Run: devops auth login")
        raise typer.Exit(1)
    return auth.get_current_session()


@app.command("logs")
def app_logs(
    name: str = typer.Argument(..., help="Application name", autocompletion=complete_app_name),
    since: str = typer.Option(
        "1h", "--since", "-s", help="Time range (e.g., 30m, 1h, 2d)"
    ),
    follow: bool = typer.Option(
        False, "--follow", "-f", help="Follow logs in real-time"
    ),
    grep: Optional[str] = typer.Option(None, "--grep", "-g", help="Filter by pattern"),
    limit: int = typer.Option(100, "--limit", "-l", help="Max number of log lines"),
    level: Optional[str] = typer.Option(
        None, "--level", help="Filter by level (error, warn, info)"
    ),
):
    """View logs for an application."""
    check_auth()  # Require authentication

    app_config = get_app_config(name)

    if not app_config:
        error(f"Application '{name}' not found")
        info("Use 'devops app list' to see available applications")
        return

    logs_config = app_config.get("logs", {})
    log_type = logs_config.get("type")

    if not log_type:
        error(f"No log configuration for '{name}'")
        return

    # Add level filter to grep
    if level:
        level_map = {
            "error": "ERROR|FATAL|CRITICAL",
            "warn": "WARN|WARNING",
            "info": "INFO",
            "debug": "DEBUG",
        }
        level_pattern = level_map.get(level.lower(), level.upper())
        grep = (
            level_pattern
            if not grep
            else f"({grep}).*({level_pattern})|({level_pattern}).*({grep})"
        )

    header(f"Logs: {name}")
    info(f"Type: {app_config.get('type')} | Since: {since}")
    if grep:
        info(f"Filter: {grep}")
    console.print()

    if log_type == "cloudwatch":
        _view_cloudwatch_logs(app_config, logs_config, since, follow, grep, limit)
    else:
        error(f"Unsupported live log type: {log_type}")
        info("Note: Uploaded documents can be viewed on the web dashboard.")


def _view_cloudwatch_logs(
    app_config: dict, logs_config: dict, since: str, follow: bool, grep: str, limit: int
):
    """View CloudWatch logs."""
    log_group = logs_config.get("log_group")
    if not log_group:
        error("No log_group configured for this app")
        return

    # Get region
    region = logs_config.get("region")
    if not region:
        if app_config.get("lambda"):
            region = app_config["lambda"].get("region")

    # Get AWS session
    aws_role = app_config.get("aws_role")
    try:
        session = get_aws_session(aws_role, region)
        logs_client = session.client("logs")
    except Exception as e:
        error(f"AWS connection failed: {e}")
        return

    start_time = parse_time_range(since)
    start_timestamp = int(start_time.timestamp() * 1000)

    info(f"Log Group: {log_group}")
    console.print()

    if follow:
        _follow_cloudwatch(logs_client, log_group, grep, start_timestamp)
    else:
        _fetch_cloudwatch(logs_client, log_group, grep, start_timestamp, limit)


def _fetch_cloudwatch(
    client, log_group: str, grep: str, start_timestamp: int, limit: int
):
    """Fetch CloudWatch logs."""
    try:
        kwargs = {
            "logGroupName": log_group,
            "startTime": start_timestamp,
            "limit": limit,
            "interleaved": True,
        }

        response = client.filter_log_events(**kwargs)
        events = response.get("events", [])

        if not events:
            warning("No log events found")
            return

        count = 0
        for event in events:
            message = mask_secrets(event["message"].strip())

            # Apply grep filter
            if grep and not re.search(grep, message, re.IGNORECASE):
                continue

            timestamp = datetime.fromtimestamp(event["timestamp"] / 1000)
            time_str = timestamp.strftime("%H:%M:%S")
            stream = event.get("logStreamName", "")
            if len(stream) > 20:
                stream = stream[:17] + "..."

            console.print(f"[dim]{time_str}[/] [cyan]{stream}[/] ", end="")
            console.print(colorize_log_level(message))
            count += 1

        info(f"\nShowing {count} events")

    except ClientError as e:
        if "ResourceNotFoundException" in str(e):
            error(f"Log group not found: {log_group}")
        else:
            error(f"AWS Error: {e}")


def _follow_cloudwatch(client, log_group: str, grep: str, start_timestamp: int):
    """Follow CloudWatch logs in real-time."""
    info("Following logs (Ctrl+C to stop)...")
    console.print()

    last_timestamp = start_timestamp
    seen_ids = set()

    try:
        while True:
            kwargs = {
                "logGroupName": log_group,
                "startTime": last_timestamp,
                "interleaved": True,
            }

            response = client.filter_log_events(**kwargs)

            for event in response.get("events", []):
                event_id = event["eventId"]
                if event_id in seen_ids:
                    continue

                seen_ids.add(event_id)
                message = mask_secrets(event["message"].strip())

                # Apply grep filter
                if grep and not re.search(grep, message, re.IGNORECASE):
                    continue

                timestamp = datetime.fromtimestamp(event["timestamp"] / 1000)
                time_str = timestamp.strftime("%H:%M:%S")

                console.print(f"[dim]{time_str}[/] ", end="")
                console.print(colorize_log_level(message))

                last_timestamp = max(last_timestamp, event["timestamp"])

            # Limit memory
            if len(seen_ids) > 10000:
                seen_ids = set(list(seen_ids)[-5000:])

            time.sleep(2)

    except KeyboardInterrupt:
        console.print("\n")
        info("Stopped")
    except ClientError as e:
        error(f"AWS Error: {e}")


# ==================== App Health ====================


@app.command("health")
def app_health(
    name: Optional[str] = typer.Argument(None, help="Application name (or check all)", autocompletion=complete_app_name),
):
    """Check health of an application (or all apps)."""
    import asyncio
    from devops_cli.monitoring.checker import HealthChecker
    from devops_cli.monitoring.config import AppConfig

    config = load_apps_config()
    apps = config.get("apps", {})

    if not apps:
        warning("No applications configured")
        return

    # If specific app
    if name:
        if name not in apps:
            error(f"Application '{name}' not found")
            return
        apps_to_check = {name: apps[name]}
    else:
        apps_to_check = apps

    header("Application Health")

    # Prepare configurations for HealthChecker
    monitoring_apps = []
    for app_name, app_config in apps_to_check.items():
        # Map apps.yaml config to AppConfig dataclass
        health_check = app_config.get("health", {})
        
        m_app = AppConfig(
            name=app_name,
            type=app_config.get("type", "custom"),
            identifier=app_name,
            host=health_check.get("host"),
            port=health_check.get("port"),
            health_endpoint=health_check.get("url")
        )
        monitoring_apps.append(m_app)

    # Run checks using HealthChecker
    checker = HealthChecker()
    
    async def run_checks():
        results = []
        for m_app in monitoring_apps:
            results.append(await checker.check_app(m_app))
        return results

    results = asyncio.run(run_checks())

    table = create_table(
        "",
        [
            ("Application", "cyan"),
            ("Status", ""),
            ("Latency", "dim"),
            ("Details", "dim"),
        ],
    )

    for res in results:
        latency_str = f"{res.response_time_ms:.0f}ms" if res.response_time_ms is not None else "-"
        table.add_row(
            res.name,
            status_badge(res.status.value),
            latency_str,
            res.message
        )

    console.print(table)


# ==================== App Errors ====================


@app.command("errors")
def app_errors(
    name: Optional[str] = typer.Argument(None, help="Application name (or check all)", autocompletion=complete_app_name),
    since: str = typer.Option("6h", "--since", "-s", help="Time range"),
):
    """View error logs from applications."""
    check_auth()  # Require authentication

    # Use the logs command with error filter
    config = load_apps_config()
    apps = config.get("apps", {})

    if not apps:
        warning("No applications configured")
        return

    if name:
        if name not in apps:
            error(f"Application '{name}' not found")
            return
        apps = {name: apps[name]}

    header("Error Logs")

    for app_name, app_config in apps.items():
        logs_config = app_config.get("logs", {})
        log_type = logs_config.get("type")

        if log_type != "cloudwatch":
            continue

        console.print(f"\n[bold cyan]{app_name}[/]")
        console.print("-" * 40)

        try:
            log_group = logs_config.get("log_group")
            region = logs_config.get("region")
            aws_role = app_config.get("aws_role")

            session = get_aws_session(aws_role, region)
            logs_client = session.client("logs")

            start_time = parse_time_range(since)
            start_timestamp = int(start_time.timestamp() * 1000)

            response = logs_client.filter_log_events(
                logGroupName=log_group,
                startTime=start_timestamp,
                filterPattern="?ERROR ?FATAL ?CRITICAL ?Exception",
                limit=20,
            )

            events = response.get("events", [])

            if not events:
                success("No errors found!")
            else:
                warning(f"Found {len(events)} errors")
                for event in events[:10]:
                    timestamp = datetime.fromtimestamp(event["timestamp"] / 1000)
                    message = mask_secrets(event["message"].strip())[:150]
                    console.print(
                        f"[dim]{timestamp.strftime('%H:%M:%S')}[/] [red]{message}[/]"
                    )

        except Exception as e:
            error(f"Failed to fetch: {e}")

    console.print()


# ==================== Quick Search ====================


@app.command("search")
def app_search(
    pattern: str = typer.Argument(..., help="Search pattern"),
    name: Optional[str] = typer.Option(
        None, "--app", "-a", help="Specific app (or search all)", autocompletion=complete_app_name
    ),
    since: str = typer.Option("1h", "--since", "-s", help="Time range"),
):
    """Search logs across applications."""
    check_auth()  # Require authentication

    config = load_apps_config()
    apps = config.get("apps", {})

    if not apps:
        warning("No applications configured")
        return

    if name:
        if name not in apps:
            error(f"Application '{name}' not found")
            return
        apps = {name: apps[name]}

    header(f"Searching: {pattern}")

    total_matches = 0

    for app_name, app_config in apps.items():
        logs_config = app_config.get("logs", {})
        log_type = logs_config.get("type")

        if log_type != "cloudwatch":
            continue

        try:
            log_group = logs_config.get("log_group")
            aws_role = app_config.get("aws_role")

            session = get_aws_session(aws_role)
            logs_client = session.client("logs")

            start_time = parse_time_range(since)
            start_timestamp = int(start_time.timestamp() * 1000)

            response = logs_client.filter_log_events(
                logGroupName=log_group,
                startTime=start_timestamp,
                filterPattern=pattern,
                limit=30,
            )

            events = response.get("events", [])

            if events:
                console.print(f"\n[bold cyan]{app_name}[/] ({len(events)} matches)")
                console.print("-" * 40)

                for event in events[:10]:
                    timestamp = datetime.fromtimestamp(event["timestamp"] / 1000)
                    message = mask_secrets(event["message"].strip())[:120]
                    console.print(f"[dim]{timestamp.strftime('%H:%M:%S')}[/] {message}")

                total_matches += len(events)

        except Exception as e:
            warning(f"{app_name}: Failed - {e}")

    console.print()
    info(f"Total: {total_matches} matches")
