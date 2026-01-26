"""Application routes for the dashboard."""

import json
import asyncio
from datetime import datetime
from fastapi import APIRouter, Request, HTTPException, Depends
from fastapi.responses import StreamingResponse
import httpx
from ..main import require_auth
from ..logic import filter_by_team_access
from ..services import fetch_cloudwatch_logs, get_document_logs
from devops_cli.utils.log_formatters import mask_secrets

router = APIRouter(prefix="/api/apps", tags=["apps"])

@router.get("")
async def api_apps(user: dict = Depends(require_auth)):
    """Get all applications (filtered by team access)."""
    from devops_cli.commands.admin import load_apps_config

    try:
        config = load_apps_config()
        # Handle cases where config might be just the apps dict or wrapped in 'apps' key
        apps = config.get("apps", {}) if "apps" in config else config

        result = []
        for name, app_data in apps.items():
            if not isinstance(app_data, dict):
                continue
            
            # Extract log and health info from different possible locations
            logs_cfg = app_data.get("logs") or {}
            if not logs_cfg and app_data.get("log_group"):
                logs_cfg = {
                    "type": "cloudwatch",
                    "log_group": app_data.get("log_group"),
                    "region": app_data.get("region")
                }
                
            health_cfg = app_data.get("health") or app_data.get("health_check") or {}

            result.append(
                {
                    "name": name,
                    "display_name": app_data.get("name", name),
                    "type": app_data.get("type", "unknown"),
                    "description": app_data.get("description", ""),
                    "health": health_cfg,
                    "logs": logs_cfg,
                }
            )

        # Only filter if not an admin
        if user.get("role") != "admin":
            result = filter_by_team_access(result, user["email"], "apps")

        print(f"DEBUG: api_apps returning {len(result)} apps")
        return {"apps": result}
    except Exception as e:
        print(f"DEBUG: api_apps error: {e}")
        return {"apps": [], "error": str(e)}


@router.get("/{app_name}/health")
async def api_app_health(app_name: str, user: dict = Depends(require_auth)):
    """Check app health."""
    from devops_cli.commands.admin import load_apps_config

    config = load_apps_config()
    apps = config.get("apps", {})

    if app_name not in apps:
        raise HTTPException(status_code=404, detail="App not found")

    app = apps[app_name]
    health_config = app.get("health_check", app.get("health", {}))

    if not health_config:
        return {"status": "unknown", "message": "No health check configured"}

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
                    "url": url,
                }
            else:
                return {
                    "status": "unhealthy",
                    "response_time": round(elapsed, 2),
                    "status_code": response.status_code,
                    "expected": expected_status,
                    "url": url,
                }
    except Exception as e:
        return {"status": "unhealthy", "error": str(e), "url": url}

@router.get("/{app_name}/logs")
async def api_app_logs(
    app_name: str,
    lines: int = 100,
    level: str = "all",
    source_preference: str = "auto",
    user: dict = Depends(require_auth),
):
    """Get application logs."""
    from devops_cli.commands.admin import load_apps_config

    config = load_apps_config()
    apps = config.get("apps", {})

    if app_name not in apps:
        raise HTTPException(status_code=404, detail="App not found")

    app_config = apps[app_name]
    logs_config = app_config.get("logs", {})
    
    # Check both top-level and nested 'logs' for log_group
    log_group = logs_config.get("log_group") or app_config.get("log_group")
    # Check both top-level and nested 'logs' for region
    region = logs_config.get("region") or app_config.get("region") or "us-east-1"
    
    log_type = logs_config.get("type") or ("cloudwatch" if log_group else "none")

    if log_type == "cloudwatch" and log_group:
        aws_role = app_config.get("aws_role")
        return await fetch_cloudwatch_logs(log_group, region, lines, aws_role=aws_role)
    
    doc_logs = get_document_logs(app_name)
    if doc_logs.get("success"):
        return doc_logs
    
    return {"success": False, "error": "No logs available"}

@router.get("/{app_name}/logs/stream")
async def api_app_logs_stream(app_name: str, request: Request):
    """Stream application logs via SSE."""
    from devops_cli.commands.admin import load_apps_config
    
    config = load_apps_config()
    apps = config.get("apps", {})
    if app_name not in apps:
        raise HTTPException(status_code=404, detail="App not found")
        
    app_config = apps[app_name]
    logs_config = app_config.get("logs", {})
    
    # Check both top-level and nested 'logs'
    log_group = logs_config.get("log_group") or app_config.get("log_group")
    region = logs_config.get("region") or app_config.get("region") or "us-east-1"

    async def log_generator():
        yield f"data: {json.dumps({'timestamp': datetime.now().isoformat(), 'level': 'INFO', 'message': f'Connecting to {app_name}...', 'source': 'system'})}\n\n"

        if not log_group:
            yield f"data: {json.dumps({'timestamp': datetime.now().isoformat(), 'level': 'ERROR', 'message': 'No log group configured', 'source': 'system'})}\n\n"
            return

        try:
            from devops_cli.utils.aws_helpers import get_aws_session
            session = get_aws_session(role_name=app_config.get("aws_role"), region=region)
            client = session.client("logs")
            last_timestamp = int((datetime.now().timestamp() - 300) * 1000)
            seen_ids = set()

            while True:
                if await request.is_disconnected():
                    break

                try:
                    response = client.filter_log_events(
                        logGroupName=log_group,
                        startTime=last_timestamp,
                        interleaved=True,
                        limit=10
                    )

                    for event in response.get("events", []):
                        if event["eventId"] in seen_ids: continue
                        seen_ids.add(event["eventId"])
                        
                        message = event.get("message", "")
                        level = "INFO"
                        if "ERROR" in message.upper(): level = "ERROR"
                        elif "WARN" in message.upper(): level = "WARN"

                        log_data = {
                            'timestamp': datetime.fromtimestamp(event['timestamp']/1000).isoformat(),
                            'level': level,
                            'message': mask_secrets(message),
                            'source': event.get('logStreamName', 'aws')
                        }
                        yield f"data: {json.dumps(log_data)}\n\n"
                        last_timestamp = max(last_timestamp, event["timestamp"])

                    if len(seen_ids) > 1000: seen_ids = set(list(seen_ids)[-500:])
                except: pass
                await asyncio.sleep(5)
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return StreamingResponse(log_generator(), media_type="text/event-stream")