"""Configuration routes for the dashboard."""

from fastapi import APIRouter, Request, HTTPException, Depends
from ..main import require_admin, require_auth
from ..logic import log_activity

router = APIRouter(prefix="/api/config", tags=["config"])

@router.get("/status")
async def api_config_status(user: dict = Depends(require_auth)):
    """Get configuration status."""
    from devops_cli.commands.admin import (
        load_apps_config,
        load_servers_config,
        load_aws_config,
        load_teams_config,
    )
    
    apps = load_apps_config().get("apps", {})
    servers = load_servers_config().get("servers", {})
    
    result = {
        "apps_count": len(apps),
        "servers_count": len(servers),
        "aws_roles_count": len(load_aws_config().get("roles", {})),
        "teams_count": len(load_teams_config().get("teams", {})),
    }
    print(f"DEBUG: api_config_status returning: {result}")
    return result

@router.post("/apps")
async def api_save_app(app_config: dict, user: dict = Depends(require_admin)):
    """Add or update an application configuration."""
    from devops_cli.commands.admin import load_apps_config, save_apps_config
    
    name = app_config.get("name")
    if not name:
        raise HTTPException(status_code=400, detail="App name required")
        
    config = load_apps_config()
    config["apps"][name] = app_config
    save_apps_config(config)
    
    log_activity("config", user["email"], f"Updated app config: {name}")
    return {"success": True}

@router.post("/servers")
async def api_save_server(server_config: dict, user: dict = Depends(require_admin)):
    """Add or update a server configuration."""
    from devops_cli.commands.admin import load_servers_config, save_servers_config
    
    name = server_config.get("name")
    if not name:
        raise HTTPException(status_code=400, detail="Server name required")
        
    config = load_servers_config()
    config["servers"][name] = server_config
    save_servers_config(config)
    
    log_activity("config", user["email"], f"Updated server config: {name}")
    return {"success": True}
