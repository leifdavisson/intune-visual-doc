"""
Documentation generator engine for Microsoft Intune.
Renders ASD-STE100 Markdown documents and organizes assets.
"""

import os
import re
import json
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from jinja2 import Environment, FileSystemLoader

from .sanitizer import sanitize_settings_list
from .badges import get_hygiene_badges, get_learn_link


def slugify(text: str) -> str:
    """Convert text into a safe filesystem slug."""
    text = re.sub(r"[^\w\s-]", "", text).strip().lower()
    return re.sub(r"[-\s]+", "-", text)


class DocGenerator:
    def __init__(self, output_dir: str = "docs", unsanitize: bool = False):
        self.output_dir = os.path.abspath(output_dir)
        self.unsanitize = unsanitize
        template_dir = os.path.join(os.path.dirname(__file__), "templates")
        self.env = Environment(loader=FileSystemLoader(template_dir), trim_blocks=True, lstrip_blocks=True)

    def render_all(
        self,
        policies: List[Dict[str, Any]],
        audit_events: List[Dict[str, Any]],
        generator_user: str = "Administrator",
        audit_days: int = 30,
        screenshots_map: Optional[Dict[str, Dict[str, str]]] = None,
    ) -> Dict[str, Any]:
        """
        Generate full documentation tree:
        - docs/README.md (Main Index)
        - docs/<category>/<policy-slug>.md
        - docs/audit/ADMIN_AUDIT_LOG.md
        - docs/raw_json/<category>/<policy-slug>.json
        """
        screenshots_map = screenshots_map or {}
        os.makedirs(self.output_dir, exist_ok=True)
        raw_json_dir = os.path.join(self.output_dir, "raw_json")
        os.makedirs(raw_json_dir, exist_ok=True)

        # Attribute last modified actor from audit events where possible
        actor_map = {}
        for ev in audit_events:
            t_name = ev.get("target", "").lower()
            if t_name and t_name not in actor_map:
                actor_map[t_name] = ev.get("actor")

        for p in policies:
            p_name = p.get("name", "").lower()
            if p_name in actor_map:
                p["last_modified_by"] = actor_map[p_name]
            p["slug"] = slugify(p.get("name", "policy"))
            # Sanitize settings
            p["settings"] = sanitize_settings_list(p.get("settings", []), unsanitize=self.unsanitize)

        # Group by category
        categories_dict = {
            "compliance": {
                "title": "Device Compliance Policies",
                "learn_title": "Microsoft Learn: Compliance Overview",
                "learn_url": "https://learn.microsoft.com/en-us/mem/intune/protect/device-compliance-get-started",
                "policies": [],
            },
            "configuration": {
                "title": "Configuration Profiles & Settings Catalog",
                "learn_title": "Microsoft Learn: Settings Catalog",
                "learn_url": "https://learn.microsoft.com/en-us/mem/intune/configuration/settings-catalog",
                "policies": [],
            },
            "apps": {
                "title": "Mobile & Managed Applications",
                "learn_title": "Microsoft Learn: App Management",
                "learn_url": "https://learn.microsoft.com/en-us/mem/intune/apps/app-management",
                "policies": [],
            },
        }

        for p in policies:
            cat = p.get("category", "configuration")
            if cat not in categories_dict:
                categories_dict[cat] = {
                    "title": p.get("category_label", cat.title()),
                    "learn_title": "Microsoft Learn Intune",
                    "learn_url": "https://learn.microsoft.com/en-us/mem/intune/",
                    "policies": [],
                }
            categories_dict[cat]["policies"].append(p)

        # Render individual policy markdown files
        policy_tmpl = self.env.get_template("policy.md.jinja2")

        for p in policies:
            cat = p.get("category", "configuration")
            cat_dir = os.path.join(self.output_dir, cat)
            os.makedirs(cat_dir, exist_ok=True)

            # Check screenshots
            p_id = p.get("id")
            shots = screenshots_map.get(p_id, {})
            ov_abs = shots.get("overview")
            pr_abs = shots.get("properties")

            # Relative paths for markdown links
            ov_rel = os.path.relpath(ov_abs, cat_dir) if ov_abs else None
            pr_rel = os.path.relpath(pr_abs, cat_dir) if pr_abs else None

            rendered = policy_tmpl.render(
                policy=p,
                badges=get_hygiene_badges(p),
                learn_link=get_learn_link(cat, p.get("name", "")),
                overview_screenshot_path=ov_abs,
                overview_relative_path=ov_rel,
                properties_screenshot_path=pr_abs,
                properties_relative_path=pr_rel,
                raw_json=json.dumps(p.get("raw", {}), indent=2),
            )

            doc_path = os.path.join(cat_dir, f"{p['slug']}.md")
            with open(doc_path, "w", encoding="utf-8") as f:
                f.write(rendered)

            # Write raw JSON backup
            cat_json_dir = os.path.join(raw_json_dir, cat)
            os.makedirs(cat_json_dir, exist_ok=True)
            with open(os.path.join(cat_json_dir, f"{p['slug']}.json"), "w", encoding="utf-8") as f:
                json.dump(p.get("raw", {}), f, indent=2)

        # Render Audit log document
        audit_dir = os.path.join(self.output_dir, "audit")
        os.makedirs(audit_dir, exist_ok=True)
        audit_tmpl = self.env.get_template("audit.md.jinja2")
        rendered_audit = audit_tmpl.render(events=audit_events, audit_days=audit_days)
        with open(os.path.join(audit_dir, "ADMIN_AUDIT_LOG.md"), "w", encoding="utf-8") as f:
            f.write(rendered_audit)

        # Render Main Index
        stats = {
            "total_policies": len(policies),
            "assigned_policies": sum(1 for p in policies if p.get("assignments")),
            "unassigned_policies": sum(1 for p in policies if not p.get("assignments")),
            "baseline_policies": sum(1 for p in policies if "baseline" in p.get("name", "").lower() or "bitlocker" in p.get("name", "").lower()),
            "sanitized_status": "Enabled (Secrets Masked)" if not self.unsanitize else "Disabled (Raw Values Shown)",
        }

        now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        index_tmpl = self.env.get_template("index.md.jinja2")
        rendered_index = index_tmpl.render(
            generated_at=now_str,
            generator_user=generator_user,
            stats=stats,
            categories=categories_dict,
        )

        index_path = os.path.join(self.output_dir, "README.md")
        with open(index_path, "w", encoding="utf-8") as f:
            f.write(rendered_index)

        return {
            "index_path": index_path,
            "total_policies": len(policies),
            "stats": stats,
        }
