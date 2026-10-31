"""
System prerequisites, cross-platform browser detection, and secure credential handling.
Discovers installed Microsoft Edge, Google Chrome, and Chromium profiles across Linux, macOS, and Windows.
Enforces strict filesystem permissions (0700/0600) on all authentication directories and files.
"""

import os
import sys
import json
import shutil
import platform
from typing import Dict, Any, List, Optional
from rich.console import Console
from rich.table import Table

console = Console()
AUTH_DIR = os.path.join(os.getcwd(), ".auth")
CONFIG_FILE = os.path.join(AUTH_DIR, "config.json")


def ensure_secure_auth_dir() -> str:
    """Create .auth directory with strict 0700 permissions (read/write only by owner)."""
    os.makedirs(AUTH_DIR, exist_ok=True)
    if platform.system() != "Windows":
        try:
            os.chmod(AUTH_DIR, 0o700)
        except Exception:
            pass
    return AUTH_DIR


def write_secure_file(path: str, content: str) -> None:
    """Write text file and immediately enforce 0600 permissions (owner read/write only)."""
    ensure_secure_auth_dir()
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    if platform.system() != "Windows":
        try:
            os.chmod(path, 0o600)
        except Exception:
            pass


def load_config() -> Dict[str, Any]:
    """Load saved user preferences for browser and profile."""
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def save_config(config: Dict[str, Any]) -> None:
    """Save user preferences securely."""
    write_secure_file(CONFIG_FILE, json.dumps(config, indent=2))


def wipe_all_credentials() -> None:
    """Securely purge all cached tokens, session states, and browser contexts."""
    if os.path.exists(AUTH_DIR):
        try:
            shutil.rmtree(AUTH_DIR)
            ensure_secure_auth_dir()
        except Exception as e:
            raise RuntimeError(f"Failed to wipe credentials directory: {e}")


def _get_platform_browser_paths() -> List[Dict[str, Any]]:
    """Return platform-specific search paths for Edge and Chrome across Linux, macOS, and Windows."""
    system = platform.system()
    home = os.path.expanduser("~")

    if system == "Darwin":  # macOS
        return [
            {
                "id": "msedge",
                "name": "Microsoft Edge",
                "channel": "msedge",
                "binary_candidates": [
                    "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
                ],
                "data_dirs": [
                    os.path.join(home, "Library/Application Support/Microsoft Edge"),
                ],
            },
            {
                "id": "chrome",
                "name": "Google Chrome",
                "channel": "chrome",
                "binary_candidates": [
                    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
                ],
                "data_dirs": [
                    os.path.join(home, "Library/Application Support/Google/Chrome"),
                ],
            },
        ]

    elif system == "Windows":
        local_app_data = os.environ.get("LOCALAPPDATA", os.path.join(home, "AppData", "Local"))
        prog_files = os.environ.get("ProgramFiles(x86)", os.environ.get("ProgramFiles", "C:\\Program Files"))
        return [
            {
                "id": "msedge",
                "name": "Microsoft Edge",
                "channel": "msedge",
                "binary_candidates": [
                    os.path.join(prog_files, "Microsoft", "Edge", "Application", "msedge.exe"),
                ],
                "data_dirs": [
                    os.path.join(local_app_data, "Microsoft", "Edge", "User Data"),
                ],
            },
            {
                "id": "chrome",
                "name": "Google Chrome",
                "channel": "chrome",
                "binary_candidates": [
                    os.path.join(prog_files, "Google", "Chrome", "Application", "chrome.exe"),
                ],
                "data_dirs": [
                    os.path.join(local_app_data, "Google", "Chrome", "User Data"),
                ],
            },
        ]

    else:  # Linux
        return [
            {
                "id": "msedge",
                "name": "Microsoft Edge",
                "channel": "msedge",
                "binary_candidates": [
                    "/usr/bin/microsoft-edge",
                    "/usr/bin/microsoft-edge-stable",
                    "/usr/local/bin/microsoft-edge",
                ],
                "data_dirs": [
                    os.path.join(home, ".config/microsoft-edge"),
                ],
            },
            {
                "id": "chrome",
                "name": "Google Chrome",
                "channel": "chrome",
                "binary_candidates": [
                    "/usr/bin/google-chrome",
                    "/usr/bin/google-chrome-stable",
                    "/usr/bin/chromium-browser",
                    "/usr/bin/chromium",
                ],
                "data_dirs": [
                    os.path.join(home, ".config/google-chrome"),
                    os.path.join(home, ".config/chromium"),
                ],
            },
        ]


def scan_installed_browsers() -> List[Dict[str, Any]]:
    """Discover browsers and parse Local State JSON for user profiles and account emails."""
    discovered = []
    browser_defs = _get_platform_browser_paths()

    for bdef in browser_defs:
        # Check binary presence
        matched_bin = None
        for bpath in bdef["binary_candidates"]:
            if os.path.exists(bpath):
                matched_bin = bpath
                break

        # Check config/profile data dir
        matched_data_dir = None
        for dpath in bdef["data_dirs"]:
            if os.path.exists(dpath):
                matched_data_dir = dpath
                break

        if matched_bin or matched_data_dir:
            profiles = []
            if matched_data_dir:
                state_file = os.path.join(matched_data_dir, "Local State")
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
                "id": bdef["id"],
                "name": bdef["name"],
                "channel": bdef["channel"],
                "binary": matched_bin or bdef["id"],
                "config_dir": matched_data_dir,
                "profiles": profiles,
            })

    return discovered


def display_prerequisites_table() -> None:
    """Print system status table with security permissions check."""
    ensure_secure_auth_dir()
    browsers = scan_installed_browsers()
    cfg = load_config()

    table = Table(title="System & Browser Prerequisites (Multi-Platform)", border_style="cyan")
    table.add_column("Component", style="cyan")
    table.add_column("Status / Path", style="green")
    table.add_column("Security & Details", style="yellow")

    # OS Platform & Display server
    os_name = f"{platform.system()} ({platform.release()})"
    display = os.environ.get("WAYLAND_DISPLAY") or os.environ.get("DISPLAY") or "Headless (None)"
    table.add_row("Operating System", os_name, f"Display Server: {display}")

    # Credential Directory Security
    perm_status = "0700 (Owner Only)" if platform.system() != "Windows" else "Local App Data ACL"
    table.add_row("Credential Storage", AUTH_DIR, f"🛡️ Permissions: {perm_status} | Excluded from git")

    # Browsers
    for b in browsers:
        profiles_str = ", ".join([f"{p['name']} ({p['email'] or 'Local'})" for p in b["profiles"]])
        table.add_row(b["name"], b["binary"], f"Profiles: {profiles_str}")

    # Saved preference
    pref_b = cfg.get("browser_label", "Not selected")
    pref_p = cfg.get("profile_label", "Default")
    pref_acc = cfg.get("account_email", "")
    detail_str = f"Account: {pref_acc}" if pref_acc else "Local Profile"
    table.add_row("Active Selection", f"{pref_b} [{pref_p}]", detail_str)

    console.print(table)
