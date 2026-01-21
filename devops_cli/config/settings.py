"""Configuration management for the CLI."""

import os
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

load_dotenv()

DEFAULT_CONFIG_PATH = Path.home() / ".devops-cli" / "config.yaml"
LOCAL_CONFIG_PATH = Path.cwd() / "devops-cli.yaml"


def get_config_path() -> Path:
    """Get the config file path (local takes precedence)."""
    if LOCAL_CONFIG_PATH.exists():
        return LOCAL_CONFIG_PATH
    return DEFAULT_CONFIG_PATH


def load_config() -> dict[str, Any]:
    """Load configuration from YAML file."""
    config_path = get_config_path()

    if not config_path.exists():
        return get_default_config()

    with open(config_path) as f:
        config = yaml.safe_load(f) or {}

    return {**get_default_config(), **config}


def save_config(config: dict[str, Any]) -> None:
    """Save configuration to YAML file."""
    config_path = get_config_path()
    config_path.parent.mkdir(parents=True, exist_ok=True)

    with open(config_path, "w") as f:
        yaml.dump(config, f, default_flow_style=False)


def get_default_config() -> dict[str, Any]:
    """Return default configuration."""
    return {
        "github": {
            "token": os.getenv("GITHUB_TOKEN", ""),
            "org": os.getenv("GITHUB_ORG", ""),
            "default_repo": os.getenv("GITHUB_REPO", ""),
        },
        "servers": {
            # Example server configuration
            # "web-1": {
            #     "host": "web1.example.com",
            #     "user": "deploy",
            #     "key": "~/.ssh/id_rsa",
            #     "tags": ["web", "production"]
            # }
        },
        "services": {
            # Example service configuration for health checks
            # "api": {
            #     "url": "https://api.example.com/health",
            #     "method": "GET",
            #     "expected_status": 200
            # }
        },
        "logs": {
            "default_lines": 100,
            "sources": {
                # "api": {
                #     "type": "docker",
                #     "container": "api-container"
                # },
                # "nginx": {
                #     "type": "file",
                #     "path": "/var/log/nginx/access.log"
                # }
            }
        },
        "environments": {
            "dev": {"branch": "develop", "auto_deploy": True},
            "staging": {"branch": "staging", "auto_deploy": True},
            "prod": {"branch": "main", "auto_deploy": False},
        },
        "ci": {
            "provider": "github",  # github, gitlab, jenkins
        }
    }


def get_env(key: str, default: str = "") -> str:
    """Get environment variable with fallback."""
    return os.getenv(key, default)


def init_config() -> Path:
    """Initialize configuration file with defaults."""
    config_path = DEFAULT_CONFIG_PATH
    config_path.parent.mkdir(parents=True, exist_ok=True)

    if not config_path.exists():
        save_config(get_default_config())

    return config_path
