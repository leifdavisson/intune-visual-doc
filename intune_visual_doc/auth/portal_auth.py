"""
Playwright session manager and network interceptor for Microsoft Intune Admin Center.
Hooks into browser network calls to extract live Microsoft Graph tokens and capture session state.
"""

import os
import sys
import time
import json
import signal
from typing import Optional, Dict, Any
from playwright.sync_api import sync_playwright

from ..prerequisites import load_config, save_config, scan_installed_browsers

AUTH_DIR = os.path.join(os.getcwd(), ".auth")
PORTAL_AUTH_FILE = os.path.join(AUTH_DIR, "playwright_state.json")
LIVE_TOKEN_FILE = os.path.join(AUTH_DIR, "live_token.json")
INTUNE_PORTAL_URL = "https://intune.microsoft.com"


def get_live_graph_token() -> Optional[str]:
    """Retrieve saved live Graph Bearer token if valid and not expired."""
    if os.path.exists(LIVE_TOKEN_FILE):
        try:
            with open(LIVE_TOKEN_FILE, "r") as f:
                data = json.load(f)
            token = data.get("access_token")
            timestamp = data.get("timestamp", 0)
            # Tokens typically last 60-90 minutes (3600-5400s). Treat as valid for 50 minutes.
            if token and (time.time() - timestamp < 3000):
                return token
        except Exception:
            pass
    return None


def save_live_graph_token(token: str, account_hint: str = "") -> None:
    """Save captured Graph Bearer token to .auth/live_token.json."""
    os.makedirs(AUTH_DIR, exist_ok=True)
    with open(LIVE_TOKEN_FILE, "w") as f:
        json.dump({
            "access_token": token,
            "timestamp": time.time(),
            "account_hint": account_hint,
        }, f, indent=2)


def has_valid_session() -> bool:
    """Check if both saved portal session and Graph token exist."""
    return (
        os.path.exists(PORTAL_AUTH_FILE)
        and os.path.getsize(PORTAL_AUTH_FILE) > 50
        and get_live_graph_token() is not None
    )


def authenticate_via_browser_hook(force_refresh: bool = False) -> Dict[str, Any]:
    """
    Launch selected browser (e.g. Microsoft Edge) via Playwright.
    Hooks into network requests to capture live Graph Bearer token and portal session state.
    Exits immediately once authenticated or if the user closes the browser.
    """
    os.makedirs(AUTH_DIR, exist_ok=True)

    if not force_refresh and has_valid_session():
        token = get_live_graph_token()
        if token:
            return {"token": token, "session_file": PORTAL_AUTH_FILE}

    cfg = load_config()
    browser_id = cfg.get("browser_id", "msedge")
    profile_dir = cfg.get("profile_dir", "Default")

    print("\n" + "=" * 70)
    print("🌐 Launching Browser for Microsoft Intune Authentication")
    print(f"Browser: {browser_id.upper()} | Profile: {profile_dir}")
    print("Hooking into network traffic to extract live Microsoft Graph tokens...")
    print("Complete sign-in or select your account in the browser window.")
    print("The browser will close automatically once the Intune dashboard loads.")
    print("=" * 70 + "\n")

    captured_token = {"token": None, "user": ""}
    should_exit = {"flag": False}

    def signal_handler(sig, frame):
        print("\n[!] User interrupted authentication. Closing browser cleanly...")
        should_exit["flag"] = True

    original_sigint = signal.getsignal(signal.SIGINT)
    signal.signal(signal.SIGINT, signal_handler)

    try:
        with sync_playwright() as p:
            # Determine channel and executable
            channel = "msedge" if browser_id == "msedge" else "chrome"
            user_data_path = os.path.join(AUTH_DIR, "browser_profile")
            os.makedirs(user_data_path, exist_ok=True)

            # Launch persistent context
            context = p.chromium.launch_persistent_context(
                user_data_dir=user_data_path,
                channel=channel,
                headless=False,
                viewport={"width": 1440, "height": 900},
                args=[
                    "--disable-blink-features=AutomationControlled",
                    f"--profile-directory={profile_dir}",
                ],
            )

            page = context.new_page()

            # Attach request interceptor
            def on_request(request):
                url = request.url
                # Look for calls to Graph API or Intune backend
                if "graph.microsoft.com" in url or "manage.microsoft.com" in url:
                    auth_header = request.headers.get("authorization", "")
                    if auth_header.startswith("Bearer "):
                        tok = auth_header[7:].strip()
                        if len(tok) > 100 and not captured_token["token"]:
                            captured_token["token"] = tok
                            save_live_graph_token(tok)
                            print("  ⚡ [Network Hook] Successfully captured live Microsoft Graph Bearer token!")

            page.on("request", on_request)

            # Listen for page/window close by user
            def on_close(p):
                print("  [Browser window closed by user]")
                should_exit["flag"] = True

            page.on("close", on_close)

            # Navigate to Intune
            try:
                page.goto(INTUNE_PORTAL_URL, timeout=45000)
            except Exception as e:
                if not should_exit["flag"]:
                    print(f"  [Navigation note: {e}]")

            # Poll for portal load and token capture
            max_seconds = 300
            start_time = time.time()

            while not should_exit["flag"] and (time.time() - start_time < max_seconds):
                # If we're on intune.microsoft.com and have captured the token, we are done!
                current_url = page.url
                if ("intune.microsoft.com" in current_url) and captured_token["token"]:
                    print("  ✅ Reached Microsoft Intune Admin Center dashboard!")
                    try:
                        page.wait_for_load_state("networkidle", timeout=5000)
                    except Exception:
                        pass
                    break

                # If URL is in Intune but token not yet captured, give it a moment to trigger background Graph calls
                if "intune.microsoft.com" in current_url and "login.microsoftonline.com" not in current_url:
                    time.sleep(2)
                    if captured_token["token"]:
                        break

                time.sleep(1)

            # Save Playwright session storage state
            try:
                context.storage_state(path=PORTAL_AUTH_FILE)
                print("  ✅ Intune Admin Center session cookies and storage state saved.")
            except Exception as e:
                print(f"  [Warning: Could not save storage state: {e}]")

            context.close()

    finally:
        signal.signal(signal.SIGINT, original_sigint)

    if not captured_token["token"]:
        # Check if saved file already had a valid token
        existing = get_live_graph_token()
        if existing:
            return {"token": existing, "session_file": PORTAL_AUTH_FILE}
        raise RuntimeError("Authentication incomplete. No Microsoft Graph token was captured from the browser session.")

    return {
        "token": captured_token["token"],
        "session_file": PORTAL_AUTH_FILE,
    }


def ensure_portal_session(force_refresh: bool = False) -> str:
    """Ensure portal session is authenticated and return path to session file."""
    res = authenticate_via_browser_hook(force_refresh=force_refresh)
    return res["session_file"]
