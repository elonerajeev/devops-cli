"""Website commands for developers.

This module provides commands for developers to:
- List configured websites
- View information about a website
- Check the health of a website
"""

import asyncio
from datetime import datetime
from typing import Optional

import typer
import yaml
from rich.console import Console

from devops_cli.config.websites import load_websites_config, get_website_config
from devops_cli.utils.output import (
    success,
    error,
    warning,
    info,
    header,
    create_table,
    status_badge,
)
from devops_cli.monitoring.checker import HealthChecker, WebsiteConfig, HealthStatus

app = typer.Typer(
    help="Website commands - List, info, and health for configured websites"
)
console = Console()


def get_website_config_for_check(name: str) -> Optional[WebsiteConfig]:
    """Load website config and convert to WebsiteConfig dataclass."""
    website_dict = get_website_config(name)
    if not website_dict:
        return None

    # Extract only fields that WebsiteConfig accepts
    return WebsiteConfig(
        name=website_dict.get("name", name),
        url=website_dict.get("url", ""),
        expected_status=website_dict.get("expected_status", 200),
        timeout=website_dict.get("timeout", 10),
        method=website_dict.get("method", "GET"),
        created_at=website_dict.get("added_at", datetime.now().isoformat()),
    )


@app.command("list")
def list_websites():
    """List all configured websites."""
    websites = load_websites_config()

    if not websites:
        warning("No websites configured")
        info("Ask your cloud engineer to add websites using: devops admin website-add")
        return

    header("Available Websites")

    table = create_table(
        "",
        [
            ("Name", "cyan"),
            ("URL", ""),
            ("Expected Status", "dim"),
            ("Method", "dim"),
            ("Teams", "dim"),
        ],
    )

    for name, website in websites.items():
        teams = ", ".join(website.get("teams", ["default"]))
        table.add_row(
            name,
            website.get("url", "-"),
            str(website.get("expected_status", "N/A")),
            website.get("method", "GET"),
            teams[:20],
        )

    console.print(table)
    info("\nUse 'devops website health <name>' to check status")
    info("Use 'devops website info <name>' for details")


@app.command("info")
def website_info(
    name: str = typer.Argument(..., help="Website name"),
):
    """Show detailed information about a website."""
    website = get_website_config(name)

    if not website:
        error(f"Website '{name}' not found")
        info("Use 'devops website list' to see available websites")
        return

    header(f"Website: {name}")

    console.print(yaml.dump(website, default_flow_style=False))


@app.command("health")
def website_health(
    name: str = typer.Argument(..., help="Website name"),
):
    """Check the health of a specific website."""
    website_config_data = get_website_config(name)

    if not website_config_data:
        error(f"Website '{name}' not found")
        info("Use 'devops website list' to see available websites")
        return

    # Convert to WebsiteConfig dataclass for the checker
    website_config = get_website_config_for_check(name)
    if (
        not website_config
    ):  # Should not happen if website_config_data exists, but for type safety
        error(f"Failed to load WebsiteConfig for '{name}'")
        return

    header(f"Health Check: {name}")
    info(f"URL: {website_config.url}")

    checker = HealthChecker()
    # Run async check in a synchronous context
    result = asyncio.run(checker.check_website(website_config))

    console.print()
    table = create_table("", [("Attribute", "cyan"), ("Value", "")])
    table.add_row("Name", result.name)
    table.add_row("Status", status_badge(result.status.value))
    table.add_row("Message", result.message)
    table.add_row(
        "Response Time",
        (
            f"{result.response_time_ms:.1f}ms"
            if result.response_time_ms is not None
            else "-"
        ),
    )
    table.add_row("Checked At", result.checked_at.strftime("%Y-%m-%d %H:%M:%S"))

    for key, value in result.details.items():
        table.add_row(key.replace("_", " ").title(), str(value))

    console.print(table)
    if result.status == HealthStatus.HEALTHY:
        success(f"Website '{name}' is healthy!")
    elif result.status == HealthStatus.DEGRADED:
        warning(f"Website '{name}' is degraded: {result.message}")
    else:
        error(f"Website '{name}' is unhealthy: {result.message}")
