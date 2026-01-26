"""Server routes for the dashboard."""

import asyncio
from fastapi import APIRouter, Request, HTTPException, Depends
from ..main import require_auth
from ..logic import filter_by_team_access, get_user_team, get_team_permissions, can_access_resource, log_activity

router = APIRouter(prefix="/api/servers", tags=["servers"])

@router.get("")
async def api_servers(user: dict = Depends(require_auth)):
    """Get all servers (filtered by team access)."""
    from devops_cli.commands.admin import load_servers_config

    try:
        config = load_servers_config()
        servers = config.get("servers", {})

        result = []
        for name, server in servers.items():
            result.append(
                {
                    "name": name,
                    "host": server.get("host", ""),
                    "user": server.get("user", ""),
                    "port": server.get("port", 22),
                    "tags": server.get("tags", []),
                }
            )

        # Filter by team access (admin sees all)
        if user.get("role") != "admin":
            result = filter_by_team_access(result, user["email"], "servers")

        return {"servers": result}
    except Exception as e:
        return {"servers": [], "error": str(e)}


@router.post("/{server_name}/exec")
async def api_server_exec(
    server_name: str, request: Request, user: dict = Depends(require_auth)
):
    """Execute a command on a server via SSH."""
    from devops_cli.commands.ssh import get_server_config, run_remote_command

    data = await request.json()
    command = data.get("command")

    if not command:
        raise HTTPException(status_code=400, detail="Command required")

    # Check team access
    if user.get("role") != "admin":
        team = get_user_team(user["email"])
        permissions = get_team_permissions(team)
        if not can_access_resource(server_name, permissions.get("servers", [])):
            raise HTTPException(status_code=403, detail="No access to this server")

    config = get_server_config(server_name)
    if not config:
        raise HTTPException(status_code=404, detail="Server not found")

    # Run command in thread to avoid blocking
    result = await asyncio.to_thread(
        run_remote_command, server_name, config, command
    )

    # Log to system activity
    log_activity(
        "server",
        user["email"],
        f"Executed '{command[:30]}...' on {server_name}",
        "success" if result["success"] else "failed",
    )

    return result
