"""Utility classes for the dashboard."""

import time
from typing import Optional, List
from collections import defaultdict

class RateLimiter:
    """Simple in-memory rate limiter for authentication endpoints."""

    def __init__(self, max_attempts: int = 5, window_seconds: int = 300):
        self.max_attempts = max_attempts
        self.window_seconds = window_seconds
        self._attempts: dict = defaultdict(list)

    def is_rate_limited(self, key: str) -> bool:
        """Check if key (IP or email) is rate limited."""
        now = time.time()
        # Clean old attempts
        self._attempts[key] = [
            t for t in self._attempts[key] if now - t < self.window_seconds
        ]
        return len(self._attempts[key]) >= self.max_attempts

    def record_attempt(self, key: str):
        """Record an authentication attempt."""
        self._attempts[key].append(time.time())

    def reset(self, key: str):
        """Reset attempts for a key (on successful login)."""
        self._attempts[key] = []

    def get_remaining_time(self, key: str) -> int:
        """Get seconds until rate limit resets."""
        if not self._attempts[key]:
            return 0
        oldest = min(self._attempts[key])
        return max(0, int(self.window_seconds - (time.time() - oldest)))


class TTLCache:
    """Simple time-to-live cache for API responses."""

    def __init__(self, default_ttl: int = 300):
        self.default_ttl = default_ttl
        self._cache: dict = {}
        self._timestamps: dict = {}

    def get(self, key: str) -> Optional[dict]:
        """Get value from cache if not expired."""
        if key not in self._cache:
            return None
        if time.time() - self._timestamps.get(key, 0) > self.default_ttl:
            self.delete(key)
            return None
        return self._cache[key]

    def set(self, key: str, value: dict, ttl: Optional[int] = None):
        """Set value in cache with optional custom TTL."""
        self._cache[key] = value
        self._timestamps[key] = time.time()

    def delete(self, key: str):
        """Delete key from cache."""
        self._cache.pop(key, None)
        self._timestamps.pop(key, None)

    def clear(self):
        """Clear entire cache."""
        self._cache.clear()
        self._timestamps.clear()

    def cleanup(self):
        """Remove expired entries."""
        now = time.time()
        expired = [k for k, t in self._timestamps.items() if now - t > self.default_ttl]
        for key in expired:
            self.delete(key)
