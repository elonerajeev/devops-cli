"""Modular dashboard entry point.

This file now serves as a thin wrapper around the modular dashboard implementation
to maintain backward compatibility with existing imports.
"""

from .main import app, create_app
from .services import fetch_cloudwatch_logs, get_document_logs

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=3000)