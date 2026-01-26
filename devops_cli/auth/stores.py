"""
Stores for handling data persistence for authentication.
"""

from pathlib import Path
from typing import Dict, Optional

from devops_cli.auth.utils import _load_json, _save_json, AUTH_DIR

# File paths
USERS_FILE = AUTH_DIR / "users.json"
SESSIONS_FILE = AUTH_DIR / "sessions.json"
LOCKOUT_FILE = AUTH_DIR / "lockout.json"


class UserStore:
    """Handles CRUD operations for users."""

    def __init__(self, users_file: Path = USERS_FILE):
        self._users_file = users_file
        self._users = None

    def _load(self) -> Dict:
        if self._users is None:
            self._users = _load_json(self._users_file)
        return self._users

    def _save(self):
        if self._users is not None:
            _save_json(self._users_file, self._users)

    def get_user(self, email: str) -> Optional[Dict]:
        """Get a user by email."""
        return self._load().get(email)

    def get_all_users(self) -> Dict:
        """Get all users."""
        return self._load()

    def add_user(self, email: str, user_data: Dict):
        """Add a new user."""
        users = self._load()
        if email in users:
            raise ValueError(f"User '{email}' already exists")
        users[email] = user_data
        self._save()

    def update_user(self, email: str, user_data: Dict):
        """Update a user's data."""
        users = self._load()
        if email not in users:
            raise ValueError(f"User '{email}' not found")
        users[email].update(user_data)
        self._save()

    def remove_user(self, email: str):
        """Remove a user."""
        users = self._load()
        if email not in users:
            raise ValueError(f"User '{email}' not found")
        del users[email]
        self._save()


class SessionStore:
    """Handles CRUD operations for sessions."""

    def __init__(self, sessions_file: Path = SESSIONS_FILE):
        self._sessions_file = sessions_file
        self._sessions = None

    def _load(self) -> Dict:
        if self._sessions is None:
            self._sessions = _load_json(self._sessions_file)
        return self._sessions

    def _save(self):
        if self._sessions is not None:
            _save_json(self._sessions_file, self._sessions)

    def get_session(self, session_token: str) -> Optional[Dict]:
        """Get a session by token."""
        return self._load().get(session_token)

    def get_all_sessions(self) -> Dict:
        return self._load()

    def add_session(self, session_token: str, session_data: Dict):
        """Add a new session."""
        sessions = self._load()
        sessions[session_token] = session_data
        self._save()

    def remove_session(self, session_token: str):
        """Remove a session."""
        sessions = self._load()
        if session_token in sessions:
            del sessions[session_token]
            self._save()

    def remove_user_sessions(self, email: str):
        """Remove all sessions for a given user."""
        sessions = self._load()
        tokens_to_remove = [
            token for token, data in sessions.items() if data.get("email") == email
        ]
        if not tokens_to_remove:
            return

        for token in tokens_to_remove:
            del sessions[token]
        self._save()
