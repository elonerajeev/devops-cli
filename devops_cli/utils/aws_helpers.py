"""AWS session and credential helpers for DevOps CLI."""

import json
from pathlib import Path
from typing import Optional

import typer
from devops_cli.config.loader import load_aws_config
from devops_cli.utils.output import error

# Secrets directory
SECRETS_DIR = Path.home() / ".devops-cli" / "secrets"

# Try to import boto3
try:
    import boto3
    from botocore.exceptions import ClientError

    BOTO3_AVAILABLE = True
except ImportError:
    BOTO3_AVAILABLE = False


def get_aws_session(role_name: str = None, region: str = None):
    """Get AWS session, optionally assuming a role.

    Args:
        role_name: Optional IAM role name to assume
        region: Optional AWS region override

    Returns:
        boto3.Session object

    Raises:
        typer.Exit: If boto3 not available or role not found

    Examples:
        >>> session = get_aws_session()  # Default session
        >>> session = get_aws_session(role_name='prod-readonly')  # Assume role
    """
    if not BOTO3_AVAILABLE:
        error("boto3 is not installed. Run: pip install boto3")
        raise typer.Exit(1)

    aws_config = load_aws_config()

    if role_name:
        role_config = aws_config.get("roles", {}).get(role_name)
        if not role_config:
            error(f"AWS role '{role_name}' not found")
            raise typer.Exit(1)

        role_arn = role_config.get("role_arn")
        region = (
            region
            or role_config.get("region")
            or aws_config.get("default_region", "us-east-1")
        )
        external_id = role_config.get("external_id")

        # Check for stored credentials
        creds_file = SECRETS_DIR / f"aws_{role_name}.creds"
        if creds_file.exists():
            from devops_cli.config.aws_credentials import _get_or_create_encryption_key
            from cryptography.fernet import Fernet

            try:
                key = _get_or_create_encryption_key()
                fernet = Fernet(key)
                encrypted = creds_file.read_bytes()
                decrypted = fernet.decrypt(encrypted)
                creds_data = json.loads(decrypted.decode())

                # Create session with stored credentials
                session = boto3.Session(
                    aws_access_key_id=creds_data["access_key"],
                    aws_secret_access_key=creds_data["secret_key"],
                    region_name=region,
                )
            except Exception as e:
                error(f"Failed to load role credentials: {e}")
                session = boto3.Session(region_name=region)
        else:
            # Use default credentials
            session = boto3.Session(region_name=region)

        # Assume the role
        sts = session.client("sts")
        assume_kwargs = {
            "RoleArn": role_arn,
            "RoleSessionName": "devops-cli-session",
            "DurationSeconds": 3600,
        }
        if external_id:
            assume_kwargs["ExternalId"] = external_id

        try:
            response = sts.assume_role(**assume_kwargs)
            credentials = response["Credentials"]

            return boto3.Session(
                aws_access_key_id=credentials["AccessKeyId"],
                aws_secret_access_key=credentials["SecretAccessKey"],
                aws_session_token=credentials["SessionToken"],
                region_name=region,
            )
        except ClientError as e:
            error(f"Failed to assume role: {e}")
            raise typer.Exit(1)
    else:
        region = region or aws_config.get("default_region", "us-east-1")
        return boto3.Session(region_name=region)


def get_aws_session_from_credentials(region: Optional[str] = None):
    """Get AWS session using stored credentials from aws-configure.

    This is for simple credential-based access (CloudWatch logs, etc.)
    Does NOT use ~/.aws/credentials or environment variables.

    Args:
        region: Optional AWS region override

    Returns:
        boto3.Session object

    Raises:
        typer.Exit: If credentials not configured or boto3 not available
    """
    if not BOTO3_AVAILABLE:
        error("boto3 is not installed. Run: pip install boto3")
        raise typer.Exit(1)

    # Load credentials from secure storage
    from devops_cli.config.aws_credentials import load_aws_credentials
    from devops_cli.utils.output import info

    creds = load_aws_credentials()

    if not creds:
        error("AWS credentials not configured")
        info("Ask your admin to configure AWS access with:")
        info("  devops admin aws-configure")
        raise typer.Exit(1)

    # Use explicit credentials (NOT boto3's default credential chain)
    try:
        session = boto3.Session(
            aws_access_key_id=creds["access_key"],
            aws_secret_access_key=creds["secret_key"],
            region_name=region or creds["region"],
        )
        return session
    except Exception as e:
        error(f"Failed to create AWS session: {e}")
        info("Contact your admin to reconfigure AWS credentials")
        raise typer.Exit(1)
