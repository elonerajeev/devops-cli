"""Log formatting and colorizing utilities for DevOps CLI."""

import re
from rich.text import Text

# Common patterns for sensitive information
SECRET_PATTERNS = [
    # AWS Access Keys
    r"AKIA[0-9A-Z]{16}",
    # AWS Secret Keys (basic check)
    r"(?i)aws_secret_access_key\s*[:=]\s*['\"]?([A-Za-z0-9/+=]{40})['\"]?",
    # Generic API Keys and Tokens
    r"(?i)(api[_-]?key|auth[_-]?token|secret|password|db[_-]?password)\s*[:=]\s*['\"]?([A-Za-z0-9_\-\.]{12,})['\"]?",
    # Bearer Tokens
    r"(?i)Bearer\s+([A-Za-z0-9_\-\.\/]{20,})",
    # GitHub Tokens
    r"gh[oprs]_[A-Za-z0-9]{36,}",
]


def mask_secrets(message: str) -> str:
    """Mask sensitive information in a string.

    Args:
        message: String potentially containing secrets

    Returns:
        String with secrets masked
    """
    masked = message
    for pattern in SECRET_PATTERNS:
        # We use a lambda to replace only the captured group (the actual secret)
        # while keeping the key/prefix intact.
        def _replace(match):
            full_match = match.group(0)
            if match.groups():
                # If there are groups, mask the last one (usually the secret)
                secret = match.groups()[-1]
                # Replace secret with asterisks, keeping it the same length (max 12)
                mask = "*" * min(len(secret), 12)
                return full_match.replace(secret, mask)
            else:
                # No groups, mask the whole match (but leave a few chars)
                mask = full_match[:4] + "*" * 8 + full_match[-4:] if len(full_match) > 12 else "********"
                return mask

        masked = re.sub(pattern, _replace, masked)

    return masked


def colorize_log_level(message: str) -> Text:
    """Colorize log message based on level.

    Args:
        message: Log message to colorize

    Returns:
        Rich Text object with appropriate styling

    Examples:
        >>> colorize_log_level("[ERROR] Something failed")  # Red
        >>> colorize_log_level("[WARNING] Check this")     # Yellow
        >>> colorize_log_level("[INFO] All good")          # Green
    """
    text = Text(message)

    # Common log level patterns
    if re.search(r"\b(ERROR|FATAL|CRITICAL)\b", message, re.IGNORECASE):
        text.stylize("bold red")
    elif re.search(r"\bWARN(ING)?\b", message, re.IGNORECASE):
        text.stylize("yellow")
    elif re.search(r"\bINFO\b", message, re.IGNORECASE):
        text.stylize("green")
    elif re.search(r"\bDEBUG\b", message, re.IGNORECASE):
        text.stylize("dim")

    return text
