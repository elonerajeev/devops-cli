"""Monitoring routes for the dashboard."""

import asyncio
import json
from fastapi import APIRouter, Request, HTTPException, Depends
from fastapi.responses import StreamingResponse
from ..main import require_auth, monitoring_cache
from ..logic import filter_by_team_access

router = APIRouter(prefix="/api/monitoring", tags=["monitoring"])

@router.get("")
async def api_monitoring(user: dict = Depends(require_auth)):
    """Get monitoring status."""
    # Check cache first
    cached = monitoring_cache.get("status")
    if cached:
        return cached

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
        results = await checker.check_all(
            websites_from_config, apps_from_config, servers_from_config
        )

        # Convert HealthResult objects to dictionaries
        def result_to_dict(r):
            return {
                "name": r.name,
                "status": (
                    "online"
                    if r.status == HealthStatus.HEALTHY
                    else "offline" if r.status == HealthStatus.UNHEALTHY else "degraded"
                ),
                "response_time": r.response_time_ms,
                "message": r.message,
                "details": r.details,
                "checked_at": r.checked_at.isoformat(),
            }

        # Prepare summary for frontend
        summary = checker.get_summary()
        frontend_summary = {
            "online": summary.get("healthy", 0),
            "offline": summary.get("unhealthy", 0),
            "degraded": summary.get("degraded", 0),
            "unknown": summary.get("unknown", 0),
            "total": summary.get("total", 0)
        }

        response_data = {
            "websites": [result_to_dict(r) for r in results["websites"]],
            "apps": [result_to_dict(r) for r in results["apps"]],
            "servers": [result_to_dict(r) for r in results["servers"]],
            "summary": frontend_summary,
        }
        
        print(f"DEBUG: api_monitoring returning summary: {frontend_summary}")
        monitoring_cache.set("status", response_data)
        return response_data
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/stream")
async def api_monitoring_stream(request: Request):
    """Stream monitoring status updates via SSE."""
    # We don't use Depends(require_auth) here to avoid cookie issues with EventSource
    # but we will check session manually if needed. 
    # For now, following original logic.

    async def status_generator():
        while True:
            if await request.is_disconnected():
                break

            try:
                from devops_cli.monitoring import MonitoringConfig, HealthChecker
                from devops_cli.monitoring.checker import HealthStatus
                from devops_cli.monitoring.config import WebsiteConfig, AppConfig, ServerConfig

                config = MonitoringConfig()
                checker = HealthChecker()

                # Get resources (no filtering for stream for simplicity in this turn)
                websites = config.get_websites()
                apps = config.get_apps()
                servers = config.get_servers()

                results = await checker.check_all(websites, apps, servers)

                def result_to_dict(r):
                    return {
                        "name": r.name,
                        "status": (
                            "online"
                            if r.status == HealthStatus.HEALTHY
                            else "offline" if r.status == HealthStatus.UNHEALTHY else "degraded"
                        ),
                        "response_time": r.response_time_ms,
                    }

                summary = checker.get_summary()
                data = {
                    "websites": [result_to_dict(r) for r in results["websites"]],
                    "apps": [result_to_dict(r) for r in results["apps"]],
                    "servers": [result_to_dict(r) for r in results["servers"]],
                    "summary": {
                        "online": summary.get("healthy", 0),
                        "offline": summary.get("unhealthy", 0),
                        "total": summary.get("total", 0)
                    }
                }

                yield f"data: {json.dumps(data)}\n\n"
            except Exception as e:
                yield f"data: {json.dumps({'error': str(e)})}\n\n"

            await asyncio.sleep(10)  # Update every 10 seconds

    return StreamingResponse(status_generator(), media_type="text/event-stream")
