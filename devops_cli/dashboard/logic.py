"""Business logic and data management for the dashboard."""

import os
import json
import yaml
import fnmatch
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict

from devops_cli.auth import AuthManager

CONFIG_DIR = Path.home() / ".devops-cli"
DEPLOYMENTS_FILE = CONFIG_DIR / "deployments.json"
ACTIVITY_FILE = CONFIG_DIR / "activity.json"

auth_manager = AuthManager()

# ==================== Team-Based Access Control ====================

def load_teams_config():
    """Load teams configuration."""
    teams_file = CONFIG_DIR / "teams.yaml"
    if teams_file.exists():
        with open(teams_file) as f:
            return yaml.safe_load(f) or {}
    return {
        "teams": {
            "default": {
                "name": "Default Team",
                "apps": ["*"],
                "servers": ["*"],
                "websites": ["*"],
                "repos": ["*"],
            }
        }
    }


def get_user_team(email: str) -> str:
    """Get user's team using AuthManager."""
    user_data = auth_manager.get_user_data(email)
    if user_data:
        return user_data.get("team", "default")
    return "default"


def get_team_permissions(team_name: str) -> dict:
    """Get team's access permissions."""
    config = load_teams_config()
    teams = config.get("teams", {})
    return teams.get(
        team_name,
        teams.get(
            "default",
            {"apps": ["*"], "servers": ["*"], "websites": ["*"], "repos": ["*"]},
        ),
    )


def can_access_resource(resource_name: str, allowed_patterns: list) -> bool:
    """Check if user can access a resource based on patterns."""
    for pattern in allowed_patterns:
        if pattern == "*" or fnmatch.fnmatch(resource_name, pattern):
            return True
    return False


def filter_by_team_access(
    items: list, user_email: str, resource_type: str, name_key: str = "name"
) -> list:
    """Filter items based on team access."""
    team = get_user_team(user_email)
    permissions = get_team_permissions(team)
    allowed = permissions.get(resource_type, ["*"])
    return [
        item for item in items if can_access_resource(item.get(name_key, ""), allowed)
    ]


# ==================== Dynamic Data Storage ====================


def load_deployments() -> list:
    """Load deployments from file."""
    if DEPLOYMENTS_FILE.exists():
        with open(DEPLOYMENTS_FILE) as f:
            return json.load(f).get("deployments", [])
    return []


def save_deployment(deployment: dict):
    """Save a new deployment."""
    data = {"deployments": load_deployments()}
    deployment["id"] = f"dep-{datetime.now().strftime('%Y%m%d%H%M%S')}"
    deployment["deployed_at"] = datetime.now().isoformat() + "Z"
    data["deployments"].insert(0, deployment)
    # Keep last 100 deployments
    data["deployments"] = data["deployments"][:100]
    DEPLOYMENTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(DEPLOYMENTS_FILE, "w") as f:
        json.dump(data, f, indent=2)
    return deployment


def load_activity() -> list:
    """Load activity logs from file."""
    activities = []
    # Load from auth audit log
    audit_file = CONFIG_DIR / "auth" / "audit.log"
    if audit_file.exists():
        try:
            with open(audit_file, "r") as f:
                lines = f.readlines()

            # Truncate if more than 10
            if len(lines) > 10:
                lines = lines[-10:]
                try:
                    with open(audit_file, "w") as f:
                        f.writelines(lines)
                except Exception:
                    pass

            for line in lines:
                try:
                    if "|" in line:
                        entry_parts = line.strip().split(" | ")
                        if len(entry_parts) >= 2:
                            timestamp = entry_parts[0]
                            action = entry_parts[1]
                            email = entry_parts[2] if len(entry_parts) > 2 else "system"

                            activities.append(
                                {
                                    "timestamp": timestamp,
                                    "type": (
                                        action.split("_")[0].lower()
                                        if "_" in action
                                        else "system"
                                    ),
                                    "user": email,
                                    "action": action.replace("_", " ").title(),
                                    "ip": "-",
                                    "status": "success",
                                }
                            )
                except Exception:
                    pass
        except Exception:
            pass

    # Load custom activity file
    if ACTIVITY_FILE.exists():
        try:
            with open(ACTIVITY_FILE) as f:
                activities.extend(json.load(f).get("activities", []))
        except Exception:
            pass

    # Sort by timestamp desc
    activities.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
    return activities[:10]


def log_activity(
    activity_type: str, user: str, action: str, status: str = "success", ip: str = "-"
):
    """Log an activity."""
    data = {"activities": []}
    if ACTIVITY_FILE.exists():
        try:
            with open(ACTIVITY_FILE) as f:
                data = json.load(f)
        except Exception:
            pass

    activity = {
        "timestamp": datetime.now().isoformat() + "Z",
        "type": activity_type,
        "user": user,
        "action": action,
        "ip": ip,
        "status": status,
    }
    data["activities"].insert(0, activity)
    data["activities"] = data["activities"][:10]

    ACTIVITY_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(ACTIVITY_FILE, "w") as f:
        json.dump(data, f, indent=2)
