"""Log formatting and colorizing utilities for DevOps CLI."""

import re
from rich.text import Text


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
