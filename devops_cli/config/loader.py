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
