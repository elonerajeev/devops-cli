"""Real-time monitoring dashboard using Rich Live display - Premium Edition."""

import asyncio
from datetime import datetime
from typing import Optional

from rich.console import Console, Group
from rich.live import Live
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich.align import Align
from rich import box

from .config import MonitoringConfig
from .checker import HealthChecker, HealthResult, HealthStatus


# Premium Color Scheme
class Colors:
    """Premium color palette."""

    # Primary colors
    PRIMARY = "#00D4FF"  # Cyan
    SECONDARY = "#7C3AED"  # Purple
    ACCENT = "#F59E0B"  # Amber

    # Status colors
    HEALTHY = "#10B981"  # Emerald green
    UNHEALTHY = "#EF4444"  # Red
    DEGRADED = "#F59E0B"  # Amber
    UNKNOWN = "#6B7280"  # Gray

    # Background accents
    HEADER_BG = "#1E293B"  # Slate
    CARD_BORDER = "#334155"  # Slate border

    # Text colors
    TEXT_PRIMARY = "#F8FAFC"
    TEXT_SECONDARY = "#94A3B8"
    TEXT_MUTED = "#64748B"


# Premium Icons
class Icons:
    """Unicode icons for status display."""

    # Status icons
    HEALTHY = "✓"
    UNHEALTHY = "✗"
    DEGRADED = "⚠"
    UNKNOWN = "?"
    CHECKING = "◐"

    # Resource type icons
    WEBSITE = "🌐"
    APP = "📦"
    SERVER = "🖥"

    # Metric icons
    CPU = "⚡"
    MEMORY = "💾"
    RESPONSE = "⏱"
    UPTIME = "📈"

    # Other
    BULLET = "›"
    DOT = "•"
    ARROW_UP = "↑"
    ARROW_DOWN = "↓"
    REFRESH = "↻"


class MonitorDashboard:
    """Premium real-time monitoring dashboard."""

    def __init__(self, config: Optional[MonitoringConfig] = None):
        self.config = config or MonitoringConfig()
        self.checker = HealthChecker()
        self.console = Console()
        self._running = False
        self._last_results: dict = {"websites": [], "apps": [], "servers": []}
        self._check_count = 0
        self._start_time: Optional[datetime] = None

    def _get_status_style(self, status: HealthStatus) -> tuple[str, str, str]:
        """Get icon, color, and label for status."""
        styles = {
            HealthStatus.HEALTHY: (Icons.HEALTHY, Colors.HEALTHY, "ONLINE"),
            HealthStatus.UNHEALTHY: (Icons.UNHEALTHY, Colors.UNHEALTHY, "OFFLINE"),
            HealthStatus.DEGRADED: (Icons.DEGRADED, Colors.DEGRADED, "DEGRADED"),
            HealthStatus.UNKNOWN: (Icons.UNKNOWN, Colors.UNKNOWN, "UNKNOWN"),
            HealthStatus.CHECKING: (Icons.CHECKING, Colors.PRIMARY, "CHECKING"),
        }
        return styles.get(status, (Icons.UNKNOWN, Colors.UNKNOWN, "UNKNOWN"))

    def _create_header(self) -> Panel:
        """Create premium dashboard header."""
        summary = self.checker.get_summary()
        counts = self.config.get_resource_counts()

        # Calculate uptime
        uptime = "00:00:00"
        if self._start_time:
            delta = datetime.now() - self._start_time
            hours, remainder = divmod(int(delta.total_seconds()), 3600)
            minutes, seconds = divmod(remainder, 60)
            uptime = f"{hours:02d}:{minutes:02d}:{seconds:02d}"

        # Build header content
        title = Text()
        title.append("  DEVOPS ", style=f"bold {Colors.PRIMARY}")
        title.append("MONITOR  ", style=f"bold {Colors.TEXT_PRIMARY}")

        # Stats line
        stats = Text()
        stats.append(f"  {Icons.REFRESH} ", style=Colors.TEXT_MUTED)
        stats.append(f"Checks: {self._check_count}", style=Colors.TEXT_SECONDARY)
        stats.append("  │  ", style=Colors.TEXT_MUTED)
        stats.append(f"Uptime: {uptime}", style=Colors.TEXT_SECONDARY)
        stats.append("  │  ", style=Colors.TEXT_MUTED)
        stats.append(f"{Icons.WEBSITE} {counts['websites']}  ", style=Colors.PRIMARY)
        stats.append(f"{Icons.APP} {counts['apps']}  ", style=Colors.SECONDARY)
        stats.append(f"{Icons.SERVER} {counts['servers']}", style=Colors.ACCENT)

        # Status summary boxes
        healthy = summary.get("healthy", 0)
        degraded = summary.get("degraded", 0)
        unhealthy = summary.get("unhealthy", 0)

        status_line = Text()
        status_line.append(f"\n  {Icons.HEALTHY} ", style=f"bold {Colors.HEALTHY}")
        status_line.append(f"{healthy} Online", style=Colors.HEALTHY)
        status_line.append("    ", style="")
        status_line.append(f"{Icons.DEGRADED} ", style=f"bold {Colors.DEGRADED}")
        status_line.append(f"{degraded} Degraded", style=Colors.DEGRADED)
        status_line.append("    ", style="")
        status_line.append(f"{Icons.UNHEALTHY} ", style=f"bold {Colors.UNHEALTHY}")
        status_line.append(f"{unhealthy} Offline", style=Colors.UNHEALTHY)

        content = Text()
        content.append_text(title)
        content.append("\n")
        content.append_text(stats)
        content.append_text(status_line)

        return Panel(
            Align.center(content),
            box=box.DOUBLE,
            border_style=Colors.PRIMARY,
            padding=(0, 2),
        )

    def _create_websites_table(self, results: list[HealthResult]) -> Panel:
        """Create premium websites status table."""
        table = Table(
            box=box.SIMPLE_HEAD,
            expand=True,
            show_header=True,
            header_style=f"bold {Colors.TEXT_SECONDARY}",
            row_styles=[f"dim {Colors.TEXT_PRIMARY}", Colors.TEXT_PRIMARY],
            padding=(0, 1),
            collapse_padding=True,
        )

        table.add_column("STATUS", justify="center", width=10)
        table.add_column("NAME", style=Colors.TEXT_PRIMARY, min_width=16)
        table.add_column(f"{Icons.RESPONSE} RESPONSE", justify="right", width=12)
        table.add_column(f"{Icons.UPTIME} UPTIME", justify="right", width=10)
        table.add_column("MESSAGE", style=Colors.TEXT_MUTED, min_width=18)

        if not results:
            table.add_row(
                f"[{Colors.TEXT_MUTED}]--[/]",
                f"[{Colors.TEXT_MUTED}]No websites configured[/]",
                "",
                "",
                "",
            )
        else:
            for result in results:
                icon, color, label = self._get_status_style(result.status)

                status_cell = Text()
                status_cell.append(f" {icon} ", style=f"bold {color}")
                status_cell.append(label, style=f"bold {color}")

                response = (
                    f"{result.response_time_ms:.0f}ms"
                    if result.response_time_ms
                    else "--"
                )
                uptime = (
                    f"{result.uptime_percent:.1f}%" if result.uptime_percent else "--"
                )

                # Color code response time
                if result.response_time_ms:
                    if result.response_time_ms < 500:
                        response = f"[{Colors.HEALTHY}]{response}[/]"
                    elif result.response_time_ms < 1500:
                        response = f"[{Colors.DEGRADED}]{response}[/]"
                    else:
                        response = f"[{Colors.UNHEALTHY}]{response}[/]"

                table.add_row(
                    status_cell, result.name, response, uptime, result.message
                )

        title_text = Text()
        title_text.append(f" {Icons.WEBSITE} ", style=f"bold {Colors.PRIMARY}")
        title_text.append("WEBSITES ", style=f"bold {Colors.PRIMARY}")
        title_text.append(f"({len(results)})", style=Colors.TEXT_MUTED)

        return Panel(
            table,
            title=title_text,
            title_align="left",
            box=box.ROUNDED,
            border_style=Colors.PRIMARY,
            padding=(0, 1),
        )

    def _create_apps_table(self, results: list[HealthResult]) -> Panel:
        """Create premium applications status table."""
        table = Table(
            box=box.SIMPLE_HEAD,
            expand=True,
            show_header=True,
            header_style=f"bold {Colors.TEXT_SECONDARY}",
            row_styles=[f"dim {Colors.TEXT_PRIMARY}", Colors.TEXT_PRIMARY],
            padding=(0, 1),
            collapse_padding=True,
        )

        table.add_column("STATUS", justify="center", width=10)
        table.add_column("NAME", style=Colors.TEXT_PRIMARY, min_width=16)
        table.add_column("TYPE", justify="center", width=10)
        table.add_column(f"{Icons.CPU} CPU", justify="right", width=8)
        table.add_column(f"{Icons.MEMORY} MEM", justify="right", width=10)
        table.add_column("RESTARTS", justify="center", width=10)

        if not results:
            table.add_row(
                f"[{Colors.TEXT_MUTED}]--[/]",
                f"[{Colors.TEXT_MUTED}]No apps configured[/]",
                "",
                "",
                "",
                "",
            )
        else:
            for result in results:
                icon, color, label = self._get_status_style(result.status)

                status_cell = Text()
                status_cell.append(f" {icon} ", style=f"bold {color}")
                status_cell.append(label, style=f"bold {color}")

                app_type = result.details.get("type", "--").upper()
                cpu = result.details.get("cpu", "--")
                memory = result.details.get(
                    "memory", result.details.get("memory_percent", "--")
                )
                restarts = result.details.get("restarts", "--")

                # Type badge color
                type_colors = {
                    "DOCKER": Colors.PRIMARY,
                    "PM2": Colors.HEALTHY,
                    "PROCESS": Colors.ACCENT,
                    "HTTP": Colors.SECONDARY,
                    "PORT": Colors.TEXT_SECONDARY,
                }
                type_color = type_colors.get(app_type, Colors.TEXT_MUTED)
                app_type_styled = f"[{type_color}]{app_type}[/]"

                # Restart warning
                if restarts != "--" and int(restarts) > 0:
                    restarts = f"[{Colors.DEGRADED}]{restarts}[/]"

                table.add_row(
                    status_cell,
                    result.name,
                    app_type_styled,
                    cpu,
                    memory,
                    str(restarts),
                )

        title_text = Text()
        title_text.append(f" {Icons.APP} ", style=f"bold {Colors.SECONDARY}")
        title_text.append("APPLICATIONS ", style=f"bold {Colors.SECONDARY}")
        title_text.append(f"({len(results)})", style=Colors.TEXT_MUTED)

        return Panel(
            table,
            title=title_text,
            title_align="left",
            box=box.ROUNDED,
            border_style=Colors.SECONDARY,
            padding=(0, 1),
        )

    def _create_servers_table(self, results: list[HealthResult]) -> Panel:
        """Create premium servers status table."""
        table = Table(
            box=box.SIMPLE_HEAD,
            expand=True,
            show_header=True,
            header_style=f"bold {Colors.TEXT_SECONDARY}",
            row_styles=[f"dim {Colors.TEXT_PRIMARY}", Colors.TEXT_PRIMARY],
            padding=(0, 1),
            collapse_padding=True,
        )

        table.add_column("STATUS", justify="center", width=10)
        table.add_column("NAME", style=Colors.TEXT_PRIMARY, min_width=14)
        table.add_column("HOST", min_width=16)
        table.add_column("CHECK", justify="center", width=8)
        table.add_column(f"{Icons.RESPONSE} PING", justify="right", width=10)
        table.add_column(f"{Icons.UPTIME} UPTIME", justify="right", width=10)

        if not results:
            table.add_row(
                f"[{Colors.TEXT_MUTED}]--[/]",
                f"[{Colors.TEXT_MUTED}]No servers configured[/]",
                "",
                "",
                "",
                "",
            )
        else:
            for result in results:
                icon, color, label = self._get_status_style(result.status)

                status_cell = Text()
                status_cell.append(f" {icon} ", style=f"bold {color}")
                status_cell.append(label, style=f"bold {color}")

                host = result.details.get("host", "--")
                check_type = result.details.get("check", "--").upper()
                response = (
                    f"{result.response_time_ms:.0f}ms"
                    if result.response_time_ms
                    else "--"
                )
                uptime = (
                    f"{result.uptime_percent:.1f}%" if result.uptime_percent else "--"
                )

                # Color code response time
                if result.response_time_ms:
                    if result.response_time_ms < 100:
                        response = f"[{Colors.HEALTHY}]{response}[/]"
                    elif result.response_time_ms < 300:
                        response = f"[{Colors.DEGRADED}]{response}[/]"
                    else:
                        response = f"[{Colors.UNHEALTHY}]{response}[/]"

                # Check type colors
                check_colors = {
                    "PING": Colors.HEALTHY,
                    "SSH": Colors.PRIMARY,
                    "HTTP": Colors.SECONDARY,
                    "PORT": Colors.ACCENT,
                }
                check_color = check_colors.get(check_type, Colors.TEXT_MUTED)
                check_styled = f"[{check_color}]{check_type}[/]"

                table.add_row(
                    status_cell,
                    result.name,
                    f"[{Colors.TEXT_SECONDARY}]{host}[/]",
                    check_styled,
                    response,
                    uptime,
                )

        title_text = Text()
        title_text.append(f" {Icons.SERVER} ", style=f"bold {Colors.ACCENT}")
        title_text.append("SERVERS ", style=f"bold {Colors.ACCENT}")
        title_text.append(f"({len(results)})", style=Colors.TEXT_MUTED)

        return Panel(
            table,
            title=title_text,
            title_align="left",
            box=box.ROUNDED,
            border_style=Colors.ACCENT,
            padding=(0, 1),
        )

    def _create_footer(self) -> Panel:
        """Create dashboard footer with controls."""
        settings = self.config.get_settings()
        refresh = settings.get("refresh_interval", 5)

        footer = Text()
        footer.append("  [", style=Colors.TEXT_MUTED)
        footer.append("q", style=f"bold {Colors.PRIMARY}")
        footer.append("] Quit  ", style=Colors.TEXT_MUTED)
        footer.append("[", style=Colors.TEXT_MUTED)
        footer.append("r", style=f"bold {Colors.PRIMARY}")
        footer.append("] Refresh  ", style=Colors.TEXT_MUTED)
        footer.append("[", style=Colors.TEXT_MUTED)
        footer.append("Ctrl+C", style=f"bold {Colors.UNHEALTHY}")
        footer.append("] Exit  ", style=Colors.TEXT_MUTED)
        footer.append("│  ", style=Colors.TEXT_MUTED)
        footer.append(f"Auto-refresh: {refresh}s", style=Colors.TEXT_SECONDARY)

        return Panel(
            Align.center(footer),
            box=box.SIMPLE,
            border_style=Colors.TEXT_MUTED,
            padding=(0, 0),
        )

    def _create_dashboard(self) -> Group:
        """Create the full premium dashboard layout."""
        return Group(
            self._create_header(),
            "",
            self._create_websites_table(self._last_results.get("websites", [])),
            "",
            self._create_apps_table(self._last_results.get("apps", [])),
            "",
            self._create_servers_table(self._last_results.get("servers", [])),
            "",
            self._create_footer(),
        )

    async def _perform_checks(self):
        """Perform health checks on all resources."""
        websites = self.config.get_websites()
        apps = self.config.get_apps()
        servers = self.config.get_servers()

        self._last_results = await self.checker.check_all(websites, apps, servers)
        self._check_count += 1

    async def run_async(self, refresh_interval: Optional[int] = None):
        """Run the dashboard asynchronously with real-time updates."""
        settings = self.config.get_settings()
        interval = refresh_interval or settings.get("refresh_interval", 5)

        self._running = True
        self._start_time = datetime.now()

        # Initial check
        await self._perform_checks()

        with Live(
            self._create_dashboard(),
            console=self.console,
            refresh_per_second=2,
            screen=True,
            transient=False,
        ) as live:
            try:
                while self._running:
                    live.update(self._create_dashboard())
                    await asyncio.sleep(interval)
                    await self._perform_checks()

            except KeyboardInterrupt:
                self._running = False

    def run(self, refresh_interval: Optional[int] = None):
        """Run the dashboard (blocking)."""
        try:
            asyncio.run(self.run_async(refresh_interval))
        except KeyboardInterrupt:
            self.console.print(f"\n[{Colors.DEGRADED}]Dashboard stopped.[/]")

    def print_status(self):
        """Print current status once (non-interactive)."""
        asyncio.run(self._perform_checks())

        self.console.print()
        self.console.print(self._create_header())
        self.console.print()
        self.console.print(
            self._create_websites_table(self._last_results.get("websites", []))
        )
        self.console.print()
        self.console.print(self._create_apps_table(self._last_results.get("apps", [])))
        self.console.print()
        self.console.print(
            self._create_servers_table(self._last_results.get("servers", []))
        )
        self.console.print()


class SimpleMonitorDashboard:
    """Simplified premium dashboard for quick status checks."""

    def __init__(self, config: Optional[MonitoringConfig] = None):
        self.config = config or MonitoringConfig()
        self.checker = HealthChecker()
        self.console = Console()

    def _get_status_display(self, status: HealthStatus) -> tuple[str, str]:
        """Get icon and color for status."""
        displays = {
            HealthStatus.HEALTHY: (f"{Icons.HEALTHY}", Colors.HEALTHY),
            HealthStatus.UNHEALTHY: (f"{Icons.UNHEALTHY}", Colors.UNHEALTHY),
            HealthStatus.DEGRADED: (f"{Icons.DEGRADED}", Colors.DEGRADED),
            HealthStatus.UNKNOWN: (f"{Icons.UNKNOWN}", Colors.UNKNOWN),
        }
        return displays.get(status, (Icons.UNKNOWN, Colors.UNKNOWN))

    async def check_and_print(self):
        """Check all resources and print premium results."""
        websites = self.config.get_websites()
        apps = self.config.get_apps()
        servers = self.config.get_servers()

        results = await self.checker.check_all(websites, apps, servers)
        summary = self.checker.get_summary()

        # Health percentage with color
        health_pct = summary["health_percent"]
        if health_pct >= 90:
            health_color = Colors.HEALTHY
        elif health_pct >= 70:
            health_color = Colors.DEGRADED
        else:
            health_color = Colors.UNHEALTHY

        # Header
        self.console.print()
        header = Text()
        header.append("  DEVOPS ", style=f"bold {Colors.PRIMARY}")
        header.append("HEALTH CHECK  ", style=f"bold {Colors.TEXT_PRIMARY}")
        header.append(
            f"│  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            style=Colors.TEXT_MUTED,
        )
        self.console.print(Panel(header, box=box.DOUBLE, border_style=Colors.PRIMARY))

        # Overall health
        health_text = Text()
        health_text.append("  Overall Health: ", style=Colors.TEXT_SECONDARY)
        health_text.append(f"{health_pct:.0f}%", style=f"bold {health_color}")
        health_text.append(f"  │  {Icons.HEALTHY} ", style=Colors.TEXT_MUTED)
        health_text.append(f"{summary['healthy']} online", style=Colors.HEALTHY)
        health_text.append(f"  {Icons.UNHEALTHY} ", style=Colors.TEXT_MUTED)
        health_text.append(f"{summary['unhealthy']} offline", style=Colors.UNHEALTHY)
        self.console.print(health_text)
        self.console.print()

        # Websites
        if results["websites"]:
            self.console.print(f"  [{Colors.PRIMARY}]{Icons.WEBSITE} WEBSITES[/]")
            for r in results["websites"]:
                icon, color = self._get_status_display(r.status)
                time_str = (
                    f"[{Colors.TEXT_MUTED}]({r.response_time_ms:.0f}ms)[/]"
                    if r.response_time_ms
                    else ""
                )
                self.console.print(
                    f"    [{color}]{icon}[/] {r.name}: [{color}]{r.message}[/] {time_str}"
                )
            self.console.print()

        # Apps
        if results["apps"]:
            self.console.print(f"  [{Colors.SECONDARY}]{Icons.APP} APPLICATIONS[/]")
            for r in results["apps"]:
                icon, color = self._get_status_display(r.status)
                extra = ""
                if r.status == HealthStatus.HEALTHY and r.details.get("cpu"):
                    extra = (
                        f"[{Colors.TEXT_MUTED}]CPU: {r.details.get('cpu', 'N/A')}[/]"
                    )
                self.console.print(
                    f"    [{color}]{icon}[/] {r.name}: [{color}]{r.message}[/] {extra}"
                )
            self.console.print()

        # Servers
        if results["servers"]:
            self.console.print(f"  [{Colors.ACCENT}]{Icons.SERVER} SERVERS[/]")
            for r in results["servers"]:
                icon, color = self._get_status_display(r.status)
                host = r.details.get("host", "N/A")
                time_str = (
                    f"[{Colors.TEXT_MUTED}]({r.response_time_ms:.0f}ms)[/]"
                    if r.response_time_ms
                    else ""
                )
                self.console.print(
                    f"    [{color}]{icon}[/] {r.name} [{Colors.TEXT_MUTED}]({host})[/]: [{color}]{r.message}[/] {time_str}"
                )
            self.console.print()

        return results

    def run(self):
        """Run single check."""
        return asyncio.run(self.check_and_print())
