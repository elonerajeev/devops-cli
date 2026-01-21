"""Authentication manager for DevOps CLI.

Security features:
- Tokens are hashed using SHA-256 + salt (never stored in plain text)
- Session tokens expire after configurable time
- Failed login attempts are rate-limited
- Audit logging for all auth events
"""

import os
import json
import hashlib
import secrets
import functools
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, Any

# Auth configuration
AUTH_DIR = Path.home() / ".devops-cli" / "auth"
USERS_FILE = AUTH_DIR / "users.json"
SESSIONS_FILE = AUTH_DIR / "sessions.json"
AUDIT_LOG = AUTH_DIR / "audit.log"
LOCKOUT_FILE = AUTH_DIR / "lockout.json"

# Security settings
TOKEN_PREFIX = "DVC"  # DevOps CLI
TOKEN_LENGTH = 32
SESSION_EXPIRY_HOURS = 8
MAX_FAILED_ATTEMPTS = 5
LOCKOUT_MINUTES = 15


def _ensure_auth_dir():
    """Ensure auth directory exists with proper permissions."""
    AUTH_DIR.mkdir(parents=True, exist_ok=True)
    # Set directory permissions to owner only (700)
    os.chmod(AUTH_DIR, 0o700)


def _hash_token(token: str, salt: str) -> str:
    """Hash token with salt using SHA-256."""
    return hashlib.sha256(f"{salt}{token}".encode()).hexdigest()


def _generate_token() -> str:
    """Generate a secure random token."""
    random_part = secrets.token_urlsafe(TOKEN_LENGTH)
    return f"{TOKEN_PREFIX}-{random_part}"


def _generate_salt() -> str:
    """Generate a random salt."""
    return secrets.token_hex(16)


def _load_json(file_path: Path) -> Dict:
    """Load JSON file safely."""
    if file_path.exists():
        try:
            return json.loads(file_path.read_text())
        except json.JSONDecodeError:
            return {}
    return {}


def _save_json(file_path: Path, data: Dict):
    """Save JSON file with secure permissions."""
    _ensure_auth_dir()
    file_path.write_text(json.dumps(data, indent=2, default=str))
    os.chmod(file_path, 0o600)  # Owner read/write only


def _log_audit(event: str, email: str = None, details: str = None):
    """Log authentication events for audit."""
    _ensure_auth_dir()
    timestamp = datetime.now().isoformat()
    log_entry = f"{timestamp} | {event}"
    if email:
        log_entry += f" | {email}"
    if details:
        log_entry += f" | {details}"
    log_entry += "\n"

    with open(AUDIT_LOG, "a") as f:
        f.write(log_entry)
    os.chmod(AUDIT_LOG, 0o600)


class AuthManager:
    """Manages user authentication for DevOps CLI."""

    def __init__(self):
        _ensure_auth_dir()

    # ==================== User Management (Admin) ====================

    def register_user(self, email: str, name: str = None, role: str = "developer") -> str:
        """Register a new user and return their token.

        Args:
            email: User's email (unique identifier)
            name: User's display name
            role: User role (developer, admin)

        Returns:
            The plain-text token (only shown once!)
        """
        users = _load_json(USERS_FILE)

        # Check if user already exists
        if email in users:
            raise ValueError(f"User '{email}' already exists")

        # Generate token and salt
        token = _generate_token()
        salt = _generate_salt()
        token_hash = _hash_token(token, salt)

        # Store user (token is hashed, never plain text)
        users[email] = {
            "name": name or email.split("@")[0],
            "email": email,
            "role": role,
            "token_hash": token_hash,
            "salt": salt,
            "created_at": datetime.now().isoformat(),
            "created_by": self.get_current_session().get("email", "system") if self.get_current_session() else "system",
            "active": True,
            "last_login": None,
        }

        _save_json(USERS_FILE, users)
        _log_audit("USER_REGISTERED", email, f"role={role}")

        return token  # Return plain token (only time it's visible!)

    def list_users(self) -> list:
        """List all registered users."""
        users = _load_json(USERS_FILE)
        return [
            {
                "email": email,
                "name": data.get("name"),
                "role": data.get("role"),
                "active": data.get("active", True),
                "created_at": data.get("created_at"),
                "last_login": data.get("last_login"),
            }
            for email, data in users.items()
        ]

    def remove_user(self, email: str) -> bool:
        """Remove a user."""
        users = _load_json(USERS_FILE)

        if email not in users:
            return False

        del users[email]
        _save_json(USERS_FILE, users)

        # Also invalidate any sessions
        self._invalidate_user_sessions(email)
        _log_audit("USER_REMOVED", email)

        return True

    def deactivate_user(self, email: str) -> bool:
        """Deactivate a user (keeps record but prevents login)."""
        users = _load_json(USERS_FILE)

        if email not in users:
            return False

        users[email]["active"] = False
        _save_json(USERS_FILE, users)

        self._invalidate_user_sessions(email)
        _log_audit("USER_DEACTIVATED", email)

        return True

    def activate_user(self, email: str) -> bool:
        """Reactivate a deactivated user."""
        users = _load_json(USERS_FILE)

        if email not in users:
            return False

        users[email]["active"] = True
        _save_json(USERS_FILE, users)
        _log_audit("USER_ACTIVATED", email)

        return True

    def reset_token(self, email: str) -> str:
        """Generate a new token for a user (invalidates old one)."""
        users = _load_json(USERS_FILE)

        if email not in users:
            raise ValueError(f"User '{email}' not found")

        # Generate new token
        token = _generate_token()
        salt = _generate_salt()
        token_hash = _hash_token(token, salt)

        users[email]["token_hash"] = token_hash
        users[email]["salt"] = salt

        _save_json(USERS_FILE, users)

        # Invalidate existing sessions
        self._invalidate_user_sessions(email)
        _log_audit("TOKEN_RESET", email)

        return token

    # ==================== Authentication (Developer) ====================

    def login(self, email: str, token: str) -> bool:
        """Authenticate user and create session.

        Args:
            email: User's email
            token: User's token

        Returns:
            True if login successful
        """
        # Check lockout
        if self._is_locked_out(email):
            _log_audit("LOGIN_BLOCKED_LOCKOUT", email)
            raise ValueError("Too many failed attempts. Try again later.")

        users = _load_json(USERS_FILE)

        # Check user exists
        if email not in users:
            self._record_failed_attempt(email)
            _log_audit("LOGIN_FAILED_USER_NOT_FOUND", email)
            return False

        user = users[email]

        # Check user is active
        if not user.get("active", True):
            _log_audit("LOGIN_FAILED_USER_INACTIVE", email)
            raise ValueError("Account is deactivated. Contact admin.")

        # Verify token
        token_hash = _hash_token(token, user["salt"])
        if token_hash != user["token_hash"]:
            self._record_failed_attempt(email)
            _log_audit("LOGIN_FAILED_INVALID_TOKEN", email)
            return False

        # Create session
        session_token = secrets.token_urlsafe(32)
        sessions = _load_json(SESSIONS_FILE)

        # Clear old sessions for this user
        sessions = {k: v for k, v in sessions.items() if v.get("email") != email}

        sessions[session_token] = {
            "email": email,
            "name": user.get("name"),
            "role": user.get("role"),
            "created_at": datetime.now().isoformat(),
            "expires_at": (datetime.now() + timedelta(hours=SESSION_EXPIRY_HOURS)).isoformat(),
        }

        _save_json(SESSIONS_FILE, sessions)

        # Update last login
        users[email]["last_login"] = datetime.now().isoformat()
        _save_json(USERS_FILE, users)

        # Clear failed attempts
        self._clear_failed_attempts(email)

        # Store current session token locally
        self._save_current_session(session_token)

        _log_audit("LOGIN_SUCCESS", email)
        return True

    def logout(self) -> bool:
        """Logout current user."""
        session = self.get_current_session()
        if not session:
            return False

        # Remove session
        sessions = _load_json(SESSIONS_FILE)
        current_token = self._get_current_session_token()

        if current_token in sessions:
            email = sessions[current_token].get("email")
            del sessions[current_token]
            _save_json(SESSIONS_FILE, sessions)
            _log_audit("LOGOUT", email)

        # Clear local session
        self._clear_current_session()
        return True

    def get_current_session(self) -> Optional[Dict]:
        """Get current session if valid."""
        token = self._get_current_session_token()
        if not token:
            return None

        sessions = _load_json(SESSIONS_FILE)
        session = sessions.get(token)

        if not session:
            return None

        # Check expiration
        expires_at = datetime.fromisoformat(session["expires_at"])
        if datetime.now() > expires_at:
            # Session expired
            del sessions[token]
            _save_json(SESSIONS_FILE, sessions)
            self._clear_current_session()
            return None

        return session

    def is_authenticated(self) -> bool:
        """Check if current user is authenticated."""
        return self.get_current_session() is not None

    def refresh_session(self) -> bool:
        """Refresh current session expiration."""
        token = self._get_current_session_token()
        if not token:
            return False

        sessions = _load_json(SESSIONS_FILE)
        if token not in sessions:
            return False

        sessions[token]["expires_at"] = (
            datetime.now() + timedelta(hours=SESSION_EXPIRY_HOURS)
        ).isoformat()

        _save_json(SESSIONS_FILE, sessions)
        return True

    # ==================== Admin Check ====================

    def is_admin(self) -> bool:
        """Check if current user is an admin."""
        session = self.get_current_session()
        if not session:
            return False
        return session.get("role") == "admin"

    def require_admin(self) -> bool:
        """Check if admin, raise error if not."""
        if not self.is_authenticated():
            raise ValueError("Not authenticated. Run: devops auth login")
        if not self.is_admin():
            raise ValueError("Admin access required")
        return True

    # ==================== Audit Logs ====================

    def get_audit_logs(self, limit: int = 50) -> list:
        """Get recent audit logs."""
        if not AUDIT_LOG.exists():
            return []

        lines = AUDIT_LOG.read_text().strip().split("\n")
        return lines[-limit:]

    # ==================== Internal Methods ====================

    def _save_current_session(self, token: str):
        """Save session token to local file."""
        session_file = AUTH_DIR / ".session"
        session_file.write_text(token)
        os.chmod(session_file, 0o600)

    def _get_current_session_token(self) -> Optional[str]:
        """Get current session token."""
        session_file = AUTH_DIR / ".session"
        if session_file.exists():
            return session_file.read_text().strip()
        return None

    def _clear_current_session(self):
        """Clear current session."""
        session_file = AUTH_DIR / ".session"
        if session_file.exists():
            session_file.unlink()

    def _invalidate_user_sessions(self, email: str):
        """Invalidate all sessions for a user."""
        sessions = _load_json(SESSIONS_FILE)
        sessions = {k: v for k, v in sessions.items() if v.get("email") != email}
        _save_json(SESSIONS_FILE, sessions)

    def _record_failed_attempt(self, email: str):
        """Record a failed login attempt."""
        lockout = _load_json(LOCKOUT_FILE)

        if email not in lockout:
            lockout[email] = {"attempts": 0, "first_attempt": None}

        lockout[email]["attempts"] += 1
        lockout[email]["last_attempt"] = datetime.now().isoformat()

        if lockout[email]["first_attempt"] is None:
            lockout[email]["first_attempt"] = datetime.now().isoformat()

        _save_json(LOCKOUT_FILE, lockout)

    def _is_locked_out(self, email: str) -> bool:
        """Check if user is locked out."""
        lockout = _load_json(LOCKOUT_FILE)

        if email not in lockout:
            return False

        data = lockout[email]

        if data["attempts"] < MAX_FAILED_ATTEMPTS:
            return False

        # Check if lockout period has passed
        last_attempt = datetime.fromisoformat(data["last_attempt"])
        lockout_until = last_attempt + timedelta(minutes=LOCKOUT_MINUTES)

        if datetime.now() > lockout_until:
            # Lockout expired, clear it
            self._clear_failed_attempts(email)
            return False

        return True

    def _clear_failed_attempts(self, email: str):
        """Clear failed attempts for a user."""
        lockout = _load_json(LOCKOUT_FILE)
        if email in lockout:
            del lockout[email]
            _save_json(LOCKOUT_FILE, lockout)


# ==================== Decorators ====================

def require_auth(func):
    """Decorator to require authentication for a command."""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        auth = AuthManager()
        if not auth.is_authenticated():
            from devops_cli.utils.output import error, info
            error("Authentication required")
            info("Run: devops auth login")
            raise SystemExit(1)
        return func(*args, **kwargs)
    return wrapper


def require_admin_auth(func):
    """Decorator to require admin authentication."""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        auth = AuthManager()
        if not auth.is_authenticated():
            from devops_cli.utils.output import error, info
            error("Authentication required")
            info("Run: devops auth login")
            raise SystemExit(1)
        if not auth.is_admin():
            from devops_cli.utils.output import error
            error("Admin access required")
            raise SystemExit(1)
        return func(*args, **kwargs)
    return wrapper


def get_current_user() -> Optional[Dict]:
    """Get current authenticated user."""
    return AuthManager().get_current_session()
