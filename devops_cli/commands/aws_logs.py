"""AWS Logs - CloudWatch log viewing for developers."""

import time
from datetime import datetime
from typing import Optional

import typer
from rich.console import Console

from devops_cli.config.settings import load_config
from devops_cli.utils.output import (
    success,
    error,
    warning,
    info,
    header,
    create_table,
)
# Import utilities (moved from duplicated code)
from devops_cli.utils.time_helpers import parse_time_range
from devops_cli.utils.log_formatters import colorize_log_level, mask_secrets
from devops_cli.utils.aws_helpers import get_aws_session_from_credentials
from devops_cli.utils.completion import complete_aws_role

app = typer.Typer(help="AWS Logs - View CloudWatch logs securely")
console = Console()


# ==================== CloudWatch Commands ====================


@app.command("cloudwatch")
def cloudwatch_logs(
    log_group: str = typer.Argument(..., help="CloudWatch log group name"),
    stream: Optional[str] = typer.Option(
        None, "--stream", "-s", help="Specific log stream"
    ),
    since: str = typer.Option("1h", "--since", help="Time range (e.g., 30m, 1h, 2d)"),
    filter_pattern: Optional[str] = typer.Option(
        None, "--filter", "-f", help="CloudWatch filter pattern"
    ),
    grep: Optional[str] = typer.Option(
        None, "--grep", "-g", help="Grep pattern to highlight"
    ),
    limit: int = typer.Option(100, "--limit", "-l", help="Max number of events"),
    follow: bool = typer.Option(
        False, "--follow", "-F", help="Follow logs in real-time"
    ),
    region: Optional[str] = typer.Option(None, "--region", "-r", help="AWS region", autocompletion=complete_aws_role),
):
    """View CloudWatch logs."""
    import boto3
    from botocore.exceptions import ClientError
    
    session = get_aws_session_from_credentials(region)
    logs_client = session.client("logs")

    start_time = parse_time_range(since)
    start_timestamp = int(start_time.timestamp() * 1000)

    header(f"CloudWatch Logs: {log_group}")
    info(f"Since: {start_time.strftime('%Y-%m-%d %H:%M:%S')} UTC")
    if filter_pattern:
        info(f"Filter: {filter_pattern}")
    console.print()

    try:
        if follow:
            _follow_cloudwatch_logs(
                logs_client, log_group, stream, filter_pattern, grep, start_timestamp
            )
        else:
            _fetch_cloudwatch_logs(
                logs_client,
                log_group,
                stream,
                filter_pattern,
                grep,
                start_timestamp,
                limit,
            )
    except ClientError as e:
        error(f"AWS Error: {e.response['Error']['Message']}")
    except KeyboardInterrupt:
        console.print("\n")
        info("Stopped")


def _fetch_cloudwatch_logs(
    client, log_group, stream, filter_pattern, grep, start_timestamp, limit
):
    """Fetch CloudWatch logs."""
    from botocore.exceptions import ClientError
    kwargs = {
        "logGroupName": log_group,
        "startTime": start_timestamp,
        "limit": limit,
        "interleaved": True,
    }

    if stream:
        kwargs["logStreamNames"] = [stream]

    if filter_pattern:
        kwargs["filterPattern"] = filter_pattern

    try:
        response = client.filter_log_events(**kwargs)
        events = response.get("events", [])

        if not events:
            warning("No log events found")
            return

        for event in events:
            timestamp = datetime.fromtimestamp(event["timestamp"] / 1000)
            message = mask_secrets(event["message"].strip())

            # Apply grep filter
            if grep and grep.lower() not in message.lower():
                continue

            time_str = timestamp.strftime("%H:%M:%S")
            stream_name = event.get("logStreamName", "")[:20]

            console.print(f"[dim]{time_str}[/] [cyan]{stream_name}[/] ", end="")
            console.print(colorize_log_level(message))

        info(f"\nShowing {len(events)} events")

    except ClientError as e:
        if "ResourceNotFoundException" in str(e):
            error(f"Log group '{log_group}' not found")
        else:
            raise


def _follow_cloudwatch_logs(
    client, log_group, stream, filter_pattern, grep, start_timestamp
):
    """Follow CloudWatch logs in real-time."""
    from botocore.exceptions import ClientError
    info("Following logs (Ctrl+C to stop)...\n")

    last_timestamp = start_timestamp
    seen_event_ids = set()

    while True:
        kwargs = {
            "logGroupName": log_group,
            "startTime": last_timestamp,
            "interleaved": True,
        }

        if stream:
            kwargs["logStreamNames"] = [stream]

        if filter_pattern:
            kwargs["filterPattern"] = filter_pattern

        try:
            response = client.filter_log_events(**kwargs)
            events = response.get("events", [])

            for event in events:
                event_id = event["eventId"]
                if event_id in seen_event_ids:
                    continue

                seen_event_ids.add(event_id)
                timestamp = datetime.fromtimestamp(event["timestamp"] / 1000)
                message = mask_secrets(event["message"].strip())

                # Apply grep filter
                if grep and grep.lower() not in message.lower():
                    continue

                time_str = timestamp.strftime("%H:%M:%S")
                stream_name = event.get("logStreamName", "")[:20]

                console.print(f"[dim]{time_str}[/] [cyan]{stream_name}[/] ", end="")
                console.print(colorize_log_level(message))

                last_timestamp = max(last_timestamp, event["timestamp"])

            # Limit memory usage
            if len(seen_event_ids) > 10000:
                seen_event_ids = set(list(seen_event_ids)[-5000:])

        except ClientError:
            pass

        time.sleep(2)


@app.command("groups")
def list_log_groups(
    prefix: Optional[str] = typer.Option(
        None, "--prefix", "-p", help="Filter by prefix"
    ),
    region: Optional[str] = typer.Option(None, "--region", "-r", help="AWS region", autocompletion=complete_aws_role),
):
    """List CloudWatch log groups."""
    from botocore.exceptions import ClientError
    session = get_aws_session_from_credentials(region)
    logs_client = session.client("logs")

    header("CloudWatch Log Groups")

    try:
        kwargs = {}
        if prefix:
            kwargs["logGroupNamePrefix"] = prefix

        paginator = logs_client.get_paginator("describe_log_groups")
        log_groups = []

        for page in paginator.paginate(**kwargs):
            log_groups.extend(page.get("logGroups", []))

        if not log_groups:
            warning("No log groups found")
            return

        table = create_table(
            "",
            [
                ("Log Group", "cyan"),
                ("Size", ""),
                ("Retention", "dim"),
                ("Created", "dim"),
            ],
        )

        for lg in log_groups[:50]:  # Limit display
            name = lg["logGroupName"]
            size_bytes = lg.get("storedBytes", 0)
            size = f"{size_bytes / 1024 / 1024:.1f} MB" if size_bytes > 0 else "-"
            retention = lg.get("retentionInDays", "Never")
            created = datetime.fromtimestamp(lg["creationTime"] / 1000).strftime(
                "%Y-%m-%d"
            )

            table.add_row(
                name,
                size,
                str(retention) + " days" if retention != "Never" else "Never",
                created,
            )

        console.print(table)
        info(f"\nTotal: {len(log_groups)} log groups")

    except ClientError as e:
        error(f"AWS Error: {e.response['Error']['Message']}")


@app.command("streams")
def list_log_streams(
    log_group: str = typer.Argument(..., help="Log group name"),
    prefix: Optional[str] = typer.Option(
        None, "--prefix", "-p", help="Filter by prefix"
    ),
    region: Optional[str] = typer.Option(None, "--region", "-r", help="AWS region", autocompletion=complete_aws_role),
):
    """List log streams in a log group."""
    from botocore.exceptions import ClientError
    session = get_aws_session_from_credentials(region)
    logs_client = session.client("logs")

    header(f"Log Streams: {log_group}")

    try:
        kwargs = {
            "logGroupName": log_group,
            "orderBy": "LastEventTime",
            "descending": True,
            "limit": 50,
        }

        if prefix:
            kwargs["logStreamNamePrefix"] = prefix

        response = logs_client.describe_log_streams(**kwargs)
        streams = response.get("logStreams", [])

        if not streams:
            warning("No log streams found")
            return

        table = create_table(
            "", [("Stream", "cyan"), ("Last Event", ""), ("Size", "dim")]
        )

        for stream in streams:
            name = stream["logStreamName"]
            if len(name) > 60:
                name = name[:57] + "..."

            last_event = stream.get("lastEventTimestamp")
            if last_event:
                last_event = datetime.fromtimestamp(last_event / 1000).strftime(
                    "%Y-%m-%d %H:%M"
                )
            else:
                last_event = "-"

            size = stream.get("storedBytes", 0)
            size_str = f"{size / 1024:.1f} KB" if size > 0 else "-"

            table.add_row(name, last_event, size_str)

        console.print(table)

    except ClientError as e:
        error(f"AWS Error: {e.response['Error']['Message']}")


# ==================== Search Commands ====================


@app.command("search")
def search_logs(
    pattern: str = typer.Argument(..., help="Search pattern"),
    log_groups: Optional[str] = typer.Option(
        None, "--groups", "-g", help="Comma-separated log groups"
    ),
    since: str = typer.Option("1h", "--since", help="Time range"),
    region: Optional[str] = typer.Option(None, "--region", "-r", help="AWS region", autocompletion=complete_aws_role),
):
    """Search across multiple log groups."""
    from botocore.exceptions import ClientError
    session = get_aws_session_from_credentials(region)
    logs_client = session.client("logs")

    config = load_config()
    apps = config.get("aws", {}).get("apps", {})

    # Get log groups to search
    if log_groups:
        groups_to_search = [g.strip() for g in log_groups.split(",")]
    else:
        # Search all configured app log groups
        groups_to_search = []
        for app_name, app_config in apps.items():
            if app_config.get("log_group"):
                groups_to_search.append(app_config["log_group"])

        if not groups_to_search:
            error("No log groups specified. Use --groups or configure apps in config")
            return

    header(f"Searching for: {pattern}")
    info(f"Log groups: {', '.join(groups_to_search)}")
    console.print()

    start_time = parse_time_range(since)
    start_timestamp = int(start_time.timestamp() * 1000)

    total_matches = 0

    for log_group in groups_to_search:
        try:
            response = logs_client.filter_log_events(
                logGroupName=log_group,
                startTime=start_timestamp,
                filterPattern=pattern,
                limit=50,
            )

            events = response.get("events", [])
            if events:
                console.print(f"\n[bold cyan]{log_group}[/] ({len(events)} matches)")
                console.print("-" * 60)

                for event in events:
                    timestamp = datetime.fromtimestamp(event["timestamp"] / 1000)
                    message = event["message"].strip()
                    time_str = timestamp.strftime("%H:%M:%S")

                    console.print(f"[dim]{time_str}[/] ", end="")
                    console.print(colorize_log_level(message))

                total_matches += len(events)

        except ClientError as e:
            warning(f"Could not search {log_group}: {e.response['Error']['Message']}")

    console.print()
    info(f"Total: {total_matches} matches across {len(groups_to_search)} log groups")


# ==================== Activity/Audit Commands ====================


@app.command("activity")
def view_activity(
    service: Optional[str] = typer.Option(
        None, "--service", "-s", help="Filter by service"
    ),
    user: Optional[str] = typer.Option(None, "--user", "-u", help="Filter by user"),
    since: str = typer.Option("24h", "--since", help="Time range"),
    region: Optional[str] = typer.Option(None, "--region", "-r", help="AWS region", autocompletion=complete_aws_role),
):
    """View AWS CloudTrail activity (audit logs)."""
    from botocore.exceptions import ClientError
    session = get_aws_session_from_credentials(region)

    try:
        cloudtrail = session.client("cloudtrail")
    except Exception:
        error("CloudTrail client not available")
        return

    header("AWS Activity (CloudTrail)")

    start_time = parse_time_range(since)

    try:
        kwargs = {
            "StartTime": start_time,
            "MaxResults": 50,
        }

        if user:
            kwargs["LookupAttributes"] = [
                {"AttributeKey": "Username", "AttributeValue": user}
            ]

        response = cloudtrail.lookup_events(**kwargs)
        events = response.get("Events", [])

        if not events:
            warning("No activity events found")
            return

        table = create_table(
            "", [("Time", "dim"), ("User", "cyan"), ("Action", ""), ("Resource", "dim")]
        )

        for event in events:
            event_time = event["EventTime"].strftime("%m-%d %H:%M")
            username = event.get("Username", "-")
            event_name = event.get("EventName", "-")

            resources = event.get("Resources", [])
            resource = resources[0]["ResourceName"] if resources else "-"
            if len(resource) > 30:
                resource = resource[:27] + "..."

            # Filter by service if specified
            if service and service.lower() not in event_name.lower():
                continue

            table.add_row(event_time, username, event_name, resource)

        console.print(table)

    except ClientError as e:
        error(f"AWS Error: {e.response['Error']['Message']}")
        info("Note: CloudTrail access may require additional permissions")


@app.command("errors")
def view_errors(
    app: Optional[str] = typer.Option(
        None, "--app", "-a", help="App name (from your apps.yaml config)"
    ),
    since: str = typer.Option("6h", "--since", help="Time range"),
    region: Optional[str] = typer.Option(None, "--region", "-r", help="AWS region", autocompletion=complete_aws_role),
):
    """View error logs from all applications."""
    from botocore.exceptions import ClientError
    session = get_aws_session_from_credentials(region)
    logs_client = session.client("logs")

    config = load_config()
    apps_config = config.get("aws", {}).get("apps", {})

    if app:
        apps_to_check = {app: apps_config.get(app, {})}
    else:
        apps_to_check = apps_config

    if not apps_to_check:
        error("No apps configured. Add to config under aws.apps")
        return

    header("Error Logs")

    start_time = parse_time_range(since)
    start_timestamp = int(start_time.timestamp() * 1000)

    error_patterns = [
        "ERROR",
        "Exception",
        "FATAL",
        "CRITICAL",
        "Traceback",
    ]

    filter_pattern = " ".join([f'?"{p}"' for p in error_patterns])

    for app_name, app_config in apps_to_check.items():
        log_group = app_config.get("log_group")
        if not log_group:
            continue

        try:
            response = logs_client.filter_log_events(
                logGroupName=log_group,
                startTime=start_timestamp,
                filterPattern=filter_pattern,
                limit=30,
            )

            events = response.get("events", [])

            console.print(f"\n[bold]{app_name.upper()}[/] - {len(events)} errors")
            console.print("-" * 50)

            if not events:
                success("No errors found!")
                continue

            for event in events[:10]:
                timestamp = datetime.fromtimestamp(event["timestamp"] / 1000)
                message = event["message"].strip()[:200]
                time_str = timestamp.strftime("%m-%d %H:%M:%S")

                console.print(f"[dim]{time_str}[/] [red]{message}[/]")

            if len(events) > 10:
                warning(f"  ... and {len(events) - 10} more errors")

        except ClientError as e:
            warning(f"Could not check {app_name}: {e.response['Error']['Message']}")

    console.print()


# ==================== Configuration ====================


@app.command("configure")
def configure_aws():
    """Show AWS configuration help."""
    header("AWS Logs Configuration")

    console.print("""
Add the following to your [bold]~/.devops-cli/config.yaml[/]:

[cyan]aws:
  # AWS credentials profile (from ~/.aws/credentials)
  profile: "dev-readonly"

  # Default region
  region: "us-east-1"

  # Default ECS cluster
  ecs_cluster: "production-cluster"

  # Application configurations
  apps:
    zintellix:
      # ECS service
      cluster: "production-cluster"
      service: "zintellix-backend"
      log_group: "/ecs/zintellix-backend"[/]

[bold]Setting up AWS credentials for developers:[/]

1. Create a read-only IAM user/role with these permissions:
   - logs:DescribeLogGroups
   - logs:DescribeLogStreams
   - logs:FilterLogEvents
   - logs:GetLogEvents
   - ecs:DescribeServices
   - ecs:DescribeTasks
   - ecs:ListTasks

2. Configure credentials:
   [dim]aws configure --profile dev-readonly[/]

3. Test access:
   [dim]devops aws groups --profile dev-readonly[/]

[bold]Quick commands:[/]
   devops aws cloudwatch <group>     # View any log group
   devops aws zintellix --since 2h  # Zintellix logs from last 2 hours
   devops aws errors                # View all errors
   devops aws search "ERROR"        # Search across all apps
""")
