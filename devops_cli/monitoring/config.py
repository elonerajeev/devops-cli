"""Monitoring configuration management."""

import yaml
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, field, asdict
from datetime import datetime


@dataclass
class WebsiteConfig:
    """Website monitoring configuration."""
    name: str
    url: str
    expected_status: int = 200
    timeout: int = 10
    method: str = "GET"
    headers: dict = field(default_factory=dict)
    enabled: bool = True
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def as_dict(self):
        return asdict(self)


@dataclass
class AppConfig:
    """Application monitoring configuration."""
    name: str
    type: str  # docker, pm2, process, ecs, kubernetes
    identifier: str  # container name, process name, service name
    host: Optional[str] = None  # for remote apps
    port: Optional[int] = None
    health_endpoint: Optional[str] = None  # /health, /api/health
    enabled: bool = True
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def as_dict(self):
        return asdict(self)


@dataclass
class ServerConfig:
    """Server monitoring configuration."""
    name: str
    host: str
    port: int = 22
    check_type: str = "ping"  # ping, ssh, http
    ssh_user: Optional[str] = None
    ssh_key: Optional[str] = None
    enabled: bool = True
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def as_dict(self):
        return asdict(self)


def _load_dedicated_config_files(config_dir: Path) -> dict:
    """
    Load resources from dedicated YAML config files (apps.yaml, websites.yaml, servers.yaml).
    This allows the monitoring system to use the same configs that the admin commands use.
    """
    result = {"websites": [], "apps": [], "servers": []}

    # Load websites from websites.yaml
    websites_file = config_dir / "websites.yaml"
    if websites_file.exists():
        try:
            with open(websites_file, 'r') as f:
                data = yaml.safe_load(f) or {}
            websites = data.get("websites", {})
            if isinstance(websites, dict):
                for name, website in websites.items():
                    if isinstance(website, dict) and website.get("url"):
                        result["websites"].append({
                            "name": website.get("name", name),
                            "url": website.get("url"),
                            "expected_status": website.get("expected_status", 200),
                            "timeout": website.get("timeout", 10),
                            "method": website.get("method", "GET"),
                            "headers": website.get("headers", {}),
                            "enabled": website.get("enabled", True),
                        })
        except Exception:
            pass

    # Load apps from apps.yaml
    apps_file = config_dir / "apps.yaml"
    if apps_file.exists():
        try:
            with open(apps_file, 'r') as f:
                data = yaml.safe_load(f) or {}
            apps = data.get("apps", {})
            if isinstance(apps, dict):
                for name, app in apps.items():
                    if isinstance(app, dict):
                        app_type = app.get("type", "http")
                        identifier = name
                        health_endpoint = None
                        host = None
                        port = None

                        # Get health check URL if available
                        health_check = app.get("health_check", app.get("health", {}))
                        if health_check.get("url"):
                            health_endpoint = health_check.get("url")

                        result["apps"].append({
                            "name": app.get("name", name),
                            "type": app_type,
                            "identifier": identifier,
                            "host": host,
                            "port": port,
                            "health_endpoint": health_endpoint,
                            "enabled": app.get("enabled", True),
                        })
        except Exception:
            pass

    # Load servers from servers.yaml
    servers_file = config_dir / "servers.yaml"
    if servers_file.exists():
        try:
            with open(servers_file, 'r') as f:
                data = yaml.safe_load(f) or {}
            servers = data.get("servers", {})
            if isinstance(servers, dict):
                for name, server in servers.items():
                    if isinstance(server, dict) and server.get("host"):
                        result["servers"].append({
                            "name": server.get("name", name),
                            "host": server.get("host"),
                            "port": server.get("port", 22),
                            "check_type": server.get("check_type", "ping"),
                            "ssh_user": server.get("user"),
                            "ssh_key": server.get("key"),
                            "enabled": server.get("enabled", True),
                        })
        except Exception:
            pass

    return result


class MonitoringConfig:
    """Manages monitoring configuration for websites, apps, and servers."""

    def __init__(self, config_dir: Optional[Path] = None):
        self.config_dir = config_dir or Path.home() / ".devops-cli"
        self.config_file = self.config_dir / "monitoring.yaml"
        self._ensure_config()

    def _ensure_config(self):
        """Ensure config directory and file exist."""
        self.config_dir.mkdir(parents=True, exist_ok=True)
        if not self.config_file.exists():
            self._save_config({
                "websites": [],
                "apps": [],
                "servers": [],
                "settings": {
                    "refresh_interval": 5,
                    "alert_on_failure": True,
                    "failure_threshold": 3,
                    "history_retention_hours": 24
                }
            })

    def _load_config(self) -> dict:
        """Load configuration from file."""
        try:
            with open(self.config_file, 'r') as f:
                return yaml.safe_load(f) or {}
        except Exception:
            return {"websites": [], "apps": [], "servers": [], "settings": {}}

    def _save_config(self, config: dict):
        """Save configuration to file."""
        with open(self.config_file, 'w') as f:
            yaml.dump(config, f, default_flow_style=False, sort_keys=False)

    # Website management
    def add_website(self, website: WebsiteConfig) -> bool:
        """Add a website to monitor."""
        config = self._load_config()

        # Check for duplicates
        for w in config.get("websites", []):
            if w["name"] == website.name:
                return False

        config.setdefault("websites", []).append(asdict(website))
        self._save_config(config)
        return True

    def remove_website(self, name: str) -> bool:
        """Remove a website from monitoring."""
        config = self._load_config()
        original_count = len(config.get("websites", []))
        config["websites"] = [w for w in config.get("websites", []) if w["name"] != name]

        if len(config["websites"]) < original_count:
            self._save_config(config)
            return True
        return False

    def get_websites(self) -> list[WebsiteConfig]:
        """Get all monitored websites from both monitoring.yaml and websites.yaml."""
        config = self._load_config()
        monitoring_websites = [w for w in config.get("websites", []) if w.get("enabled", True)]

        # Load from dedicated websites.yaml
        dedicated = _load_dedicated_config_files(self.config_dir)
        dedicated_websites = [w for w in dedicated.get("websites", []) if w.get("enabled", True)]

        # Merge, avoiding duplicates by name
        seen_names = set()
        all_websites = []

        for w in monitoring_websites:
            if w["name"] not in seen_names:
                seen_names.add(w["name"])
                all_websites.append(w)

        for w in dedicated_websites:
            if w["name"] not in seen_names:
                seen_names.add(w["name"])
                all_websites.append(w)

        return [WebsiteConfig(**w) for w in all_websites]

    def get_all_websites(self) -> list[WebsiteConfig]:
        """Get all websites including disabled."""
        config = self._load_config()
        monitoring_websites = config.get("websites", [])

        dedicated = _load_dedicated_config_files(self.config_dir)
        dedicated_websites = dedicated.get("websites", [])

        seen_names = set()
        all_websites = []

        for w in monitoring_websites:
            if w["name"] not in seen_names:
                seen_names.add(w["name"])
                all_websites.append(w)

        for w in dedicated_websites:
            if w["name"] not in seen_names:
                seen_names.add(w["name"])
                all_websites.append(w)

        return [WebsiteConfig(**w) for w in all_websites]

    # App management
    def add_app(self, app: AppConfig) -> bool:
        """Add an application to monitor."""
        config = self._load_config()

        for a in config.get("apps", []):
            if a["name"] == app.name:
                return False

        config.setdefault("apps", []).append(asdict(app))
        self._save_config(config)
        return True

    def remove_app(self, name: str) -> bool:
        """Remove an application from monitoring."""
        config = self._load_config()
        original_count = len(config.get("apps", []))
        config["apps"] = [a for a in config.get("apps", []) if a["name"] != name]

        if len(config["apps"]) < original_count:
            self._save_config(config)
            return True
        return False

    def get_apps(self) -> list[AppConfig]:
        """Get all monitored applications from both monitoring.yaml and apps.yaml."""
        config = self._load_config()
        monitoring_apps = [a for a in config.get("apps", []) if a.get("enabled", True)]

        dedicated = _load_dedicated_config_files(self.config_dir)
        dedicated_apps = [a for a in dedicated.get("apps", []) if a.get("enabled", True)]

        seen_names = set()
        all_apps = []

        for a in monitoring_apps:
            if a["name"] not in seen_names:
                seen_names.add(a["name"])
                all_apps.append(a)

        for a in dedicated_apps:
            if a["name"] not in seen_names:
                seen_names.add(a["name"])
                all_apps.append(a)

        return [AppConfig(**a) for a in all_apps]

    def get_all_apps(self) -> list[AppConfig]:
        """Get all apps including disabled."""
        config = self._load_config()
        monitoring_apps = config.get("apps", [])

        dedicated = _load_dedicated_config_files(self.config_dir)
        dedicated_apps = dedicated.get("apps", [])

        seen_names = set()
        all_apps = []

        for a in monitoring_apps:
            if a["name"] not in seen_names:
                seen_names.add(a["name"])
                all_apps.append(a)

        for a in dedicated_apps:
            if a["name"] not in seen_names:
                seen_names.add(a["name"])
                all_apps.append(a)

        return [AppConfig(**a) for a in all_apps]

    # Server management
    def add_server(self, server: ServerConfig) -> bool:
        """Add a server to monitor."""
        config = self._load_config()

        for s in config.get("servers", []):
            if s["name"] == server.name:
                return False

        config.setdefault("servers", []).append(asdict(server))
        self._save_config(config)
        return True

    def remove_server(self, name: str) -> bool:
        """Remove a server from monitoring."""
        config = self._load_config()
        original_count = len(config.get("servers", []))
        config["servers"] = [s for s in config.get("servers", []) if s["name"] != name]

        if len(config["servers"]) < original_count:
            self._save_config(config)
            return True
        return False

    def get_servers(self) -> list[ServerConfig]:
        """Get all monitored servers from both monitoring.yaml and servers.yaml."""
        config = self._load_config()
        monitoring_servers = [s for s in config.get("servers", []) if s.get("enabled", True)]

        dedicated = _load_dedicated_config_files(self.config_dir)
        dedicated_servers = [s for s in dedicated.get("servers", []) if s.get("enabled", True)]

        seen_names = set()
        all_servers = []

        for s in monitoring_servers:
            if s["name"] not in seen_names:
                seen_names.add(s["name"])
                all_servers.append(s)

        for s in dedicated_servers:
            if s["name"] not in seen_names:
                seen_names.add(s["name"])
                all_servers.append(s)

        return [ServerConfig(**s) for s in all_servers]

    def get_all_servers(self) -> list[ServerConfig]:
        """Get all servers including disabled."""
        config = self._load_config()
        monitoring_servers = config.get("servers", [])

        dedicated = _load_dedicated_config_files(self.config_dir)
        dedicated_servers = dedicated.get("servers", [])

        seen_names = set()
        all_servers = []

        for s in monitoring_servers:
            if s["name"] not in seen_names:
                seen_names.add(s["name"])
                all_servers.append(s)

        for s in dedicated_servers:
            if s["name"] not in seen_names:
                seen_names.add(s["name"])
                all_servers.append(s)

        return [ServerConfig(**s) for s in all_servers]

    # Settings
    def get_settings(self) -> dict:
        """Get monitoring settings."""
        config = self._load_config()
        return config.get("settings", {
            "refresh_interval": 5,
            "alert_on_failure": True,
            "failure_threshold": 3,
            "history_retention_hours": 24
        })

    def update_settings(self, **kwargs):
        """Update monitoring settings."""
        config = self._load_config()
        config.setdefault("settings", {}).update(kwargs)
        self._save_config(config)

    # Bulk operations
    def get_all_resources(self) -> dict:
        """Get all monitored resources."""
        return {
            "websites": self.get_websites(),
            "apps": self.get_apps(),
            "servers": self.get_servers()
        }

    def get_resource_counts(self) -> dict:
        """Get count of each resource type (from both monitoring.yaml and dedicated files)."""
        return {
            "websites": len(self.get_websites()),
            "apps": len(self.get_apps()),
            "servers": len(self.get_servers())
        }