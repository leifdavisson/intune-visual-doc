"""
Playwright screenshot capture engine for Microsoft Intune Admin Center.
Captures Overview dashboards and Properties blades for documented policies.
"""

import os
import time
from typing import Dict, Any, List, Optional
from playwright.sync_api import sync_playwright

from ..auth.portal_auth import ensure_portal_session, has_valid_session


def build_blade_urls(policy: Dict[str, Any]) -> Dict[str, str]:
    """Build deep-link URLs to Intune Admin Center blades."""
    p_id = policy.get("id")
    category = policy.get("category", "")

    base = "https://intune.microsoft.com/#view/Microsoft_Intune_DeviceSettings"
    if category == "compliance":
        overview = f"{base}/CompliancePolicyDetailsBlade/policyId/{p_id}"
        properties = f"{base}/CompliancePolicyMenuBlade/~/properties/policyId/{p_id}"
    elif category == "apps":
        overview = f"{base}/ApplicationDetailsBlade/appId/{p_id}"
        properties = f"{base}/ApplicationMenuBlade/~/properties/appId/{p_id}"
    else:  # configuration
        overview = f"{base}/ConfigurationPolicyDetailsBlade/policyId/{p_id}"
        properties = f"{base}/ConfigurationPolicyMenuBlade/~/properties/policyId/{p_id}"

    return {
        "overview": overview,
        "properties": properties,
    }


class ScreenshotManager:
    def __init__(self, output_dir: str = "docs", headless: bool = True):
        self.output_dir = os.path.abspath(output_dir)
        self.assets_dir = os.path.join(self.output_dir, "assets", "screenshots")
        self.headless = headless
        os.makedirs(self.assets_dir, exist_ok=True)

    def capture_policy_screenshots(
        self,
        policies: List[Dict[str, Any]],
        on_progress=None
    ) -> Dict[str, Dict[str, str]]:
        """
        Capture overview and properties screenshots for a list of policies.
        Returns a mapping of policy_id -> {"overview": "/abs/path", "properties": "/abs/path"}
        """
        results: Dict[str, Dict[str, str]] = {}
        if not policies:
            return results

        # Ensure authentication session is valid
        auth_file = ensure_portal_session()

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=self.headless)
            context = browser.new_context(
                storage_state=auth_file,
                viewport={"width": 1440, "height": 900},
                device_scale_factor=1,
            )
            page = context.new_page()

            for idx, policy in enumerate(policies, start=1):
                p_id = policy.get("id")
                p_slug = policy.get("slug", p_id)
                category = policy.get("category", "configuration")

                if on_progress:
                    on_progress(idx, len(policies), policy.get("name", p_id))

                policy_assets_dir = os.path.join(self.assets_dir, category, p_slug)
                os.makedirs(policy_assets_dir, exist_ok=True)

                urls = build_blade_urls(policy)
                shots: Dict[str, str] = {}

                # 1. Capture Overview
                ov_path = os.path.join(policy_assets_dir, "overview.png")
                try:
                    page.goto(urls["overview"], wait_until="networkidle", timeout=15000)
                    time.sleep(1.5)  # Let portal graphs/charts render
                    page.screenshot(path=ov_path, full_page=False)
                    shots["overview"] = ov_path
                except Exception as e:
                    shots["overview"] = ""

                # 2. Capture Properties Blade
                pr_path = os.path.join(policy_assets_dir, "properties.png")
                try:
                    page.goto(urls["properties"], wait_until="networkidle", timeout=15000)
                    time.sleep(1.5)
                    page.screenshot(path=pr_path, full_page=True)
                    shots["properties"] = pr_path
                except Exception as e:
                    shots["properties"] = ""

                results[p_id] = shots

            browser.close()

        return results
