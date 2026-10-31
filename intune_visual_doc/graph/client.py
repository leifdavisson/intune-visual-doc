"""
Resilient Microsoft Graph client with throttling protection and pagination.
"""

import time
import requests
from typing import Dict, Any, List, Optional

GRAPH_V1 = "https://graph.microsoft.com/v1.0"
GRAPH_BETA = "https://graph.microsoft.com/beta"


class GraphClient:
    def __init__(self, token: str):
        self.token = token
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "ConsistencyLevel": "eventual",
        })

    def get(self, endpoint: str, beta: bool = False, params: Optional[Dict[str, Any]] = None, max_retries: int = 5) -> Dict[str, Any]:
        """Send a GET request with automatic rate limit backoff and retries."""
        base = GRAPH_BETA if beta else GRAPH_V1
        url = endpoint if endpoint.startswith("http") else f"{base}{endpoint}"

        retries = 0
        backoff = 1.0

        while retries < max_retries:
            resp = self.session.get(url, params=params)

            if resp.status_code == 200:
                return resp.json()

            # Handle throttling (429) or transient server errors (503, 504)
            if resp.status_code in (429, 503, 504):
                retry_after = resp.headers.get("Retry-After")
                wait_time = float(retry_after) if retry_after else backoff
                time.sleep(wait_time)
                backoff *= 2.0
                retries += 1
                continue

            if resp.status_code == 403:
                err_data = {}
                try:
                    err_data = resp.json()
                except Exception:
                    pass
                err_msg = err_data.get("error", {}).get("message", resp.text)
                raise PermissionError(f"HTTP 403 Forbidden on {url}: {err_msg}")

            resp.raise_for_status()

        raise RuntimeError(f"Maximum retries reached for endpoint: {url}")

    def get_all_pages(self, endpoint: str, beta: bool = False, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Fetch all pages of a paginated Graph collection using @odata.nextLink."""
        items: List[Dict[str, Any]] = []
        data = self.get(endpoint, beta=beta, params=params)
        items.extend(data.get("value", []))

        next_link = data.get("@odata.nextLink")
        while next_link:
            data = self.get(next_link, beta=beta)
            items.extend(data.get("value", []))
            next_link = data.get("@odata.nextLink")

        return items
