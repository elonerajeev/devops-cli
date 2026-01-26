"""Authentication manager for DevOps CLI.

This module provides the main interface for authentication and session management.
It acts as a facade, coordinating the AuthService, Stores, and other components.
"""

import functools
import os
from datetime import datetime, timedelta
from typing import Optional, Dict

from devops_cli.auth.service import AuthService, SESSION_EXPIRY_HOURS
from devops_cli.auth.stores import UserStore, SessionStore
from devops_cli.auth.utils import _ensure_auth_dir, _load_json, _save_json, AUTH_DIR

# Auth configuration
AUDIT_LOG = AUTH_DIR / "audit.log"
LOCKOUT_FILE = AUTH_DIR / "lockout.json"

# Security settings
MAX_FAILED_ATTEMPTS = 5
LOCKOUT_MINUTES = 15


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
        self._user_store = UserStore()
        self._session_store = SessionStore()
        current_user_email = (
            self.get_current_session().get("email")
            if self.get_current_session()
            else "system"
        )
        self._auth_service = AuthService(
            self._user_store, self._session_store, current_user_email
        )

    # ==================== User Management (Admin) ====================

    def register_user(
        self,
        email: str,
        name: str = None,
        role: str = "developer",
        team: str = "default",
    ) -> str:
        """Register a new user and return their token."""
        token = self._auth_service.register_user(email, name, role, team)
        _log_audit("USER_REGISTERED", email, f"role={role} team={team}")
        return token

    def get_user_data(self, email: str) -> Optional[Dict]:
        """Get full user data."""
        return self._user_store.get_user(email)

    def list_users(self) -> list:
        """List all registered users."""
        users = self._user_store.get_all_users()
        return [
            {
                "email": email,
                "name": data.get("name"),
                "role": data.get("role"),
                "team": data.get("team", "default"),
                "active": data.get("active", True),
                "created_at": data.get("created_at"),
                "last_login": data.get("last_login"),
            }
            for email, data in users.items()
        ]

    def remove_user(self, email: str) -> bool:
        """Remove a user."""
        try:
            self._user_store.remove_user(email)
            self._session_store.remove_user_sessions(email)
            _log_audit("USER_REMOVED", email)
            return True
        except ValueError:
            return False

    def deactivate_user(self, email: str) -> bool:
        """Deactivate a user (keeps record but prevents login)."""
        user = self._user_store.get_user(email)
        if not user:
            return False
        user["active"] = False
        self._user_store.update_user(email, user)
        self._session_store.remove_user_sessions(email)
        _log_audit("USER_DEACTIVATED", email)
        return True

    def activate_user(self, email: str) -> bool:
        """Reactivate a deactivated user."""
        user = self._user_store.get_user(email)
        if not user:
            return False
        user["active"] = True
        self._user_store.update_user(email, user)
        _log_audit("USER_ACTIVATED", email)
        return True

    def reset_token(self, email: str) -> str:
        """Generate a new token for a user (invalidates old one)."""
        token = self._auth_service.reset_token(email)
        _log_audit("TOKEN_RESET", email)
        return token

    # ==================== Authentication (Developer) ====================

    def login(self, email: str, token: str) -> bool:
        """Authenticate user and create session."""
        if self._is_locked_out(email):
            _log_audit("LOGIN_BLOCKED_LOCKOUT", email)
            raise ValueError("Too many failed attempts. Try again later.")

        session_token = self._auth_service.login(email, token)

        if not session_token:
            self._record_failed_attempt(email)
            _log_audit("LOGIN_FAILED_INVALID_TOKEN", email)
            return False

        self._clear_failed_attempts(email)
        self._save_current_session(session_token)
        _log_audit("LOGIN_SUCCESS", email)
        return True

    def logout(self) -> bool:
        """Logout current user."""
        session_token = self._get_current_session_token()
        if not session_token:
            return False

        session = self._session_store.get_session(session_token)
        if session:
            email = session.get("email")
            self._session_store.remove_session(session_token)
            _log_audit("LOGOUT", email)

        self._clear_current_session()
        return True

    def get_current_session(self) -> Optional[Dict]:
        """Get current session if valid."""
        token = self._get_current_session_token()
        if not token:
            return None

        session = self._session_store.get_session(token)
        if not session:
            return None

        # Check expiration
        expires_at = datetime.fromisoformat(session["expires_at"])
        if datetime.now() > expires_at:
            self._session_store.remove_session(token)
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

        session = self._session_store.get_session(token)
        if not session:
            return False

        session["expires_at"] = (
            datetime.now() + timedelta(hours=SESSION_EXPIRY_HOURS)
        ).isoformat()
        self._session_store.add_session(token, session)
        return True

    # ==================== Admin Check ====================

    def is_admin(self) -> bool:
        """Check if current user is an admin."""
        session = self.get_current_session()
        return session and session.get("role") == "admin"

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
        last_attempt = datetime.fromisoformat(data["last_attempt"])
        if datetime.now() > last_attempt + timedelta(minutes=LOCKOUT_MINUTES):
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
