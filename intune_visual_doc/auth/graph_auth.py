"""
Authentication provider for Microsoft Graph API.
Integrates live browser network hooking, Device Code fallback, and Service Principal (SPN).
"""

import os
from typing import Optional, Dict, Any, List
import msal

from .portal_auth import get_live_graph_token, authenticate_via_browser_hook
from ..prerequisites import load_config

DEFAULT_CLIENT_ID = "d1ddf0e0-d672-4503-883e-346669d56585"
DEFAULT_SCOPES = [
    "https://graph.microsoft.com/DeviceManagementConfiguration.Read.All",
    "https://graph.microsoft.com/DeviceManagementApps.Read.All",
    "https://graph.microsoft.com/DeviceManagementServiceConfig.Read.All",
    "https://graph.microsoft.com/Directory.Read.All",
]


def get_graph_token(
    client_id: Optional[str] = None,
    tenant_id: Optional[str] = None,
    client_secret: Optional[str] = None,
    scopes: Optional[List[str]] = None,
    use_device_code: bool = False,
    force_refresh: bool = False,
) -> str:
    """
    Acquire access token for Microsoft Graph.
    Priority:
    1. Unattended Service Principal if AZURE_CLIENT_SECRET is provided.
    2. Cached live token from previous browser session (if still valid).
    3. Browser network hook (launches Edge/Chrome and intercepts live Graph Bearer token).
    4. Device Code Flow fallback.
    """
    cfg = load_config()
    c_id = (
        client_id
        or os.environ.get("AZURE_CLIENT_ID")
        or os.environ.get("INTUNE_CLIENT_ID")
        or cfg.get("azure_client_id")
        or DEFAULT_CLIENT_ID
    )
    t_id = (
        tenant_id
        or os.environ.get("AZURE_TENANT_ID")
        or os.environ.get("INTUNE_TENANT_ID")
        or cfg.get("azure_tenant_id")
        or "common"
    )
    secret = (
        client_secret
        or os.environ.get("AZURE_CLIENT_SECRET")
        or os.environ.get("INTUNE_CLIENT_SECRET")
        or cfg.get("azure_client_secret")
    )
    scope_list = scopes or DEFAULT_SCOPES
    authority = f"https://login.microsoftonline.com/{t_id}"

    # 1. Unattended Service Principal
    if secret:
        app = msal.ConfidentialClientApplication(
            client_id=c_id,
            client_credential=secret,
            authority=authority,
        )
        res = app.acquire_token_for_client(scopes=["https://graph.microsoft.com/.default"])
        if "access_token" in res:
            return res["access_token"]
        raise RuntimeError(f"Service principal authentication failed: {res.get('error_description')}")

    # 2. Check cached live token
    if not force_refresh:
        cached_token = get_live_graph_token()
        if cached_token:
            return cached_token

    # 3. Explicit Device Code Flow if requested
    if use_device_code:
        app = msal.PublicClientApplication(
            client_id=c_id,
            authority=authority,
        )
        flow = app.initiate_device_flow(scopes=scope_list)
        if "user_code" not in flow:
            raise RuntimeError(f"Failed to initiate device code flow: {flow}")
        print("\n" + "=" * 60)
        print(f"👉 To sign in, open: {flow['verification_uri']}")
        print(f"👉 Enter the code:   {flow['user_code']}")
        print("=" * 60 + "\n")
        res = app.acquire_token_by_device_flow(flow)
        if "access_token" in res:
            return res["access_token"]
        raise RuntimeError(f"Device code login failed: {res.get('error_description')}")

    # 4. Primary Interactive Login: Browser Network Hook via Playwright
    # This completely eliminates localhost loopback redirect issues and the chromiumapp.org broker hang!
    try:
        auth_data = authenticate_via_browser_hook(force_refresh=force_refresh)
        if auth_data and auth_data.get("token"):
            return auth_data["token"]
    except Exception as e:
        print(f"[Warning] Browser hook login failed ({e}). Falling back to Device Code...")
        app = msal.PublicClientApplication(
            client_id=c_id,
            authority=authority,
        )
        flow = app.initiate_device_flow(scopes=scope_list)
        print("\n" + "=" * 60)
        print(f"👉 To sign in, open: {flow['verification_uri']}")
        print(f"👉 Enter the code:   {flow['user_code']}")
        print("=" * 60 + "\n")
        res = app.acquire_token_by_device_flow(flow)
        if "access_token" in res:
            return res["access_token"]

    raise RuntimeError("Authentication failed. Please verify credentials or run 'intunedoc login'.")
