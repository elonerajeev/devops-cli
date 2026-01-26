"""Security routes for the dashboard."""

import asyncio
from datetime import datetime
from pathlib import Path
from fastapi import APIRouter, Request, HTTPException, Depends
from ..main import require_auth
from ..logic import log_activity
from devops_cli.utils.security_scanner import run_local_scan

router = APIRouter(prefix="/api/security", tags=["security"])

security_events = []

@router.post("/webhooks/github")
async def github_security_webhook(request: Request):
    """Handle GitHub security alert webhooks."""
    event_type = request.headers.get("X-GitHub-Event")
    data = await request.json()

    event = {
        "timestamp": datetime.now().isoformat(),
        "event_type": event_type,
        "repo": data.get("repository", {}).get("full_name"),
        "action": data.get("action"),
        "alert": data.get("alert"),
    }

    security_events.insert(0, event)
    if len(security_events) > 50:
        security_events.pop()

    log_activity(
        "alert",
        "github-webhook",
        f"Security Alert: {event_type} {data.get('action')} in {event['repo']}",
    )

    return {"status": "received"}

@router.get("/events")
async def api_security_events(user: dict = Depends(require_auth)):
    """Get recent security webhook events."""
    return {"events": security_events}

@router.get("/local-scan")
async def api_local_security_scan(path: str = ".", user: dict = Depends(require_auth)):
    """Run a local security scan on a specific codebase path."""
    try:
        processed_path = path
        if ":" in path and (path.startswith("/") is False):
            drive = path[0].lower()
            remainder = path[2:].replace("\\", "/")
            processed_path = f"/mnt/{drive}{remainder}"

        scan_path = Path(processed_path).expanduser()
        if not scan_path.exists():
            raise HTTPException(
                status_code=404, detail=f"Path not found: {processed_path}"
            )

        results = await asyncio.to_thread(run_local_scan, str(scan_path))
        return {
            "success": True,
            "results": results,
            "path": str(scan_path.absolute()),
        }
    except Exception as e:
        return {"success": False, "error": str(e)}
