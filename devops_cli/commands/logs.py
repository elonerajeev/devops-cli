"""Log viewing commands (Simplified)."""

import typer
from rich.console import Console
from devops_cli.config.settings import load_config
from devops_cli.utils.output import (
    success, error, warning, info, header
)

app = typer.Typer(help="View logs from supported sources")
console = Console()

@app.command("list")
def list_sources():
    """List supported log sources."""
    header("Supported Log Sources")
    
    info("1. CloudWatch Logs (AWS)")
    info("   - Use: [cyan]devops app logs <app-name>[/cyan]")
    info("   - Use: [cyan]devops aws cloudwatch <group-name>[/cyan]")
    
    info("\n2. Uploaded Documents (Dashboard)")
    info("   - View on the web dashboard under the 'Documents' and 'Logs' sections.")
    
    warning("\nNote: Direct Docker, K8s, and File tailing has been removed.")
    info("Please route your logs to CloudWatch for centralized access.")

if __name__ == "__main__":
    app()