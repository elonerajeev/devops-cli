"""Secure AWS credentials management for DevOps CLI.

Admin stores AWS credentials (Access Key + Secret Key) directly in CLI config.
These credentials are encrypted and used for all AWS operations.
No dependency on ~/.aws/credentials or AWS CLI installation.
"""

import json
import os
import tempfile
from pathlib import Path
from typing import Optional, Dict, Tuple
from cryptography.fernet import Fernet

ADMIN_DIR = Path.home() / ".devops-cli"
AWS_CREDS_FILE = ADMIN_DIR / ".aws_credentials.enc"
AWS_KEY_FILE = ADMIN_DIR / ".aws_key"


def _secure_write_file(filepath: Path, data: bytes, mode: int = 0o600) -> None:
    """
    Securely write data to file with correct permissions from the start.

    Uses atomic write pattern: write to temp file with correct permissions,
    then move to final location. This prevents race conditions where the
    file is briefly world-readable.
    """
    filepath.parent.mkdir(parents=True, exist_ok=True)

    # Create temp file in same directory (ensures same filesystem for rename)
    fd, temp_path = tempfile.mkstemp(dir=filepath.parent, prefix=".tmp_")
    try:
        # Set permissions before writing data
        os.fchmod(fd, mode)
        os.write(fd, data)
        os.close(fd)
        fd = None

        # Atomic move to final location
        os.rename(temp_path, filepath)
    finally:
        if fd is not None:
            os.close(fd)
        # Clean up temp file if still exists (rename failed)
        if os.path.exists(temp_path):
            os.unlink(temp_path)


def _get_or_create_encryption_key() -> bytes:
    """Get or create encryption key for AWS credentials."""
    ADMIN_DIR.mkdir(parents=True, mode=0o700, exist_ok=True)

    if AWS_KEY_FILE.exists():
        with open(AWS_KEY_FILE, "rb") as f:
            return f.read()

    # Generate new key and write securely
    key = Fernet.generate_key()
    _secure_write_file(AWS_KEY_FILE, key, mode=0o600)
    return key


def save_aws_credentials(
    access_key: str,
    secret_key: str,
    region: str,
    description: str = "DevOps CLI AWS Credentials",
) -> bool:
    """
    Save AWS credentials securely (encrypted).

    Uses atomic write with correct permissions to prevent race conditions.

    Args:
        access_key: AWS Access Key ID
        secret_key: AWS Secret Access Key
        region: AWS region (e.g., ap-south-1)
        description: Description of these credentials

    Returns:
        True if saved successfully
    """
    try:
        # Encrypt credentials
        key = _get_or_create_encryption_key()
        fernet = Fernet(key)

        credentials = {
            "access_key": access_key,
            "secret_key": secret_key,
            "region": region,
            "description": description,
        }

        encrypted_data = fernet.encrypt(json.dumps(credentials).encode())

        # Save encrypted file securely (atomic write with permissions)
        _secure_write_file(AWS_CREDS_FILE, encrypted_data, mode=0o600)

        return True

    except Exception as e:
        print(f"Error saving credentials: {e}")
        return False


def load_aws_credentials() -> Optional[Dict[str, str]]:
    """
    Load and decrypt AWS credentials.

    Returns:
        Dict with 'access_key', 'secret_key', 'region', 'description'
        or None if not configured
    """
    if not AWS_CREDS_FILE.exists():
        return None

    try:
        key = _get_or_create_encryption_key()
        fernet = Fernet(key)

        encrypted_data = AWS_CREDS_FILE.read_bytes()
        decrypted_data = fernet.decrypt(encrypted_data)

        credentials = json.loads(decrypted_data.decode())
        return credentials

    except Exception as e:
        print(f"Error loading credentials: {e}")
        return None


def validate_aws_credentials(
    access_key: str, secret_key: str, region: str
) -> Tuple[bool, Optional[str]]:
    """
    Validate AWS credentials by making a test API call.

    Returns:
        (is_valid, error_message)
    """
    try:
        import boto3
        from botocore.exceptions import ClientError, NoCredentialsError

        # Create session with explicit credentials
        session = boto3.Session(
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name=region,
        )

        # Test with STS GetCallerIdentity (always allowed)
        sts = session.client("sts")
        identity = sts.get_caller_identity()

        # Test CloudWatch Logs access
        logs = session.client("logs")
        try:
            logs.describe_log_groups(limit=1)
        except ClientError as e:
            error_code = e.response["Error"]["Code"]
            if error_code == "AccessDeniedException":
                return (
                    False,
                    "Credentials lack CloudWatch Logs permissions. Need: logs:DescribeLogGroups, logs:FilterLogEvents",
                )
            else:
                return False, f"AWS Error: {e.response['Error']['Message']}"

        return True, None

    except NoCredentialsError:
        return False, "Invalid credentials"
    except ClientError as e:
        return False, f"AWS Error: {e.response['Error']['Message']}"
    except Exception as e:
        return False, f"Error: {str(e)}"


def delete_aws_credentials() -> bool:
    """Delete stored AWS credentials."""
    try:
        if AWS_CREDS_FILE.exists():
            AWS_CREDS_FILE.unlink()
        if AWS_KEY_FILE.exists():
            AWS_KEY_FILE.unlink()
        return True
    except Exception:
        return False


def credentials_exist() -> bool:
    """Check if AWS credentials are configured."""
    return AWS_CREDS_FILE.exists()


def get_credentials_info() -> Optional[Dict[str, str]]:
    """
    Get non-sensitive info about stored credentials.

    Returns:
        Dict with 'region', 'description', 'access_key_preview' (masked)
    """
    creds = load_aws_credentials()
    if not creds:
        return None

    # Mask access key (show only first 4 and last 4 chars)
    access_key = creds.get("access_key", "")
    if len(access_key) > 8:
        masked_key = f"{access_key[:4]}...{access_key[-4:]}"
    else:
        masked_key = "****"

    return {
        "region": creds.get("region", "unknown"),
        "description": creds.get("description", ""),
        "access_key_preview": masked_key,
    }


def import_from_dict(credentials: Dict[str, str]) -> bool:
    """
    Import AWS credentials from a dictionary.

    This is used by YAML import functionality. Credentials are encrypted
    and stored securely. This replaces any existing credentials.

    Args:
        credentials: Dict containing 'access_key', 'secret_key', 'region',
                    and optionally 'description'

    Returns:
        True if saved successfully, False otherwise
    """
    required_keys = ["access_key", "secret_key", "region"]
    missing = [k for k in required_keys if k not in credentials]

    if missing:
        print(f"Error: Missing required keys: {', '.join(missing)}")
        return False

    return save_aws_credentials(
        access_key=credentials["access_key"],
        secret_key=credentials["secret_key"],
        region=credentials["region"],
        description=credentials.get("description", "Imported credentials"),
    )
