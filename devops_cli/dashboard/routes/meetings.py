"""Meeting routes for the dashboard."""

import copy
from fastapi import APIRouter, Depends
from ..main import require_auth
from devops_cli.config.manager import config_manager
from datetime import datetime

router = APIRouter(prefix="/api/meetings", tags=["meetings"])

@router.get("")
async def get_meetings(user: dict = Depends(require_auth)):
    """Get all configured meetings, ranked by time."""
    try:
        # Get raw data and deep copy to avoid modifying cache
        raw_config = config_manager.meetings
        print(f"DEBUG: raw_config type: {type(raw_config)}")
        print(f"DEBUG: raw_config content: {raw_config}")
        
        meetings_data = copy.deepcopy(raw_config.get("meetings", {}))
        print(f"DEBUG: meetings_data: {meetings_data}")
        
        # Convert to list and add IDs
        meetings_list = []
        for m_id, m_data in meetings_data.items():
            if isinstance(m_data, dict):
                m_data["id"] = m_id
                meetings_list.append(m_data)
        
        print(f"DEBUG: meetings_list before sort: {meetings_list}")
        
        # Rank by time
        def parse_time(time_str):
            try:
                if not time_str:
                    return datetime.strptime("23:59", "%H:%M")
                # Handle 12h format if user provides it, though we expect 24h
                if 'AM' in str(time_str).upper() or 'PM' in str(time_str).upper():
                    return datetime.strptime(str(time_str).upper(), "%I:%M %p")
                return datetime.strptime(str(time_str), "%H:%M")
            except Exception as e:
                print(f"DEBUG: Error parsing time '{time_str}': {e}")
                return datetime.strptime("23:59", "%H:%M")

        meetings_list.sort(key=lambda x: parse_time(x.get("time", "00:00")))
        print(f"DEBUG: meetings_list after sort: {meetings_list}")
        
        return {"meetings": meetings_list}
    except Exception as e:
        import traceback
        print(f"DEBUG: Error in get_meetings: {e}")
        print(traceback.format_exc())
        return {"meetings": [], "error": str(e)}
