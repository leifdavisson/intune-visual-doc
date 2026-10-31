"""
System prerequisites and browser profile detection module.
Discovers installed Chromium/Edge/Chrome browsers and user profiles.
"""

import os
import json
from typing import Dict, Any, List, Optional
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

console = Console()
AUTH_DIR = os.path.join(os.getcwd(), ".auth")
CONFIG_FILE = os.path.join(AUTH_DIR, "config.json")


def load_config() -> Dict[str, Any]:
    """Load saved user preferences for browser and profile."""
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def save_config(config: Dict[str, Any]) -> None:
    """Save user preferences for browser and profile."""
    os.makedirs(AUTH_DIR, exist_ok=True)
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2)


def scan_installed_browsers() -> List[Dict[str, Any]]:
    """Scan the system for Microsoft Edge, Google Chrome, and Chromium installations and profiles."""
    discovered = []

    # 1. Microsoft Edge
    edge_dir = os.path.expanduser("~/.config/microsoft-edge")
    edge_bin = "/usr/bin/microsoft-edge" if os.path.exists("/usr/bin/microsoft-edge") else None
    if not edge_bin and os.path.exists("/usr/bin/microsoft-edge-stable"):
        edge_bin = "/usr/bin/microsoft-edge-stable"

    if edge_bin or os.path.exists(edge_dir):
        profiles = []
        state_file = os.path.join(edge_dir, "Local State")
        if os.path.exists(state_file):
            try:
                with open(state_file, "r", errors="ignore") as f:
                    state_data = json.load(f)
                info_cache = state_data.get("profile", {}).get("info_cache", {})
                for p_dir, p_info in info_cache.items():
                    profiles.append({
                        "directory": p_dir,
                        "name": p_info.get("name", p_dir),
                        "email": p_info.get("user_name", ""),
                    })
            except Exception:
                pass

        if not profiles:
            profiles.append({"directory": "Default", "name": "Default Profile", "email": ""})

        discovered.append({
            "id": "msedge",
            "name": "Microsoft Edge",
            "channel": "msedge",
            "binary": edge_bin or "microsoft-edge",
            "config_dir": edge_dir,
            "profiles": profiles,
        })

    # 2. Google Chrome
    chrome_dir = os.path.expanduser("~/.config/google-chrome")
    chrome_bin = "/usr/bin/google-chrome" if os.path.exists("/usr/bin/google-chrome") else None
    if not chrome_bin and os.path.exists("/usr/bin/google-chrome-stable"):
        chrome_bin = "/usr/bin/google-chrome-stable"

    if chrome_bin or os.path.exists(chrome_dir):
        profiles = []
        state_file = os.path.join(chrome_dir, "Local State")
        if os.path.exists(state_file):
            try:
                with open(state_file, "r", errors="ignore") as f:
                    state_data = json.load(f)
                info_cache = state_data.get("profile", {}).get("info_cache", {})
                for p_dir, p_info in info_cache.items():
                    profiles.append({
                        "directory": p_dir,
                        "name": p_info.get("name", p_dir),
                        "email": p_info.get("user_name", ""),
                    })
            except Exception:
                pass

        if not profiles:
            profiles.append({"directory": "Default", "name": "Default Profile", "email": ""})

        discovered.append({
            "id": "chrome",
            "name": "Google Chrome",
            "channel": "chrome",
            "binary": chrome_bin or "google-chrome",
            "config_dir": chrome_dir,
            "profiles": profiles,
        })

    return discovered


def display_prerequisites_table() -> None:
    """Print a clean Rich status table showing detected browsers, display, and auth files."""
    browsers = scan_installed_browsers()
    cfg = load_config()

    table = Table(title="System & Browser Prerequisites", border_style="cyan")
    table.add_column("Component", style="cyan")
    table.add_column("Status / Path", style="green")
    table.add_column("Details", style="yellow")

    # Display server
    display = os.environ.get("WAYLAND_DISPLAY") or os.environ.get("DISPLAY") or "Headless (None)"
    table.add_row("Display Server", display, "🟢 GUI Window Available" if display != "Headless (None)" else "🟡 Headless Mode")

    # Browsers
    for b in browsers:
        profiles_str = ", ".join([f"{p['name']} ({p['email'] or 'Local'})" for p in b["profiles"]])
        table.add_row(b["name"], b["binary"], f"Profiles: {profiles_str}")

    # Saved preference
    pref_b = cfg.get("browser_id", "Not configured (will prompt)")
    pref_p = cfg.get("profile_dir", "Not configured")
    table.add_row("Active Selection", f"{pref_b} [{pref_p}]", "Saved in .auth/config.json")

    console.print(table)
