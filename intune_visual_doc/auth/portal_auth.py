"""
Playwright session manager and network interceptor for Microsoft Intune Admin Center.
Hooks into browser network calls to extract live Microsoft Graph tokens and capture session state.
Enforces strict filesystem permissions on all credential artifacts.
"""

import os
import sys
import time
import json
import signal
from typing import Optional, Dict, Any
from playwright.sync_api import sync_playwright

from ..prerequisites import (
    load_config,
    save_config,
    scan_installed_browsers,
    ensure_secure_auth_dir,
    write_secure_file,
)

AUTH_DIR = os.path.join(os.getcwd(), ".auth")
PORTAL_AUTH_FILE = os.path.join(AUTH_DIR, "playwright_state.json")
LIVE_TOKEN_FILE = os.path.join(AUTH_DIR, "live_token.json")
INTUNE_PORTAL_URL = "https://intune.microsoft.com"


def get_live_graph_token() -> Optional[str]:
    """Retrieve saved live Graph Bearer token if valid and not expired."""
    if os.path.exists(LIVE_TOKEN_FILE):
        try:
            with open(LIVE_TOKEN_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            token = data.get("access_token")
            timestamp = data.get("timestamp", 0)
            if token and (time.time() - timestamp < 3000):
                return token
        except Exception:
            pass
    return None


def save_live_graph_token(token: str, account_hint: str = "") -> None:
    """Save captured Graph Bearer token securely with 0600 permissions."""
    ensure_secure_auth_dir()
    payload = json.dumps({
        "access_token": token,
        "timestamp": time.time(),
        "account_hint": account_hint,
    }, indent=2)
    write_secure_file(LIVE_TOKEN_FILE, payload)


def has_valid_session() -> bool:
    """Check if both saved portal session and Graph token exist."""
    return (
        os.path.exists(PORTAL_AUTH_FILE)
        and os.path.getsize(PORTAL_AUTH_FILE) > 50
        and get_live_graph_token() is not None
    )


def authenticate_via_browser_hook(
    force_refresh: bool = False,
    browser_id: Optional[str] = None,
    profile_dir: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """
    Launch selected browser (e.g. Microsoft Edge) via Playwright.
    Hooks into network requests to capture live Graph Bearer token and portal session state.
    Catches window close and user cancellations without raising unhandled exceptions.
    """
    ensure_secure_auth_dir()

    if not force_refresh and has_valid_session():
        token = get_live_graph_token()
        if token:
            return {"token": token, "session_file": PORTAL_AUTH_FILE, "status": "success"}

    cfg = load_config()
    b_id = browser_id or cfg.get("browser_id", "msedge")
    p_dir = profile_dir or cfg.get("profile_dir", "Default")
    p_label = cfg.get("profile_label", p_dir)
    acc = cfg.get("account_email", "")

    print("\n" + "=" * 70)
    print("🌐 Launching Browser for Microsoft Intune Authentication")
    print(f"👉 Target Browser: {b_id.upper()} | Profile: {p_label} ({acc or 'Local'})")
    print("Hooking into network traffic to extract live Microsoft Graph tokens...")
    print("Complete sign-in or select your account in the browser window.")
    print("If you close the browser window, login will cancel cleanly.")
    print("=" * 70 + "\n")

    captured_token = {"token": None, "user": ""}
    user_closed_window = {"flag": False}

    def signal_handler(sig, frame):
        print("\n[!] Ctrl+C detected. Closing browser session cleanly...")
        user_closed_window["flag"] = True

    original_sigint = signal.getsignal(signal.SIGINT)
    signal.signal(signal.SIGINT, signal_handler)

    try:
        with sync_playwright() as p:
            channel = "msedge" if b_id == "msedge" else "chrome"
            user_data_path = os.path.join(AUTH_DIR, "browser_profile")
            os.makedirs(user_data_path, exist_ok=True)

            try:
                context = p.chromium.launch_persistent_context(
                    user_data_dir=user_data_path,
                    channel=channel,
                    headless=False,
                    viewport={"width": 1440, "height": 900},
                    args=[
                        "--disable-blink-features=AutomationControlled",
                        f"--profile-directory={p_dir}",
                    ],
                )
            except Exception as e:
                print(f"[Warning] Direct persistent profile launch note: {e}")
                browser = p.chromium.launch(channel=channel, headless=False)
                context = browser.new_context(viewport={"width": 1440, "height": 900})

            page = context.new_page()

            # Attach request interceptor
            def on_request(request):
                url = request.url
                if "graph.microsoft.com" in url or "manage.microsoft.com" in url:
                    auth_header = request.headers.get("authorization", "")
                    if auth_header.startswith("Bearer "):
                        tok = auth_header[7:].strip()
                        if len(tok) > 100 and not captured_token["token"]:
                            captured_token["token"] = tok
                            save_live_graph_token(tok)
                            print("  ⚡ [Network Hook] Successfully captured live Microsoft Graph Bearer token!")

            page.on("request", on_request)

            def on_close(p):
                user_closed_window["flag"] = True

            page.on("close", on_close)

            # Navigate to Intune Admin Center
            try:
                page.goto(INTUNE_PORTAL_URL, timeout=45000)
            except Exception:
                pass

            # Loop while user interacts with browser
            max_seconds = 300
            start_time = time.time()

            while not user_closed_window["flag"] and (time.time() - start_time < max_seconds):
                if page.is_closed():
                    user_closed_window["flag"] = True
                    break

                current_url = page.url
                if ("intune.microsoft.com" in current_url) and captured_token["token"]:
                    print("  ✅ Reached Microsoft Intune Admin Center dashboard!")
                    try:
                        page.wait_for_load_state("networkidle", timeout=4000)
                    except Exception:
                        pass
                    break

                if "intune.microsoft.com" in current_url and "login.microsoftonline.com" not in current_url:
                    time.sleep(1.5)
                    if captured_token["token"]:
                        break

                time.sleep(0.5)

            # Save session state securely
            if captured_token["token"]:
                try:
                    context.storage_state(path=PORTAL_AUTH_FILE)
                    if os.name != "nt":
                        try:
                            os.chmod(PORTAL_AUTH_FILE, 0o600)
                        except Exception:
                            pass
                    print("  ✅ Intune Admin Center session cookies and storage state saved.")
                except Exception:
                    pass

            try:
                context.close()
            except Exception:
                pass

    except Exception as e:
        if not user_closed_window["flag"]:
            print(f"  [Browser session closed: {e}]")
    finally:
        signal.signal(signal.SIGINT, original_sigint)

    if captured_token["token"]:
        return {
            "token": captured_token["token"],
            "session_file": PORTAL_AUTH_FILE,
            "status": "success",
        }

    if user_closed_window["flag"]:
        return {
            "token": None,
            "session_file": None,
            "status": "cancelled",
            "message": "Browser window was closed before login completed.",
        }

    return {
        "token": None,
        "session_file": None,
        "status": "timeout",
        "message": "Authentication timed out before completing sign-in.",
    }


def ensure_portal_session(force_refresh: bool = False) -> str:
    """Ensure portal session is authenticated and return path to session file."""
    res = authenticate_via_browser_hook(force_refresh=force_refresh)
    if not res or res.get("status") != "success":
        raise RuntimeError(res.get("message", "Browser login did not complete."))
    return res["session_file"]
