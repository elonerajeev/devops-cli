"""Authentication routes for the dashboard."""

import secrets
from datetime import datetime, timedelta
from fastapi import APIRouter, Request, HTTPException, Response
from ..main import auth_manager, auth_rate_limiter, sessions, templates
from ..logic import log_activity

router = APIRouter(prefix="/api/auth", tags=["auth"])

@router.post("/login")
async def api_login(request: Request, response: Response):
    """Login endpoint with rate limiting."""
    client_ip = request.client.host if request.client else "unknown"

    if auth_rate_limiter.is_rate_limited(client_ip):
        remaining = auth_rate_limiter.get_remaining_time(client_ip)
        raise HTTPException(
            status_code=429,
            detail=f"Too many login attempts. Try again in {remaining} seconds.",
        )

    data = await request.json()
    email = data.get("email")
    token = data.get("token")

    if not email or not token:
        raise HTTPException(status_code=400, detail="Email and token required")

    if auth_rate_limiter.is_rate_limited(email):
        remaining = auth_rate_limiter.get_remaining_time(email)
        raise HTTPException(
            status_code=429,
            detail=f"Too many login attempts for this account. Try again in {remaining} seconds.",
        )

    auth_rate_limiter.record_attempt(client_ip)
    auth_rate_limiter.record_attempt(email)

    try:
        if auth_manager.login(email, token):
            auth_rate_limiter.reset(client_ip)
            auth_rate_limiter.reset(email)

            users = auth_manager.list_users()
            user_info = next((u for u in users if u["email"] == email), None)

            if user_info:
                session_id = secrets.token_urlsafe(32)
                expires_at = datetime.now() + timedelta(hours=8)
                
                sessions[session_id] = {
                    "user": user_info,
                    "expires_at": expires_at.isoformat(),
                }

                response.set_cookie(
                    key="session_id",
                    value=session_id,
                    httponly=True,
                    max_age=8 * 3600,
                    samesite="lax",
                )

                log_activity("auth", email, "Dashboard Login", ip=client_ip)
                return {"success": True, "user": user_info}
        
        return {"success": False, "error": "Invalid email or token"}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/logout")
async def api_logout(request: Request, response: Response):
    """Logout endpoint."""
    session_id = request.cookies.get("session_id")
    if session_id in sessions:
        user = sessions[session_id]["user"]
        log_activity("auth", user["email"], "Dashboard Logout")
        del sessions[session_id]

    response.delete_cookie("session_id")
    return {"success": True}

@router.get("/status")
async def auth_status(request: Request):
    """Check current auth status."""
    from ..main import get_current_user
    user = get_current_user(request)
    if user:
        return {"authenticated": True, "user": user}
    return {"authenticated": False}
