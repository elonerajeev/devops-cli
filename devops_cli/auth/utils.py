"""
Utility functions for authentication and session management.
"""

import json
import os
import stat
from pathlib import Path
from typing import Dict

# Auth configuration
AUTH_DIR = Path.home() / ".devops-cli" / "auth"


def _ensure_auth_dir():
    """Ensure the authentication directory exists with correct permissions."""
    if not AUTH_DIR.exists():
        AUTH_DIR.mkdir(parents=True, exist_ok=True)
    # Set directory permissions to 700 (drwx------)
    os.chmod(AUTH_DIR, stat.S_IRWXU)


def _load_json(file_path: Path) -> Dict:
    """Load data from a JSON file safely."""
    if not file_path.exists():
        return {}
    try:
        with open(file_path, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return {}


def _save_json(file_path: Path, data: Dict):
    """Save data to a JSON file securely and atomically."""
    _ensure_auth_dir()

    # Write to a temporary file first for atomicity
    temp_file = file_path.with_suffix(".tmp")
    try:
        # Use os.open with O_CREAT and mode 0600 to ensure the file is created 
        # with restricted permissions from the start.
        fd = os.open(temp_file, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w") as f:
            json.dump(data, f, indent=4)

        # Atomic rename
        temp_file.replace(file_path)
    except Exception as e:
        if temp_file.exists():
            temp_file.unlink()
        raise e
