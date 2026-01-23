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
        """Get all monitored websites."""
        config = self._load_config()
        return [WebsiteConfig(**w) for w in config.get("websites", []) if w.get("enabled", True)]

    def get_all_websites(self) -> list[WebsiteConfig]:
        """Get all websites including disabled."""
        config = self._load_config()
        return [WebsiteConfig(**w) for w in config.get("websites", [])]

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
        """Get all monitored applications."""
        config = self._load_config()
        return [AppConfig(**a) for a in config.get("apps", []) if a.get("enabled", True)]

    def get_all_apps(self) -> list[AppConfig]:
        """Get all apps including disabled."""
        config = self._load_config()
        return [AppConfig(**a) for a in config.get("apps", [])]

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
        """Get all monitored servers."""
        config = self._load_config()
        return [ServerConfig(**s) for s in config.get("servers", []) if s.get("enabled", True)]

    def get_all_servers(self) -> list[ServerConfig]:
        """Get all servers including disabled."""
        config = self._load_config()
        return [ServerConfig(**s) for s in config.get("servers", [])]

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
        """Get count of each resource type."""
        config = self._load_config()
        return {
            "websites": len([w for w in config.get("websites", []) if w.get("enabled", True)]),
            "apps": len([a for a in config.get("apps", []) if a.get("enabled", True)]),
            "servers": len([s for s in config.get("servers", []) if s.get("enabled", True)])
        }
