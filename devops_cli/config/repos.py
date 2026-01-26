"""Repository configuration management."""

import yaml
import requests
from pathlib import Path
from typing import Optional, Dict, List
import re

REPOS_FILE = Path.home() / ".devops-cli" / "repos.yaml"


def validate_github_token(token: str) -> tuple[bool, Optional[str]]:
    """
    Validate GitHub token and check scopes.

    Returns: (is_valid, error_message)
    """
    if not token or not token.strip():
        return False, "Token is empty"

    # Check token format
    if not (token.startswith("ghp_") or token.startswith("github_pat_")):
        return (
            False,
            "Invalid token format. Token should start with 'ghp_' or 'github_pat_'",
        )

    # Verify token with GitHub API
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json",
    }

    try:
        resp = requests.get("https://api.github.com/user", headers=headers, timeout=5)

        if resp.status_code == 200:
            # Check scopes
            scopes = resp.headers.get("X-OAuth-Scopes", "")
            if "repo" not in scopes:
                return (
                    False,
                    "Token lacks 'repo' scope. Please create a token with 'repo' access.",
                )
            return True, None
        elif resp.status_code == 401:
            return False, "Invalid or expired token"
        elif resp.status_code == 403:
            return False, "Token forbidden or rate limited"
        else:
            return False, f"GitHub API error: {resp.status_code}"

    except requests.RequestException as e:
        return False, f"Network error: {str(e)}"


def validate_repo_name(name: str) -> tuple[bool, Optional[str]]:
    """
    Validate repository name.

    Returns: (is_valid, error_message)
    """
    if not name or not name.strip():
        return False, "Repository name cannot be empty"

    # Allow alphanumeric, dash, underscore, slash
    if not re.match(r"^[a-zA-Z0-9_\-/]+$", name):
        return (
            False,
            "Repository name can only contain letters, numbers, dash, underscore, and slash",
        )

    if len(name) > 100:
        return False, "Repository name too long (max 100 characters)"

    return True, None


def sanitize_repo_input(value: str) -> str:
    """Sanitize repository input to prevent injection."""
    if not value:
        return ""
    # Remove any potentially dangerous characters
    return re.sub(r"[^\w\-/.]", "", value)


def ensure_repos_file():
    """Ensure repos.yaml exists."""
    REPOS_FILE.parent.mkdir(parents=True, exist_ok=True)
    if not REPOS_FILE.exists():
        with open(REPOS_FILE, "w") as f:
            yaml.dump({"repos": {}}, f)


def load_repos() -> Dict:
    """Load configured repositories."""
    ensure_repos_file()
    try:
        with open(REPOS_FILE) as f:
            data = yaml.safe_load(f) or {}
            return data.get("repos", {})
    except Exception:
        return {}


def save_repos(repos: Dict):
    """Save repositories to file."""
    ensure_repos_file()
    with open(REPOS_FILE, "w") as f:
        yaml.dump({"repos": repos}, f, default_flow_style=False)


def get_repo_config(repo_name: str) -> Optional[Dict]:
    """Get specific repository configuration."""
    repos = load_repos()
    return repos.get(repo_name)


def add_repo(name: str, owner: str, repo: str, **extra) -> bool:
    """Add a repository to configuration."""
    repos = load_repos()

    repos[name] = {"owner": owner, "repo": repo, **extra}

    save_repos(repos)
    return True


def remove_repo(name: str) -> bool:
    """Remove a repository from configuration."""
    repos = load_repos()

    if name not in repos:
        return False

    del repos[name]
    save_repos(repos)
    return True


def fetch_repo_from_github(owner: str, repo: str, token: str) -> Optional[Dict]:
    """
    Fetch repository details from GitHub API automatically.

    Returns repo metadata: description, default_branch, created_at, visibility, etc.
    """
    # Sanitize inputs
    owner = sanitize_repo_input(owner)
    repo = sanitize_repo_input(repo)

    if not owner or not repo:
        return None

    url = f"https://api.github.com/repos/{owner}/{repo}"
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json",
    }

    try:
        resp = requests.get(url, headers=headers, timeout=10)

        if resp.status_code == 200:
            data = resp.json()
            return {
                "name": data["name"],
                "full_name": data["full_name"],
                "description": data.get("description", "No description"),
                "default_branch": data.get("default_branch", "main"),
                "visibility": data.get("visibility", "private"),
                "created_at": data.get("created_at", ""),
                "language": data.get("language", "Unknown"),
                "url": data.get("html_url", ""),
                "private": data.get("private", True),
            }
        elif resp.status_code == 404:
            return None  # Repo not found
        elif resp.status_code == 403:
            # Check if rate limited
            if "rate limit" in resp.text.lower():
                return {
                    "error": "rate_limit",
                    "message": "GitHub API rate limit exceeded",
                }
            return {"error": "forbidden", "message": "Access forbidden"}
        elif resp.status_code == 401:
            return {"error": "unauthorized", "message": "Invalid or expired token"}
        else:
            return {
                "error": "api_error",
                "message": f"GitHub API error: {resp.status_code}",
            }

    except requests.Timeout:
        return {"error": "timeout", "message": "Request timed out"}
    except requests.RequestException as e:
        return {"error": "network", "message": f"Network error: {str(e)}"}
    except Exception as e:
        return {"error": "unknown", "message": f"Unexpected error: {str(e)}"}


def discover_org_repos(org: str, token: str) -> List[Dict]:
    """
    Discover all repositories in a GitHub organization automatically.

    Returns list of repos with metadata.
    """
    # Sanitize org name
    org = sanitize_repo_input(org)
    if not org:
        return []

    url = f"https://api.github.com/orgs/{org}/repos"
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json",
    }

    all_repos = []
    page = 1

    try:
        while True:
            params = {"page": page, "per_page": 100, "type": "all"}
            resp = requests.get(url, headers=headers, params=params, timeout=15)

            if resp.status_code == 200:
                repos = resp.json()
                if not repos:
                    break

                for repo in repos:
                    all_repos.append(
                        {
                            "name": repo["name"],
                            "owner": org,
                            "description": repo.get("description", "No description"),
                            "default_branch": repo.get("default_branch", "main"),
                            "visibility": repo.get("visibility", "private"),
                            "private": repo.get("private", True),
                            "language": repo.get("language", "Unknown"),
                            "created_at": repo.get("created_at", ""),
                            "url": repo.get("html_url", ""),
                        }
                    )

                page += 1

                # Safety limit to prevent infinite loops
                if page > 10:
                    break

            elif resp.status_code == 404:
                # Org not found or no access
                break
            elif resp.status_code == 403:
                # Rate limited or forbidden
                break
            else:
                break

        return all_repos

    except requests.Timeout:
        return []
    except requests.RequestException:
        return []
    except Exception:
        return []


def discover_user_repos(username: str, token: str) -> List[Dict]:
    """
    Discover all repositories for a user (personal repos).

    Returns list of repos with metadata.
    """
    url = "https://api.github.com/user/repos"
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json",
    }

    all_repos = []
    page = 1

    try:
        while True:
            params = {
                "page": page,
                "per_page": 100,
                "type": "all",  # all, owner, member
                "affiliation": "owner,collaborator,organization_member",
            }
            resp = requests.get(url, headers=headers, params=params, timeout=15)

            if resp.status_code == 200:
                repos = resp.json()
                if not repos:
                    break

                for repo in repos:
                    all_repos.append(
                        {
                            "name": repo["name"],
                            "owner": repo["owner"]["login"],
                            "description": repo.get("description", "No description"),
                            "default_branch": repo.get("default_branch", "main"),
                            "visibility": repo.get("visibility", "private"),
                            "private": repo.get("private", True),
                            "language": repo.get("language", "Unknown"),
                            "created_at": repo.get("created_at", ""),
                            "url": repo.get("html_url", ""),
                        }
                    )

                page += 1

                # Safety limit to prevent infinite loops
                if page > 10:
                    break

            elif resp.status_code == 403:
                # Rate limited or forbidden
                break
            elif resp.status_code == 401:
                # Unauthorized
                break
            else:
                break

        return all_repos

    except requests.Timeout:
        return []
    except requests.RequestException:
        return []
    except Exception:
        return []
