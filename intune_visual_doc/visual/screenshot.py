"""
Playwright screenshot capture engine for Microsoft Intune Admin Center.
Captures Overview dashboards and Properties blades for documented policies.
"""

import os
import shutil
import time
from urllib.parse import quote
from typing import Dict, Any, List, Optional
from playwright.sync_api import sync_playwright, Page

from ..auth.portal_auth import ensure_portal_session
from ..generator.engine import slugify
from ..prerequisites import AUTH_DIR, load_config


def build_blade_urls(policy: Dict[str, Any]) -> Dict[str, str]:
    """Build modern Ibiza / ReactView deep-link URLs to Intune Admin Center blades."""
    p_id = policy.get("id") or ""
    p_name = policy.get("name") or ""
    encoded_name = quote(p_name, safe="")
    category = policy.get("category", "")
    cat_label = policy.get("category_label", "")
    raw = policy.get("raw") or {}
    odata_type = str(raw.get("@odata.type") or "")
    is_assigned = "true" if policy.get("assignments") else "false"

    dev_base = "https://intune.microsoft.com/#view/Microsoft_Intune_DeviceSettings"
    wf_base = "https://intune.microsoft.com/#view/Microsoft_Intune_Workflows"
    app_base = "https://intune.microsoft.com/#view/Microsoft_Intune_Apps"

    if category == "compliance" or "CompliancePolicy" in odata_type:
        overview = (
            f"{dev_base}/CompliancePolicyOverview.ReactView/policyId/{p_id}"
            f"/policyName/{encoded_name}/platform~/8/policyType~/35/policyJourneyState~/1"
        )
        return {"overview": overview, "properties": overview}

    if category == "apps" or cat_label == "Mobile Application":
        return {
            "overview": f"{app_base}/SettingsMenu/~/0/appId/{p_id}",
            "properties": f"{app_base}/SettingsMenu/~/1/appId/{p_id}",
        }

    if category == "scripts" or cat_label == "Device Script":
        return {
            "overview": f"{dev_base}/PowershellScriptMenuBlade/~/overview/policyId/{p_id}",
            "properties": f"{dev_base}/PowershellScriptMenuBlade/~/properties/policyId/{p_id}",
        }

    if category == "enrollment" or cat_label == "Enrollment Configuration":
        url = f"{dev_base}/DevicesMenu/~/enrollment"
        return {"overview": url, "properties": url}

    # Settings Catalog & Unified Endpoint Security Policies (configurationPolicies)
    if (
        raw.get("technologies")
        or category == "endpoint_security"
        or cat_label in ("Settings Catalog", "Endpoint Security")
    ):
        tech = raw.get("technologies") or "mdm"
        t_ref = raw.get("templateReference") or {}
        tmpl_id = t_ref.get("templateId") or ""
        platform = raw.get("platforms") or "windows10"
        url = (
            f"{wf_base}/PolicySummaryBlade/policyId/{p_id}"
            f"/isAssigned~/{is_assigned}/technology/{tech}"
            f"/templateId/{tmpl_id}/platformName/{platform}"
        )
        return {"overview": url, "properties": url}

    # Legacy Device Configuration Templates (deviceConfigurations)
    url = (
        f"{dev_base}/PolicySummaryReportBlade/policyId/{p_id}"
        f"/policyName/{encoded_name}/policyJourneyState~/0"
        f"/policyType~/74/isAssigned~/{is_assigned}"
    )
    return {"overview": url, "properties": url}


class ScreenshotManager:
    def __init__(self, output_dir: str = "docs", headless: bool = True):
        self.output_dir = os.path.abspath(output_dir)
        self.assets_dir = os.path.join(self.output_dir, "assets", "screenshots")
        self.headless = headless
        os.makedirs(self.assets_dir, exist_ok=True)

    @staticmethod
    def _is_login_or_error_page(page: Page) -> bool:
        """Detect if Playwright landed on an Entra login redirect or Ibiza 404 blade."""
        try:
            url = (page.url or "").lower()
            title = (page.title() or "").lower()
            if "login.microsoftonline.com" in url or "/kmsi" in url:
                return True
            if "sign in" in title or title.startswith("error -"):
                return True
        except Exception:
            return True
        return False

    @staticmethod
    def _wait_for_blade_render(page: Page, timeout_sec: float = 5.0) -> None:
        """Wait for Ibiza ReactView iframes and progress spinners to settle."""
        deadline = time.time() + timeout_sec
        while time.time() < deadline:
            try:
                if len(page.frames) > 1:
                    break
            except Exception:
                pass
            time.sleep(0.4)
        time.sleep(2.5)

    @staticmethod
    def _activate_properties_view(page: Page) -> None:
        """Click the 'Properties' tab or scroll 'Configuration settings' into view inside React blades."""
        current_url = page.url or ""

        # 1. If not on unified PolicySummaryBlade, try clicking a 'Properties' tab or blade nav link
        if "PolicySummaryBlade" not in current_url:
            for frame in reversed(page.frames):
                for selector in (
                    '[role="tab"]:has-text("Properties")',
                    'a:has-text("Properties")',
                    'button[role="tab"]:has-text("Properties")',
                    '.fxs-blade-navigation-item:has-text("Properties")',
                ):
                    try:
                        loc = frame.locator(selector).first
                        if loc.count() > 0 and loc.is_visible():
                            loc.click(timeout=3000)
                            time.sleep(2.5)
                            return
                    except Exception:
                        continue

        # 2. On Unified Settings (PolicySummaryBlade), scroll Configuration settings into view
        for frame in reversed(page.frames):
            try:
                loc = frame.locator('text="Configuration settings"').first
                if loc.count() > 0:
                    loc.evaluate("el => el.scrollIntoView({block: 'center', behavior: 'instant'})")
                    time.sleep(1.5)
                    return
            except Exception:
                continue

    @staticmethod
    def _inject_visual_markup(page: Page, policy: Dict[str, Any], view_label: str) -> None:
        """Inject a non-destructive hygiene badge and focus border into the active blade."""
        is_assigned = bool(policy.get("assignments"))
        border_color = "#107c10" if is_assigned else "#d83b01"
        status_text = "ASSIGNED POLICY" if is_assigned else "UNASSIGNED / DORMANT POLICY"
        p_name = (policy.get("name") or "Policy").replace("'", "\\'")
        js = f"""() => {{
            const old = document.getElementById('intunedoc-markup-banner');
            if (old) old.remove();
            const bar = document.createElement('div');
            bar.id = 'intunedoc-markup-banner';
            bar.style.cssText = 'position:fixed;bottom:12px;right:16px;z-index:999999;background:{border_color};color:#fff;padding:6px 14px;border-radius:4px;font-family:Segoe UI,sans-serif;font-size:12px;font-weight:600;box-shadow:0 2px 8px rgba(0,0,0,0.35);';
            bar.innerText = '{status_text} • {view_label.upper()} • {p_name}';
            document.body.appendChild(bar);
        }}"""
        try:
            page.evaluate(js)
        except Exception:
            pass

    @staticmethod
    def _remove_visual_markup(page: Page) -> None:
        """Remove injected markup banner after screenshot capture."""
        try:
            page.evaluate("() => { const el = document.getElementById('intunedoc-markup-banner'); if (el) el.remove(); }")
        except Exception:
            pass

    def capture_policy_screenshots(
        self,
        policies: List[Dict[str, Any]],
        on_progress=None
    ) -> Dict[str, Dict[str, str]]:
        """
        Capture overview and properties screenshots for a list of policies.
        Uses the persistent browser profile (.auth/browser_profile) to preserve Entra SSO cookies.
        Returns a mapping of policy_id -> {"overview": "/abs/path", "properties": "/abs/path"}
        """
        results: Dict[str, Dict[str, str]] = {}
        if not policies:
            return results

        cfg = load_config()
        browser_id = cfg.get("browser_id", "msedge")
        profile_dir = cfg.get("profile_dir", "Default")
        channel = "msedge" if browser_id == "msedge" else ("chrome" if browser_id == "chrome" else None)
        user_data_path = os.path.join(AUTH_DIR, "browser_profile")

        with sync_playwright() as p:
            browser = None
            context = None

            if os.path.isdir(user_data_path):
                try:
                    launch_kwargs: Dict[str, Any] = {
                        "user_data_dir": user_data_path,
                        "headless": self.headless,
                        "viewport": {"width": 1440, "height": 900},
                        "device_scale_factor": 1,
                        "args": [
                            "--disable-blink-features=AutomationControlled",
                            f"--profile-directory={profile_dir}",
                        ],
                    }
                    if channel:
                        launch_kwargs["channel"] = channel
                    context = p.chromium.launch_persistent_context(**launch_kwargs)
                except Exception:
                    context = None

            if context is None:
                auth_file = ensure_portal_session()
                try:
                    browser = p.chromium.launch(channel=channel, headless=self.headless) if channel else p.chromium.launch(headless=self.headless)
                except Exception:
                    browser = p.chromium.launch(headless=self.headless)
                context = browser.new_context(
                    storage_state=auth_file,
                    viewport={"width": 1440, "height": 900},
                    device_scale_factor=1,
                )

            page = context.pages[0] if context.pages else context.new_page()
            shared_url_cache: Dict[str, Dict[str, str]] = {}

            for idx, policy in enumerate(policies, start=1):
                p_id = policy.get("id")
                p_slug = policy.get("slug") or slugify(policy.get("name", p_id))
                category = policy.get("category", "configuration")

                if on_progress:
                    on_progress(idx, len(policies), policy.get("name", p_id))

                policy_assets_dir = os.path.join(self.assets_dir, category, p_slug)
                os.makedirs(policy_assets_dir, exist_ok=True)

                urls = build_blade_urls(policy)
                shots: Dict[str, str] = {"overview": "", "properties": ""}
                ov_path = os.path.join(policy_assets_dir, "overview.png")
                pr_path = os.path.join(policy_assets_dir, "properties.png")

                # Reuse capture when multiple policies share the exact same portal blade URL (e.g., Enrollment)
                cache_key = f"{urls['overview']}|{urls['properties']}"
                if cache_key in shared_url_cache:
                    cached = shared_url_cache[cache_key]
                    if cached.get("overview") and os.path.exists(cached["overview"]):
                        shutil.copy2(cached["overview"], ov_path)
                        shots["overview"] = ov_path
                    if cached.get("properties") and os.path.exists(cached["properties"]):
                        shutil.copy2(cached["properties"], pr_path)
                        shots["properties"] = pr_path
                    results[p_id] = shots
                    continue

                # 1. Capture Overview
                try:
                    page.goto(urls["overview"], timeout=25000)
                    self._wait_for_blade_render(page)
                    if not self._is_login_or_error_page(page):
                        self._inject_visual_markup(page, policy, "Overview")
                        page.screenshot(path=ov_path, full_page=False)
                        self._remove_visual_markup(page)
                        shots["overview"] = ov_path
                except Exception:
                    shots["overview"] = ""

                # 2. Capture Properties Blade
                try:
                    if urls["properties"] != urls["overview"]:
                        page.goto(urls["properties"], timeout=25000)
                        self._wait_for_blade_render(page)
                    else:
                        self._activate_properties_view(page)

                    if not self._is_login_or_error_page(page):
                        self._inject_visual_markup(page, policy, "Properties")
                        page.screenshot(path=pr_path, full_page=True)
                        self._remove_visual_markup(page)
                        shots["properties"] = pr_path
                except Exception:
                    shots["properties"] = ""

                if shots["overview"] or shots["properties"]:
                    shared_url_cache[cache_key] = shots
                results[p_id] = shots

            try:
                context.close()
            except Exception:
                pass
            if browser:
                try:
                    browser.close()
                except Exception:
                    pass

        return results
