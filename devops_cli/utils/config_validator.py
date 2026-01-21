"""Configuration validation utility for DevOps CLI.

Provides friendly error messages when features aren't configured,
guiding users to set things up properly.
"""

from pathlib import Path
from typing import Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import yaml


class ConfigStatus(Enum):
    """Configuration status levels."""
    NOT_INITIALIZED = "not_initialized"
    PARTIALLY_CONFIGURED = "partially_configured"
    CONFIGURED = "configured"


@dataclass
class ConfigCheck:
    """Result of a configuration check."""
    status: ConfigStatus
    message: str
    hint: str
    admin_action: Optional[str] = None


# Config paths
CONFIG_DIR = Path.home() / ".devops-cli"
APPS_CONFIG = CONFIG_DIR / "apps.yaml"
SERVERS_CONFIG = CONFIG_DIR / "servers.yaml"
AWS_CONFIG = CONFIG_DIR / "aws.yaml"
TEAMS_CONFIG = CONFIG_DIR / "teams.yaml"
AUTH_DIR = CONFIG_DIR / "auth"
USERS_FILE = AUTH_DIR / "users.json"
MONITORING_CONFIG = CONFIG_DIR / "monitoring.yaml"


class ConfigValidator:
    """Validates CLI configuration and provides helpful messages."""

    # Friendly messages
    MESSAGES = {
        "cli_not_initialized": {
            "title": "CLI Not Initialized",
            "message": "DevOps CLI has not been set up for your organization yet.",
            "hint": "Ask your Cloud Engineer/Admin to run: devops admin init",
            "icon": "🔧"
        },
        "no_users": {
            "title": "No Users Registered",
            "message": "No users have been registered in the system.",
            "hint": "Ask your Admin to register you: devops admin user-add --email your@email.com",
            "icon": "👤"
        },
        "no_apps": {
            "title": "No Applications Configured",
            "message": "No applications have been added to monitor.",
            "hint": "Ask your Admin to add apps: devops admin app-add",
            "icon": "📦"
        },
        "no_servers": {
            "title": "No Servers Configured",
            "message": "No SSH servers have been configured.",
            "hint": "Ask your Admin to add servers: devops admin server-add",
            "icon": "🖥️"
        },
        "no_aws_roles": {
            "title": "No AWS Roles Configured",
            "message": "No AWS IAM roles have been set up for log access.",
            "hint": "Ask your Admin to configure AWS: devops admin aws-add-role",
            "icon": "☁️"
        },
        "no_monitoring": {
            "title": "No Monitoring Resources",
            "message": "No websites, apps, or servers configured for monitoring.",
            "hint": "Add resources: devops monitor add-website/add-app/add-server",
            "icon": "📊"
        },
        "not_authenticated": {
            "title": "Not Logged In",
            "message": "You need to log in to use this feature.",
            "hint": "Run: devops auth login",
            "icon": "🔐"
        },
        "app_not_found": {
            "title": "Application Not Found",
            "message": "The requested application doesn't exist or you don't have access.",
            "hint": "Run 'devops app list' to see available applications.",
            "icon": "❓"
        },
        "server_not_found": {
            "title": "Server Not Found",
            "message": "The requested server doesn't exist or you don't have access.",
            "hint": "Run 'devops ssh list' to see available servers.",
            "icon": "❓"
        },
    }

    @classmethod
    def is_initialized(cls) -> bool:
        """Check if CLI has been initialized."""
        return CONFIG_DIR.exists() and (
            APPS_CONFIG.exists() or
            AWS_CONFIG.exists() or
            SERVERS_CONFIG.exists()
        )

    @classmethod
    def has_users(cls) -> bool:
        """Check if any users are registered."""
        if not USERS_FILE.exists():
            return False
        try:
            import json
            users = json.loads(USERS_FILE.read_text())
            return len(users) > 0
        except:
            return False

    @classmethod
    def has_apps(cls) -> bool:
        """Check if any apps are configured."""
        if not APPS_CONFIG.exists():
            return False
        try:
            config = yaml.safe_load(APPS_CONFIG.read_text()) or {}
            apps = config.get("apps", {})
            return len(apps) > 0
        except:
            return False

    @classmethod
    def has_servers(cls) -> bool:
        """Check if any servers are configured."""
        if not SERVERS_CONFIG.exists():
            return False
        try:
            config = yaml.safe_load(SERVERS_CONFIG.read_text()) or {}
            servers = config.get("servers", {})
            return len(servers) > 0
        except:
            return False

    @classmethod
    def has_aws_roles(cls) -> bool:
        """Check if any AWS roles are configured."""
        if not AWS_CONFIG.exists():
            return False
        try:
            config = yaml.safe_load(AWS_CONFIG.read_text()) or {}
            roles = config.get("roles", {})
            return len(roles) > 0
        except:
            return False

    @classmethod
    def has_monitoring_resources(cls) -> bool:
        """Check if any monitoring resources are configured."""
        if not MONITORING_CONFIG.exists():
            return False
        try:
            config = yaml.safe_load(MONITORING_CONFIG.read_text()) or {}
            websites = config.get("websites", [])
            apps = config.get("apps", [])
            servers = config.get("servers", [])
            return len(websites) + len(apps) + len(servers) > 0
        except:
            return False

    @classmethod
    def get_app(cls, app_name: str) -> Optional[dict]:
        """Get app configuration by name."""
        if not APPS_CONFIG.exists():
            return None
        try:
            config = yaml.safe_load(APPS_CONFIG.read_text()) or {}
            return config.get("apps", {}).get(app_name)
        except:
            return None

    @classmethod
    def get_server(cls, server_name: str) -> Optional[dict]:
        """Get server configuration by name."""
        if not SERVERS_CONFIG.exists():
            return None
        try:
            config = yaml.safe_load(SERVERS_CONFIG.read_text()) or {}
            return config.get("servers", {}).get(server_name)
        except:
            return None

    @classmethod
    def get_aws_role(cls, role_name: str) -> Optional[dict]:
        """Get AWS role configuration by name."""
        if not AWS_CONFIG.exists():
            return None
        try:
            config = yaml.safe_load(AWS_CONFIG.read_text()) or {}
            return config.get("roles", {}).get(role_name)
        except:
            return None

    @classmethod
    def get_config_summary(cls) -> dict:
        """Get summary of what's configured."""
        summary = {
            "initialized": cls.is_initialized(),
            "users": cls.has_users(),
            "apps": cls.has_apps(),
            "servers": cls.has_servers(),
            "aws_roles": cls.has_aws_roles(),
            "monitoring": cls.has_monitoring_resources(),
        }

        # Count items
        summary["counts"] = {
            "users": 0,
            "apps": 0,
            "servers": 0,
            "aws_roles": 0,
            "monitoring_resources": 0,
        }

        try:
            if USERS_FILE.exists():
                import json
                users = json.loads(USERS_FILE.read_text())
                summary["counts"]["users"] = len(users)
        except:
            pass

        try:
            if APPS_CONFIG.exists():
                config = yaml.safe_load(APPS_CONFIG.read_text()) or {}
                summary["counts"]["apps"] = len(config.get("apps", {}))
        except:
            pass

        try:
            if SERVERS_CONFIG.exists():
                config = yaml.safe_load(SERVERS_CONFIG.read_text()) or {}
                summary["counts"]["servers"] = len(config.get("servers", {}))
        except:
            pass

        try:
            if AWS_CONFIG.exists():
                config = yaml.safe_load(AWS_CONFIG.read_text()) or {}
                summary["counts"]["aws_roles"] = len(config.get("roles", {}))
        except:
            pass

        try:
            if MONITORING_CONFIG.exists():
                config = yaml.safe_load(MONITORING_CONFIG.read_text()) or {}
                total = len(config.get("websites", [])) + len(config.get("apps", [])) + len(config.get("servers", []))
                summary["counts"]["monitoring_resources"] = total
        except:
            pass

        return summary


def print_not_configured(key: str, console=None):
    """Print a friendly 'not configured' message."""
    from rich.console import Console
    from rich.panel import Panel
    from rich import box

    if console is None:
        console = Console()

    msg = ConfigValidator.MESSAGES.get(key, {
        "title": "Not Configured",
        "message": "This feature hasn't been set up yet.",
        "hint": "Contact your administrator.",
        "icon": "⚠️"
    })

    content = f"""[yellow]{msg['message']}[/yellow]

[dim]💡 {msg['hint']}[/dim]"""

    console.print()
    console.print(Panel(
        content,
        title=f"[bold]{msg['icon']} {msg['title']}[/bold]",
        border_style="yellow",
        box=box.ROUNDED,
        padding=(1, 2)
    ))
    console.print()


def require_initialized(func):
    """Decorator to require CLI initialization."""
    import functools

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        if not ConfigValidator.is_initialized():
            print_not_configured("cli_not_initialized")
            raise SystemExit(0)
        return func(*args, **kwargs)
    return wrapper


def require_apps_configured(func):
    """Decorator to require apps to be configured."""
    import functools

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        if not ConfigValidator.has_apps():
            print_not_configured("no_apps")
            raise SystemExit(0)
        return func(*args, **kwargs)
    return wrapper


def require_servers_configured(func):
    """Decorator to require servers to be configured."""
    import functools

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        if not ConfigValidator.has_servers():
            print_not_configured("no_servers")
            raise SystemExit(0)
        return func(*args, **kwargs)
    return wrapper


def require_aws_configured(func):
    """Decorator to require AWS to be configured."""
    import functools

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        if not ConfigValidator.has_aws_roles():
            print_not_configured("no_aws_roles")
            raise SystemExit(0)
        return func(*args, **kwargs)
    return wrapper
