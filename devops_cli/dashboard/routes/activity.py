"""Activity and deployment routes for the dashboard."""

from fastapi import APIRouter, Depends
from ..main import require_auth
from ..logic import load_activity, load_deployments, save_deployment

router = APIRouter(prefix="/api", tags=["activity"])

@router.get("/activity")
async def api_activity(user: dict = Depends(require_auth)):
    """Get recent activity."""
    return {"activities": load_activity()}

@router.get("/deployments")
async def api_deployments(user: dict = Depends(require_auth)):
    """Get recent deployments."""
    return {"deployments": load_deployments()}

@router.post("/deployments")
async def api_create_deployment(deployment: dict, user: dict = Depends(require_auth)):
    """Record a new deployment."""
    deployment["user"] = user["email"]
    return save_deployment(deployment)
