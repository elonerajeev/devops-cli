"""Website routes for the dashboard."""

from fastapi import APIRouter, Depends
from ..main import require_auth
from ..logic import filter_by_team_access

router = APIRouter(prefix="/api/websites", tags=["websites"])

@router.get("")
async def api_websites(user: dict = Depends(require_auth)):
    """Get all websites (filtered by team access)."""
    from devops_cli.config.websites import load_websites_config

    try:
        websites = load_websites_config()

        result = []
        for name, website in websites.items():
            if isinstance(website, dict):
                result.append(
                    {
                        "name": website.get("name", name),
                        "url": website.get("url", ""),
                        "description": website.get("description", ""),
                        "expected_status": website.get("expected_status", 200),
                        "method": website.get("method", "GET"),
                        "timeout": website.get("timeout", 10),
                        "tags": website.get("tags", []),
                    }
                )

        # Filter by team access (admin sees all)
        if user.get("role") != "admin":
            result = filter_by_team_access(result, user["email"], "websites")

        return {"websites": result}
    except Exception as e:
        return {"websites": [], "error": str(e)}
