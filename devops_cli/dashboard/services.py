"Core services for the dashboard."

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional
from devops_cli.utils.log_formatters import mask_secrets

CONFIG_DIR = Path.home() / ".devops-cli"
DOCUMENTS_DIR = CONFIG_DIR / "documents"

def get_documents_metadata() -> dict:
    """Get metadata for uploaded documents."""
    metadata_file = DOCUMENTS_DIR / "metadata.json"
    if metadata_file.exists():
        try:
            with open(metadata_file) as f:
                return json.load(f)
        except Exception:
            pass
    return {"documents": {}}

async def fetch_cloudwatch_logs(log_group: str, region: str, lines: int = 100, aws_role: str = None) -> dict:
    """Fetch logs from AWS CloudWatch using the correct session."""
    try:
        from devops_cli.utils.aws_helpers import get_aws_session
        from botocore.exceptions import ClientError

        # Use our helper to get a session (handles roles and stored credentials)
        session = get_aws_session(role_name=aws_role, region=region)
        client = session.client("logs")

        # Get log streams
        try:
            streams_response = client.describe_log_streams(
                logGroupName=log_group, orderBy="LastEventTime", descending=True, limit=5
            )
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            if error_code == "ResourceNotFoundException":
                return {"success": False, "error": f"Log group '{log_group}' not found"}
            raise

        logs = []
        streams = streams_response.get("logStreams", [])
        if not streams:
            return {"success": True, "logs": [], "source": "cloudwatch", "message": "No log streams found in this group"}

        for stream in streams:
            try:
                events_response = client.get_log_events(
                    logGroupName=log_group,
                    logStreamName=stream["logStreamName"],
                    limit=max(1, lines // len(streams)),
                    startFromHead=False,
                )

                for event in events_response.get("events", []):
                    message = event.get("message", "")
                    level = "INFO"
                    if "ERROR" in message.upper(): level = "ERROR"
                    elif "WARN" in message.upper(): level = "WARN"

                    logs.append({
                        "timestamp": datetime.fromtimestamp(event["timestamp"] / 1000).isoformat(),
                        "level": level,
                        "message": mask_secrets(message),
                        "source": stream["logStreamName"],
                    })
            except Exception as stream_err:
                print(f"DEBUG: Error fetching from stream {stream['logStreamName']}: {stream_err}")

        logs.sort(key=lambda x: x["timestamp"], reverse=True)
        return {"success": True, "logs": logs[:lines], "source": "cloudwatch"}

    except Exception as e:
        print(f"DEBUG: fetch_cloudwatch_logs failed: {e}")
        return {"success": False, "error": str(e)}

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
        with open(doc_path, "r", errors="ignore") as f:
            text = f.read()

        logs = []
        for line in text.split("\n")[:100]:
            if line.strip():
                level = "INFO"
                if "error" in line.lower():
                    level = "ERROR"
                logs.append(
                    {
                        "timestamp": datetime.now().isoformat(),
                        "level": level,
                        "message": mask_secrets(line),
                        "source": "document",
                    }
                )

        return {
            "success": True,
            "logs": logs,
            "source": "document",
            "document_info": doc_info,
        }
    except Exception as e:
        return {"success": False, "error": str(e)}
