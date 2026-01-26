"""Unified Configuration Manager for DevOps CLI.

Provides centralized access to all configuration files with:
- Caching to avoid repeated disk reads
- Consistent error handling
- Thread-safe operations
- Automatic directory creation
"""

import os
import threading
from pathlib import Path
from typing import Any, Dict, Optional, TypeVar, Generic
from dataclasses import dataclass, field
from datetime import datetime
import yaml


T = TypeVar("T", bound=Dict[str, Any])


@dataclass
class CacheEntry:
    """A cached configuration entry with metadata."""

    data: Dict[str, Any]
    loaded_at: datetime
    file_mtime: float


class ConfigManager:
    """Centralized configuration manager for DevOps CLI.

    This class provides a unified interface for all configuration access,
    including apps, servers, websites, AWS, teams, repos, and global settings.

    Features:
    - Lazy loading: configs are loaded only when first accessed
    - Caching: loaded configs are cached to avoid repeated disk I/O
    - Auto-reload: optional reloading when files change
    - Thread-safe: uses locks for concurrent access

    Usage:
        from devops_cli.config.manager import config_manager

        # Get apps config
        apps = config_manager.apps

        # Get specific app
        my_app = config_manager.get_app("my-app")

        # Save apps config
        config_manager.save_apps(apps)

        # Clear cache to force reload
        config_manager.clear_cache()
    """

    def __init__(self, auto_reload: bool = False):
        """Initialize the ConfigManager.

        Args:
            auto_reload: If True, check file modification times and reload
                        configs when they change. Disabled by default for
                        performance.
        """
        self._cache: Dict[str, CacheEntry] = {}
        self._lock = threading.RLock()
        self._auto_reload = auto_reload
        self.CONFIG_DIR = self._resolve_config_dir()
        
        # Secrets directory
        self.SECRETS_DIR = self.CONFIG_DIR / "secrets"

        # Config file paths
        self.CONFIG_FILES = {
            "global": self.CONFIG_DIR / "config.yaml",
            "apps": self.CONFIG_DIR / "apps.yaml",
            "servers": self.CONFIG_DIR / "servers.yaml",
            "websites": self.CONFIG_DIR / "websites.yaml",
            "aws": self.CONFIG_DIR / "aws.yaml",
            "teams": self.CONFIG_DIR / "teams.yaml",
            "repos": self.CONFIG_DIR / "repos.yaml",
            "meetings": self.CONFIG_DIR / "meetings.yaml",
        }

    def _resolve_config_dir(self) -> Path:
        """Resolve the configuration directory path.
        
        Priority:
        1. DEVOPS_CONFIG_DIR environment variable
        2. .devops-cli directory in current working directory (local config)
        3. ~/.devops-cli directory (global config)
        """
        # 1. Environment variable
        env_dir = os.environ.get("DEVOPS_CONFIG_DIR")
        if env_dir:
            return Path(env_dir).resolve()
            
        # 2. Local config
        local_dir = Path.cwd() / ".devops-cli"
        if local_dir.exists() and local_dir.is_dir():
            return local_dir
            
        # 3. Global config (default)
        return Path.home() / ".devops-cli"

    def _ensure_dirs(self) -> None:
        """Ensure configuration directories exist."""
        self.CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        self.SECRETS_DIR.mkdir(parents=True, exist_ok=True)

    def _load_yaml(self, file_path: Path, default: Optional[Dict] = None) -> Dict[str, Any]:
        """Load a YAML file safely.

        Args:
            file_path: Path to the YAML file
            default: Default value if file doesn't exist or is invalid

        Returns:
            Parsed YAML content or default
        """
        if default is None:
            default = {}

        if not file_path.exists():
            return default.copy()

        try:
            with open(file_path) as f:
                data = yaml.safe_load(f)
                return data if data is not None else default.copy()
        except yaml.YAMLError:
            return default.copy()
        except IOError:
            return default.copy()

    def _save_yaml(self, file_path: Path, data: Dict[str, Any]) -> bool:
        """Save data to a YAML file.

        Args:
            file_path: Path to save to
            data: Data to save

        Returns:
            True if successful, False otherwise
        """
        try:
            self._ensure_dirs()
            with open(file_path, "w") as f:
                yaml.dump(data, f, default_flow_style=False, sort_keys=False)
            return True
        except IOError:
            return False

    def _get_cached(self, key: str) -> Optional[Dict[str, Any]]:
        """Get cached config if valid.

        Args:
            key: Config key (e.g., "apps", "servers")

        Returns:
            Cached data or None if not cached or stale
        """
        with self._lock:
            if key not in self._cache:
                return None

            entry = self._cache[key]

            # Check for auto-reload
            if self._auto_reload:
                file_path = self.CONFIG_FILES.get(key)
                if file_path and file_path.exists():
                    current_mtime = file_path.stat().st_mtime
                    if current_mtime > entry.file_mtime:
                        # File changed, invalidate cache
                        del self._cache[key]
                        return None

            return entry.data

    def _set_cached(self, key: str, data: Dict[str, Any]) -> None:
        """Set cached config.

        Args:
            key: Config key
            data: Data to cache
        """
        with self._lock:
            file_path = self.CONFIG_FILES.get(key)
            mtime = file_path.stat().st_mtime if file_path and file_path.exists() else 0

            self._cache[key] = CacheEntry(
                data=data,
                loaded_at=datetime.now(),
                file_mtime=mtime,
            )

    def _invalidate_cache(self, key: str) -> None:
        """Invalidate a specific cache entry.

        Args:
            key: Config key to invalidate
        """
        with self._lock:
            self._cache.pop(key, None)

    def clear_cache(self) -> None:
        """Clear all cached configurations."""
        with self._lock:
            self._cache.clear()

    # ========================
    # Global Configuration
    # ========================

    @property
    def global_config(self) -> Dict[str, Any]:
        """Get global CLI configuration."""
        cached = self._get_cached("global")
        if cached is not None:
            return cached

        default = self._get_default_global_config()
        data = self._load_yaml(self.CONFIG_FILES["global"], default)

        # Merge with defaults
        merged = {**default, **data}
        self._set_cached("global", merged)
        return merged

    def _get_default_global_config(self) -> Dict[str, Any]:
        """Return default global configuration."""
        return {
            "github": {
                "token": os.getenv("GITHUB_TOKEN", ""),
                "org": os.getenv("GITHUB_ORG", ""),
                "default_repo": os.getenv("GITHUB_REPO", ""),
            },
            "servers": {},
            "services": {},
            "logs": {
                "default_lines": 100,
                "sources": {},
            },
            "environments": {
                "dev": {"branch": "develop", "auto_deploy": True},
                "staging": {"branch": "staging", "auto_deploy": True},
                "prod": {"branch": "main", "auto_deploy": False},
            },
            "ci": {
                "provider": "github",
            },
        }

    def save_global_config(self, config: Dict[str, Any]) -> bool:
        """Save global configuration."""
        success = self._save_yaml(self.CONFIG_FILES["global"], config)
        if success:
            self._invalidate_cache("global")
        return success

    # ========================
    # Apps Configuration
    # ========================

    @property
    def apps(self) -> Dict[str, Any]:
        """Get apps configuration."""
        cached = self._get_cached("apps")
        if cached is not None:
            return cached

        data = self._load_yaml(self.CONFIG_FILES["apps"])
        self._set_cached("apps", data)
        return data

    def get_app(self, name: str) -> Optional[Dict[str, Any]]:
        """Get a specific app configuration by name."""
        apps_data = self.apps
        return apps_data.get("apps", {}).get(name)

    def save_apps(self, config: Dict[str, Any]) -> bool:
        """Save apps configuration."""
        success = self._save_yaml(self.CONFIG_FILES["apps"], config)
        if success:
            self._invalidate_cache("apps")
        return success

    # ========================
    # Servers Configuration
    # ========================

    @property
    def servers(self) -> Dict[str, Any]:
        """Get servers configuration."""
        cached = self._get_cached("servers")
        if cached is not None:
            return cached

        data = self._load_yaml(self.CONFIG_FILES["servers"])
        self._set_cached("servers", data)
        return data

    def get_server(self, name: str) -> Optional[Dict[str, Any]]:
        """Get a specific server configuration by name."""
        servers_data = self.servers
        return servers_data.get("servers", {}).get(name)

    def save_servers(self, config: Dict[str, Any]) -> bool:
        """Save servers configuration."""
        success = self._save_yaml(self.CONFIG_FILES["servers"], config)
        if success:
            self._invalidate_cache("servers")
        return success

    # ========================
    # Websites Configuration
    # ========================

    @property
    def websites(self) -> Dict[str, Any]:
        """Get websites configuration."""
        cached = self._get_cached("websites")
        if cached is not None:
            return cached

        data = self._load_yaml(self.CONFIG_FILES["websites"])
        self._set_cached("websites", data)
        return data

    def get_website(self, name: str) -> Optional[Dict[str, Any]]:
        """Get a specific website configuration by name."""
        websites_data = self.websites
        return websites_data.get("websites", {}).get(name)

    def save_websites(self, config: Dict[str, Any]) -> bool:
        """Save websites configuration."""
        success = self._save_yaml(self.CONFIG_FILES["websites"], config)
        if success:
            self._invalidate_cache("websites")
        return success

    # ========================
    # AWS Configuration
    # ========================

    @property
    def aws(self) -> Dict[str, Any]:
        """Get AWS configuration."""
        cached = self._get_cached("aws")
        if cached is not None:
            return cached

        data = self._load_yaml(self.CONFIG_FILES["aws"])
        self._set_cached("aws", data)
        return data

    def get_aws_role(self, name: str) -> Optional[Dict[str, Any]]:
        """Get a specific AWS role configuration by name."""
        aws_data = self.aws
        return aws_data.get("roles", {}).get(name)

    def save_aws(self, config: Dict[str, Any]) -> bool:
        """Save AWS configuration."""
        success = self._save_yaml(self.CONFIG_FILES["aws"], config)
        if success:
            self._invalidate_cache("aws")
        return success

    # ========================
    # Teams Configuration
    # ========================

    @property
    def teams(self) -> Dict[str, Any]:
        """Get teams configuration."""
        cached = self._get_cached("teams")
        if cached is not None:
            return cached

        data = self._load_yaml(self.CONFIG_FILES["teams"])
        self._set_cached("teams", data)
        return data

    def get_team(self, name: str) -> Optional[Dict[str, Any]]:
        """Get a specific team configuration by name."""
        teams_data = self.teams
        return teams_data.get("teams", {}).get(name)

    def save_teams(self, config: Dict[str, Any]) -> bool:
        """Save teams configuration."""
        success = self._save_yaml(self.CONFIG_FILES["teams"], config)
        if success:
            self._invalidate_cache("teams")
        return success

    # ========================
    # Repos Configuration
    # ========================

    @property
    def repos(self) -> Dict[str, Any]:
        """Get repos configuration."""
        cached = self._get_cached("repos")
        if cached is not None:
            return cached

        data = self._load_yaml(self.CONFIG_FILES["repos"])
        self._set_cached("repos", data)
        return data

    def get_repo(self, name: str) -> Optional[Dict[str, Any]]:
        """Get a specific repo configuration by name."""
        repos_data = self.repos
        return repos_data.get("repos", {}).get(name)

    def save_repos(self, config: Dict[str, Any]) -> bool:
        """Save repos configuration."""
        success = self._save_yaml(self.CONFIG_FILES["repos"], config)
        if success:
            self._invalidate_cache("repos")
        return success

    # ========================
    # Meetings Configuration
    # ========================

    @property
    def meetings(self) -> Dict[str, Any]:
        """Get meetings configuration."""
        cached = self._get_cached("meetings")
        if cached is not None:
            return cached

        default = {
            "meetings": {
                "standup": {
                    "name": "Daily Stand-up",
                    "time": "10:00",
                    "link": "",
                    "description": "Morning team alignment"
                },
                "afternoon": {
                    "name": "Afternoon Meet",
                    "time": "16:00",
                    "link": "",
                    "description": "Mid-day sync"
                },
                "evening": {
                    "name": "Evening Meet",
                    "time": "18:30",
                    "link": "",
                    "description": "End of day wrap-up"
                }
            }
        }
        data = self._load_yaml(self.CONFIG_FILES["meetings"], default)
        
        # Merge with defaults to ensure all keys exist
        if "meetings" not in data:
            data["meetings"] = default["meetings"]
        else:
            for key, val in default["meetings"].items():
                if key not in data["meetings"]:
                    data["meetings"][key] = val

        self._set_cached("meetings", data)
        return data

    def save_meetings(self, config: Dict[str, Any]) -> bool:
        """Save meetings configuration."""
        success = self._save_yaml(self.CONFIG_FILES["meetings"], config)
        if success:
            self._invalidate_cache("meetings")
        return success

    # ========================
    # Utility Methods
    # ========================

    def is_initialized(self) -> bool:
        """Check if the CLI has been initialized."""
        # Check if at least aws.yaml exists (created during admin init)
        return self.CONFIG_FILES["aws"].exists()

    def get_organization(self) -> Optional[str]:
        """Get the organization name from AWS config."""
        return self.aws.get("organization")

    def get_all_app_names(self) -> list:
        """Get a list of all configured app names."""
        return list(self.apps.get("apps", {}).keys())

    def get_all_server_names(self) -> list:
        """Get a list of all configured server names."""
        return list(self.servers.get("servers", {}).keys())

    def get_all_website_names(self) -> list:
        """Get a list of all configured website names."""
        return list(self.websites.get("websites", {}).keys())

    def get_all_team_names(self) -> list:
        """Get a list of all configured team names."""
        return list(self.teams.get("teams", {}).keys())

    def get_all_repo_names(self) -> list:
        """Get a list of all configured repo names."""
        return list(self.repos.get("repos", {}).keys())

    def get_config_summary(self) -> Dict[str, Any]:
        """Get a summary of all configurations.

        Returns:
            Dict with counts and status of all config types
        """
        return {
            "initialized": self.is_initialized(),
            "organization": self.get_organization(),
            "counts": {
                "apps": len(self.get_all_app_names()),
                "servers": len(self.get_all_server_names()),
                "websites": len(self.get_all_website_names()),
                "teams": len(self.get_all_team_names()),
                "repos": len(self.get_all_repo_names()),
                "aws_roles": len(self.aws.get("roles", {})),
            },
            "paths": {
                "config_dir": str(self.CONFIG_DIR),
                "secrets_dir": str(self.SECRETS_DIR),
            },
        }


# Global singleton instance
_config_manager: Optional[ConfigManager] = None
_config_manager_lock = threading.Lock()


def get_config_manager(auto_reload: bool = False) -> ConfigManager:
    """Get the global ConfigManager singleton.

    Args:
        auto_reload: Enable auto-reload on file changes

    Returns:
        The global ConfigManager instance
    """
    global _config_manager

    with _config_manager_lock:
        if _config_manager is None:
            _config_manager = ConfigManager(auto_reload=auto_reload)
        return _config_manager


# Convenience alias
config_manager = get_config_manager()