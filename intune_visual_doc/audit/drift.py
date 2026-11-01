"""
Configuration drift detector comparing current policies against saved raw_json/ backups.
"""

import os
import json
from typing import Dict, Any, List
from ..generator.engine import slugify
from ..generator.sanitizer import sanitize_value
from ..deliverables import get_latest_deliverables_dir


def compare_with_backups(
    policies: List[Dict[str, Any]],
    output_dir: str = "deliverables",
    unsanitize: bool = False,
) -> List[Dict[str, str]]:
    """
    Compare extracted policies against saved JSON backups in <output_dir>/raw_json/.
    Automatically resolves the latest timestamped run if output_dir is a deliverables root.
    Returns a list of drift findings: Added, Modified, or Removed policies.
    """
    target_dir = os.path.abspath(output_dir)
    if not os.path.exists(os.path.join(target_dir, "raw_json")):
        latest = get_latest_deliverables_dir(output_dir)
        if latest and os.path.exists(os.path.join(latest, "raw_json")):
            target_dir = latest

    raw_json_root = os.path.join(target_dir, "raw_json")
    findings: List[Dict[str, str]] = []

    seen_files = set()

    for p in policies:
        cat = p.get("category", "configuration")
        slug = p.get("slug") or slugify(p.get("name", p.get("id", "policy")))
        backup_path = os.path.join(raw_json_root, cat, f"{slug}.json")
        seen_files.add(os.path.abspath(backup_path))

        current_raw = sanitize_value("raw", p.get("raw", {}), unsanitize=unsanitize)

        if not os.path.exists(backup_path):
            findings.append({
                "policy": p.get("name", slug),
                "category": cat,
                "status": "Added",
                "details": "No previous backup file in raw_json/",
            })
            continue

        try:
            with open(backup_path, "r", encoding="utf-8") as f:
                saved_raw = json.load(f)
        except Exception as exc:
            findings.append({
                "policy": p.get("name", slug),
                "category": cat,
                "status": "Unreadable",
                "details": f"Could not parse backup JSON: {exc}",
            })
            continue

        if current_raw != saved_raw:
            changed_keys = [
                k for k in set(current_raw.keys()) | set(saved_raw.keys())
                if current_raw.get(k) != saved_raw.get(k)
            ]
            findings.append({
                "policy": p.get("name", slug),
                "category": cat,
                "status": "Modified",
                "details": f"Changed fields: {', '.join(sorted(changed_keys))}",
            })

    if os.path.exists(raw_json_root):
        for root, _, files in os.walk(raw_json_root):
            for fname in files:
                if not fname.endswith(".json"):
                    continue
                fpath = os.path.abspath(os.path.join(root, fname))
                if fpath not in seen_files:
                    rel_cat = os.path.basename(root)
                    findings.append({
                        "policy": fname[:-5],
                        "category": rel_cat,
                        "status": "Removed",
                        "details": "Backup exists in raw_json/ without matching live policy",
                    })

    return findings
