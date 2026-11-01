"""
Playwright session manager and network interceptor for Microsoft Intune Admin Center.
Hooks into browser network calls and local session storage to extract live Microsoft Graph tokens.
Provides a live feedback loop and automatically closes the browser upon successful login.
Enforces strict filesystem permissions on all credential artifacts.
"""

import os
import sys
import time
import json
import base64
import signal
import select
from typing import Optional, Dict, Any, List, Tuple
from rich.console import Console
from rich.panel import Panel
from playwright.sync_api import sync_playwright

from ..prerequisites import (
    load_config,
    save_config,
    scan_installed_browsers,
    ensure_secure_auth_dir,
    write_secure_file,
)

console = Console()
AUTH_DIR = os.path.join(os.getcwd(), ".auth")
PORTAL_AUTH_FILE = os.path.join(AUTH_DIR, "playwright_state.json")
LIVE_TOKEN_FILE = os.path.join(AUTH_DIR, "live_token.json")
INTUNE_PORTAL_URL = "https://intune.microsoft.com"


def parse_jwt_claims(jwt_str: str) -> Dict[str, Any]:
    """Parse JWT claims payload without third-party dependencies."""
    try:
        parts = jwt_str.split(".")
        if len(parts) >= 2:
            payload_b64 = parts[1]
            rem = len(payload_b64) % 4
            if rem > 0:
                payload_b64 += "=" * (4 - rem)
            return json.loads(base64.urlsafe_b64decode(payload_b64).decode("utf-8"))
    except Exception:
        pass
    return {}


def is_graph_token(jwt_token: str) -> Tuple[bool, str]:
    """Check if JWT token audience is Microsoft Graph and extract user identity."""
    claims = parse_jwt_claims(jwt_token)
    aud = str(claims.get("aud", ""))
    upn = claims.get("upn") or claims.get("unique_name") or ""
    # Microsoft Graph App ID is 00000003-0000-0000-c000-000000000000 or https://graph.microsoft.com
    if "graph.microsoft.com" in aud or "00000003-0000-0000-c000-000000000000" in aud:
        return True, upn
    return False, upn


def is_intune_token(jwt_token: str) -> Tuple[bool, str]:
    """Check if JWT token audience is Microsoft Graph and contains DeviceManagement permissions."""
    claims = parse_jwt_claims(jwt_token)
    aud = str(claims.get("aud", ""))
    upn = claims.get("upn") or claims.get("unique_name") or ""
    scp = str(claims.get("scp", ""))
    roles = claims.get("roles", [])

    is_graph = "graph.microsoft.com" in aud or "00000003-0000-0000-c000-000000000000" in aud
    if not is_graph:
        return False, upn

    has_intune_scope = "DeviceManagement" in scp or any("DeviceManagement" in r for r in roles)
    if has_intune_scope:
        return True, upn

    return False, upn


def extract_tokens_from_page(page) -> List[str]:
    """Extract cached MSAL tokens from browser sessionStorage and localStorage."""
    try:
        tokens = page.evaluate("""() => {
            const list = [];
            for (const store of [window.sessionStorage, window.localStorage]) {
                if (!store) continue;
                for (let i = 0; i < store.length; i++) {
                    try {
                        const k = store.key(i);
                        const v = store.getItem(k);
                        if (!v) continue;
                        if (v.includes("eyJ")) {
                            try {
                                const obj = JSON.parse(v);
                                if (obj.secret && typeof obj.secret === 'string') list.push(obj.secret);
                                if (obj.accessToken && typeof obj.accessToken === 'string') list.push(obj.accessToken);
                                if (obj.access_token && typeof obj.access_token === 'string') list.push(obj.access_token);
                            } catch (e) {
                                if (v.startsWith("eyJ")) list.push(v);
                            }
                        }
                    } catch (e) {}
                }
            }
            return list;
        }""")
        return [t for t in tokens if isinstance(t, str) and len(t) > 100]
    except Exception:
        return []


def is_token_expired(jwt_token: str) -> bool:
    """Check if JWT token is expired based on exp claim with 60s buffer."""
    claims = parse_jwt_claims(jwt_token)
    exp = claims.get("exp")
    if exp is not None:
        try:
            return time.time() >= (float(exp) - 60)
        except Exception:
            pass
    return False


def get_live_graph_token(require_intune: bool = True) -> Optional[str]:
    """Retrieve saved live Graph Bearer token if valid, not expired, and has Intune scopes."""
    if os.path.exists(LIVE_TOKEN_FILE):
        try:
            with open(LIVE_TOKEN_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            token = data.get("access_token")
            timestamp = data.get("timestamp", 0)
            if token:
                # Check expiration via JWT exp claim first, fallback to timestamp
                if is_token_expired(token):
                    return None
                if not parse_jwt_claims(token).get("exp") and (time.time() - timestamp >= 3600):
                    return None

                if require_intune:
                    valid_intune, _ = is_intune_token(token)
                    if valid_intune:
                        return token
                else:
                    valid_graph, _ = is_graph_token(token)
                    if valid_graph:
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
    Hooks into network requests and session storage to capture live Graph Bearer token.
    Provides a real-time terminal feedback loop and automatically closes the browser upon success.
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

    console.print(Panel(
        f"[bold cyan]🌐 Microsoft Intune Interactive Authentication[/bold cyan]\n\n"
        f"Browser: [bold]{b_id.upper()}[/bold] | Profile: [bold]{p_label}[/bold] ({acc or 'Local'})\n\n"
        f"[bold yellow]📌 Live Breadcrumbs & Feedback Loop:[/bold yellow]\n"
        f" 1. [bold]Sign In:[/bold] Enter password and approve MFA if prompted.\n"
        f" 2. [bold]Target Blade:[/bold] Loading Intune Compliance blade directly.\n"
        f" 3. [bold]Automatic Capture:[/bold] When the policy blade loads, this tool intercepts\n"
        f"    the Intune DeviceManagement token and [bold green]AUTOMATICALLY CLOSES[/bold green] the browser!\n\n"
        f"[bold green]👉 Breadcrumb:[/bold green] If the blade is visible and the browser does not close,\n"
        f"click 'Devices' on the left menu or press [bold cyan][ENTER][/bold cyan] in this terminal.",
        title="Interactive Authentication Wizard",
        border_style="cyan",
    ))

    captured_token = {"token": None, "user": "", "seen_shell": False}
    user_closed_window = {"flag": False}

    def signal_handler(sig, frame):
        console.print("\n[yellow]⚠️  Ctrl+C detected. Closing browser session cleanly...[/yellow]")
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
                console.print(f"[dim]Note on direct persistent profile launch: {e}[/dim]")
                browser = p.chromium.launch(channel=channel, headless=False)
                context = browser.new_context(viewport={"width": 1440, "height": 900})

            # Clean up extraneous blank tabs on startup
            if len(context.pages) > 1:
                for p_extra in list(context.pages[1:]):
                    if p_extra.url in ("", "about:blank"):
                        try:
                            p_extra.close()
                        except Exception:
                            pass
            page = context.pages[0] if context.pages else context.new_page()

            # Attach context-wide request interceptor across all tabs and iframes
            def on_request(request):
                auth_val = ""
                try:
                    for k, v in request.headers.items():
                        if k.lower() == "authorization":
                            auth_val = v
                            break
                except Exception:
                    pass

                if not auth_val:
                    try:
                        for k, v in request.all_headers().items():
                            if k.lower() == "authorization":
                                auth_val = v
                                break
                    except Exception:
                        pass

                if auth_val.startswith("Bearer "):
                    tok = auth_val[7:].strip()
                    if len(tok) > 100:
                        is_intune, user_upn = is_intune_token(tok)
                        if is_intune:
                            if not captured_token["token"]:
                                captured_token["token"] = tok
                                captured_token["user"] = user_upn or acc
                                save_live_graph_token(tok, account_hint=captured_token["user"])
                                console.print(
                                    f"\n[bold green]⚡ [Network Hook] Successfully captured live Intune DeviceManagement Bearer token"
                                    f"{' for ' + captured_token['user'] if captured_token['user'] else ''}![/bold green]"
                                )
                        else:
                            is_graph, _ = is_graph_token(tok)
                            if is_graph and not captured_token["seen_shell"]:
                                captured_token["seen_shell"] = True
                                console.print(
                                    "\n[dim]ℹ️  Portal shell token detected. Waiting for Intune DeviceManagement token...[/dim]"
                                )

            context.on("request", on_request)

            def on_close(p):
                user_closed_window["flag"] = True

            page.on("close", on_close)

            # Navigate directly to Intune Compliance blade
            intune_compliance_url = "https://intune.microsoft.com/#view/Microsoft_Intune_DeviceSettings/DevicesMenu/~/compliance"
            console.print("[cyan]⏳ Launching browser and navigating to Intune Compliance blade...[/cyan]")
            try:
                page.goto(intune_compliance_url, timeout=45000)
            except Exception:
                pass

            # Loop while user interacts with browser, with continuous feedback
            max_seconds = 300
            start_time = time.time()
            last_status_time = 0.0

            while not user_closed_window["flag"] and (time.time() - start_time < max_seconds):
                elapsed = int(time.time() - start_time)
                mins, secs = divmod(elapsed, 60)
                time_str = f"[{mins}:{secs:02d}]"

                if page.is_closed():
                    user_closed_window["flag"] = True
                    break

                # Non-blocking check for Enter key in terminal
                user_signaled_done = False
                try:
                    if sys.platform == "win32":
                        import msvcrt
                        if msvcrt.kbhit():
                            ch = msvcrt.getch()
                            if ch in (b"\r", b"\n"):
                                user_signaled_done = True
                                console.print(f"\n[cyan]{time_str} ⌨️  User signaled sign-in completed. Scanning session storage...[/cyan]")
                    else:
                        if sys.stdin in select.select([sys.stdin], [], [], 0)[0]:
                            sys.stdin.readline()
                            user_signaled_done = True
                            console.print(f"\n[cyan]{time_str} ⌨️  User signaled sign-in completed. Scanning session storage...[/cyan]")
                except Exception:
                    pass

                current_url = ""
                active_page = page
                try:
                    for p_candidate in reversed(context.pages):
                        u = p_candidate.url or ""
                        if "intune.microsoft.com" in u:
                            current_url = u
                            active_page = p_candidate
                            break
                        if not current_url and u and u != "about:blank":
                            current_url = u
                            active_page = p_candidate
                except Exception:
                    current_url = ""

                # If user landed on #home after login, auto-route to compliance blade to trigger DeviceManagement token
                if "intune.microsoft.com/#home" in current_url and not captured_token["token"]:
                    try:
                        active_page.goto(intune_compliance_url, timeout=15000)
                        current_url = active_page.url or current_url
                    except Exception:
                        pass

                # Scan all pages in context for cached MSAL tokens
                if ("intune.microsoft.com" in current_url or user_signaled_done) and not captured_token["token"]:
                    for p_item in context.pages:
                        try:
                            for pt in extract_tokens_from_page(p_item):
                                is_intune, user_upn = is_intune_token(pt)
                                if is_intune:
                                    captured_token["token"] = pt
                                    captured_token["user"] = user_upn or acc
                                    save_live_graph_token(pt, account_hint=captured_token["user"])
                                    console.print(
                                        f"\n[bold green]{time_str} ⚡ [Session Storage Hook] Captured Intune DeviceManagement token"
                                        f"{' for ' + captured_token['user'] if captured_token['user'] else ''}![/bold green]"
                                    )
                                    break
                        except Exception:
                            pass
                        if captured_token["token"]:
                            break

                # If token captured: secure session state and close browser automatically!
                if captured_token["token"]:
                    console.print(f"[bold green]{time_str} ✅ Authentication verified! Securing session state...[/bold green]")
                    try:
                        context.storage_state(path=PORTAL_AUTH_FILE)
                        if os.name != "nt":
                            try:
                                os.chmod(PORTAL_AUTH_FILE, 0o600)
                            except Exception:
                                pass
                        console.print(f"[dim]{time_str} 💾 Session state secured at .auth/playwright_state.json (0600)[/dim]")
                    except Exception as e:
                        console.print(f"[yellow]{time_str} ⚠️ Could not save storage state: {e}[/yellow]")

                    console.print(f"[bold green]{time_str} 🚪 Sign-in complete! Automatically closing browser window...[/bold green]\n")
                    time.sleep(1.0)
                    break

                # If user signaled done but no Intune token captured yet, guide them
                if user_signaled_done and not captured_token["token"]:
                    console.print(
                        f"[yellow]{time_str} ⚠️  Intune DeviceManagement token not captured yet. "
                        "Click 'Devices' or 'Compliance' in Edge to trigger policy requests...[/yellow]"
                    )
                    try:
                        page.goto(intune_compliance_url, timeout=15000)
                    except Exception:
                        pass

                # Periodic live feedback in the terminal every 2 seconds
                if time.time() - last_status_time >= 2.0:
                    last_status_time = time.time()
                    if "login.microsoftonline.com" in current_url:
                        console.print(f"[dim]{time_str} ⏳ Waiting for credentials / MFA in browser window (login.microsoftonline.com)...[/dim]")
                    elif "kmsi" in current_url:
                        console.print(f"[dim]{time_str} ⏳ On 'Stay signed in?' prompt in browser window...[/dim]")
                    elif "intune.microsoft.com" in current_url:
                        console.print(f"[cyan]{time_str} 🎯 In Intune Admin Center. Click 'Devices' in Edge or press [ENTER] here.[/cyan]")
                    else:
                        domain = current_url.split("/")[2] if "/" in current_url else "portal"
                        console.print(f"[dim]{time_str} 🌐 Browser active on {domain}...[/dim]")

                time.sleep(0.5)

            # Close browser context cleanly
            try:
                context.close()
            except Exception:
                pass

    except Exception as e:
        if not user_closed_window["flag"]:
            console.print(f"[dim]Browser session notice: {e}[/dim]")
    finally:
        signal.signal(signal.SIGINT, original_sigint)

    # Check if token exists in live token file even if closed
    if not captured_token["token"]:
        cached = get_live_graph_token()
        if cached:
            captured_token["token"] = cached

    if captured_token["token"]:
        return {
            "token": captured_token["token"],
            "session_file": PORTAL_AUTH_FILE,
            "status": "success",
            "user": captured_token["user"],
        }

    if user_closed_window["flag"]:
        return {
            "token": None,
            "session_file": None,
            "status": "cancelled",
            "message": "Browser window was closed before sign-in completed. Run Step 2 again or use 'intunedoc setup' for unattended SPN.",
        }

    return {
        "token": None,
        "session_file": None,
        "status": "timeout",
        "message": "Authentication timed out after 5 minutes before sign-in completed.",
    }


def ensure_portal_session(force_refresh: bool = False) -> str:
    """Ensure portal session is authenticated and return path to session file."""
    res = authenticate_via_browser_hook(force_refresh=force_refresh)
    if not res or res.get("status") != "success":
        raise RuntimeError(res.get("message", "Browser login did not complete."))
    return res["session_file"]
