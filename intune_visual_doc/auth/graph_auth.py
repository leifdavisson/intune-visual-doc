"""
Authentication provider for Microsoft Graph API.
Supports interactive browser login, device code fallback, and Service Principal (SPN).
"""

import os
import atexit
from typing import Optional, Dict, Any, List
import msal

# Pre-consented well-known client ID for Microsoft Intune / Graph PowerShell
DEFAULT_CLIENT_ID = "d1ddf0e0-d672-4503-883e-346669d56585"
DEFAULT_AUTHORITY = "https://login.microsoftonline.com/common"
DEFAULT_SCOPES = [
    "https://graph.microsoft.com/DeviceManagementConfiguration.Read.All",
    "https://graph.microsoft.com/DeviceManagementApps.Read.All",
    "https://graph.microsoft.com/DeviceManagementServiceConfig.Read.All",
    "https://graph.microsoft.com/Directory.Read.All",
]

AUTH_DIR = os.path.join(os.getcwd(), ".auth")
CACHE_FILE = os.path.join(AUTH_DIR, "graph_token_cache.bin")


def _get_cache() -> msal.SerializableTokenCache:
    os.makedirs(AUTH_DIR, exist_ok=True)
    cache = msal.SerializableTokenCache()
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r") as f:
                cache.deserialize(f.read())
        except Exception:
            pass

    def _save():
        if cache.has_state_changed:
            with open(CACHE_FILE, "w") as f:
                f.write(cache.serialize())

    atexit.register(_save)
    return cache


def get_graph_token(
    client_id: Optional[str] = None,
    tenant_id: Optional[str] = None,
    client_secret: Optional[str] = None,
    scopes: Optional[List[str]] = None,
    use_device_code: bool = False,
) -> str:
    """
    Acquire access token for Microsoft Graph.
    Checks environment variables first, then falls back to interactive browser login.
    """
    c_id = client_id or os.environ.get("AZURE_CLIENT_ID", DEFAULT_CLIENT_ID)
    t_id = tenant_id or os.environ.get("AZURE_TENANT_ID", "common")
    secret = client_secret or os.environ.get("AZURE_CLIENT_SECRET")
    scope_list = scopes or DEFAULT_SCOPES
    authority = f"https://login.microsoftonline.com/{t_id}"

    # Scenario 1: Unattended Service Principal (Client Secret)
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

    # Scenario 2: Interactive User Login with Local Cache
    cache = _get_cache()
    app = msal.PublicClientApplication(
        client_id=c_id,
        authority=authority,
        token_cache=cache,
    )

    accounts = app.get_accounts()
    if accounts:
        res = app.acquire_token_silent(scope_list, account=accounts[0])
        if res and "access_token" in res:
            return res["access_token"]

    if use_device_code:
        flow = app.initiate_device_flow(scopes=scope_list)
        if "user_code" not in flow:
            raise RuntimeError(f"Failed to initiate device code flow: {flow}")
        print("\n" + "=" * 60)
        print(f"👉 To sign in, open: {flow['verification_uri']}")
        print(f"👉 Enter the code:   {flow['user_code']}")
        print("=" * 60 + "\n")
        res = app.acquire_token_by_device_flow(flow)
    else:
        try:
            # Interactive browser redirect (opens default browser tab)
            res = app.acquire_token_interactive(scopes=scope_list)
        except Exception as e:
            # Fallback to device flow if port-binding fails
            print(f"[Warning] Interactive browser failed ({e}). Falling back to Device Code...")
            flow = app.initiate_device_flow(scopes=scope_list)
            print("\n" + "=" * 60)
            print(f"👉 To sign in, open: {flow['verification_uri']}")
            print(f"👉 Enter the code:   {flow['user_code']}")
            print("=" * 60 + "\n")
            res = app.acquire_token_by_device_flow(flow)

    if "access_token" in res:
        return res["access_token"]

    raise RuntimeError(f"Authentication failed: {res.get('error_description', res)}")
