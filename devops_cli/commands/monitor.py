"""Monitor commands - Real-time dashboard for websites, apps, and servers."""

import typer
from typing import Optional
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import box

from ..monitoring import MonitoringConfig, MonitorDashboard, HealthChecker
from ..monitoring.config import WebsiteConfig, AppConfig, ServerConfig
from ..monitoring.dashboard import SimpleMonitorDashboard

app = typer.Typer(help="Real-time monitoring dashboard for infrastructure")
console = Console()


@app.callback(invoke_without_command=True)
def monitor_default(
    ctx: typer.Context,
    refresh: int = typer.Option(5, "--refresh", "-r", help="Refresh interval in seconds"),
    once: bool = typer.Option(False, "--once", "-1", help="Check once and exit (no live dashboard)")
):
    """
    Launch the real-time monitoring dashboard.

    Shows status of all configured websites, applications, and servers
    with automatic refresh like PM2 monit.

    Examples:
        devops monitor              # Start live dashboard
        devops monitor --once       # Check once and exit
        devops monitor -r 10        # Refresh every 10 seconds
    """
    if ctx.invoked_subcommand is None:
        config = MonitoringConfig()
        counts = config.get_resource_counts()

        if counts["websites"] == 0 and counts["apps"] == 0 and counts["servers"] == 0:
            console.print()
            console.print(Panel(
                "[yellow]No resources configured for monitoring.[/yellow]\n\n"
                "Add resources using:\n"
                "  [cyan]devops monitor add-website[/cyan] --name mysite --url https://example.com\n"
                "  [cyan]devops monitor add-app[/cyan] --name myapp --type docker --identifier container-name\n"
                "  [cyan]devops monitor add-server[/cyan] --name web1 --host 10.0.1.10",
                title="[bold]Monitor Setup Required[/bold]",
                box=box.ROUNDED
            ))
            raise typer.Exit(0)

        if once:
            # Single check mode
            dashboard = SimpleMonitorDashboard(config)
            dashboard.run()
        else:
            # Live dashboard mode
            console.print("[dim]Starting monitor dashboard... Press Ctrl+C to exit[/dim]")
            dashboard = MonitorDashboard(config)
            dashboard.run(refresh_interval=refresh)


@app.command("status")
def status():
    """Show current status of all monitored resources (single check)."""
    config = MonitoringConfig()
    dashboard = SimpleMonitorDashboard(config)
    dashboard.run()


@app.command("list")
def list_resources():
    """List all configured monitoring resources."""
    config = MonitoringConfig()

    websites = config.get_all_websites()
    apps = config.get_all_apps()
    servers = config.get_all_servers()

    console.print()

    # Websites table
    if websites:
        table = Table(title="[bold blue]Websites[/bold blue]", box=box.ROUNDED)
        table.add_column("Name", style="cyan")
        table.add_column("URL")
        table.add_column("Expected", justify="center")
        table.add_column("Timeout", justify="center")
        table.add_column("Enabled", justify="center")

        for w in websites:
            enabled = "[green]Yes[/green]" if w.enabled else "[red]No[/red]"
            table.add_row(w.name, w.url, str(w.expected_status), f"{w.timeout}s", enabled)

        console.print(table)
        console.print()

    # Apps table
    if apps:
        table = Table(title="[bold magenta]Applications[/bold magenta]", box=box.ROUNDED)
        table.add_column("Name", style="cyan")
        table.add_column("Type")
        table.add_column("Identifier")
        table.add_column("Host")
        table.add_column("Enabled", justify="center")

        for a in apps:
            enabled = "[green]Yes[/green]" if a.enabled else "[red]No[/red]"
            table.add_row(a.name, a.type, a.identifier, a.host or "--", enabled)

        console.print(table)
        console.print()

    # Servers table
    if servers:
        table = Table(title="[bold green]Servers[/bold green]", box=box.ROUNDED)
        table.add_column("Name", style="cyan")
        table.add_column("Host")
        table.add_column("Port", justify="center")
        table.add_column("Check Type")
        table.add_column("Enabled", justify="center")

        for s in servers:
            enabled = "[green]Yes[/green]" if s.enabled else "[red]No[/red]"
            table.add_row(s.name, s.host, str(s.port), s.check_type, enabled)

        console.print(table)
        console.print()

    if not websites and not apps and not servers:
        console.print("[yellow]No resources configured.[/yellow]")
        console.print("Use [cyan]devops monitor add-website/add-app/add-server[/cyan] to add resources.")


@app.command("add-website")
def add_website(
    name: str = typer.Option(..., "--name", "-n", help="Unique name for the website"),
    url: str = typer.Option(..., "--url", "-u", help="URL to monitor"),
    expected_status: int = typer.Option(200, "--status", "-s", help="Expected HTTP status code"),
    timeout: int = typer.Option(10, "--timeout", "-t", help="Request timeout in seconds"),
    method: str = typer.Option("GET", "--method", "-m", help="HTTP method (GET, HEAD, POST)")
):
    """
    Add a website to monitor.

    Examples:
        devops monitor add-website --name main-site --url https://example.com
        devops monitor add-website -n api -u https://api.example.com/health -s 200
        devops monitor add-website -n blog -u https://blog.example.com --timeout 5
    """
    config = MonitoringConfig()

    website = WebsiteConfig(
        name=name,
        url=url,
        expected_status=expected_status,
        timeout=timeout,
        method=method.upper()
    )

    if config.add_website(website):
        console.print(f"[green]Website '{name}' added successfully.[/green]")
        console.print(f"  URL: {url}")
        console.print(f"  Expected: HTTP {expected_status}")
        console.print(f"  Timeout: {timeout}s")
    else:
        console.print(f"[red]Website '{name}' already exists.[/red]")
        raise typer.Exit(1)


@app.command("add-app")
def add_app(
    name: str = typer.Option(..., "--name", "-n", help="Unique name for the application"),
    app_type: str = typer.Option(..., "--type", "-t", help="App type: docker, pm2, process, http, port"),
    identifier: str = typer.Option(..., "--identifier", "-i", help="Container name, process name, or service ID"),
    host: Optional[str] = typer.Option(None, "--host", "-H", help="Host address (for remote apps)"),
    port: Optional[int] = typer.Option(None, "--port", "-p", help="Port number"),
    health_endpoint: Optional[str] = typer.Option(None, "--health", help="Health check endpoint (e.g., /health)")
):
    """
    Add an application to monitor.

    Supported types:
    - docker: Monitor Docker container by name
    - pm2: Monitor PM2 process by name
    - process: Monitor system process by name pattern
    - http: Monitor via HTTP health endpoint
    - port: Monitor by checking if port is open

    Examples:
        devops monitor add-app --name api --type docker --identifier api-container
        devops monitor add-app -n worker -t pm2 -i background-worker
        devops monitor add-app -n redis -t port -H localhost -p 6379
        devops monitor add-app -n backend -t http -H localhost -p 8080 --health /api/health
    """
    config = MonitoringConfig()

    valid_types = ["docker", "pm2", "process", "http", "port"]
    if app_type.lower() not in valid_types:
        console.print(f"[red]Invalid app type '{app_type}'. Must be one of: {', '.join(valid_types)}[/red]")
        raise typer.Exit(1)

    app_config = AppConfig(
        name=name,
        type=app_type.lower(),
        identifier=identifier,
        host=host,
        port=port,
        health_endpoint=health_endpoint
    )

    if config.add_app(app_config):
        console.print(f"[green]Application '{name}' added successfully.[/green]")
        console.print(f"  Type: {app_type}")
        console.print(f"  Identifier: {identifier}")
        if host:
            console.print(f"  Host: {host}")
        if port:
            console.print(f"  Port: {port}")
    else:
        console.print(f"[red]Application '{name}' already exists.[/red]")
        raise typer.Exit(1)


@app.command("add-server")
def add_server(
    name: str = typer.Option(..., "--name", "-n", help="Unique name for the server"),
    host: str = typer.Option(..., "--host", "-H", help="Server hostname or IP"),
    port: int = typer.Option(22, "--port", "-p", help="Port to check (default: 22 for SSH)"),
    check_type: str = typer.Option("ping", "--check", "-c", help="Check type: ping, ssh, http, port")
):
    """
    Add a server to monitor.

    Check types:
    - ping: ICMP ping (default, fast)
    - ssh: Check SSH port is responding
    - http: Check HTTP endpoint
    - port: Check if specific port is open

    Examples:
        devops monitor add-server --name web1 --host 10.0.1.10
        devops monitor add-server -n db-master -H 10.0.2.10 -c ssh
        devops monitor add-server -n nginx -H 10.0.1.10 -p 80 -c http
        devops monitor add-server -n redis -H 10.0.3.10 -p 6379 -c port
    """
    config = MonitoringConfig()

    valid_checks = ["ping", "ssh", "http", "port"]
    if check_type.lower() not in valid_checks:
        console.print(f"[red]Invalid check type '{check_type}'. Must be one of: {', '.join(valid_checks)}[/red]")
        raise typer.Exit(1)

    server = ServerConfig(
        name=name,
        host=host,
        port=port,
        check_type=check_type.lower()
    )

    if config.add_server(server):
        console.print(f"[green]Server '{name}' added successfully.[/green]")
        console.print(f"  Host: {host}")
        console.print(f"  Port: {port}")
        console.print(f"  Check: {check_type}")
    else:
        console.print(f"[red]Server '{name}' already exists.[/red]")
        raise typer.Exit(1)


@app.command("remove")
def remove_resource(
    name: str = typer.Argument(..., help="Name of the resource to remove"),
    resource_type: str = typer.Option(
        None, "--type", "-t",
        help="Resource type: website, app, server (auto-detected if unique)"
    ),
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation")
):
    """
    Remove a monitored resource.

    Examples:
        devops monitor remove main-site
        devops monitor remove api --type app
        devops monitor remove web1 -t server -f
    """
    config = MonitoringConfig()

    # Try to find the resource
    found = []
    if config.remove_website(name) if resource_type == "website" else False:
        found.append("website")
    if config.remove_app(name) if resource_type == "app" else False:
        found.append("app")
    if config.remove_server(name) if resource_type == "server" else False:
        found.append("server")

    # If no type specified, try all
    if not resource_type:
        websites = [w for w in config.get_all_websites() if w.name == name]
        apps = [a for a in config.get_all_apps() if a.name == name]
        servers = [s for s in config.get_all_servers() if s.name == name]

        if websites:
            found.append("website")
        if apps:
            found.append("app")
        if servers:
            found.append("server")

        if len(found) > 1:
            console.print(f"[yellow]Multiple resources named '{name}' found: {', '.join(found)}[/yellow]")
            console.print("Please specify --type to remove a specific one.")
            raise typer.Exit(1)

        if not found:
            console.print(f"[red]Resource '{name}' not found.[/red]")
            raise typer.Exit(1)

        resource_type = found[0]

    # Confirm removal
    if not force:
        confirm = typer.confirm(f"Remove {resource_type} '{name}'?")
        if not confirm:
            console.print("[yellow]Cancelled.[/yellow]")
            raise typer.Exit(0)

    # Remove
    removed = False
    if resource_type == "website":
        removed = config.remove_website(name)
    elif resource_type == "app":
        removed = config.remove_app(name)
    elif resource_type == "server":
        removed = config.remove_server(name)

    if removed:
        console.print(f"[green]{resource_type.capitalize()} '{name}' removed.[/green]")
    else:
        console.print(f"[red]Failed to remove '{name}'.[/red]")
        raise typer.Exit(1)


@app.command("settings")
def settings(
    refresh_interval: Optional[int] = typer.Option(None, "--refresh", "-r", help="Set refresh interval (seconds)"),
    show: bool = typer.Option(False, "--show", "-s", help="Show current settings")
):
    """
    View or update monitoring settings.

    Examples:
        devops monitor settings --show
        devops monitor settings --refresh 10
    """
    config = MonitoringConfig()

    if refresh_interval:
        config.update_settings(refresh_interval=refresh_interval)
        console.print(f"[green]Refresh interval set to {refresh_interval} seconds.[/green]")

    if show or not refresh_interval:
        current = config.get_settings()
        console.print()
        console.print(Panel(
            f"[bold]Refresh Interval:[/bold] {current.get('refresh_interval', 5)} seconds\n"
            f"[bold]Alert on Failure:[/bold] {current.get('alert_on_failure', True)}\n"
            f"[bold]Failure Threshold:[/bold] {current.get('failure_threshold', 3)} consecutive failures\n"
            f"[bold]History Retention:[/bold] {current.get('history_retention_hours', 24)} hours",
            title="[bold cyan]Monitoring Settings[/bold cyan]",
            box=box.ROUNDED
        ))


@app.command("demo")
def demo():
    """
    Add demo resources for testing the dashboard.

    Adds sample websites, apps, and servers for demonstration.
    """
    config = MonitoringConfig()

    # Add demo websites
    demo_websites = [
        WebsiteConfig(name="google", url="https://www.google.com"),
        WebsiteConfig(name="github", url="https://github.com"),
        WebsiteConfig(name="httpbin", url="https://httpbin.org/status/200"),
    ]

    # Add demo servers (localhost checks)
    demo_servers = [
        ServerConfig(name="localhost", host="127.0.0.1", check_type="ping"),
    ]

    added_count = 0

    console.print("[cyan]Adding demo resources...[/cyan]")

    for website in demo_websites:
        if config.add_website(website):
            console.print(f"  [green]+[/green] Website: {website.name} ({website.url})")
            added_count += 1
        else:
            console.print(f"  [yellow]-[/yellow] Website: {website.name} (already exists)")

    for server in demo_servers:
        if config.add_server(server):
            console.print(f"  [green]+[/green] Server: {server.name} ({server.host})")
            added_count += 1
        else:
            console.print(f"  [yellow]-[/yellow] Server: {server.name} (already exists)")

    console.print()
    console.print(f"[green]Added {added_count} demo resources.[/green]")
    console.print("Run [cyan]devops monitor[/cyan] to see the dashboard.")


# Export the app
monitor_app = app
