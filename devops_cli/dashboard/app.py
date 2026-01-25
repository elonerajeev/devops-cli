"""FastAPI Web Dashboard Application."""

import os
import asyncio
from pathlib import Path
from typing import Optional, List
from datetime import datetime, timedelta
from collections import defaultdict
import json
import time

from fastapi import FastAPI, Request, HTTPException, Depends, status, File, UploadFile, Form
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from pydantic import ValidationError
from devops_cli.auth import AuthManager

# Dashboard paths
DASHBOARD_DIR = Path(__file__).parent
STATIC_DIR = DASHBOARD_DIR / "static"
TEMPLATES_DIR = DASHBOARD_DIR / "templates"
CONFIG_DIR = Path.home() / ".devops-cli"

# =============================================================================
# SECURITY: CORS Configuration
# =============================================================================
# Load allowed origins from config or environment
def get_cors_origins() -> List[str]:
    """Get allowed CORS origins from config file or environment."""
    # Check environment variable first
    env_origins = os.getenv("DASHBOARD_CORS_ORIGINS")
    if env_origins:
        return [origin.strip() for origin in env_origins.split(",")]

    # Check config file
    cors_file = CONFIG_DIR / "cors.json"
    if cors_file.exists():
        try:
            with open(cors_file) as f:
                config = json.load(f)
                return config.get("allowed_origins", [])
        except Exception:
            pass

    # Dynamic default based on environment
    port = int(os.getenv("DASHBOARD_PORT", "3000"))
    return [
        f"http://localhost:{port}",
        f"http://127.0.0.1:{port}",
    ]

ALLOWED_ORIGINS = get_cors_origins()

# =============================================================================
# SECURITY: Rate Limiting for Auth Endpoints
# =============================================================================
class RateLimiter:
    """Simple in-memory rate limiter for authentication endpoints."""

    def __init__(self, max_attempts: int = 5, window_seconds: int = 300):
        self.max_attempts = max_attempts
        self.window_seconds = window_seconds
        self._attempts: dict = defaultdict(list)

    def is_rate_limited(self, key: str) -> bool:
        """Check if key (IP or email) is rate limited."""
        now = time.time()
        # Clean old attempts
        self._attempts[key] = [
            t for t in self._attempts[key]
            if now - t < self.window_seconds
        ]
        return len(self._attempts[key]) >= self.max_attempts

    def record_attempt(self, key: str):
        """Record an authentication attempt."""
        self._attempts[key].append(time.time())

    def reset(self, key: str):
        """Reset attempts for a key (on successful login)."""
        self._attempts[key] = []

    def get_remaining_time(self, key: str) -> int:
        """Get seconds until rate limit resets."""
        if not self._attempts[key]:
            return 0
        oldest = min(self._attempts[key])
        return max(0, int(self.window_seconds - (time.time() - oldest)))

# Global rate limiter instance
auth_rate_limiter = RateLimiter(max_attempts=5, window_seconds=300)


# =============================================================================
# PERFORMANCE: TTL Cache for API Responses
# =============================================================================
class TTLCache:
    """Simple time-to-live cache for API responses."""

    def __init__(self, default_ttl: int = 300):
        self.default_ttl = default_ttl
        self._cache: dict = {}
        self._timestamps: dict = {}

    def get(self, key: str) -> Optional[dict]:
        """Get value from cache if not expired."""
        if key not in self._cache:
            return None
        if time.time() - self._timestamps.get(key, 0) > self.default_ttl:
            self.delete(key)
            return None
        return self._cache[key]

    def set(self, key: str, value: dict, ttl: Optional[int] = None):
        """Set value in cache with optional custom TTL."""
        self._cache[key] = value
        self._timestamps[key] = time.time()

    def delete(self, key: str):
        """Delete key from cache."""
        self._cache.pop(key, None)
        self._timestamps.pop(key, None)

    def clear(self):
        """Clear entire cache."""
        self._cache.clear()
        self._timestamps.clear()

    def cleanup(self):
        """Remove expired entries."""
        now = time.time()
        expired = [k for k, t in self._timestamps.items() if now - t > self.default_ttl]
        for key in expired:
            self.delete(key)


# Global cache instances
github_cache = TTLCache(default_ttl=300)  # 5 minute cache for GitHub API
monitoring_cache = TTLCache(default_ttl=30)  # 30 second cache for monitoring


# Create FastAPI app
app = FastAPI(
    title="DevOps CLI Dashboard",
    description="Web interface for DevOps CLI",
    version="1.0.0"
)
auth = AuthManager()

# Add CORS middleware with secure configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-Requested-With"],
)

# Mount static files
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# Templates
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

# Session storage (in-memory for simplicity)
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


# ==================== Team-Based Access Control ====================
DEPLOYMENTS_FILE = CONFIG_DIR / "deployments.json"
ACTIVITY_FILE = CONFIG_DIR / "activity.json"

def load_teams_config():
    """Load teams configuration."""
    import yaml
    teams_file = CONFIG_DIR / "teams.yaml"
    if teams_file.exists():
        with open(teams_file) as f:
            return yaml.safe_load(f) or {}
    return {"teams": {"default": {"name": "Default Team", "apps": ["*"], "servers": ["*"], "websites": ["*"], "repos": ["*"]}}}

def get_user_team(email: str) -> str:
    """Get user's team using AuthManager."""
    user_data = auth.get_user_data(email)
    if user_data:
        return user_data.get("team", "default")
    return "default"

def set_user_team(email: str, team: str):
    """Set user's team."""
    users_file = CONFIG_DIR / "auth" / "users.json"
    if users_file.exists():
        with open(users_file) as f:
            users = json.load(f)
        if email in users:
            users[email]["team"] = team
            with open(users_file, "w") as f:
                json.dump(users, f, indent=2)

def get_team_permissions(team_name: str) -> dict:
    """Get team's access permissions."""
    config = load_teams_config()
    teams = config.get("teams", {})
    return teams.get(team_name, teams.get("default", {"apps": ["*"], "servers": ["*"], "websites": ["*"], "repos": ["*"]}))

def can_access_resource(resource_name: str, allowed_patterns: list) -> bool:
    """Check if user can access a resource based on patterns."""
    import fnmatch
    for pattern in allowed_patterns:
        if pattern == "*" or fnmatch.fnmatch(resource_name, pattern):
            return True
    return False

def filter_by_team_access(items: list, user_email: str, resource_type: str, name_key: str = "name") -> list:
    """Filter items based on team access."""
    team = get_user_team(user_email)
    permissions = get_team_permissions(team)
    allowed = permissions.get(resource_type, ["*"])
    return [item for item in items if can_access_resource(item.get(name_key, ""), allowed)]

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
            # Read all lines
            with open(audit_file, "r") as f:
                lines = f.readlines()
            
            # Truncate if more than 10 (as requested for performance)
            if len(lines) > 10:
                lines = lines[-10:]
                try:
                    with open(audit_file, "w") as f:
                        f.writelines(lines)
                except Exception:
                    pass
            
            for line in lines:
                try:
                    # Fix: audit.log is pipe-separated, not JSON
                    if "|" in line:
                        entry_parts = line.strip().split(" | ")
                        if len(entry_parts) >= 2:
                            timestamp = entry_parts[0]
                            action = entry_parts[1]
                            email = entry_parts[2] if len(entry_parts) > 2 else "system"
                            
                            activities.append({
                                "timestamp": timestamp,
                                "type": action.split("_")[0].lower() if "_" in action else "system",
                                "user": email,
                                "action": action.replace("_", " ").title(),
                                "ip": "-",
                                "status": "success"
                            })
                    else:
                        # Fallback for legacy JSON lines if any
                        entry = json.loads(line.strip())
                        activities.append({
                            "timestamp": entry.get("timestamp", ""),
                            "type": entry.get("action", "").split("_")[0] if "_" in entry.get("action", "") else "system",
                            "user": entry.get("email", entry.get("user", "system")),
                            "action": entry.get("action", "").replace("_", " ").title(),
                            "ip": entry.get("ip", "-"),
                            "status": "success" if entry.get("success", True) else "failed"
                        })
                except Exception:
                    pass
        except Exception:
            pass

    # Load custom activity file
    if ACTIVITY_FILE.exists():
        with open(ACTIVITY_FILE) as f:
            activities.extend(json.load(f).get("activities", []))
    
    # Sort by timestamp desc
    activities.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
    return activities[:10] # Enforce overall limit

def log_activity(activity_type: str, user: str, action: str, status: str = "success", ip: str = "-"):
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
        "status": status
    }
    data["activities"].insert(0, activity)
    data["activities"] = data["activities"][:10]  # Keep last 10 as requested
    
    ACTIVITY_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(ACTIVITY_FILE, "w") as f:
        json.dump(data, f, indent=2)


# ==================== Pages ====================

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """Main dashboard page."""
    user = get_current_user(request)
    if not user:
        return templates.TemplateResponse("login.html", {"request": request})
    return templates.TemplateResponse("index.html", {
        "request": request,
        "user": user
    })


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    """Login page."""
    return templates.TemplateResponse("login.html", {"request": request})


# ==================== Auth API ====================

@app.post("/api/auth/login")
async def api_login(request: Request):
    """Login endpoint with rate limiting."""
    # Get client IP for rate limiting
    client_ip = request.client.host if request.client else "unknown"

    # Check rate limit by IP
    if auth_rate_limiter.is_rate_limited(client_ip):
        remaining = auth_rate_limiter.get_remaining_time(client_ip)
        raise HTTPException(
            status_code=429,
            detail=f"Too many login attempts. Try again in {remaining} seconds."
        )

    data = await request.json()
    email = data.get("email")
    token = data.get("token")

    if not email or not token:
        raise HTTPException(status_code=400, detail="Email and token required")

    # Also check rate limit by email
    if auth_rate_limiter.is_rate_limited(email):
        remaining = auth_rate_limiter.get_remaining_time(email)
        raise HTTPException(
            status_code=429,
            detail=f"Too many login attempts for this account. Try again in {remaining} seconds."
        )

    # Record the attempt
    auth_rate_limiter.record_attempt(client_ip)
    auth_rate_limiter.record_attempt(email)

    try:
        if auth.login(email, token):
            # Reset rate limits on successful login
            auth_rate_limiter.reset(client_ip)
            auth_rate_limiter.reset(email)

            # Get user info
            users = auth.list_users()
            user_info = next((u for u in users if u["email"] == email), None)

            if user_info:
                # Create session
                import secrets
                session_id = secrets.token_urlsafe(32)
                sessions[session_id] = {
                    "user": {
                        "email": email,
                        "name": user_info.get("name", email.split("@")[0]),
                        "role": user_info.get("role", "developer"),
                        "team": get_user_team(email)
                    },
                    "expires_at": (datetime.now() + timedelta(hours=8)).isoformat()
                }

                # Log successful login
                log_activity("login", email, "User logged in via dashboard", "success", client_ip)

                response = JSONResponse({
                    "success": True,
                    "user": sessions[session_id]["user"]
                })
                response.set_cookie(
                    key="session_id",
                    value=session_id,
                    httponly=True,
                    max_age=8 * 3600,
                    samesite="lax"
                )
                return response
    except HTTPException:
        raise
    except Exception:
        pass

    # Log failed login
    log_activity("login", email, "Login attempt failed", "failed", client_ip)
    raise HTTPException(status_code=401, detail="Invalid email or token")


@app.post("/api/auth/logout")
async def api_logout(request: Request):
    """Logout endpoint."""
    session_id = request.cookies.get("session_id")
    if session_id and session_id in sessions:
        del sessions[session_id]

    response = JSONResponse({"success": True})
    response.delete_cookie("session_id")
    return response


@app.get("/api/auth/me")
async def api_me(user: dict = Depends(require_auth)):
    """Get current user info."""
    return {"user": user}


# ==================== Apps API ====================

@app.get("/api/apps")
async def api_apps(user: dict = Depends(require_auth)):
    """Get all applications (filtered by team access)."""
    from devops_cli.commands.admin import load_apps_config

    try:
        config = load_apps_config()
        apps = config.get("apps", {})

        result = []
        for name, app in apps.items():
            result.append({
                "name": name,
                "type": app.get("type", "unknown"),
                "description": app.get("description", ""),
                "health": app.get("health", {}),
                "logs": app.get("logs", {})
            })

        # Filter by team access (admin sees all)
        if user.get("role") != "admin":
            result = filter_by_team_access(result, user["email"], "apps")

        return {"apps": result}
    except Exception as e:
        return {"apps": [], "error": str(e)}


@app.get("/api/apps/{app_name}/health")
async def api_app_health(app_name: str, user: dict = Depends(require_auth)):
    """Check app health."""
    from devops_cli.commands.admin import load_apps_config
    import httpx

    config = load_apps_config()
    apps = config.get("apps", {})

    if app_name not in apps:
        raise HTTPException(status_code=404, detail="App not found")

    app = apps[app_name]
    # Support both "health_check" and "health" keys for backwards compatibility
    health_config = app.get("health_check", app.get("health", {}))

    if not health_config:
        return {"status": "unknown", "message": "No health check configured"}

    # Get URL - works with or without "type" field
    url = health_config.get("url")
    if not url:
        return {"status": "unknown", "message": "No health check URL configured"}

    expected_status = health_config.get("expected_status", 200)
    timeout = health_config.get("timeout", 10)

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            start = datetime.now()
            response = await client.get(url)
            elapsed = (datetime.now() - start).total_seconds() * 1000

            if response.status_code == expected_status:
                return {
                    "status": "healthy",
                    "response_time": round(elapsed, 2),
                    "status_code": response.status_code,
                    "url": url
                }
            else:
                return {
                    "status": "unhealthy",
                    "response_time": round(elapsed, 2),
                    "status_code": response.status_code,
                    "expected": expected_status,
                    "url": url
                }
    except Exception as e:
        return {"status": "unhealthy", "error": str(e), "url": url}


# ==================== Servers API ====================

@app.get("/api/servers")
async def api_servers(user: dict = Depends(require_auth)):
    """Get all servers (filtered by team access)."""
    from devops_cli.commands.admin import load_servers_config

    try:
        config = load_servers_config()
        servers = config.get("servers", {})

        result = []
        for name, server in servers.items():
            result.append({
                "name": name,
                "host": server.get("host", ""),
                "user": server.get("user", ""),
                "port": server.get("port", 22),
                "tags": server.get("tags", [])
            })

        # Filter by team access (admin sees all)
        if user.get("role") != "admin":
            result = filter_by_team_access(result, user["email"], "servers")

        return {"servers": result}
    except Exception as e:
        return {"servers": [], "error": str(e)}


# ==================== Websites API ====================

@app.get("/api/websites")
async def api_websites(user: dict = Depends(require_auth)):
    """Get all websites (filtered by team access)."""
    from devops_cli.config.websites import load_websites_config

    try:
        # load_websites_config() returns the websites dict directly (not wrapped)
        websites = load_websites_config()

        result = []
        for name, website in websites.items():
            if isinstance(website, dict):
                result.append({
                    "name": website.get("name", name),
                    "url": website.get("url", ""),
                    "description": website.get("description", ""),
                    "expected_status": website.get("expected_status", 200),
                    "method": website.get("method", "GET"),
                    "timeout": website.get("timeout", 10),
                    "tags": website.get("tags", []),
                })

        # Filter by team access (admin sees all)
        if user.get("role") != "admin":
            result = filter_by_team_access(result, user["email"], "websites")

        return {"websites": result}
    except Exception as e:
        return {"websites": [], "error": str(e)}


# ==================== Monitoring API ====================

@app.get("/api/monitoring")
async def api_monitoring(user: dict = Depends(require_auth)):
    """Get monitoring status."""
    try:
        from devops_cli.monitoring import MonitoringConfig, HealthChecker
        from devops_cli.monitoring.checker import HealthStatus
        from devops_cli.monitoring.config import WebsiteConfig, AppConfig, ServerConfig

        config = MonitoringConfig()
        checker = HealthChecker()

        websites_from_config = config.get_websites()
        apps_from_config = config.get_apps()
        servers_from_config = config.get_servers()

        # Filter resources by team access (admin sees all)
        if user.get("role") != "admin":
            websites_from_config = filter_by_team_access(
                [w.as_dict() for w in websites_from_config], user["email"], "websites"
            )
            websites_from_config = [WebsiteConfig(**w) for w in websites_from_config]

            apps_from_config = filter_by_team_access(
                [a.as_dict() for a in apps_from_config], user["email"], "apps"
            )
            apps_from_config = [AppConfig(**a) for a in apps_from_config]

            servers_from_config = filter_by_team_access(
                [s.as_dict() for s in servers_from_config], user["email"], "servers"
            )
            servers_from_config = [ServerConfig(**s) for s in servers_from_config]


        # Run health checks
        results = await checker.check_all(websites_from_config, apps_from_config, servers_from_config)

        # Convert HealthResult objects to dictionaries
        def result_to_dict(r):
            return {
                "name": r.name,
                "status": "online" if r.status == HealthStatus.HEALTHY else "offline" if r.status == HealthStatus.UNHEALTHY else "degraded",
                "response_time": r.response_time_ms,
                "message": r.message,
                "details": r.details,
                "url": r.details.get("url", "")
            }

        websites_data = [result_to_dict(w) for w in results.get("websites", [])]
        apps_data = [result_to_dict(a) for a in results.get("apps", [])]
        servers_data = [result_to_dict(s) for s in results.get("servers", [])]

        online_count = sum(1 for w in websites_data if w["status"] == "online") + \
                       sum(1 for a in apps_data if a["status"] == "online") + \
                       sum(1 for s in servers_data if s["status"] == "online")

        offline_count = sum(1 for w in websites_data if w["status"] == "offline") + \
                        sum(1 for a in apps_data if a["status"] == "offline") + \
                        sum(1 for s in servers_data if s["status"] == "offline")

        return {
            "websites": websites_data,
            "apps": apps_data,
            "servers": servers_data,
            "summary": {
                "total": len(websites_from_config) + len(apps_from_config) + len(servers_from_config),
                "online": online_count,
                "offline": offline_count
            }
        }
    except Exception as e:
        return {"websites": [], "apps": [], "servers": [], "error": str(e)}


@app.get("/api/monitoring/stream")
async def api_monitoring_stream(request: Request, user: dict = Depends(require_auth)):
    """Server-Sent Events for real-time monitoring."""
    # Capture user info before entering generator (closure)
    user_role = user.get("role")
    user_email = user.get("email")

    async def event_generator():
        while True:
            # Check if client disconnected
            if await request.is_disconnected():
                break

            try:
                from devops_cli.monitoring import MonitoringConfig, HealthChecker
                from devops_cli.monitoring.checker import HealthStatus

                config = MonitoringConfig()
                checker = HealthChecker()

                websites_from_config = config.get_websites()
                apps_from_config = config.get_apps()
                servers_from_config = config.get_servers()

                # Filter resources by team access (admin sees all)
                if user_role != "admin":
                    from devops_cli.monitoring.config import WebsiteConfig, AppConfig, ServerConfig

                    websites_from_config = filter_by_team_access(
                        [w.as_dict() for w in websites_from_config], user_email, "websites"
                    )
                    websites_from_config = [WebsiteConfig(**w) for w in websites_from_config]

                    apps_from_config = filter_by_team_access(
                        [a.as_dict() for a in apps_from_config], user_email, "apps"
                    )
                    apps_from_config = [AppConfig(**a) for a in apps_from_config]

                    servers_from_config = filter_by_team_access(
                        [s.as_dict() for s in servers_from_config], user_email, "servers"
                    )
                    servers_from_config = [ServerConfig(**s) for s in servers_from_config]

                results = await checker.check_all(websites_from_config, apps_from_config, servers_from_config)

                # Convert HealthResult objects to dictionaries
                def result_to_dict(r):
                    return {
                        "name": r.name,
                        "status": "online" if r.status == HealthStatus.HEALTHY else "offline" if r.status == HealthStatus.UNHEALTHY else "degraded",
                        "response_time": r.response_time_ms,
                        "message": r.message,
                        "url": r.details.get("url", "")
                    }

                data = json.dumps({
                    "timestamp": datetime.now().isoformat(),
                    "websites": [result_to_dict(w) for w in results.get("websites", [])],
                    "apps": [result_to_dict(a) for a in results.get("apps", [])],
                    "servers": [result_to_dict(s) for s in results.get("servers", [])]
                })

                yield f"data: {data}\n\n"
            except Exception as e:
                yield f"data: {json.dumps({'error': str(e)})}\n\n"

            await asyncio.sleep(10)  # Update every 10 seconds

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive"
        }
    )


# ==================== Users API (Admin Only) ====================

@app.get("/api/users")
async def api_users(user: dict = Depends(require_admin)):
    """Get all users (admin only)."""
    users = auth.list_users()
    # Add team info to users
    for u in users:
        u["team"] = get_user_team(u["email"])
    teams_config = load_teams_config()
    teams = list(teams_config.get("teams", {}).keys())
    return {"users": users, "teams": teams}


@app.post("/api/users")
async def api_create_user(request: Request, user: dict = Depends(require_admin)):
    """Create new user (admin only)."""
    data = await request.json()
    email = data.get("email")
    name = data.get("name")
    role = data.get("role", "developer")
    team = data.get("team", "default")

    if not email:
        raise HTTPException(status_code=400, detail="Email required")

    if role not in ["developer", "admin"]:
        raise HTTPException(status_code=400, detail="Role must be developer or admin")

    try:
        token = auth.register_user(email, name, role)
        # Set team for user
        set_user_team(email, team)
        log_activity("user", user["email"], f"Created user {email} with team {team}")
        return {"success": True, "token": token, "email": email, "team": team}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.put("/api/users/{email}/team")
async def api_set_user_team(email: str, request: Request, user: dict = Depends(require_admin)):
    """Set user's team (admin only)."""
    data = await request.json()
    team = data.get("team", "default")

    set_user_team(email, team)
    log_activity("user", user["email"], f"Changed {email} team to {team}")
    return {"success": True, "email": email, "team": team}


@app.delete("/api/users/{email}")
async def api_delete_user(email: str, user: dict = Depends(require_admin)):
    """Delete user (admin only)."""
    if auth.remove_user(email):
        log_activity("user", user["email"], f"Deleted user {email}")
        return {"success": True}
    else:
        raise HTTPException(status_code=404, detail="User not found")


# ==================== Document Storage ====================

DOCUMENTS_DIR = Path.home() / ".devops-cli" / "documents"
DOCUMENTS_DIR.mkdir(parents=True, exist_ok=True)


def get_documents_metadata() -> dict:
    """Get metadata for all uploaded documents."""
    metadata_file = DOCUMENTS_DIR / "metadata.json"
    if metadata_file.exists():
        with open(metadata_file) as f:
            return json.load(f)
    return {"documents": {}}


def save_documents_metadata(metadata: dict):
    """Save documents metadata."""
    metadata_file = DOCUMENTS_DIR / "metadata.json"
    with open(metadata_file, "w") as f:
        json.dump(metadata, f, indent=2)


# ==================== CloudWatch Log Fetching ====================

async def fetch_cloudwatch_logs(log_group: str, region: str, lines: int = 100) -> dict:
    """Fetch logs from AWS CloudWatch."""
    try:
        import boto3
        from botocore.exceptions import ClientError, NoCredentialsError

        client = boto3.client('logs', region_name=region)

        # Get log streams
        streams_response = client.describe_log_streams(
            logGroupName=log_group,
            orderBy='LastEventTime',
            descending=True,
            limit=5
        )

        logs = []
        for stream in streams_response.get('logStreams', []):
            events_response = client.get_log_events(
                logGroupName=log_group,
                logStreamName=stream['logStreamName'],
                limit=lines // len(streams_response.get('logStreams', [1])),
                startFromHead=False
            )

            for event in events_response.get('events', []):
                message = event.get('message', '')
                level = 'INFO'
                if 'ERROR' in message.upper():
                    level = 'ERROR'
                elif 'WARN' in message.upper():
                    level = 'WARN'
                elif 'DEBUG' in message.upper():
                    level = 'DEBUG'

                logs.append({
                    "timestamp": datetime.fromtimestamp(event['timestamp'] / 1000).isoformat(),
                    "level": level,
                    "message": message,
                    "source": stream['logStreamName']
                })

        logs.sort(key=lambda x: x['timestamp'], reverse=True)
        return {"success": True, "logs": logs[:lines], "source": "cloudwatch"}

    except NoCredentialsError:
        return {"success": False, "error": "AWS credentials not configured", "hint": "Run 'devops admin aws configure' to set up AWS access"}
    except ClientError as e:
        error_code = e.response.get('Error', {}).get('Code', 'Unknown')
        if error_code == 'ResourceNotFoundException':
            return {"success": False, "error": f"Log group '{log_group}' not found", "hint": "Check if the log group exists in CloudWatch"}
        return {"success": False, "error": str(e), "hint": "Check AWS permissions and log group configuration"}
    except ImportError:
        return {"success": False, "error": "boto3 not installed", "hint": "Run 'pip install boto3' to enable AWS integration"}
    except Exception as e:
        return {"success": False, "error": str(e), "hint": "Check your AWS configuration and network connectivity"}



def get_document_logs(app_name: str) -> dict:
    """Get logs from uploaded document."""
    metadata = get_documents_metadata()
    doc_info = metadata.get("documents", {}).get(app_name)

    if not doc_info:
        return {"success": False, "error": "No document uploaded"}

    doc_path = DOCUMENTS_DIR / doc_info.get("filename", "")
    if not doc_path.exists():
        return {"success": False, "error": "Document file not found"}

    try:
        if doc_path.suffix.lower() == '.pdf':
            # Try to extract text from PDF
            try:
                import PyPDF2
                with open(doc_path, 'rb') as f:
                    reader = PyPDF2.PdfReader(f)
                    text = ""
                    for page in reader.pages:
                        text += page.extract_text() + "\n"
            except ImportError:
                return {
                    "success": True,
                    "logs": [{
                        "timestamp": datetime.now().isoformat(),
                        "level": "INFO",
                        "message": f"📄 PDF document available: {doc_info.get('original_name', 'document.pdf')}",
                        "source": "document"
                    }, {
                        "timestamp": datetime.now().isoformat(),
                        "level": "INFO",
                        "message": f"Uploaded by: {doc_info.get('uploaded_by', 'admin')} on {doc_info.get('uploaded_at', 'unknown')}",
                        "source": "document"
                    }, {
                        "timestamp": datetime.now().isoformat(),
                        "level": "INFO",
                        "message": "💡 Install PyPDF2 to view PDF contents inline: pip install PyPDF2",
                        "source": "document"
                    }],
                    "source": "document",
                    "document_info": doc_info
                }
        else:
            # Text file
            with open(doc_path, 'r', errors='ignore') as f:
                text = f.read()

        # Parse text into log entries
        logs = []
        for line in text.split('\n')[:100]:
            if line.strip():
                level = 'INFO'
                if 'error' in line.lower():
                    level = 'ERROR'
                elif 'warn' in line.lower():
                    level = 'WARN'
                elif 'debug' in line.lower():
                    level = 'DEBUG'
                logs.append({
                    "timestamp": datetime.now().isoformat(),
                    "level": level,
                    "message": line,
                    "source": "document"
                })

        return {"success": True, "logs": logs, "source": "document", "document_info": doc_info}

    except Exception as e:
        return {"success": False, "error": str(e)}


# ==================== Logs API ====================

@app.get("/api/apps/{app_name}/logs")
async def api_app_logs(
    app_name: str,
    lines: int = 100,
    level: str = "all",
    source_preference: str = "auto",  # auto, live, document
    user: dict = Depends(require_auth)
):
    """Get application logs with priority: live source (CloudWatch) > document > friendly message."""
    from devops_cli.commands.admin import load_apps_config

    config = load_apps_config()
    apps = config.get("apps", {})

    if app_name not in apps:
        raise HTTPException(status_code=404, detail="App not found")

    app_config = apps[app_name]
    logs_config = app_config.get("logs", {})
    
    # Backwards compatibility for flat config structure
    if not logs_config and app_config.get("log_group"):
        logs_config = {
            "type": "cloudwatch",
            "log_group": app_config.get("log_group"),
            "region": app_config.get("region", "us-east-1")
        }
        
    log_type = logs_config.get("type", "none")

    result = {
        "app": app_name,
        "log_type": log_type,
        "log_source": logs_config,
        "logs": [],
        "source_used": None,
        "document_available": False,
        "live_source_available": bool(logs_config and log_type == "cloudwatch"),
        "message": None,
        "hint": None
    }

    # Check if document is available
    metadata = get_documents_metadata()
    if app_name in metadata.get("documents", {}):
        result["document_available"] = True
        result["document_info"] = metadata["documents"][app_name]

    logs_fetched = False

    # Try live source first (only CloudWatch supported)
    if source_preference in ["auto", "live"] and log_type == "cloudwatch":
        log_group = logs_config.get("log_group")
        region = logs_config.get("region", "us-east-1")
        if log_group:
            fetch_result = await fetch_cloudwatch_logs(log_group, region, lines)
            if fetch_result.get("success"):
                result["logs"] = fetch_result["logs"]
                result["source_used"] = "cloudwatch"
                logs_fetched = True
            else:
                result["live_error"] = fetch_result.get("error")
                result["hint"] = fetch_result.get("hint")

    # Try document if live source failed or user prefers document
    if not logs_fetched and (source_preference in ["auto", "document"]) and result["document_available"]:
        doc_result = get_document_logs(app_name)
        if doc_result.get("success"):
            result["logs"] = doc_result["logs"]
            result["source_used"] = "document"
            result["document_info"] = doc_result.get("document_info")
            logs_fetched = True

    # Friendly message if nothing available
    if not logs_fetched:
        if log_type == "cloudwatch" and result.get("live_error"):
            # Logs are configured but failed to fetch
            result["logs"] = [{
                "timestamp": datetime.now().isoformat(),
                "level": "ERROR",
                "message": f"❌ Failed to fetch logs from CloudWatch",
                "source": "system"
            }, {
                "timestamp": datetime.now().isoformat(),
                "level": "ERROR",
                "message": f"Error: {result['live_error']}",
                "source": "system"
            }]
            if result.get("hint"):
                result["logs"].append({
                    "timestamp": datetime.now().isoformat(),
                    "level": "WARN",
                    "message": f"💡 Hint: {result['hint']}",
                    "source": "system"
                })
        else:
            # No logs configured or unsupported type
            result["logs"] = [{
                "timestamp": datetime.now().isoformat(),
                "level": "INFO",
                "message": f"👋 Welcome! Logs for '{app_name}' are not yet configured.",
                "source": "system"
            }, {
                "timestamp": datetime.now().isoformat(),
                "level": "INFO",
                "message": "💡 Ask your admin to configure CloudWatch log groups or upload log documentation.",
                "source": "system"
            }, {
                "timestamp": datetime.now().isoformat(),
                "level": "INFO",
                "message": f"📋 Supported sources: CloudWatch, Uploaded Documents",
                "source": "system"
            }]
        
        result["source_used"] = "none"
        if not result.get("message"):
            result["message"] = "No logs available"

    # Filter by level
    if level != "all":
        result["logs"] = [l for l in result["logs"] if l["level"].lower() == level.lower()]

    result["total"] = len(result["logs"])
    return result


@app.get("/api/apps/{app_name}/logs/stream")
async def api_app_logs_stream(app_name: str, request: Request):
    """Stream application logs in real-time via SSE.

    Fetches real logs from CloudWatch. Shows error message if source is unavailable.
    """
    from devops_cli.commands.admin import load_apps_config

    config = load_apps_config()
    apps = config.get("apps", {})

    if app_name not in apps:
        raise HTTPException(status_code=404, detail="App not found")

    app_config = apps[app_name]
    logs_config = app_config.get("logs", {})
    log_type = logs_config.get("type", "none")
    log_group = app_config.get("log_group") or logs_config.get("log_group")
    region = app_config.get("region", "us-east-1") or logs_config.get("region", "us-east-1")

    async def log_generator():
        # Send initial status message
        status_entry = {
            "timestamp": datetime.now().isoformat(),
            "level": "INFO",
            "message": f"[{app_name}] Connecting to log source...",
            "source": "system"
        }
        yield f"data: {json.dumps(status_entry)}\n\n"

        # Check if CloudWatch log group is configured
        if log_group and (log_type == "cloudwatch" or app_config.get("log_group")):
            try:
                import boto3
                from botocore.exceptions import ClientError, NoCredentialsError

                client = boto3.client('logs', region_name=region)

                while True:
                    if await request.is_disconnected():
                        break

                    try:
                        # Get log streams
                        streams_response = client.describe_log_streams(
                            logGroupName=log_group,
                            orderBy='LastEventTime',
                            descending=True,
                            limit=3
                        )

                        for stream in streams_response.get('logStreams', []):
                            params = {
                                'logGroupName': log_group,
                                'logStreamName': stream['logStreamName'],
                                'limit': 10,
                                'startFromHead': False
                            }

                            events_response = client.get_log_events(**params)

                            for event in events_response.get('events', []):
                                message = event.get('message', '')
                                level = 'INFO'
                                if 'ERROR' in message.upper():
                                    level = 'ERROR'
                                elif 'WARN' in message.upper():
                                    level = 'WARN'
                                elif 'DEBUG' in message.upper():
                                    level = 'DEBUG'

                                log_entry = {
                                    "timestamp": datetime.fromtimestamp(event['timestamp'] / 1000).isoformat(),
                                    "level": level,
                                    "message": f"[{app_name}] {message}",
                                    "source": stream['logStreamName']
                                }
                                yield f"data: {json.dumps(log_entry)}\n\n"

                        await asyncio.sleep(5)  # Poll every 5 seconds

                    except ClientError as e:
                        error_entry = {
                            "timestamp": datetime.now().isoformat(),
                            "level": "ERROR",
                            "message": f"[{app_name}] CloudWatch error: {e.response.get('Error', {}).get('Message', str(e))}",
                            "source": "system"
                        }
                        yield f"data: {json.dumps(error_entry)}\n\n"
                        await asyncio.sleep(10)

            except NoCredentialsError:
                error_entry = {
                    "timestamp": datetime.now().isoformat(),
                    "level": "ERROR",
                    "message": f"[{app_name}] AWS credentials not configured. Run 'devops admin aws configure' to set up access.",
                    "source": "system"
                }
                yield f"data: {json.dumps(error_entry)}\n\n"

            except ImportError:
                error_entry = {
                    "timestamp": datetime.now().isoformat(),
                    "level": "ERROR",
                    "message": f"[{app_name}] boto3 not installed. Run 'pip install boto3' for AWS log streaming.",
                    "source": "system"
                }
                yield f"data: {json.dumps(error_entry)}\n\n"

        else:
            # No log source configured - show helpful message instead of random logs
            no_logs_entry = {
                "timestamp": datetime.now().isoformat(),
                "level": "INFO",
                "message": f"[{app_name}] No real-time log source configured.",
                "source": "system"
            }
            yield f"data: {json.dumps(no_logs_entry)}\n\n"

            hint_entry = {
                "timestamp": datetime.now().isoformat(),
                "level": "INFO",
                "message": f"[{app_name}] Admin: Configure CloudWatch log group for streaming.",
                "source": "system"
            }
            yield f"data: {json.dumps(hint_entry)}\n\n"

            supported_entry = {
                "timestamp": datetime.now().isoformat(),
                "level": "INFO",
                "message": f"[{app_name}] Supported: CloudWatch (ECS/Lambda/EC2)",
                "source": "system"
            }
            yield f"data: {json.dumps(supported_entry)}\n\n"

            # Keep connection alive with periodic status updates
            while True:
                if await request.is_disconnected():
                    break

                status_entry = {
                    "timestamp": datetime.now().isoformat(),
                    "level": "INFO",
                    "message": f"[{app_name}] Waiting for log source configuration...",
                    "source": "system"
                }
                yield f"data: {json.dumps(status_entry)}\n\n"
                await asyncio.sleep(30)

    return StreamingResponse(
        log_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"}
    )


@app.get("/api/servers/{server_name}/logs")
async def api_server_logs(
    server_name: str,
    log_type: str = "system",
    lines: int = 50,
    user: dict = Depends(require_auth)
):
    """Get server logs (primarily from documents)."""
    from devops_cli.commands.admin import load_servers_config

    config = load_servers_config()
    servers = config.get("servers", {})

    if server_name not in servers:
        raise HTTPException(status_code=404, detail="Server not found")

    server = servers[server_name]
    host = server.get("host")

    logs = []
    message = None
    hint = None

    # Check for uploaded document (primary source for server logs now)
    doc_key = f"server_{server_name}"
    metadata = get_documents_metadata()
    doc_available = doc_key in metadata.get("documents", {})

    if doc_available:
        doc_result = get_document_logs(doc_key) 
        if doc_result.get("success"):
            logs = doc_result["logs"]
            message = "Showing logs from uploaded document."
    else:
        message = f"No log documents uploaded for server '{server_name}'."
        hint = "Admin: Upload log documentation for this server in the Documents section."

    return {
        "server": server_name,
        "host": host,
        "log_type": log_type,
        "logs": logs[:lines],
        "message": message,
        "hint": hint,
        "document_available": doc_available
    }


# ==================== Activity/Audit Logs API ====================

@app.get("/api/activity")
async def api_activity(
    limit: int = 50,
    activity_type: str = "all",
    user: dict = Depends(require_auth)
):
    """Get activity/audit logs (dynamic from files)."""
    # Load from audit.log and activity.json
    activities = load_activity()

    # Filter by type
    if activity_type != "all":
        activities = [a for a in activities if a.get("type") == activity_type]

    return {
        "activities": activities[:limit],
        "total": len(activities),
        "types": ["all", "login", "deploy", "config", "user", "alert"]
    }


@app.get("/api/activity/stream")
async def api_activity_stream(request: Request, user: dict = Depends(require_auth)):
    """Live activity stream via SSE."""
    async def event_generator():
        last_count = 0
        while True:
            if await request.is_disconnected():
                break
            activities = load_activity()
            if len(activities) > last_count:
                new_activities = activities[:len(activities) - last_count] if last_count > 0 else activities[:5]
                last_count = len(activities)
                yield f"data: {json.dumps({'activities': new_activities})}\n\n"
            await asyncio.sleep(2)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


# ==================== Deployments API ====================

@app.get("/api/deployments")
async def api_deployments(
    app_name: str = None,
    status: str = "all",
    limit: int = 20,
    user: dict = Depends(require_auth)
):
    """Get deployment history (dynamic from file, team-filtered)."""
    from devops_cli.commands.admin import load_apps_config

    config = load_apps_config()
    all_apps = list(config.get("apps", {}).keys())

    # Load deployments from file
    deployments = load_deployments()

    # Filter by team access (admin sees all)
    if user.get("role") != "admin":
        deployments = filter_by_team_access(deployments, user["email"], "apps", "app")
        all_apps = [a["name"] for a in filter_by_team_access([{"name": a} for a in all_apps], user["email"], "apps")]

    # Filter by app
    if app_name:
        deployments = [d for d in deployments if d.get("app") == app_name]

    # Filter by status
    if status != "all":
        deployments = [d for d in deployments if d.get("status") == status]

    return {
        "deployments": deployments[:limit],
        "total": len(deployments),
        "apps": all_apps,
        "statuses": ["all", "success", "failed", "in_progress", "rolled_back"]
    }


@app.post("/api/deployments/{app_name}/deploy")
async def api_trigger_deployment(
    app_name: str,
    request: Request,
    user: dict = Depends(require_auth)
):
    """Trigger a new deployment (saves to file)."""
    data = await request.json()
    version = data.get("version", "latest")
    environment = data.get("environment", "staging")
    message = data.get("message", "Deployment triggered via dashboard")
    commit = data.get("commit", "HEAD")

    # Check team access
    if user.get("role") != "admin":
        team = get_user_team(user["email"])
        permissions = get_team_permissions(team)
        if not can_access_resource(app_name, permissions.get("apps", [])):
            raise HTTPException(status_code=403, detail="No access to this app")

    # Save deployment to file
    deployment = save_deployment({
        "app": app_name,
        "version": version,
        "environment": environment,
        "status": "in_progress",
        "deployed_by": user["email"],
        "duration": "-",
        "commit": commit,
        "message": message
    })

    # Log activity
    log_activity("deploy", user["email"], f"Deployed {app_name} {version} to {environment}")

    return {
        "success": True,
        "message": f"Deployment of {app_name} {version} to {environment} initiated",
        "deployment_id": deployment["id"],
        "triggered_by": user["email"]
    }


# ==================== Document Management API (Admin Only) ====================

@app.get("/api/documents")
async def api_list_documents(user: dict = Depends(require_admin)):
    """List all uploaded documents (admin only)."""
    metadata = get_documents_metadata()
    return {
        "documents": metadata.get("documents", {}),
        "total": len(metadata.get("documents", {}))
    }


@app.post("/api/documents/{resource_type}/{resource_name}")
async def api_upload_document(
    resource_type: str,
    resource_name: str,
    request: Request,
    user: dict = Depends(require_admin)
):
    """Upload a document for an app or server (admin only)."""
    from fastapi import UploadFile, File, Form

    # Get form data
    form = await request.form()
    file = form.get("file")

    if not file:
        raise HTTPException(status_code=400, detail="No file uploaded")

    # Validate file type
    filename = file.filename
    if not filename.lower().endswith(('.pdf', '.txt', '.log', '.md')):
        raise HTTPException(status_code=400, detail="Only PDF, TXT, LOG, and MD files are allowed")

    # Validate resource type
    if resource_type not in ["app", "server", "website"]:
        raise HTTPException(status_code=400, detail="Resource type must be 'app', 'server', or 'website'")

    # Create unique filename
    ext = Path(filename).suffix
    safe_name = f"{resource_type}_{resource_name}_{datetime.now().strftime('%Y%m%d%H%M%S')}{ext}"
    file_path = DOCUMENTS_DIR / safe_name

    # Save file
    content = await file.read()
    with open(file_path, "wb") as f:
        f.write(content)

    # Update metadata
    metadata = get_documents_metadata()
    key = f"{resource_type}_{resource_name}"
    metadata["documents"][key] = {
        "filename": safe_name,
        "original_name": filename,
        "resource_type": resource_type,
        "resource_name": resource_name,
        "size": len(content),
        "uploaded_by": user["email"],
        "uploaded_at": datetime.now().isoformat(),
        "description": form.get("description", "")
    }
    save_documents_metadata(metadata)

    return {
        "success": True,
        "message": f"Document uploaded successfully for {resource_type} '{resource_name}'",
        "document": metadata["documents"][key]
    }


@app.delete("/api/documents/{resource_type}/{resource_name}")
async def api_delete_document(
    resource_type: str,
    resource_name: str,
    user: dict = Depends(require_admin)
):
    """Delete a document (admin only)."""
    metadata = get_documents_metadata()
    key = f"{resource_type}_{resource_name}"

    if key not in metadata.get("documents", {}):
        raise HTTPException(status_code=404, detail="Document not found")

    doc_info = metadata["documents"][key]
    file_path = DOCUMENTS_DIR / doc_info["filename"]

    # Delete file
    if file_path.exists():
        file_path.unlink()

    # Update metadata
    del metadata["documents"][key]
    save_documents_metadata(metadata)

    return {"success": True, "message": "Document deleted successfully"}


@app.get("/api/documents/{resource_type}/{resource_name}/download")
async def api_download_document(
    resource_type: str,
    resource_name: str,
    user: dict = Depends(require_auth)
):
    """Download a document."""
    from fastapi.responses import FileResponse

    metadata = get_documents_metadata()
    key = f"{resource_type}_{resource_name}"

    if key not in metadata.get("documents", {}):
        raise HTTPException(status_code=404, detail="Document not found")

    doc_info = metadata["documents"][key]
    file_path = DOCUMENTS_DIR / doc_info["filename"]

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Document file not found")

    return FileResponse(
        path=str(file_path),
        filename=doc_info["original_name"],
        media_type="application/octet-stream"
    )


# ==================== GitHub API ====================

def get_github_config():
    """Load GitHub config from global settings."""
    from devops_cli.config.settings import load_config
    return load_config()

def can_access_repo(repo_name: str, team_repos: list) -> bool:
    """Check if team can access repo."""
    import fnmatch
    for pattern in team_repos:
        if pattern == '*' or fnmatch.fnmatch(repo_name, pattern):
            return True
    return False

@app.get("/api/github/repos")
async def api_github_repos(user: dict = Depends(require_auth)):
    """Fetch GitHub org repos with team-based filtering and caching."""
    import httpx

    config = get_github_config()
    github_config = config.get("github", {})
    org = github_config.get("org", "")
    token = github_config.get("token", "")

    if not org:
        return {"error": "GitHub organization not configured", "repos": [], "hint": "Admin: Configure github.org in config.yaml or via 'devops init'"}

    # Get user's team and allowed repos
    # We still need teams.yaml for team permissions
    from devops_cli.commands.admin import load_teams_config
    teams_config = load_teams_config()
    user_team = get_user_team(user["email"])
    teams = teams_config.get("teams", {})
    team_config = teams.get(user_team, teams.get("default", {}))
    allowed_repos = team_config.get("repos", ["*"])

    # Check cache first (cache key includes org)
    cache_key = f"github_repos:{org}"
    cached_repos = github_cache.get(cache_key)

    if cached_repos is None:
        # Fetch repos from GitHub API
        headers = {"Accept": "application/vnd.github.v3+json"}
        if token:
            headers["Authorization"] = f"token {token}"

        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    f"https://api.github.com/orgs/{org}/repos?per_page=100&sort=updated",
                    headers=headers,
                    timeout=10.0
                )

                if resp.status_code == 404:
                    return {"error": f"Organization '{org}' not found", "repos": []}
                elif resp.status_code == 403:
                    return {"error": "Rate limited or token invalid", "repos": [], "hint": "Add GitHub token in teams.yaml"}
                elif resp.status_code != 200:
                    return {"error": f"GitHub API error: {resp.status_code}", "repos": []}

                all_repos = resp.json()

                # Cache the raw repos for 5 minutes
                github_cache.set(cache_key, all_repos)

        except httpx.TimeoutException:
            return {"error": "GitHub API timeout", "repos": []}
        except Exception as e:
            return {"error": str(e), "repos": []}
    else:
        all_repos = cached_repos

    # Filter by team access (done after caching to support per-user filtering)
    filtered_repos = []
    for repo in all_repos:
        if can_access_repo(repo["name"], allowed_repos):
            filtered_repos.append({
                "name": repo["name"],
                "description": repo.get("description") or "No description",
                "url": repo["html_url"],
                "language": repo.get("language"),
                "stars": repo.get("stargazers_count", 0),
                "forks": repo.get("forks_count", 0),
                "updated_at": repo.get("updated_at"),
                "private": repo.get("private", False),
                "default_branch": repo.get("default_branch", "main")
            })

    return {
        "org": org,
        "team": user_team,
        "team_name": team_config.get("name", user_team),
        "repos": filtered_repos,
        "total": len(filtered_repos),
        "all_count": len(all_repos),
        "cached": cached_repos is not None
    }

@app.get("/api/github/repos/{owner}/{repo}/status")
async def api_github_repo_status(owner: str, repo: str, user: dict = Depends(require_auth)):
    """Fetch latest commit and CI status for a repository."""
    import httpx

    config = get_github_config()
    token = config.get("github", {}).get("token", "")
    
    headers = {"Accept": "application/vnd.github.v3+json"}
    if token:
        headers["Authorization"] = f"token {token}"

    try:
        async with httpx.AsyncClient() as client:
            # 1. Get default branch (to know what to check)
            repo_resp = await client.get(
                f"https://api.github.com/repos/{owner}/{repo}",
                headers=headers, timeout=5.0
            )
            if repo_resp.status_code != 200:
                return {"error": "Repo not found"}
            
            default_branch = repo_resp.json().get("default_branch", "main")

            # 2. Fetch latest commit on default branch
            commit_resp = await client.get(
                f"https://api.github.com/repos/{owner}/{repo}/commits/{default_branch}",
                headers=headers, timeout=5.0
            )
            
            commit_data = {}
            if commit_resp.status_code == 200:
                c = commit_resp.json()
                commit_data = {
                    "sha": c.get("sha", "")[:7],
                    "message": c.get("commit", {}).get("message", ""),
                    "author": c.get("commit", {}).get("author", {}).get("name", ""),
                    "date": c.get("commit", {}).get("author", {}).get("date", ""),
                    "html_url": c.get("html_url", "")
                }

            # 3. Fetch latest workflow run
            # We look for the latest run on the default branch
            runs_resp = await client.get(
                f"https://api.github.com/repos/{owner}/{repo}/actions/runs?branch={default_branch}&per_page=1",
                headers=headers, timeout=5.0
            )

            pipeline_data = {"status": "unknown"}
            if runs_resp.status_code == 200:
                runs = runs_resp.json().get("workflow_runs", [])
                if runs:
                    latest = runs[0]
                    pipeline_data = {
                        "status": latest.get("status", "unknown"),
                        "conclusion": latest.get("conclusion", "unknown"), # success, failure, etc.
                        "name": latest.get("name", ""),
                        "html_url": latest.get("html_url", ""),
                        "created_at": latest.get("created_at", "")
                    }
                else:
                    pipeline_data = {"status": "no_runs", "conclusion": "neutral"}

            return {
                "repo": repo,
                "commit": commit_data,
                "pipeline": pipeline_data
            }

    except Exception as e:
        return {"error": str(e)}

@app.get("/api/github/config")
async def api_github_config(user: dict = Depends(require_admin)):
    """Get GitHub configuration (admin only)."""
    from devops_cli.commands.admin import load_teams_config
    
    config = get_github_config()
    teams_config = load_teams_config()
    
    return {
        "org": config.get("github", {}).get("org", ""),
        "has_token": bool(config.get("github", {}).get("token")),
        "teams": {k: {"name": v.get("name", k), "repos": v.get("repos", [])} for k, v in teams_config.get("teams", {}).items()}
    }

@app.post("/api/github/config")
async def api_update_github_config(request: Request, user: dict = Depends(require_admin)):
    """Update GitHub configuration (admin only)."""
    from devops_cli.config.settings import save_config
    
    data = await request.json()
    config = get_github_config()
    
    if "github" not in config:
        config["github"] = {}

    if "org" in data:
        config["github"]["org"] = data["org"]
    if "token" in data:
        config["github"]["token"] = data["token"]

    save_config(config)

    return {"success": True, "message": "GitHub configuration updated"}


# ==================== Config API ====================

@app.get("/api/config/status")
async def api_config_status(user: dict = Depends(require_auth)):
    """Get configuration status."""
    from devops_cli.commands.admin import (
        load_apps_config, load_servers_config, load_aws_config, load_teams_config,
        ADMIN_CONFIG_DIR
    )
    from devops_cli.config.websites import load_websites_config

    try:
        apps_config = load_apps_config()
        servers_config = load_servers_config()
        aws_config = load_aws_config()
        websites_config = load_websites_config()
        teams_config = load_teams_config() # Also load teams config

        users = auth.list_users()

        # websites_config is already the websites dict (not wrapped)
        websites_count = len(websites_config) if isinstance(websites_config, dict) else 0

        return {
            "initialized": ADMIN_CONFIG_DIR.exists(),
            "organization": aws_config.get("organization", "Not set"),
            "apps_count": len(apps_config.get("apps", {})),
            "servers_count": len(servers_config.get("servers", {})),
            "websites_count": websites_count,
            "aws_roles_count": len(aws_config.get("roles", {})),
            "teams_count": len(teams_config.get("teams", {})),
            "users_count": len(users)
        }
    except Exception as e:
        return {"error": str(e)}

@app.post("/api/config/upload")
async def api_config_upload(
    file: UploadFile = File(...),
    config_type: str = Form(...),
    merge: bool = Form(...),
    user: dict = Depends(require_admin)
):
    """
    Upload a YAML configuration file to update various configurations.
    Requires admin role.
    """
    import yaml
    from devops_cli.commands.admin import (
        save_apps_config, save_aws_config, save_servers_config, save_teams_config,
        load_apps_config, load_aws_config, load_servers_config, load_teams_config
    )
    from devops_cli.config.websites import load_websites_config, save_websites_config
    from devops_cli.config.settings import save_config as save_global_config, load_config as load_global_config
    from devops_cli.config.schemas import (
        AppConfigSchema, WebsiteConfigSchema, ServerConfigSchema,
        AwsConfigSchema, TeamsConfigSchema, FullConfigSchema, AwsRoleSchema, TeamAccessSchema
    )

    try:
        content = (await file.read()).decode('utf-8')
        uploaded_data = yaml.safe_load(content)

        if not isinstance(uploaded_data, dict):
            raise HTTPException(status_code=400, detail="Uploaded file is not a valid YAML dictionary.")

        # --- Validation and Saving Logic ---
        if config_type == "full":
            # For full config, the uploaded_data should match FullConfigSchema structure
            try:
                validated_config = FullConfigSchema.model_validate(uploaded_data)
            except ValidationError as e:
                raise HTTPException(status_code=400, detail=f"Full config validation error: {e.errors()}")

            if not merge:
                # Replace all configs
                # Note: The underlying save functions are designed to save the *content* of the respective YAML file.
                # Here, uploaded_data for "full" contains separate sections, not the direct content of one file.
                # So we extract sections and save them to their corresponding files.
                if validated_config.apps is not None: save_apps_config({"apps": {name: app.model_dump(by_alias=True) for name, app in validated_config.apps.items()}})
                if validated_config.servers is not None: save_servers_config({"servers": {name: server.model_dump(by_alias=True) for name, server in validated_config.servers.items()}})
                if validated_config.websites is not None: save_websites_config({name: website.model_dump(by_alias=True) for name, website in validated_config.websites.items()})
                if validated_config.aws is not None: save_aws_config(validated_config.aws.model_dump(by_alias=True))
                if validated_config.teams is not None: save_teams_config(validated_config.teams.model_dump(by_alias=True))

                # Handle global settings that might be part of full export but not covered by other saves
                # (e.g., github token is in settings.py's global config, not aws.yaml etc.)
                current_global_config = load_global_config()
                if "github" in uploaded_data:
                    current_global_config["github"] = uploaded_data["github"]
                save_global_config(current_global_config)

            else:
                # Merge logic for full config
                # For now, restrict merge to specific sections for simplicity and to avoid complex recursive merges
                # A full merge would require deep merging logic.
                raise HTTPException(status_code=400, detail="Merge option not directly supported for 'full' config type. Please use 'replace' to overwrite or upload individual sections.")
            
            log_activity("config", user["email"], f"Uploaded and {'replaced' if not merge else 'merged'} full config.")
            return {"success": True, "message": f"Full configuration {'replaced' if not merge else 'merged'} successfully."}

        elif config_type == "apps":
            # For apps, the uploaded data should be a dict where keys are app names and values are app configs
            try:
                validated_apps = {k: AppConfigSchema.model_validate(v) for k, v in uploaded_data.items()}
            except ValidationError as e:
                raise HTTPException(status_code=400, detail=f"Applications config validation error: {e.errors()}")

            current_config = load_apps_config()
            if merge:
                for name, app_data in validated_apps.items():
                    current_config.setdefault("apps", {})[name] = app_data.model_dump(by_alias=True)
            else:
                current_config["apps"] = {name: app.model_dump(by_alias=True) for name, app in validated_apps.items()}
            save_apps_config(current_config)
            log_activity("config", user["email"], f"Uploaded and {'merged' if merge else 'replaced'} apps config.")
            return {"success": True, "message": f"Applications configuration {'merged' if merge else 'replaced'} successfully."}

        elif config_type == "servers":
            try:
                validated_servers = {k: ServerConfigSchema.model_validate(v) for k, v in uploaded_data.items()}
            except ValidationError as e:
                raise HTTPException(status_code=400, detail=f"Servers config validation error: {e.errors()}")

            current_config = load_servers_config()
            if merge:
                for name, server_data in validated_servers.items():
                    current_config.setdefault("servers", {})[name] = server_data.model_dump(by_alias=True)
            else:
                current_config["servers"] = {name: server.model_dump(by_alias=True) for name, server in validated_servers.items()}
            save_servers_config(current_config)
            log_activity("config", user["email"], f"Uploaded and {'merged' if merge else 'replaced'} servers config.")
            return {"success": True, "message": f"Servers configuration {'merged' if merge else 'replaced'} successfully."}

        elif config_type == "websites":
            try:
                validated_websites = {k: WebsiteConfigSchema.model_validate(v) for k, v in uploaded_data.items()}
            except ValidationError as e:
                raise HTTPException(status_code=400, detail=f"Websites config validation error: {e.errors()}")

            current_config = load_websites_config()
            if merge:
                for name, website_data in validated_websites.items():
                    current_config[name] = website_data.model_dump(by_alias=True)
            else:
                current_config = {name: website.model_dump(by_alias=True) for name, website in validated_websites.items()}
            save_websites_config(current_config)
            log_activity("config", user["email"], f"Uploaded and {'merged' if merge else 'replaced'} websites config.")
            return {"success": True, "message": f"Websites configuration {'merged' if merge else 'replaced'} successfully."}

        elif config_type == "aws":
            # AWS config file usually contains top-level keys like 'organization', 'roles'
            # The uploaded_data should be validated as AwsConfigSchema
            try:
                validated_aws_config = AwsConfigSchema.model_validate(uploaded_data)
            except ValidationError as e:
                raise HTTPException(status_code=400, detail=f"AWS config validation error: {e.errors()}")

            current_config = load_aws_config()
            if merge:
                # Merge top-level keys, specifically roles
                current_config.update(validated_aws_config.model_dump(by_alias=True, exclude_unset=True))
                # For roles, need a deeper merge
                if validated_aws_config.roles:
                    current_config.setdefault("roles", {}).update(validated_aws_config.roles.model_dump(by_alias=True, exclude_unset=True))
            else:
                current_config = validated_aws_config.model_dump(by_alias=True)
            save_aws_config(current_config)
            log_activity("config", user["email"], f"Uploaded and {'merged' if merge else 'replaced'} AWS config.")
            return {"success": True, "message": f"AWS configuration {'merged' if merge else 'replaced'} successfully."}

        elif config_type == "teams":
            try:
                validated_teams_config = TeamsConfigSchema.model_validate(uploaded_data)
            except ValidationError as e:
                raise HTTPException(status_code=400, detail=f"Teams config validation error: {e.errors()}")

            current_config = load_teams_config()
            if merge:
                current_config.setdefault("teams", {}).update({name: team.model_dump(by_alias=True) for name, team in validated_teams_config.teams.items()})
            else:
                current_config["teams"] = {name: team.model_dump(by_alias=True) for name, team in validated_teams_config.teams.items()}
            save_teams_config(current_config)
            log_activity("config", user["email"], f"Uploaded and {'merged' if merge else 'replaced'} teams config.")
            return {"success": True, "message": f"Teams configuration {'merged' if merge else 'replaced'} successfully."}
    except Exception as e:
        log_activity("config", user["email"], f"Config upload failed: {str(e)}", "failed")
        raise HTTPException(status_code=500, detail=f"Configuration upload failed: {str(e)}")



# ==================== Run Server ====================

def create_app():
    """Create and return the FastAPI app."""
    return app


def run_dashboard(host: str = None, port: int = None, reload: bool = False):
    """Run the dashboard server with dynamic defaults from environment."""
    # Use environment variables if not provided
    if host is None:
        host = os.getenv("DASHBOARD_HOST", "0.0.0.0")
    if port is None:
        port = int(os.getenv("DASHBOARD_PORT", "3000"))

    uvicorn.run(
        "devops_cli.dashboard.app:app",
        host=host,
        port=port,
        reload=reload,
        log_level="info"
    )


if __name__ == "__main__":
    run_dashboard()
