"""
Utility functions for authentication and session management.
"""
import json
import os
import stat
from pathlib import Path
from typing import Dict, Optional

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
        with open(temp_file, "w") as f:
            json.dump(data, f, indent=4)
        
        # Set file permissions to 600 (-rw-------)
        os.chmod(temp_file, stat.S_IRUSR | stat.S_IWUSR)
        
        # Atomic rename
        temp_file.replace(file_path)
    except Exception as e:
        if temp_file.exists():
            temp_file.unlink()
        raise e
