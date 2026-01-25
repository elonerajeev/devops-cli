import re
from pathlib import Path
from typing import List, Dict
from datetime import datetime

# Simple regex patterns for common secrets
SECRET_PATTERNS = {
    "AWS Access Key": r"AKIA[0-9A-Z]{16}",
    "AWS Secret Key": r"(?i)aws_secret_access_key.*\b[0-9a-zA-Z/+=]{40}\b",
    "GitHub Token": r"ghp_[a-zA-Z0-9]{36}",
    "Stripe API Key": r"sk_live_[0-9a-zA-Z]{24}",
    "Google API Key": r"AIza[0-9A-Za-z\-_]{35}",
    "Slack Token": r"xox[baps]-[0-9a-zA-Z]{10,48}",
    "Heroku API Key": r"(?i)heroku.*[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
    "Private Key": r"-----BEGIN [A-Z ]+ PRIVATE KEY-----",
    "Generic Password": r"(?i)password\s*[:=]\s*['\"][^'\"]{8,}['\"]",
}


def scan_file_for_secrets(file_path: Path) -> List[Dict]:
    """Scan a single file for secrets."""
    alerts = []
    try:
        content = file_path.read_text(errors="ignore")
        for line_num, line in enumerate(content.splitlines(), 1):
            for name, pattern in SECRET_PATTERNS.items():
                if re.search(pattern, line):
                    # Mask the secret for display
                    alerts.append(
                        {
                            "type": "secret",
                            "secret_type": name,
                            "summary": f"Potential {name} found in local file",
                            "file": str(file_path),
                            "location": f"{file_path.name}:{line_num}",
                            "line": line_num,
                            "severity": "critical",
                            "created_at": datetime.now().isoformat(),
                            "html_url": f"file://{file_path.absolute()}",
                        }
                    )
    except Exception:
        pass
    return alerts

def run_local_scan(root_dir: str = ".") -> Dict:
    """Run a local security scan on the codebase."""
    results = {
        "secrets": [],
        "vulnerabilities": [],  # Placeholder for Bandit/Safety integration
        "summary": {"critical": 0, "high": 0, "medium": 0, "low": 0},
    }

    ignore_dirs = {".git", "venv", "__pycache__", "node_modules", "dist", "build"}

    root_path = Path(root_dir)
    for path in root_path.rglob("*"):
        # Check if path is file and not in ignored directories
        if path.is_file() and not any(part in ignore_dirs for part in path.parts):
            # Scan for secrets
            file_secrets = scan_file_for_secrets(path)
            results["secrets"].extend(file_secrets)

    results["summary"]["critical"] = len(results["secrets"])
    return results
