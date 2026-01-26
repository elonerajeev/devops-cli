"""Centralized configuration loading and saving utilities."""

import yaml
from pathlib import Path
from typing import Dict, Any, Optional, Tuple

from devops_cli.config.manager import config_manager

# Admin config paths
ADMIN_CONFIG_DIR = config_manager.CONFIG_DIR
APPS_CONFIG_FILE = config_manager.CONFIG_FILES["apps"]
SERVERS_CONFIG_FILE = config_manager.CONFIG_FILES["servers"]
WEBSITES_CONFIG_FILE = config_manager.CONFIG_FILES["websites"]
AWS_CONFIG_FILE = config_manager.CONFIG_FILES["aws"]
TEAMS_CONFIG_FILE = config_manager.CONFIG_FILES["teams"]
SECRETS_DIR = config_manager.SECRETS_DIR

# AWS credentials YAML template file (input only - not stored by CLI)
AWS_CREDENTIALS_YAML_FILE = "aws-credentials.yaml"


def ensure_admin_dirs():
    """Ensure admin config directories exist."""
    config_manager._ensure_dirs()


def _load_yaml_file(file_path: Path) -> Dict[str, Any]:
    """Helper to load a YAML file, returning empty dict if not found or invalid."""
    return config_manager._load_yaml(file_path)


def _save_yaml_file(file_path: Path, config: Dict[str, Any]):
    """Helper to save a config dict to a YAML file."""
    config_manager._save_yaml(file_path, config)


# --- Application Configuration ---
def load_apps_config() -> Dict[str, Any]:
    """Load applications configuration."""
    return config_manager.apps


def save_apps_config(config: Dict[str, Any]):
    """Save applications configuration."""
    config_manager.save_apps(config)


# --- Server Configuration ---
def load_servers_config() -> Dict[str, Any]:
    """Load servers configuration."""
    return config_manager.servers


def save_servers_config(config: Dict[str, Any]):
    """Save servers configuration."""
    config_manager.save_servers(config)


# --- Website Configuration ---
def load_websites_config() -> Dict[str, Any]:
    """Load websites configuration."""
    return config_manager.websites


def save_websites_config(config: Dict[str, Any]):
    """Save websites configuration."""
    config_manager.save_websites(config)


# --- AWS Configuration ---
def load_aws_config() -> Dict[str, Any]:
    """Load AWS configuration."""
    return config_manager.aws


def save_aws_config(config: Dict[str, Any]):
    """Save AWS configuration."""
    config_manager.save_aws(config)


# --- Team Configuration ---
def load_teams_config() -> Dict[str, Any]:
    """Load teams configuration."""
    return config_manager.teams


def save_teams_config(config: Dict[str, Any]):
    """Save teams configuration."""
    config_manager.save_teams(config)


# --- Global Config (from settings.py) ---
# It's better to keep global config logic in settings.py itself,
# but ensure paths are consistent.


# --- AWS Credentials YAML Import ---
def load_aws_credentials_yaml(file_path: Path) -> Dict[str, Any]:
    """
    Load AWS credentials from a YAML input file.

    Expected format:
        aws_credentials:
          access_key: AKIAXXXXXXXXXXXXXXXXXX
          secret_key: your-secret-access-key
          region: ap-south-1
          description: DevOps CLI AWS Access

    Args:
        file_path: Path to the YAML file

    Returns:
        Dict with aws_credentials or empty dict if file not found/invalid
    """
    file_path = Path(file_path)
    if not file_path.exists():
        return {}

    try:
        with open(file_path) as f:
            data = yaml.safe_load(f) or {}
        return data
    except yaml.YAMLError:
        return {}


def validate_aws_credentials_yaml(data: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    """
    Validate the structure and format of AWS credentials from YAML.

    Args:
        data: Parsed YAML data

    Returns:
        (is_valid, error_message)
    """
    if not data:
        return False, "Empty or invalid YAML data"

    # Check for aws_credentials key
    if "aws_credentials" not in data:
        return False, "Missing 'aws_credentials' key in YAML file"

    creds = data["aws_credentials"]

    if not isinstance(creds, dict):
        return False, "'aws_credentials' must be a dictionary"

    # Required fields
    required_fields = ["access_key", "secret_key", "region"]
    missing = [f for f in required_fields if f not in creds or not creds[f]]

    if missing:
        return False, f"Missing required fields: {', '.join(missing)}"

    # Validate access key format (AWS access keys start with AKIA)
    access_key = creds["access_key"]
    if not access_key.startswith("AKIA"):
        return (
            False,
            "Invalid Access Key format. AWS Access Keys should start with 'AKIA'",
        )

    if len(access_key) != 20:
        return (
            False,
            f"Invalid Access Key length. Expected 20 characters, got {len(access_key)}",
        )

    # Validate secret key length
    secret_key = creds["secret_key"]
    if len(secret_key) < 20:
        return False, "Invalid Secret Key. Too short (minimum 20 characters)"

    # Validate region format (basic check)
    region = creds["region"]
    if not region or " " in region:
        return False, "Invalid region format"

    return True, None


def get_aws_credentials_template() -> str:
    """
    Generate a template YAML file content for AWS credentials.

    Returns:
        YAML template string with placeholder values
    """
    template = """# AWS Credentials Configuration File
# =====================================
# This file is used as INPUT only - credentials will be encrypted
# and stored securely by the DevOps CLI.
#
# IMPORTANT: Delete this file after import for security!
#
# Usage:
#   1. Fill in your AWS credentials below
#   2. Run: devops admin aws-import --file aws-credentials.yaml
#   3. Delete this file after successful import
#

aws_credentials:
  # AWS Access Key ID (starts with AKIA)
  access_key: AKIAXXXXXXXXXXXXXXXX

  # AWS Secret Access Key
  secret_key: your-secret-access-key-here

  # AWS Region (e.g., us-east-1, ap-south-1, eu-west-1)
  region: ap-south-1

  # Description (optional - for your reference)
  description: DevOps CLI AWS Access

# Required IAM Permissions:
# - logs:DescribeLogGroups
# - logs:FilterLogEvents
# - logs:GetLogEvents
# - ec2:DescribeInstances (optional)
"""
    return template


def import_aws_credentials_from_yaml(
    file_path: Path, skip_validation: bool = False
) -> Tuple[bool, Optional[str], Optional[Dict[str, str]]]:
    """
    Import AWS credentials from a YAML file, validate, and prepare for encryption.

    This function:
    1. Loads the YAML file
    2. Validates the structure and format
    3. Optionally validates against AWS API
    4. Returns the credentials dict ready for saving

    Args:
        file_path: Path to the YAML file
        skip_validation: Skip AWS API validation (for CI/CD)

    Returns:
        (success, error_message, credentials_dict)
    """
    # Load YAML file
    data = load_aws_credentials_yaml(file_path)

    if not data:
        return False, f"Could not load YAML file: {file_path}", None

    # Validate structure
    is_valid, error_msg = validate_aws_credentials_yaml(data)
    if not is_valid:
        return False, error_msg, None

    creds = data["aws_credentials"]

    # Extract credentials
    credentials = {
        "access_key": creds["access_key"],
        "secret_key": creds["secret_key"],
        "region": creds["region"],
        "description": creds.get("description", "Imported from YAML"),
    }

    # Validate against AWS API unless skipped
    if not skip_validation:
        from devops_cli.config.aws_credentials import validate_aws_credentials

        is_valid, error_msg = validate_aws_credentials(
            credentials["access_key"], credentials["secret_key"], credentials["region"]
        )

        if not is_valid:
            return False, f"AWS validation failed: {error_msg}", None

    return True, None, credentials


# --- AWS Roles YAML Import ---
def get_aws_roles_template() -> str:
    """
    Generate a template YAML file content for AWS roles.

    Returns:
        YAML template string with placeholder values
    """
    template = """# AWS Roles Configuration File
# =====================================
# Define IAM roles for cross-account access or role-based permissions.
#
# Usage:
#   1. Fill in your AWS roles below
#   2. Run: devops admin aws-roles-import --file aws-roles.yaml
#

aws_roles:
  # Example role for development environment
  dev-readonly:
    role_arn: arn:aws:iam::123456789012:role/DevOpsReadOnly
    region: us-east-1
    external_id: optional-external-id  # Optional
    description: Read-only access for development

  # Example role for production environment
  prod-admin:
    role_arn: arn:aws:iam::987654321098:role/DevOpsAdmin
    region: ap-south-1
    external_id: ~  # Use ~ or null for no external ID
    description: Admin access for production

# Notes:
# - role_arn: Required - The ARN of the IAM role to assume
# - region: Required - AWS region for this role
# - external_id: Optional - External ID for role assumption (security)
# - description: Optional - Human-readable description
"""
    return template


def validate_aws_roles_yaml(data: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    """
    Validate the structure and format of AWS roles from YAML.

    Args:
        data: Parsed YAML data

    Returns:
        (is_valid, error_message)
    """
    if not data:
        return False, "Empty or invalid YAML data"

    # Check for aws_roles key
    if "aws_roles" not in data:
        return False, "Missing 'aws_roles' key in YAML file"

    roles = data["aws_roles"]

    if not isinstance(roles, dict):
        return False, "'aws_roles' must be a dictionary"

    if not roles:
        return False, "No roles defined in 'aws_roles'"

    # Validate each role
    for role_name, role_config in roles.items():
        if not isinstance(role_config, dict):
            return False, f"Role '{role_name}' must be a dictionary"

        # Required fields
        if "role_arn" not in role_config or not role_config["role_arn"]:
            return False, f"Role '{role_name}' missing required 'role_arn'"

        if "region" not in role_config or not role_config["region"]:
            return False, f"Role '{role_name}' missing required 'region'"

        # Validate ARN format
        arn = role_config["role_arn"]
        if not arn.startswith("arn:aws:iam::"):
            return (
                False,
                f"Role '{role_name}' has invalid ARN format. Should start with 'arn:aws:iam::'",
            )

    return True, None


def load_aws_roles_yaml(file_path: Path) -> Dict[str, Any]:
    """
    Load AWS roles from a YAML input file.

    Args:
        file_path: Path to the YAML file

    Returns:
        Dict with aws_roles or empty dict if file not found/invalid
    """
    file_path = Path(file_path)
    if not file_path.exists():
        return {}

    try:
        with open(file_path) as f:
            data = yaml.safe_load(f) or {}
        return data
    except yaml.YAMLError:
        return {}


# --- Users YAML Import/Export ---
def get_users_template() -> str:
    """
    Generate a template YAML file content for bulk user registration.

    Returns:
        YAML template string with placeholder values
    """
    template = """# Users Configuration File
# =====================================
# Bulk register users for the DevOps CLI.
#
# Usage:
#   1. Fill in your users below
#   2. Run: devops admin users-import --file users.yaml
#
# IMPORTANT: Tokens will be generated and displayed after import.
# Share tokens securely with each user!
#

users:
  # Example admin user
  - email: admin@company.com
    name: Admin User
    role: admin
    team: default

  # Example developer users
  - email: dev1@company.com
    name: Developer One
    role: developer
    team: backend

  - email: dev2@company.com
    name: Developer Two
    role: developer
    team: frontend

# Notes:
# - email: Required - User's email address (must be unique)
# - name: Optional - User's display name
# - role: Required - Either 'admin' or 'developer'
# - team: Optional - Team name (defaults to 'default')
"""
    return template


def validate_users_yaml(data: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    """
    Validate the structure and format of users from YAML.

    Args:
        data: Parsed YAML data

    Returns:
        (is_valid, error_message)
    """
    if not data:
        return False, "Empty or invalid YAML data"

    # Check for users key
    if "users" not in data:
        return False, "Missing 'users' key in YAML file"

    users = data["users"]

    if not isinstance(users, list):
        return False, "'users' must be a list"

    if not users:
        return False, "No users defined in 'users'"

    emails_seen = set()

    # Validate each user
    for i, user in enumerate(users):
        if not isinstance(user, dict):
            return False, f"User at index {i} must be a dictionary"

        # Required fields
        if "email" not in user or not user["email"]:
            return False, f"User at index {i} missing required 'email'"

        email = user["email"]

        # Check for duplicate emails
        if email in emails_seen:
            return False, f"Duplicate email found: {email}"
        emails_seen.add(email)

        # Validate email format (basic check)
        if "@" not in email or "." not in email:
            return False, f"Invalid email format: {email}"

        # Validate role
        if "role" not in user or not user["role"]:
            return False, f"User '{email}' missing required 'role'"

        role = user["role"]
        if role not in ["admin", "developer"]:
            return (
                False,
                f"User '{email}' has invalid role '{role}'. Must be 'admin' or 'developer'",
            )

    return True, None


def load_users_yaml(file_path: Path) -> Dict[str, Any]:
    """
    Load users from a YAML input file.

    Args:
        file_path: Path to the YAML file

    Returns:
        Dict with users list or empty dict if file not found/invalid
    """
    file_path = Path(file_path)
    if not file_path.exists():
        return {}

    try:
        with open(file_path) as f:
            data = yaml.safe_load(f) or {}
        return data
    except yaml.YAMLError:
        return {}


# --- Apps YAML Import/Export ---
def get_apps_template() -> str:
    """Generate a template YAML file content for apps."""
    template = """# Applications Configuration File
# =====================================
# Bulk import applications for the DevOps CLI.
#
# Usage:
#   1. Fill in your applications below
#   2. Run: devops admin apps-import --file apps.yaml
#

apps:
  # Example Lambda application
  api-service:
    type: lambda
    description: API service Lambda function
    lambda:
      function_name: api-service
      region: us-east-1
    logs:
      type: cloudwatch
      log_group: /aws/lambda/api-service
    health:
      type: http
      url: https://api.example.com/health
      expected_status: 200
    teams:
      - default
      - backend

  # Example Kubernetes application
  worker:
    type: kubernetes
    description: Background worker service
    kubernetes:
      namespace: production
      deployment: worker
      container: worker-app
    logs:
      type: cloudwatch
      log_group: /k8s/production/worker
    teams:
      - default

  # Example custom application
  scheduler:
    type: custom
    description: Custom scheduler service
    logs:
      type: cloudwatch
      log_group: /custom/scheduler
      region: us-east-1
    teams:
      - default

# Notes:
# - type: Required - One of: lambda, kubernetes, docker, custom
# - description: Optional - Human-readable description
# - logs: Required - Log configuration (type and log_group)
# - health: Optional - Health check configuration
# - teams: Optional - Teams with access (defaults to ['default'])
"""
    return template


def validate_apps_yaml(data: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    """Validate the structure of apps from YAML."""
    if not data:
        return False, "Empty or invalid YAML data"

    if "apps" not in data:
        return False, "Missing 'apps' key in YAML file"

    apps = data["apps"]

    if not isinstance(apps, dict):
        return False, "'apps' must be a dictionary"

    if not apps:
        return False, "No apps defined in 'apps'"

    valid_types = ["lambda", "kubernetes", "docker", "custom"]

    for app_name, app_config in apps.items():
        if not isinstance(app_config, dict):
            return False, f"App '{app_name}' must be a dictionary"

        # Validate type
        app_type = app_config.get("type")
        if not app_type:
            return False, f"App '{app_name}' missing required 'type'"
        if app_type not in valid_types:
            return False, f"App '{app_name}' has invalid type '{app_type}'. Must be one of: {', '.join(valid_types)}"

        # Validate logs config
        if "logs" not in app_config:
            return False, f"App '{app_name}' missing required 'logs' configuration"

        logs = app_config["logs"]
        if not isinstance(logs, dict):
            return False, f"App '{app_name}' logs must be a dictionary"
        if "log_group" not in logs:
            return False, f"App '{app_name}' missing required 'logs.log_group'"

    return True, None


def load_apps_yaml(file_path: Path) -> Dict[str, Any]:
    """Load apps from a YAML input file."""
    file_path = Path(file_path)
    if not file_path.exists():
        return {}

    try:
        with open(file_path) as f:
            data = yaml.safe_load(f) or {}
        return data
    except yaml.YAMLError:
        return {}


# --- Servers YAML Import/Export ---
def get_servers_template() -> str:
    """Generate a template YAML file content for servers."""
    template = """# Servers Configuration File
# =====================================
# Bulk import servers for SSH access.
#
# Usage:
#   1. Fill in your servers below
#   2. Run: devops admin servers-import --file servers.yaml
#

servers:
  # Example web server
  web-1:
    host: 10.0.1.10
    user: deploy
    port: 22
    key: ~/.ssh/id_rsa
    tags:
      - web
      - production
    teams:
      - default
      - frontend

  # Example API server
  api-prod:
    host: api.example.com
    user: ubuntu
    port: 22
    key: ~/.ssh/api_key
    tags:
      - api
      - production
    teams:
      - default
      - backend

  # Example database server
  db-master:
    host: 10.0.2.100
    user: admin
    port: 2222
    key: ~/.ssh/db_key
    tags:
      - database
      - production
    teams:
      - default

# Notes:
# - host: Required - Hostname or IP address
# - user: Required - SSH username
# - port: Optional - SSH port (defaults to 22)
# - key: Optional - Path to SSH key (defaults to ~/.ssh/id_rsa)
# - tags: Optional - List of tags for grouping
# - teams: Optional - Teams with access (defaults to ['default'])
"""
    return template


def validate_servers_yaml(data: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    """Validate the structure of servers from YAML."""
    if not data:
        return False, "Empty or invalid YAML data"

    if "servers" not in data:
        return False, "Missing 'servers' key in YAML file"

    servers = data["servers"]

    if not isinstance(servers, dict):
        return False, "'servers' must be a dictionary"

    if not servers:
        return False, "No servers defined in 'servers'"

    for server_name, server_config in servers.items():
        if not isinstance(server_config, dict):
            return False, f"Server '{server_name}' must be a dictionary"

        # Required fields
        if "host" not in server_config or not server_config["host"]:
            return False, f"Server '{server_name}' missing required 'host'"

        if "user" not in server_config or not server_config["user"]:
            return False, f"Server '{server_name}' missing required 'user'"

    return True, None


def load_servers_yaml(file_path: Path) -> Dict[str, Any]:
    """Load servers from a YAML input file."""
    file_path = Path(file_path)
    if not file_path.exists():
        return {}

    try:
        with open(file_path) as f:
            data = yaml.safe_load(f) or {}
        return data
    except yaml.YAMLError:
        return {}


# --- Teams YAML Import/Export ---
def get_teams_template() -> str:
    """Generate a template YAML file content for teams."""
    template = """# Teams Configuration File
# =====================================
# Bulk import teams for access control.
#
# Usage:
#   1. Fill in your teams below
#   2. Run: devops admin teams-import --file teams.yaml
#

teams:
  # Example backend team
  backend:
    name: backend
    description: Backend development team
    apps:
      - api-service
      - worker
    servers:
      - api-prod
      - db-master

  # Example frontend team
  frontend:
    name: frontend
    description: Frontend development team
    apps:
      - "*"  # Access to all apps
    servers:
      - web-1

  # Example devops team with full access
  devops:
    name: devops
    description: DevOps team with full access
    apps:
      - "*"
    servers:
      - "*"

# Notes:
# - name: Required - Team name
# - description: Optional - Human-readable description
# - apps: Optional - List of app names or ['*'] for all
# - servers: Optional - List of server names/tags or ['*'] for all
"""
    return template


def validate_teams_yaml(data: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    """Validate the structure of teams from YAML."""
    if not data:
        return False, "Empty or invalid YAML data"

    if "teams" not in data:
        return False, "Missing 'teams' key in YAML file"

    teams = data["teams"]

    if not isinstance(teams, dict):
        return False, "'teams' must be a dictionary"

    if not teams:
        return False, "No teams defined in 'teams'"

    for team_name, team_config in teams.items():
        if not isinstance(team_config, dict):
            return False, f"Team '{team_name}' must be a dictionary"

        # Name is required (can default to key)
        if "name" not in team_config:
            team_config["name"] = team_name

    return True, None


def load_teams_yaml(file_path: Path) -> Dict[str, Any]:
    """Load teams from a YAML input file."""
    file_path = Path(file_path)
    if not file_path.exists():
        return {}

    try:
        with open(file_path) as f:
            data = yaml.safe_load(f) or {}
        return data
    except yaml.YAMLError:
        return {}


# --- Websites YAML Import/Export ---
def get_websites_template() -> str:
    """Generate a template YAML file content for websites."""
    template = """# Websites Configuration File
# =====================================
# Bulk import websites for health monitoring.
#
# Usage:
#   1. Fill in your websites below
#   2. Run: devops admin websites-import --file websites.yaml
#

websites:
  # Example production website
  frontend-prod:
    name: frontend-prod
    url: https://www.example.com/health
    expected_status: 200
    method: GET
    timeout: 10
    teams:
      - default
      - frontend

  # Example API health check
  api-health:
    name: api-health
    url: https://api.example.com/health
    expected_status: 200
    method: GET
    timeout: 5
    teams:
      - default
      - backend

  # Example internal service
  internal-dashboard:
    name: internal-dashboard
    url: https://dashboard.internal.com
    expected_status: 200
    method: HEAD
    timeout: 15
    teams:
      - default

# Notes:
# - name: Optional - Display name (defaults to key)
# - url: Required - Full URL to check
# - expected_status: Optional - Expected HTTP status (defaults to 200)
# - method: Optional - HTTP method: GET, POST, HEAD (defaults to GET)
# - timeout: Optional - Timeout in seconds (defaults to 10)
# - teams: Optional - Teams with access (defaults to ['default'])
"""
    return template


def validate_websites_yaml(data: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    """Validate the structure of websites from YAML."""
    if not data:
        return False, "Empty or invalid YAML data"

    if "websites" not in data:
        return False, "Missing 'websites' key in YAML file"

    websites = data["websites"]

    if not isinstance(websites, dict):
        return False, "'websites' must be a dictionary"

    if not websites:
        return False, "No websites defined in 'websites'"

    valid_methods = ["GET", "POST", "HEAD"]

    for website_name, website_config in websites.items():
        if not isinstance(website_config, dict):
            return False, f"Website '{website_name}' must be a dictionary"

        # URL is required
        if "url" not in website_config or not website_config["url"]:
            return False, f"Website '{website_name}' missing required 'url'"

        url = website_config["url"]
        if not url.startswith(("http://", "https://")):
            return False, f"Website '{website_name}' has invalid URL format. Must start with http:// or https://"

        # Validate method if provided
        method = website_config.get("method", "GET")
        if method not in valid_methods:
            return False, f"Website '{website_name}' has invalid method '{method}'. Must be one of: {', '.join(valid_methods)}"

    return True, None


def load_websites_yaml(file_path: Path) -> Dict[str, Any]:
    """Load websites from a YAML input file."""
    file_path = Path(file_path)
    if not file_path.exists():
        return {}

    try:
        with open(file_path) as f:
            data = yaml.safe_load(f) or {}
        return data
    except yaml.YAMLError:
        return {}


# --- Repos YAML Import/Export ---
def get_repos_template() -> str:
    """Generate a template YAML file content for repos."""
    template = """# Repositories Configuration File
# =====================================
# Bulk import GitHub repositories.
#
# Usage:
#   1. Fill in your repositories below
#   2. Run: devops admin repos-import --file repos.yaml
#

repos:
  # Example backend repository
  backend:
    owner: myorg
    repo: backend-service
    description: Main backend API service
    default_branch: main
    visibility: private
    private: true
    language: Python

  # Example frontend repository
  frontend:
    owner: myorg
    repo: frontend-app
    description: React frontend application
    default_branch: main
    visibility: private
    private: true
    language: TypeScript

  # Example shared library
  shared-lib:
    owner: myorg
    repo: shared-library
    description: Shared utilities library
    default_branch: develop
    visibility: internal
    private: true
    language: JavaScript

# Notes:
# - owner: Required - GitHub organization or username
# - repo: Required - Repository name
# - description: Optional - Repository description
# - default_branch: Optional - Default branch (defaults to 'main')
# - visibility: Optional - One of: public, private, internal
# - private: Optional - Boolean indicating if repo is private
# - language: Optional - Primary programming language
"""
    return template


def validate_repos_yaml(data: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    """Validate the structure of repos from YAML."""
    if not data:
        return False, "Empty or invalid YAML data"

    if "repos" not in data:
        return False, "Missing 'repos' key in YAML file"

    repos = data["repos"]

    if not isinstance(repos, dict):
        return False, "'repos' must be a dictionary"

    if not repos:
        return False, "No repos defined in 'repos'"

    for repo_name, repo_config in repos.items():
        if not isinstance(repo_config, dict):
            return False, f"Repo '{repo_name}' must be a dictionary"

        # Required fields
        if "owner" not in repo_config or not repo_config["owner"]:
            return False, f"Repo '{repo_name}' missing required 'owner'"

        if "repo" not in repo_config or not repo_config["repo"]:
            return False, f"Repo '{repo_name}' missing required 'repo'"

    return True, None


def load_repos_yaml(file_path: Path) -> Dict[str, Any]:
    """Load repos from a YAML input file."""
    file_path = Path(file_path)
    if not file_path.exists():
        return {}

    try:
        with open(file_path) as f:
            data = yaml.safe_load(f) or {}
        return data
    except yaml.YAMLError:
        return {}


# --- Meetings YAML Import/Export ---
def get_meetings_template() -> str:
    """Generate a template YAML file content for meetings."""
    template = """# Meetings Configuration File
# =====================================
# Bulk import meeting configurations.
#
# Usage:
#   1. Fill in your meetings below
#   2. Run: devops admin meetings-import --file meetings.yaml
#

meetings:
  # Daily standup
  standup:
    name: Daily Standup
    time: "09:30"
    link: https://meet.google.com/abc-defg-hij

  # Afternoon sync
  afternoon:
    name: Afternoon Sync
    time: "15:00"
    link: https://zoom.us/j/1234567890

  # Evening review
  evening:
    name: Evening Review
    time: "18:00"
    link: https://meet.google.com/xyz-uvwx-rst

# Notes:
# - name: Optional - Display name for the meeting
# - time: Required - Time in HH:MM format (24-hour)
# - link: Required - Google Meet, Zoom, or other meeting link
"""
    return template


def validate_meetings_yaml(data: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    """Validate the structure of meetings from YAML."""
    if not data:
        return False, "Empty or invalid YAML data"

    if "meetings" not in data:
        return False, "Missing 'meetings' key in YAML file"

    meetings = data["meetings"]

    if not isinstance(meetings, dict):
        return False, "'meetings' must be a dictionary"

    if not meetings:
        return False, "No meetings defined in 'meetings'"

    import re
    time_pattern = re.compile(r'^([01]?[0-9]|2[0-3]):[0-5][0-9]$')

    for meeting_id, meeting_config in meetings.items():
        if not isinstance(meeting_config, dict):
            return False, f"Meeting '{meeting_id}' must be a dictionary"

        # Time is required
        if "time" not in meeting_config or not meeting_config["time"]:
            return False, f"Meeting '{meeting_id}' missing required 'time'"

        time_str = str(meeting_config["time"])
        if not time_pattern.match(time_str):
            return False, f"Meeting '{meeting_id}' has invalid time format. Use HH:MM (24-hour)"

        # Link is required
        if "link" not in meeting_config or not meeting_config["link"]:
            return False, f"Meeting '{meeting_id}' missing required 'link'"

    return True, None


def load_meetings_yaml(file_path: Path) -> Dict[str, Any]:
    """Load meetings from a YAML input file."""
    file_path = Path(file_path)
    if not file_path.exists():
        return {}

    try:
        with open(file_path) as f:
            data = yaml.safe_load(f) or {}
        return data
    except yaml.YAMLError:
        return {}
