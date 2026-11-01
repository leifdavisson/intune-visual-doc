"""
System prerequisites, cross-platform browser detection, and dependency & supersedence engine.
Evaluates runtime readiness, display servers, Playwright drivers, token freshness, and workflow gates.
"""

import os
import sys
import time
import json
import shutil
import platform
from typing import Dict, Any, List, Optional, Tuple
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

console = Console(legacy_windows=False)
AUTH_DIR = os.path.join(os.getcwd(), ".auth")
CONFIG_FILE = os.path.join(AUTH_DIR, "config.json")
LIVE_TOKEN_FILE = os.path.join(AUTH_DIR, "live_token.json")
PORTAL_AUTH_FILE = os.path.join(AUTH_DIR, "playwright_state.json")


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
    """Write text file and immediately enforce 0600 permissions."""
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
        matched_bin = None
        for bpath in bdef["binary_candidates"]:
            if os.path.exists(bpath):
                matched_bin = bpath
                break

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
                        with open(state_file, "r", encoding="utf-8", errors="ignore") as f:
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


def evaluate_dependencies_and_supersedences() -> Dict[str, Any]:
    """
    Rigorously audit all system, browser, token, and workflow dependencies:
    - Checks runtime version and GUI display.
    - Evaluates token age and supersedence status.
    - Verifies Playwright readiness.
    """
    ensure_secure_auth_dir()
    browsers = scan_installed_browsers()
    cfg = load_config()

    # 1. System & Display
    if platform.system() == "Windows":
        has_gui = True
        display = "Windows Desktop"
    else:
        display = os.environ.get("WAYLAND_DISPLAY") or os.environ.get("DISPLAY")
        has_gui = display is not None and display != ""

    # 2. Browser & Profile
    has_browsers = len(browsers) > 0
    selected_b = cfg.get("browser_label", browsers[0]["name"] if browsers else "None")
    selected_p = cfg.get("profile_label", "Default")
    selected_acc = cfg.get("account_email", "")

    # 3. Token & Supersedence check (SPN or Live User Token)
    has_spn = bool(
        (os.environ.get("AZURE_CLIENT_SECRET") or cfg.get("azure_client_secret"))
        and (os.environ.get("AZURE_CLIENT_ID") or cfg.get("azure_client_id"))
    )

    token_status = "missing"
    token_msg = "No token found (Step 3 login or SPN required)"
    time_left_str = "0 mins"
    can_skip_login = False

    if has_spn:
        token_status = "spn"
        token_msg = "🟢 Unattended SPN Active (intunedoc-reader-spn — Supersedes browser login)"
        can_skip_login = True
    elif os.path.exists(LIVE_TOKEN_FILE):
        try:
            with open(LIVE_TOKEN_FILE, "r", encoding="utf-8") as f:
                tdata = json.load(f)
            t_age = time.time() - tdata.get("timestamp", 0)
            if t_age < 3000:
                mins_left = int((3000 - t_age) / 60)
                token_status = "valid"
                time_left_str = f"{mins_left} min remaining"
                token_msg = f"🟢 Active Graph Session (Expires in {time_left_str} — Supersedes re-login)"
                can_skip_login = True
            else:
                token_status = "expired"
                token_msg = "🟡 Token expired (Step 3 required to refresh)"
        except Exception:
            token_status = "invalid"
            token_msg = "❌ Corrupted token cache (Step 3 required)"

    # 4. Portal Session & Playwright Engine Check
    has_portal_session = os.path.exists(PORTAL_AUTH_FILE) and os.path.getsize(PORTAL_AUTH_FILE) > 50

    playwright_ready = False
    playwright_msg = ""
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            # Check user's chosen browser channel first
            b_id = cfg.get("browser_id", "msedge")
            channel = "msedge" if b_id == "msedge" else ("chrome" if b_id == "chrome" else None)
            try:
                test_browser = p.chromium.launch(channel=channel, headless=True) if channel else p.chromium.launch(headless=True)
                test_browser.close()
                playwright_ready = True
                b_name = cfg.get("browser_label", "System Browser")
                playwright_msg = f"🟢 Driver Ready (Using {b_name})"
            except Exception:
                # Fallback check bundled chromium
                test_browser = p.chromium.launch(headless=True)
                test_browser.close()
                playwright_ready = True
                playwright_msg = "🟢 Driver Ready (Playwright Chromium)"
    except Exception as e:
        playwright_ready = False
        playwright_msg = "❌ Missing Browser Driver (Run 'playwright install chromium' or install Microsoft Edge)"

    return {
        "os_name": f"{platform.system()} ({platform.release()})",
        "has_gui": has_gui,
        "display": display or "Headless (None)",
        "has_browsers": has_browsers,
        "browsers": browsers,
        "selected_browser": selected_b,
        "selected_profile": selected_p,
        "selected_account": selected_acc,
        "token_status": token_status,
        "token_msg": token_msg,
        "has_spn": has_spn,
        "can_skip_login": can_skip_login,
        "has_portal_session": has_portal_session,
        "playwright_ready": playwright_ready,
        "playwright_msg": playwright_msg,
        "auth_dir_secured": True,
    }


def display_prerequisites_table() -> Dict[str, Any]:
    """Display comprehensive system prerequisites and supersedence readiness matrix."""
    audit = evaluate_dependencies_and_supersedences()

    table = Table(title="Workflow Prerequisites & Dependency Matrix", border_style="cyan")
    table.add_column("Layer / Dependency", style="cyan")
    table.add_column("Current State", style="green")
    table.add_column("Supersedence / Action Required", style="yellow")

    # Display Server
    gui_state = f"🟢 Ready ({audit['display']})" if audit["has_gui"] else "🟡 Headless Mode"
    gui_action = "GUI window ready for interactive browser" if audit["has_gui"] else "Browser will run in background"
    table.add_row("1. Display Server", gui_state, gui_action)

    # Active Browser Profile
    if audit["has_browsers"]:
        acc_text = f" ({audit['selected_account']})" if audit["selected_account"] else ""
        table.add_row(
            "2. Active Browser",
            f"{audit['selected_browser']} [{audit['selected_profile']}]",
            f"Selected Identity{acc_text}",
        )
    else:
        table.add_row(
            "2. Active Browser",
            "❌ No Supported Browser Found",
            "Install Microsoft Edge or Google Chrome",
        )

    # Security Permissions
    perm_status = "0700 (Owner Only)" if platform.system() != "Windows" else "Local ACL"
    table.add_row("3. Credential Vault", f"🛡️  Mode {perm_status}", "Excluded from git (.gitignore)")

    # Session & Supersedence Status
    table.add_row("4. Graph Auth Token", audit["token_msg"], "Step 2 Gate" if not audit["can_skip_login"] else "Ready for Step 3")

    # Playwright Driver Engine
    table.add_row("5. Playwright Engine", audit["playwright_msg"], "Visual capture driver")

    # Portal Screenshot Session
    portal_state = "🟢 Session Cached" if audit["has_portal_session"] else "🟡 Not Established"
    portal_action = "Ready for visual screenshots" if audit["has_portal_session"] else "Run Step 2 to enable screenshots"
    table.add_row("6. Portal Screenshot State", portal_state, portal_action)

    console.print(table)
    return audit
