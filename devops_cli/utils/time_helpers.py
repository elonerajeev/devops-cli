"""Time and date utilities for DevOps CLI."""

from datetime import datetime, timedelta


def parse_time_range(time_str: str) -> datetime:
    """Parse time string like '1h', '30m', '2d' to datetime.

    Args:
        time_str: Time string (e.g., '30m', '1h', '2d')

    Returns:
        datetime object representing the parsed time

    Examples:
        >>> parse_time_range('30m')  # 30 minutes ago
        >>> parse_time_range('1h')   # 1 hour ago
        >>> parse_time_range('2d')   # 2 days ago
    """
    now = datetime.utcnow()

    if time_str.endswith("m"):
        return now - timedelta(minutes=int(time_str[:-1]))
    elif time_str.endswith("h"):
        return now - timedelta(hours=int(time_str[:-1]))
    elif time_str.endswith("d"):
        return now - timedelta(days=int(time_str[:-1]))
    else:
        # Default to 1 hour if format not recognized
        return now - timedelta(hours=1)


def format_timestamp(timestamp: int) -> str:
    """Format Unix timestamp (milliseconds) to readable string.

    Args:
        timestamp: Unix timestamp in milliseconds

    Returns:
        Formatted time string
    """
    dt = datetime.fromtimestamp(timestamp / 1000)
    return dt.strftime("%Y-%m-%d %H:%M:%S")
