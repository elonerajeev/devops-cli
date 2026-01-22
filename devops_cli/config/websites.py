from pathlib import Path
from typing import Dict, Any, Optional
import yaml

WEBSITES_FILE = Path.home() / ".devops-cli" / "websites.yaml"

def ensure_websites_file():
    """Ensure websites.yaml exists."""
    WEBSITES_FILE.parent.mkdir(parents=True, exist_ok=True)
    if not WEBSITES_FILE.exists():
        with open(WEBSITES_FILE, 'w') as f:
            yaml.dump({"websites": {}}, f)

def load_websites_config() -> Dict[str, Any]:
    """Load websites configuration."""
    ensure_websites_file()
    try:
        with open(WEBSITES_FILE) as f:
            data = yaml.safe_load(f) or {}
            return data.get("websites", {})
    except Exception:
        return {}

def save_websites_config(websites: Dict[str, Any]):
    """Save websites configuration to file."""
    ensure_websites_file()
    with open(WEBSITES_FILE, 'w') as f:
        yaml.dump({"websites": websites}, f, default_flow_style=False)

def get_website_config(name: str) -> Optional[Dict[str, Any]]:
    """Get specific website configuration."""
    websites = load_websites_config()
    return websites.get(name)

def add_website(name: str, url: str, **extra) -> bool:
    """Add a website to configuration."""
    websites = load_websites_config()
    websites[name] = {
        "url": url,
        **extra
    }
    save_websites_config(websites)
    return True

def remove_website(name: str) -> bool:
    """Remove a website from configuration."""
    websites = load_websites_config()
    if name not in websites:
        return False
    del websites[name]
    save_websites_config(websites)
    return True
