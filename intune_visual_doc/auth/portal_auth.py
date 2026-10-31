"""
Playwright session manager for Microsoft Intune Admin Center.
Saves authenticated browser session to avoid repeated logins.
"""

import os
import time
from typing import Optional
from playwright.sync_api import sync_playwright

AUTH_DIR = os.path.join(os.getcwd(), ".auth")
PORTAL_AUTH_FILE = os.path.join(AUTH_DIR, "playwright_state.json")
INTUNE_PORTAL_URL = "https://intune.microsoft.com"


def has_valid_session() -> bool:
    """Check if a saved session file exists and has non-zero size."""
    return os.path.exists(PORTAL_AUTH_FILE) and os.path.getsize(PORTAL_AUTH_FILE) > 50


def ensure_portal_session(force_refresh: bool = False) -> str:
    """
    Ensure an authenticated session exists for Playwright.
    If no session exists, opens headed Chromium for the admin to complete login and MFA.
    """
    os.makedirs(AUTH_DIR, exist_ok=True)

    if not force_refresh and has_valid_session():
        return PORTAL_AUTH_FILE

    print("\n" + "=" * 65)
    print("🌐 Microsoft Intune Portal Login Required for Screenshots")
    print("Launching Chromium browser window...")
    print("Please complete sign-in and any Multi-Factor Authentication (MFA).")
    print("The browser will close automatically once the Intune dashboard loads.")
    print("=" * 65 + "\n")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(
            viewport={"width": 1440, "height": 900},
            user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
        )
        page = context.new_page()
        page.goto(INTUNE_PORTAL_URL)

        # Wait for redirect to Intune admin center after login
        max_wait_seconds = 300
        start = time.time()
        logged_in = False

        while time.time() - start < max_wait_seconds:
            curr_url = page.url
            if "intune.microsoft.com" in curr_url and "login.microsoftonline.com" not in curr_url:
                # Wait for main shell header to render
                try:
                    page.wait_for_load_state("networkidle", timeout=8000)
                except Exception:
                    pass
                logged_in = True
                break
            time.sleep(1)

        if not logged_in:
            browser.close()
            raise TimeoutError("Login timed out before reaching Intune Admin Center.")

        context.storage_state(path=PORTAL_AUTH_FILE)
        browser.close()
        print("✅ Intune Admin Center session saved successfully to .auth/playwright_state.json\n")

    return PORTAL_AUTH_FILE
