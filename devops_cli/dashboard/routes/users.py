"""User management routes for the dashboard."""

from fastapi import APIRouter, Request, HTTPException, Depends
from ..main import require_admin, require_auth, auth_manager
from ..logic import log_activity

router = APIRouter(prefix="/api/users", tags=["users"])

@router.get("")
async def api_list_users(user: dict = Depends(require_auth)):
    """List all users."""
    # We allow authenticated users to see the team list
    try:
        users = auth_manager.list_users()
        # Return simplified list for security
        return {
            "users": [
                {
                    "email": u["email"],
                    "name": u.get("name"),
                    "role": u.get("role"),
                    "team": u.get("team"),
                    "active": u.get("active", True),
                    "last_login": u.get("last_login")
                }
                for u in users
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("")
async def api_add_user(user_data: dict, current_user: dict = Depends(require_admin)):
    """Register a new user (admin only)."""
    email = user_data.get("email")
    name = user_data.get("name")
    role = user_data.get("role", "developer")
    team = user_data.get("team", "default")

    if not email:
        raise HTTPException(status_code=400, detail="Email required")

    try:
        token = auth_manager.register_user(email, name, role, team)
        log_activity("user", current_user["email"], f"Registered user: {email}")
        return {"success": True, "token": token}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/{email}")
async def api_remove_user(email: str, current_user: dict = Depends(require_admin)):
    """Remove a user (admin only)."""
    if current_user["email"] == email:
        raise HTTPException(status_code=400, detail="Cannot remove yourself")

    if auth_manager.remove_user(email):
        log_activity("user", current_user["email"], f"Removed user: {email}")
        return {"success": True}
    else:
        raise HTTPException(status_code=404, detail="User not found")
