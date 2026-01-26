"""Main entry point for the dashboard application."""

import os
from pathlib import Path
from typing import List, Optional
from datetime import datetime

from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware

from devops_cli.auth import AuthManager
from .utils import RateLimiter, TTLCache

# Dashboard paths
DASHBOARD_DIR = Path(__file__).parent
STATIC_DIR = DASHBOARD_DIR / "static"
TEMPLATES_DIR = DASHBOARD_DIR / "templates"
CONFIG_DIR = Path.home() / ".devops-cli"

def get_cors_origins() -> List[str]:
    """Get allowed CORS origins from config file or environment."""
    env_origins = os.getenv("DASHBOARD_CORS_ORIGINS")
    if env_origins:
        return [origin.strip() for origin in env_origins.split(",")]

    port = int(os.getenv("DASHBOARD_PORT", "3000"))
    return [
        f"http://localhost:{port}",
        f"http://127.0.0.1:{port}",
    ]

ALLOWED_ORIGINS = get_cors_origins()

# Global instances
auth_rate_limiter = RateLimiter(max_attempts=5, window_seconds=300)
github_cache = TTLCache(default_ttl=300)
monitoring_cache = TTLCache(default_ttl=30)
auth_manager = AuthManager()
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

# Session storage (in-memory)
sessions = {}

def get_current_user(request: Request) -> Optional[dict]:
    """Get current user from session cookie."""
    session_id = request.cookies.get("session_id")
    if session_id and session_id in sessions:
        session = sessions[session_id]
        if datetime.fromisoformat(session["expires_at"]) > datetime.now():
            return session["user"]
    return None

def require_auth(request: Request) -> dict:
    """Require authentication."""
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user

def require_admin(request: Request) -> dict:
    """Require admin role."""
    user = require_auth(request)
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return user

def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="DevOps CLI Dashboard",
        description="Web interface for DevOps CLI",
        version="1.0.0",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "Authorization", "X-Requested-With"],
    )

    if STATIC_DIR.exists():
        app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    @app.get("/", response_class=HTMLResponse)
    async def index(request: Request):
        """Main dashboard page."""
        user = get_current_user(request)
        if not user:
            return templates.TemplateResponse("login.html", {"request": request})
        return templates.TemplateResponse("index.html", {"request": request, "user": user})

    @app.get("/login", response_class=HTMLResponse)
    async def login_page(request: Request):
        """Login page."""
        return templates.TemplateResponse("login.html", {"request": request})

    # Add routers
    from .routes import auth, monitoring, apps, servers, websites, activity, github, security, config as config_route, meetings, users
    
    app.include_router(auth.router)
    app.include_router(monitoring.router)
    app.include_router(apps.router)
    app.include_router(servers.router)
    app.include_router(websites.router)
    app.include_router(activity.router)
    app.include_router(github.router)
    app.include_router(security.router)
    app.include_router(config_route.router)
    app.include_router(meetings.router)
    app.include_router(users.router)

    return app

def run_dashboard(host: str = "127.0.0.1", port: int = 3000, reload: bool = False):
    """Run the dashboard web server."""
    import uvicorn
    uvicorn.run("devops_cli.dashboard.main:app", host=host, port=port, reload=reload)

# The app instance will be created and routers will be added here
app = create_app()
