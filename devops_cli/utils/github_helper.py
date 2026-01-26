"""GitHub API helper functions for CI/CD and repo operations.

Simple, focused utilities for common GitHub operations.
"""

import requests
from typing import Optional, Dict, List, Tuple
from datetime import datetime


def get_headers(token: str) -> dict:
    """Get GitHub API headers."""
    return {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json",
    }


# Alias for backwards compatibility
get_github_headers = get_headers


def get_latest_commit(owner: str, repo: str, branch: str, token: str) -> Optional[Dict]:
    """
    Get latest commit info for a branch.

    Returns:
        Dict with 'sha', 'message', 'author', 'date' or None on error
    """
    url = f"https://api.github.com/repos/{owner}/{repo}/commits/{branch}"

    try:
        resp = requests.get(url, headers=get_headers(token), timeout=10)

        if resp.status_code == 200:
            data = resp.json()
            return {
                "sha": data["sha"][:7],  # Short SHA
                "sha_full": data["sha"],
                "message": data["commit"]["message"].split("\n")[0],  # First line only
                "author": data["commit"]["author"]["name"],
                "date": data["commit"]["author"]["date"],
                "url": data["html_url"],
            }
    except Exception:
        pass

    return None


def get_workflow_runs(
    owner: str,
    repo: str,
    branch: Optional[str] = None,
    limit: int = 10,
    token: str = None,
) -> Tuple[bool, Optional[List[Dict]]]:
    """
    Get recent workflow runs from GitHub Actions.

    Returns:
        (success, runs_list) where runs_list contains workflow run info
    """
    url = f"https://api.github.com/repos/{owner}/{repo}/actions/runs"
    params = {"per_page": limit}

    if branch:
        params["branch"] = branch

    try:
        resp = requests.get(url, params=params, headers=get_headers(token), timeout=15)

        if resp.status_code == 200:
            runs = resp.json().get("workflow_runs", [])

            # Simplify run data
            simplified = []
            for run in runs:
                simplified.append(
                    {
                        "id": run["id"],
                        "name": run["name"],
                        "status": run["status"],  # queued, in_progress, completed
                        "conclusion": run.get(
                            "conclusion"
                        ),  # success, failure, cancelled, etc.
                        "created_at": run["created_at"],
                        "updated_at": run["updated_at"],
                        "html_url": run["html_url"],
                        "head_sha": run["head_sha"][:7],
                        "head_branch": run["head_branch"],
                        "event": run["event"],  # push, pull_request, workflow_dispatch
                    }
                )

            return True, simplified

        elif resp.status_code == 404:
            return False, None
        else:
            return False, None

    except Exception:
        return False, None


def get_workflow_jobs(
    owner: str, repo: str, run_id: int, token: str
) -> Optional[List[Dict]]:
    """
    Get jobs for a specific workflow run.

    Returns:
        List of jobs with their status or None on error
    """
    url = f"https://api.github.com/repos/{owner}/{repo}/actions/runs/{run_id}/jobs"

    try:
        resp = requests.get(url, headers=get_headers(token), timeout=10)

        if resp.status_code == 200:
            jobs = resp.json().get("jobs", [])

            simplified = []
            for job in jobs:
                simplified.append(
                    {
                        "name": job["name"],
                        "status": job["status"],
                        "conclusion": job.get("conclusion"),
                        "started_at": job.get("started_at"),
                        "completed_at": job.get("completed_at"),
                    }
                )

            return simplified
    except Exception:
        pass

    return None


def format_time_ago(iso_timestamp: str) -> str:
    """
    Format ISO timestamp as 'X time ago'.

    Args:
        iso_timestamp: ISO 8601 timestamp string

    Returns:
        Human-friendly time string like '2 hours ago'
    """
    try:
        dt = datetime.fromisoformat(iso_timestamp.replace("Z", "+00:00"))
        now = datetime.now(dt.tzinfo)
        diff = now - dt

        seconds = diff.total_seconds()

        if seconds < 60:
            return "just now"
        elif seconds < 3600:
            mins = int(seconds / 60)
            return f"{mins} min{'s' if mins != 1 else ''} ago"
        elif seconds < 86400:
            hours = int(seconds / 3600)
            return f"{hours} hour{'s' if hours != 1 else ''} ago"
        else:
            days = int(seconds / 86400)
            return f"{days} day{'s' if days != 1 else ''} ago"
    except Exception:
        return iso_timestamp[:16].replace("T", " ")


def get_status_emoji(status: str, conclusion: Optional[str] = None) -> str:
    """
    Get emoji for workflow status.

    Args:
        status: Workflow status (queued, in_progress, completed)
        conclusion: Workflow conclusion (success, failure, cancelled, etc.)

    Returns:
        Emoji string
    """
    if status == "completed":
        if conclusion == "success":
            return "✓"
        elif conclusion == "failure":
            return "✗"
        elif conclusion == "cancelled":
            return "⊘"
        elif conclusion == "skipped":
            return "⊝"
        else:
            return "?"
    elif status == "in_progress":
        return "●"
    elif status == "queued":
        return "○"
    else:
        return "-"


def get_status_color(status: str, conclusion: Optional[str] = None) -> str:
    """
    Get Rich color for workflow status.

    Args:
        status: Workflow status
        conclusion: Workflow conclusion

    Returns:
        Rich color name
    """
    if status == "completed":
        if conclusion == "success":
            return "green"
        elif conclusion == "failure":
            return "red"
        elif conclusion == "cancelled":
            return "yellow"
        else:
            return "dim"
    elif status == "in_progress":
        return "cyan"
    elif status == "queued":
        return "yellow"
    else:
        return "dim"


def get_status_message(status: str, conclusion: Optional[str] = None) -> str:
    """
    Get friendly status message.

    Args:
        status: Workflow status
        conclusion: Workflow conclusion

    Returns:
        Human-friendly status message
    """
    if status == "completed":
        if conclusion == "success":
            return "Build passed successfully"
        elif conclusion == "failure":
            return "Build failed - check logs for details"
        elif conclusion == "cancelled":
            return "Build was cancelled"
        elif conclusion == "skipped":
            return "Build was skipped"
        else:
            return "Build completed with unknown status"
    elif status == "in_progress":
        return "Build is running..."
    elif status == "queued":
        return "Build is queued and waiting to start"
    else:
        return "Status unknown"


# ==================== Security Alerts ====================


def get_dependabot_alerts(
    owner: str, repo: str, token: str, state: str = "open", limit: int = 50
) -> Optional[List[Dict]]:
    """
    Fetch Dependabot alerts for a repository.

    Returns:
        List of alerts or None on error
    """
    url = f"https://api.github.com/repos/{owner}/{repo}/dependabot/alerts"
    params = {"state": state, "per_page": limit}

    try:
        resp = requests.get(url, params=params, headers=get_headers(token), timeout=10)
        if resp.status_code == 200:
            alerts = resp.json()
            simplified = []
            for alert in alerts:
                adv = alert.get("security_advisory", {})
                simplified.append(
                    {
                        "id": alert["number"],
                        "state": alert["state"],
                        "severity": alert["security_advisory"]["severity"],
                        "summary": adv.get("summary"),
                        "description": adv.get("description"),
                        "package_name": alert["dependency"]["package"]["name"],
                        "manifest_path": alert["dependency"]["manifest_path"],
                        "vulnerable_version_range": alert["security_vulnerability"].get(
                            "vulnerable_version_range"
                        ),
                        "first_patched_version": alert["security_vulnerability"]
                        .get("first_patched_version", {})
                        .get("identifier"),
                        "html_url": alert["html_url"],
                        "created_at": alert["created_at"],
                    }
                )
            return simplified
    except Exception:
        pass
    return None


def get_secret_scanning_alerts(
    owner: str, repo: str, token: str, state: str = "open", limit: int = 50
) -> Optional[List[Dict]]:
    """
    Fetch Secret Scanning alerts for a repository.

    Returns:
        List of alerts or None on error
    """
    url = f"https://api.github.com/repos/{owner}/{repo}/secret-scanning/alerts"
    params = {"state": state, "per_page": limit}

    try:
        resp = requests.get(url, params=params, headers=get_headers(token), timeout=10)
        if resp.status_code == 200:
            alerts = resp.json()
            simplified = []
            for alert in alerts:
                simplified.append(
                    {
                        "id": alert["number"],
                        "state": alert["state"],
                        "secret_type": alert["secret_type"],
                        "secret_type_display_name": alert.get(
                            "secret_type_display_name"
                        ),
                        "created_at": alert["created_at"],
                        "html_url": alert["html_url"],
                        "resolved_at": alert.get("resolved_at"),
                        "resolved_by": alert.get("resolved_by", {}).get("login"),
                        "resolution": alert.get("resolution"),
                    }
                )
            return simplified
    except Exception:
        pass
    return None


def get_code_scanning_alerts(
    owner: str, repo: str, token: str, state: str = "open", limit: int = 50
) -> Optional[List[Dict]]:
    """
    Fetch Code Scanning alerts for a repository.

    Returns:
        List of alerts or None on error
    """
    url = f"https://api.github.com/repos/{owner}/{repo}/code-scanning/alerts"
    params = {"state": state, "per_page": limit}

    try:
        resp = requests.get(url, params=params, headers=get_headers(token), timeout=10)
        if resp.status_code == 200:
            alerts = resp.json()
            simplified = []
            for alert in alerts:
                simplified.append(
                    {
                        "id": alert["number"],
                        "state": alert["state"],
                        "severity": alert["rule"]["severity"],
                        "description": alert["rule"]["description"],
                        "tool": alert["tool"]["name"],
                        "location": alert.get("most_recent_instance", {})
                        .get("location", {})
                        .get("path"),
                        "html_url": alert["html_url"],
                        "created_at": alert["created_at"],
                    }
                )
            return simplified
    except Exception:
        pass
    return None
