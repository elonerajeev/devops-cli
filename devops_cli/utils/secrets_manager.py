"""Utility functions for interacting with AWS Secrets Manager.

Supports secret references in configuration files:
  - ${ENV_VAR_NAME}           - Read from environment variable
  - ${AWS_SECRET:secret-name} - Read from AWS Secrets Manager
  - ${GITHUB_SECRET:name}     - Read from GitHub Secrets (via env var in CI/CD)
"""

import os
import re
import boto3
from typing import Optional, Any, Dict, Union

from botocore.exceptions import ClientError, NoCredentialsError

# Regex patterns for secret references
ENV_VAR_PATTERN = re.compile(r"\$\{([A-Z_][A-Z0-9_]*)\}")
AWS_SECRET_PATTERN = re.compile(r"\$\{AWS_SECRET:([^}]+)\}")
GITHUB_SECRET_PATTERN = re.compile(r"\$\{GITHUB_SECRET:([^}]+)\}")

# Assuming these imports exist and are accessible from a shared context
from devops_cli.config.settings import load_config
from devops_cli.config.aws_credentials import (
    load_aws_credentials,
)  # For explicit credentials


def _get_secrets_manager_client():
    """Helper to get an authenticated AWS Secrets Manager client."""
    # Attempt to load credentials configured via devops admin aws-configure
    creds = load_aws_credentials()
    if (
        creds
        and creds.get("access_key")
        and creds.get("secret_key")
        and creds.get("region")
    ):
        try:
            return boto3.client(
                "secretsmanager",
                aws_access_key_id=creds["access_key"],
                aws_secret_access_key=creds["secret_key"],
                region_name=creds["region"],
            )
        except Exception:
            # Fallback to default AWS environment configuration
            pass

    # Fallback to default AWS environment configuration (e.g., IAM role, ~/.aws/credentials)
    try:
        config = load_config()
        aws_region = config.get("aws", {}).get(
            "default_region", os.environ.get("AWS_REGION", "us-east-1")
        )
        return boto3.client("secretsmanager", region_name=aws_region)
    except Exception:
        # If all else fails, return None and let caller handle the error
        return None


def set_secret(
    name: str, value: str, description: Optional[str] = None, overwrite: bool = False
) -> bool:
    """Store a secret in AWS Secrets Manager."""
    client = _get_secrets_manager_client()
    if not client:
        print(
            "Error: Could not get AWS Secrets Manager client. Check AWS configuration."
        )
        return False

    try:
        # Check if secret already exists
        exists = False
        try:
            client.describe_secret(SecretId=name)
            exists = True
        except ClientError as e:
            if e.response["Error"]["Code"] != "ResourceNotFoundException":
                print(f"Error checking secret '{name}': {e}")
                return False

        if exists and not overwrite:
            print(
                f"Error: Secret '{name}' already exists. Use overwrite=True to update."
            )
            return False

        if exists:
            client.update_secret(
                SecretId=name,
                SecretString=value,
                Description=description or "Secret managed by DevOps CLI",
            )
            print(f"Secret '{name}' updated successfully in AWS Secrets Manager.")
        else:
            client.create_secret(
                Name=name,
                SecretString=value,
                Description=description or "Secret managed by DevOps CLI",
            )
            print(f"Secret '{name}' created successfully in AWS Secrets Manager.")
        return True

    except (ClientError, NoCredentialsError) as e:
        print(f"Error setting secret '{name}': {e}")
        print(
            "Hint: Ensure AWS credentials are configured and have Secrets Manager permissions."
        )
        return False
    except Exception as e:
        print(f"An unexpected error occurred while setting secret '{name}': {e}")
        return False


def get_secret(name: str) -> Optional[str]:
    """Retrieve a secret from AWS Secrets Manager."""
    client = _get_secrets_manager_client()
    if not client:
        return None

    try:
        response = client.get_secret_value(SecretId=name)
        return response["SecretString"]
    except ClientError as e:
        if e.response["Error"]["Code"] == "ResourceNotFoundException":
            print(f"Warning: Secret '{name}' not found in AWS Secrets Manager.")
        else:
            print(f"Error retrieving secret '{name}': {e}")
        return None
    except NoCredentialsError as e:
        print(f"Error retrieving secret '{name}': {e}")
        print("Hint: Ensure AWS credentials are configured.")
        return None
    except Exception as e:
        print(f"An unexpected error occurred while retrieving secret '{name}': {e}")
        return None


def resolve_secret_reference(value: str) -> str:
    """
    Resolve a secret reference string to its actual value.

    Supported formats:
      - ${ENV_VAR_NAME}           - Environment variable
      - ${AWS_SECRET:secret-name} - AWS Secrets Manager
      - ${GITHUB_SECRET:name}     - GitHub Secret (via env var)

    Args:
        value: String that may contain secret references

    Returns:
        Resolved string with secrets replaced, or original if no match
    """
    if not isinstance(value, str) or "${" not in value:
        return value

    result = value

    # Resolve AWS Secrets Manager references first (most specific)
    for match in AWS_SECRET_PATTERN.finditer(value):
        secret_name = match.group(1)
        secret_value = get_secret(secret_name)
        if secret_value:
            result = result.replace(match.group(0), secret_value)
        else:
            print(f"Warning: Could not resolve AWS secret: {secret_name}")

    # Resolve GitHub Secrets (these are passed as environment variables in CI/CD)
    for match in GITHUB_SECRET_PATTERN.finditer(result):
        secret_name = match.group(1)
        # GitHub secrets are exposed as environment variables in Actions
        env_value = os.environ.get(secret_name)
        if env_value:
            result = result.replace(match.group(0), env_value)
        else:
            print(f"Warning: Could not resolve GitHub secret: {secret_name}")

    # Resolve plain environment variables
    for match in ENV_VAR_PATTERN.finditer(result):
        # Skip if it's an AWS_SECRET or GITHUB_SECRET pattern
        full_match = match.group(0)
        if "AWS_SECRET:" in full_match or "GITHUB_SECRET:" in full_match:
            continue

        var_name = match.group(1)
        env_value = os.environ.get(var_name)
        if env_value:
            result = result.replace(match.group(0), env_value)
        else:
            print(f"Warning: Could not resolve environment variable: {var_name}")

    return result


def resolve_secrets_in_dict(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Recursively resolve all secret references in a dictionary.

    Args:
        data: Dictionary that may contain secret references in string values

    Returns:
        New dictionary with all secrets resolved
    """
    resolved = {}

    for key, value in data.items():
        if isinstance(value, str):
            resolved[key] = resolve_secret_reference(value)
        elif isinstance(value, dict):
            resolved[key] = resolve_secrets_in_dict(value)
        elif isinstance(value, list):
            resolved[key] = resolve_secrets_in_list(value)
        else:
            resolved[key] = value

    return resolved


def resolve_secrets_in_list(data: list) -> list:
    """
    Recursively resolve all secret references in a list.

    Args:
        data: List that may contain secret references

    Returns:
        New list with all secrets resolved
    """
    resolved = []

    for item in data:
        if isinstance(item, str):
            resolved.append(resolve_secret_reference(item))
        elif isinstance(item, dict):
            resolved.append(resolve_secrets_in_dict(item))
        elif isinstance(item, list):
            resolved.append(resolve_secrets_in_list(item))
        else:
            resolved.append(item)

    return resolved


def has_secret_references(value: Union[str, Dict, list]) -> bool:
    """
    Check if a value contains any secret references.

    Args:
        value: String, dict, or list to check

    Returns:
        True if any secret references found
    """
    if isinstance(value, str):
        return bool(
            ENV_VAR_PATTERN.search(value)
            or AWS_SECRET_PATTERN.search(value)
            or GITHUB_SECRET_PATTERN.search(value)
        )
    elif isinstance(value, dict):
        return any(has_secret_references(v) for v in value.values())
    elif isinstance(value, list):
        return any(has_secret_references(item) for item in value)
    return False


def list_secret_references(data: Union[str, Dict, list]) -> list:
    """
    List all secret references in a value (for validation/debugging).

    Args:
        data: String, dict, or list to scan

    Returns:
        List of tuples: (type, name) for each reference found
    """
    refs = []

    def scan_string(s: str):
        for match in AWS_SECRET_PATTERN.finditer(s):
            refs.append(("AWS_SECRET", match.group(1)))
        for match in GITHUB_SECRET_PATTERN.finditer(s):
            refs.append(("GITHUB_SECRET", match.group(1)))
        for match in ENV_VAR_PATTERN.finditer(s):
            var_name = match.group(1)
            if "AWS_SECRET:" not in match.group(
                0
            ) and "GITHUB_SECRET:" not in match.group(0):
                refs.append(("ENV_VAR", var_name))

    def scan_value(val):
        if isinstance(val, str):
            scan_string(val)
        elif isinstance(val, dict):
            for v in val.values():
                scan_value(v)
        elif isinstance(val, list):
            for item in val:
                scan_value(item)

    scan_value(data)
    return refs
