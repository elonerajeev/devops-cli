"""DevOps CLI Web Dashboard.

A beautiful web interface for monitoring and managing your infrastructure.
"""

from .app import create_app, run_dashboard

__all__ = ["create_app", "run_dashboard"]
