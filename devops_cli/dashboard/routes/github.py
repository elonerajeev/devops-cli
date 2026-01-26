"""GitHub routes for the dashboard."""

from fastapi import APIRouter, Depends
import httpx
from ..main import require_auth, github_cache
from ..logic import get_user_team
from devops_cli.utils.github_helper import (
    get_latest_commit, 
    get_workflow_runs,
    get_dependabot_alerts,
    get_secret_scanning_alerts,
    get_code_scanning_alerts
)

router = APIRouter(prefix="/api/github", tags=["github"])

def get_github_config():
    """Load GitHub config from global settings."""
    from devops_cli.config.settings import load_config
    return load_config()

@router.get("/repos")
async def api_github_repos(user: dict = Depends(require_auth)):
    """Fetch GitHub org repos with team-based filtering and caching."""
    config = get_github_config()
    github_config = config.get("github", {})
    org = github_config.get("org", "")
    token = github_config.get("token", "")

    if not org:
        return {"error": "GitHub organization not configured", "repos": []}

    cache_key = f"github_repos:{org}"
    cached_repos = github_cache.get(cache_key)

    if cached_repos is None:
        headers = {"Accept": "application/vnd.github.v3+json"}
        if token:
            headers["Authorization"] = f"token {token}"

        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    f"https://api.github.com/orgs/{org}/repos?per_page=100&sort=updated",
                    headers=headers,
                    timeout=10.0,
                )
                if resp.status_code != 200:
                    return {"error": f"GitHub API error: {resp.status_code}", "repos": []}
                
                all_repos = resp.json()
                mapped_repos = []
                for r in all_repos:
                    mapped_repos.append({
                        "name": r["name"],
                        "url": r["html_url"],
                        "description": r.get("description", ""),
                        "private": r.get("private", False),
                        "default_branch": r.get("default_branch", "main"),
                        "language": r.get("language"),
                        "stars": r.get("stargazers_count", 0),
                        "forks": r.get("forks_count", 0),
                    })
                github_cache.set(cache_key, mapped_repos)
                all_repos = mapped_repos
        except Exception as e:
            return {"error": str(e), "repos": []}
    else:
        all_repos = cached_repos

    user_team = get_user_team(user["email"])
    
    return {
        "repos": all_repos, 
        "org": org,
        "total": len(all_repos),
        "team_name": user_team,
        "all_count": len(all_repos)
    }

@router.get("/config")
async def api_github_config(user: dict = Depends(require_auth)):
    """Get GitHub configuration."""
    config = get_github_config()
    github_config = config.get("github", {})
    return {"org": github_config.get("org", ""), "has_token": bool(github_config.get("token"))}

@router.get("/repos/{owner}/{repo}/status")
async def api_repo_status(owner: str, repo: str, user: dict = Depends(require_auth)):
    """Get repository pipeline and commit status."""
    config = get_github_config()
    token = config.get("github", {}).get("token", "")
    
    cache_key = f"status:{owner}:{repo}"
    cached = github_cache.get(cache_key)
    if cached:
        return cached

    # Determine default branch
    default_branch = "main"
    try:
        async with httpx.AsyncClient() as client:
            headers = {"Accept": "application/vnd.github.v3+json"}
            if token:
                headers["Authorization"] = f"token {token}"
            repo_resp = await client.get(f"https://api.github.com/repos/{owner}/{repo}", headers=headers)
            if repo_resp.status_code == 200:
                default_branch = repo_resp.json().get("default_branch", "main")
    except:
        pass

    commit = get_latest_commit(owner, repo, default_branch, token)
    success, runs = get_workflow_runs(owner, repo, limit=1, token=token)
    
    pipeline = {"status": "no_runs", "conclusion": None, "html_url": "#"}
    if success and runs:
        run = runs[0]
        pipeline = {
            "status": run["status"],
            "conclusion": run["conclusion"],
            "html_url": run["html_url"]
        }

    response = {
        "pipeline": pipeline,
        "commit": commit or {
            "message": "No commit data",
            "author": "Unknown",
            "date": "",
            "sha": "---"
        }
    }
    
    github_cache.set(cache_key, response, ttl=60)
    return response

@router.get("/repos/{owner}/{repo}/security-alerts")
async def api_repo_security(owner: str, repo: str, user: dict = Depends(require_auth)):
    """Get repository security alerts."""
    config = get_github_config()
    token = config.get("github", {}).get("token", "")
    
    cache_key = f"security:{owner}:{repo}"
    cached = github_cache.get(cache_key)
    if cached:
        return cached

    dependabot = get_dependabot_alerts(owner, repo, token) or []
    secrets = get_secret_scanning_alerts(owner, repo, token) or []
    code = get_code_scanning_alerts(owner, repo, token) or []
    
    # Calculate summary
    critical = sum(1 for a in (dependabot + code) if a.get("severity") == "critical")
    high = sum(1 for a in (dependabot + code) if a.get("severity") == "high")
    medium = sum(1 for a in (dependabot + code) if a.get("severity") == "medium")
    low = sum(1 for a in (dependabot + code) if a.get("severity") == "low")
    
    response = {
        "summary": {
            "total": len(dependabot) + len(secrets) + len(code),
            "critical": critical,
            "high": high,
            "medium": medium,
            "low": low
        },
        "alerts": {
            "dependabot": dependabot,
            "secret_scanning": secrets,
            "code_scanning": code
        }
    }
    
    github_cache.set(cache_key, response, ttl=300)
    return response
