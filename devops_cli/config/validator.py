"""Configuration validation utilities for YAML config files.

Validates structure, format, and provides detailed error messages.
Supports both local and centralized config management strategies.
"""

import re
import yaml
from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional, Set
from enum import Enum


class ConfigType(Enum):
    """Configuration file types."""

    APPS = "apps"
    SERVERS = "servers"
    WEBSITES = "websites"
    TEAMS = "teams"
    REPOS = "repos"
    AWS_ROLES = "aws_roles"
    AWS_CREDENTIALS = "aws_credentials"
    USERS = "users"


class ValidationResult:
    """Result of a configuration validation."""

    def __init__(self):
        self.valid = True
        self.errors: List[str] = []
        self.warnings: List[str] = []
        self.info: List[str] = []
        self.secret_refs: List[Tuple[str, str]] = []  # (type, name)

    def add_error(self, message: str):
        """Add an error message."""
        self.valid = False
        self.errors.append(message)

    def add_warning(self, message: str):
        """Add a warning message."""
        self.warnings.append(message)

    def add_info(self, message: str):
        """Add an info message."""
        self.info.append(message)

    def add_secret_ref(self, ref_type: str, name: str):
        """Add a secret reference."""
        self.secret_refs.append((ref_type, name))

    def get_summary(self) -> str:
        """Get a formatted summary of validation results."""
        lines = []

        if self.valid:
            lines.append("✓ Configuration is valid!")
        else:
            lines.append("✗ Configuration has errors!")

        if self.errors:
            lines.append("\nErrors:")
            for error in self.errors:
                lines.append(f"  - {error}")

        if self.warnings:
            lines.append("\nWarnings:")
            for warning in self.warnings:
                lines.append(f"  - {warning}")

        if self.info:
            lines.append("\nInformation:")
            for info in self.info:
                lines.append(f"  - {info}")

        if self.secret_refs:
            lines.append("\nSecret References Found:")
            grouped = {}
            for ref_type, name in self.secret_refs:
                if ref_type not in grouped:
                    grouped[ref_type] = []
                grouped[ref_type].append(name)

            for ref_type, names in grouped.items():
                lines.append(f"  {ref_type}:")
                for name in names:
                    lines.append(f"    - {name}")

        return "\n".join(lines)


class ConfigValidator:
    """Validates DevOps CLI configuration files."""

    # Secret reference patterns
    ENV_VAR_PATTERN = re.compile(r"\$\{([A-Z_][A-Z0-9_]*)\}")
    AWS_SECRET_PATTERN = re.compile(r"\$\{AWS_SECRET:([^}]+)\}")
    GITHUB_SECRET_PATTERN = re.compile(r"\$\{GITHUB_SECRET:([^}]+)\}")
    LOCAL_FILE_PATTERN = re.compile(r"^[~\/].*")  # Paths starting with ~ or /

    def __init__(self):
        self.result = ValidationResult()

    def validate_file(
        self, file_path: Path, config_type: ConfigType
    ) -> ValidationResult:
        """
        Validate a YAML configuration file.

        Args:
            file_path: Path to the YAML file
            config_type: Type of configuration

        Returns:
            ValidationResult with details
        """
        self.result = ValidationResult()

        # Check file exists
        if not file_path.exists():
            self.result.add_error(f"File not found: {file_path}")
            return self.result

        # Load YAML
        try:
            with open(file_path) as f:
                data = yaml.safe_load(f)
        except yaml.YAMLError as e:
            self.result.add_error(f"Invalid YAML syntax: {e}")
            return self.result
        except Exception as e:
            self.result.add_error(f"Could not read file: {e}")
            return self.result

        if not data:
            self.result.add_error("Empty YAML file")
            return self.result

        # Validate based on type
        validators = {
            ConfigType.APPS: self._validate_apps,
            ConfigType.SERVERS: self._validate_servers,
            ConfigType.WEBSITES: self._validate_websites,
            ConfigType.TEAMS: self._validate_teams,
            ConfigType.REPOS: self._validate_repos,
            ConfigType.AWS_ROLES: self._validate_aws_roles,
            ConfigType.AWS_CREDENTIALS: self._validate_aws_credentials,
            ConfigType.USERS: self._validate_users,
        }

        validator = validators.get(config_type)
        if validator:
            validator(data)
        else:
            self.result.add_error(f"Unknown config type: {config_type}")

        return self.result

    def _scan_secrets(self, data: Any, path: str = ""):
        """Recursively scan for secret references."""
        if isinstance(data, str):
            # Check for AWS Secrets Manager
            for match in self.AWS_SECRET_PATTERN.finditer(data):
                self.result.add_secret_ref("AWS_SECRET", match.group(1))

            # Check for GitHub Secrets
            for match in self.GITHUB_SECRET_PATTERN.finditer(data):
                self.result.add_secret_ref("GITHUB_SECRET", match.group(1))

            # Check for environment variables
            for match in self.ENV_VAR_PATTERN.finditer(data):
                var_name = match.group(1)
                # Skip if it's part of AWS_SECRET or GITHUB_SECRET
                if "AWS_SECRET:" not in match.group(
                    0
                ) and "GITHUB_SECRET:" not in match.group(0):
                    self.result.add_secret_ref("ENV_VAR", var_name)

            # Check for local file paths
            if self.LOCAL_FILE_PATTERN.match(data):
                self.result.add_info(f"Local file path found at {path}: {data}")

        elif isinstance(data, dict):
            for key, value in data.items():
                new_path = f"{path}.{key}" if path else key
                self._scan_secrets(value, new_path)

        elif isinstance(data, list):
            for i, item in enumerate(data):
                new_path = f"{path}[{i}]"
                self._scan_secrets(item, new_path)

    def _validate_apps(self, data: Dict[str, Any]):
        """Validate apps configuration."""
        if "apps" not in data:
            self.result.add_error("Missing 'apps' key")
            return

        apps = data["apps"]
        if not isinstance(apps, dict):
            self.result.add_error("'apps' must be a dictionary")
            return

        if not apps:
            self.result.add_warning("No apps defined")
            return

        self.result.add_info(f"Found {len(apps)} app(s)")

        for app_name, app_config in apps.items():
            self._validate_app(app_name, app_config)

        # Scan for secrets
        self._scan_secrets(data)

    def _validate_app(self, name: str, config: Dict[str, Any]):
        """Validate a single app configuration."""
        if not isinstance(config, dict):
            self.result.add_error(f"App '{name}': must be a dictionary")
            return

        # Required fields
        if "type" not in config:
            self.result.add_error(f"App '{name}': missing 'type' field")
        else:
            valid_types = ["lambda", "kubernetes", "docker", "custom"]
            if config["type"] not in valid_types:
                self.result.add_error(
                    f"App '{name}': invalid type '{config['type']}'. "
                    f"Must be one of: {', '.join(valid_types)}"
                )

        # Validate logs section
        if "logs" in config:
            logs = config["logs"]
            if not isinstance(logs, dict):
                self.result.add_error(f"App '{name}': 'logs' must be a dictionary")
            elif "type" in logs:
                valid_log_types = ["cloudwatch"]
                if logs["type"] not in valid_log_types:
                    self.result.add_warning(
                        f"App '{name}': log type '{logs['type']}' may not be supported. "
                        f"Expected: {', '.join(valid_log_types)}"
                    )

        # Validate health section
        if "health" in config:
            health = config["health"]
            if isinstance(health, dict) and "type" in health:
                valid_health_types = ["http", "tcp", "command", "none"]
                if health["type"] not in valid_health_types:
                    self.result.add_warning(
                        f"App '{name}': health type '{health['type']}' may not be supported"
                    )

    def _validate_servers(self, data: Dict[str, Any]):
        """Validate servers configuration."""
        if "servers" not in data:
            self.result.add_error("Missing 'servers' key")
            return

        servers = data["servers"]
        if not isinstance(servers, dict):
            self.result.add_error("'servers' must be a dictionary")
            return

        if not servers:
            self.result.add_warning("No servers defined")
            return

        self.result.add_info(f"Found {len(servers)} server(s)")

        for server_name, server_config in servers.items():
            self._validate_server(server_name, server_config)

        self._scan_secrets(data)

    def _validate_server(self, name: str, config: Dict[str, Any]):
        """Validate a single server configuration."""
        if not isinstance(config, dict):
            self.result.add_error(f"Server '{name}': must be a dictionary")
            return

        # Required fields
        required_fields = ["host", "user"]
        for field in required_fields:
            if field not in config or not config[field]:
                self.result.add_error(
                    f"Server '{name}': missing required field '{field}'"
                )

        # Validate port
        if "port" in config:
            port = config["port"]
            if not isinstance(port, int) or port < 1 or port > 65535:
                self.result.add_error(f"Server '{name}': invalid port '{port}'")

        # Check for SSH key
        if "key" not in config and "password" not in config:
            self.result.add_warning(
                f"Server '{name}': no 'key' or 'password' specified. "
                "SSH authentication may fail."
            )

    def _validate_websites(self, data: Dict[str, Any]):
        """Validate websites configuration."""
        if "websites" not in data:
            self.result.add_error("Missing 'websites' key")
            return

        websites = data["websites"]
        if not isinstance(websites, dict):
            self.result.add_error("'websites' must be a dictionary")
            return

        if not websites:
            self.result.add_warning("No websites defined")
            return

        self.result.add_info(f"Found {len(websites)} website(s)")

        for website_name, website_config in websites.items():
            self._validate_website(website_name, website_config)

        self._scan_secrets(data)

    def _validate_website(self, name: str, config: Dict[str, Any]):
        """Validate a single website configuration."""
        if not isinstance(config, dict):
            self.result.add_error(f"Website '{name}': must be a dictionary")
            return

        # Required fields
        if "url" not in config or not config["url"]:
            self.result.add_error(f"Website '{name}': missing required field 'url'")
        elif not config["url"].startswith(("http://", "https://")):
            self.result.add_error(
                f"Website '{name}': URL must start with http:// or https://"
            )

        # Validate method
        if "method" in config:
            valid_methods = ["GET", "POST", "HEAD", "PUT", "PATCH", "DELETE"]
            if config["method"].upper() not in valid_methods:
                self.result.add_warning(
                    f"Website '{name}': unusual HTTP method '{config['method']}'"
                )

        # Validate expected_status
        if "expected_status" in config:
            status = config["expected_status"]
            if not isinstance(status, int) or status < 100 or status > 599:
                self.result.add_error(
                    f"Website '{name}': invalid expected_status '{status}'"
                )

    def _validate_teams(self, data: Dict[str, Any]):
        """Validate teams configuration."""
        if "teams" not in data:
            self.result.add_error("Missing 'teams' key")
            return

        teams = data["teams"]
        if not isinstance(teams, dict):
            self.result.add_error("'teams' must be a dictionary")
            return

        if not teams:
            self.result.add_warning("No teams defined")
            return

        self.result.add_info(f"Found {len(teams)} team(s)")

        # Check for default team
        if "default" not in teams:
            self.result.add_warning(
                "No 'default' team defined. Users may not have default access."
            )

        for team_name, team_config in teams.items():
            self._validate_team(team_name, team_config)

    def _validate_team(self, name: str, config: Dict[str, Any]):
        """Validate a single team configuration."""
        if not isinstance(config, dict):
            self.result.add_error(f"Team '{name}': must be a dictionary")
            return

        # Check for access lists
        for resource_type in ["apps", "servers", "websites"]:
            if resource_type not in config:
                self.result.add_warning(
                    f"Team '{name}': no '{resource_type}' access list defined"
                )
            elif not isinstance(config[resource_type], list):
                self.result.add_error(
                    f"Team '{name}': '{resource_type}' must be a list"
                )

    def _validate_repos(self, data: Dict[str, Any]):
        """Validate repos configuration."""
        if "repos" not in data:
            self.result.add_error("Missing 'repos' key")
            return

        repos = data["repos"]
        if not isinstance(repos, dict):
            self.result.add_error("'repos' must be a dictionary")
            return

        if not repos:
            self.result.add_warning("No repositories defined")
            return

        self.result.add_info(f"Found {len(repos)} repository(ies)")

        for repo_name, repo_config in repos.items():
            self._validate_repo(repo_name, repo_config)

    def _validate_repo(self, name: str, config: Dict[str, Any]):
        """Validate a single repository configuration."""
        if not isinstance(config, dict):
            self.result.add_error(f"Repo '{name}': must be a dictionary")
            return

        # Required fields
        required_fields = ["owner", "repo"]
        for field in required_fields:
            if field not in config or not config[field]:
                self.result.add_error(
                    f"Repo '{name}': missing required field '{field}'"
                )

    def _validate_aws_roles(self, data: Dict[str, Any]):
        """Validate AWS roles configuration."""
        if "aws_roles" not in data:
            self.result.add_error("Missing 'aws_roles' key")
            return

        roles = data["aws_roles"]
        if not isinstance(roles, dict):
            self.result.add_error("'aws_roles' must be a dictionary")
            return

        if not roles:
            self.result.add_warning("No AWS roles defined")
            return

        self.result.add_info(f"Found {len(roles)} AWS role(s)")

        for role_name, role_config in roles.items():
            self._validate_aws_role(role_name, role_config)

    def _validate_aws_role(self, name: str, config: Dict[str, Any]):
        """Validate a single AWS role configuration."""
        if not isinstance(config, dict):
            self.result.add_error(f"Role '{name}': must be a dictionary")
            return

        # Required fields
        if "role_arn" not in config or not config["role_arn"]:
            self.result.add_error(f"Role '{name}': missing required field 'role_arn'")
        elif not config["role_arn"].startswith("arn:aws:iam::"):
            self.result.add_error(
                f"Role '{name}': invalid ARN format. Should start with 'arn:aws:iam::'"
            )

        if "region" not in config or not config["region"]:
            self.result.add_error(f"Role '{name}': missing required field 'region'")

    def _validate_aws_credentials(self, data: Dict[str, Any]):
        """Validate AWS credentials configuration."""
        if "aws_credentials" not in data:
            self.result.add_error("Missing 'aws_credentials' key")
            return

        creds = data["aws_credentials"]
        if not isinstance(creds, dict):
            self.result.add_error("'aws_credentials' must be a dictionary")
            return

        # Required fields
        required_fields = ["access_key", "secret_key", "region"]
        for field in required_fields:
            if field not in creds or not creds[field]:
                self.result.add_error(f"Missing required field '{field}'")

        # Validate access key format
        if "access_key" in creds and creds["access_key"]:
            access_key = creds["access_key"]
            if not access_key.startswith("AKIA"):
                self.result.add_error(
                    "Invalid Access Key format. AWS Access Keys should start with 'AKIA'"
                )
            if len(access_key) != 20:
                self.result.add_error(
                    f"Invalid Access Key length. Expected 20 characters, got {len(access_key)}"
                )

        # Validate secret key
        if "secret_key" in creds and creds["secret_key"]:
            if len(creds["secret_key"]) < 20:
                self.result.add_error(
                    "Invalid Secret Key. Too short (minimum 20 characters)"
                )

        self.result.add_warning(
            "Remember to delete this file after import for security!"
        )

    def _validate_users(self, data: Dict[str, Any]):
        """Validate users configuration."""
        if "users" not in data:
            self.result.add_error("Missing 'users' key")
            return

        users = data["users"]
        if not isinstance(users, list):
            self.result.add_error("'users' must be a list")
            return

        if not users:
            self.result.add_warning("No users defined")
            return

        self.result.add_info(f"Found {len(users)} user(s)")

        emails_seen = set()

        for i, user in enumerate(users):
            self._validate_user(i, user, emails_seen)

    def _validate_user(self, index: int, config: Dict[str, Any], emails_seen: Set[str]):
        """Validate a single user configuration."""
        if not isinstance(config, dict):
            self.result.add_error(f"User at index {index}: must be a dictionary")
            return

        # Required fields
        if "email" not in config or not config["email"]:
            self.result.add_error(
                f"User at index {index}: missing required field 'email'"
            )
            return

        email = config["email"]

        # Check for duplicate emails
        if email in emails_seen:
            self.result.add_error(f"Duplicate email found: {email}")
        emails_seen.add(email)

        # Validate email format
        if "@" not in email or "." not in email:
            self.result.add_error(f"User '{email}': invalid email format")

        # Validate role
        if "role" not in config or not config["role"]:
            self.result.add_error(f"User '{email}': missing required field 'role'")
        elif config["role"] not in ["admin", "developer"]:
            self.result.add_error(
                f"User '{email}': invalid role '{config['role']}'. Must be 'admin' or 'developer'"
            )


def validate_config_file(file_path: Path, config_type: ConfigType) -> ValidationResult:
    """
    Validate a configuration file.

    Args:
        file_path: Path to the YAML file
        config_type: Type of configuration

    Returns:
        ValidationResult with validation details
    """
    validator = ConfigValidator()
    return validator.validate_file(file_path, config_type)


def detect_config_type(file_path: Path) -> Optional[ConfigType]:
    """
    Detect configuration type from file name or content.

    Args:
        file_path: Path to the YAML file

    Returns:
        ConfigType or None if cannot detect
    """
    filename = file_path.name.lower()

    # Check filename
    if "app" in filename:
        return ConfigType.APPS
    elif "server" in filename:
        return ConfigType.SERVERS
    elif "website" in filename:
        return ConfigType.WEBSITES
    elif "team" in filename:
        return ConfigType.TEAMS
    elif "repo" in filename:
        return ConfigType.REPOS
    elif "aws-role" in filename or "aws_role" in filename:
        return ConfigType.AWS_ROLES
    elif "aws-cred" in filename or "aws_cred" in filename:
        return ConfigType.AWS_CREDENTIALS
    elif "user" in filename:
        return ConfigType.USERS

    # Check file content
    try:
        with open(file_path) as f:
            data = yaml.safe_load(f)

        if not data:
            return None

        # Check for specific keys
        if "apps" in data:
            return ConfigType.APPS
        elif "servers" in data:
            return ConfigType.SERVERS
        elif "websites" in data:
            return ConfigType.WEBSITES
        elif "teams" in data:
            return ConfigType.TEAMS
        elif "repos" in data:
            return ConfigType.REPOS
        elif "aws_roles" in data:
            return ConfigType.AWS_ROLES
        elif "aws_credentials" in data:
            return ConfigType.AWS_CREDENTIALS
        elif "users" in data:
            return ConfigType.USERS
    except Exception:
        pass

    return None
