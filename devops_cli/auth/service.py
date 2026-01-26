"""
Authentication service providing business logic for auth operations.
"""

import hashlib
import secrets
from datetime import datetime, timedelta
from typing import Optional

from devops_cli.auth.stores import UserStore, SessionStore

# Security settings
TOKEN_PREFIX = "DVC"
TOKEN_LENGTH = 32
SESSION_EXPIRY_HOURS = 8


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


class AuthService:
    """Service for authentication business logic."""

    def __init__(
        self,
        user_store: UserStore,
        session_store: SessionStore,
        current_user: Optional[str] = "system",
    ):
        self._user_store = user_store
        self._session_store = session_store
        self._current_user = current_user

    def register_user(
        self,
        email: str,
        name: str = None,
        role: str = "developer",
        team: str = "default",
    ) -> str:
        """Register a new user and return their token."""
        token = _generate_token()
        salt = _generate_salt()
        token_hash = _hash_token(token, salt)

        user_data = {
            "name": name or email.split("@")[0],
            "email": email,
            "role": role,
            "team": team,
            "token_hash": token_hash,
            "salt": salt,
            "created_at": datetime.now().isoformat(),
            "created_by": self._current_user,
            "active": True,
            "last_login": None,
        }
        self._user_store.add_user(email, user_data)
        return token

    def login(self, email: str, token: str) -> Optional[str]:
        """Authenticate user and create a session, returning a session token."""
        user = self._user_store.get_user(email)

        if not user:
            return None

        if not user.get("active", True):
            raise ValueError("Account is deactivated. Contact admin.")

        token_hash = _hash_token(token, user["salt"])
        if token_hash != user["token_hash"]:
            return None

        # Create session
        session_token = secrets.token_urlsafe(32)
        session_data = {
            "email": email,
            "name": user.get("name"),
            "role": user.get("role"),
            "created_at": datetime.now().isoformat(),
            "expires_at": (
                datetime.now() + timedelta(hours=SESSION_EXPIRY_HOURS)
            ).isoformat(),
        }
        self._session_store.add_session(session_token, session_data)

        # Update last login
        user["last_login"] = datetime.now().isoformat()
        self._user_store.update_user(email, user)

        return session_token

    def reset_token(self, email: str) -> str:
        """Generate a new token for a user (invalidates old one)."""
        user = self._user_store.get_user(email)
        if not user:
            raise ValueError(f"User '{email}' not found")

        token = _generate_token()
        salt = _generate_salt()
        token_hash = _hash_token(token, salt)

        user["token_hash"] = token_hash
        user["salt"] = salt
        self._user_store.update_user(email, user)

        # Invalidate existing sessions
        self._session_store.remove_user_sessions(email)

        return token
