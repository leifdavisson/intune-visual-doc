"""
Deliverables management for Microsoft Intune documentation snapshots.
Organizes documentation runs into timestamped directories with a latest pointer and catalog.
Licensed under GNU AGPLv3.
"""

import os
import re
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional


CATALOG_HEADER = """# Microsoft Intune Deliverables Catalog

[Back to Project Documentation](../docs/README.md)

This catalog records all Intune documentation runs.
Each run creates a timestamped folder with full Markdown reports, screenshots, and raw JSON payloads.

---

## Latest Deliverable

- **Latest Run**: [Open Latest Tenant Documentation](latest/README.md) (`latest/README.md`)

---

## Historical Documentation Runs

| Run Timestamp (UTC) | Tenant / Account | Total Policies | Assigned / Dormant | Admin Events | Deliverable Link |
| :--- | :--- | :--- | :--- | :--- | :--- |
"""


def get_timestamp_string(dt: Optional[datetime] = None) -> str:
    """Return standard timestamp string for deliverable directory names."""
    dt = dt or datetime.now(timezone.utc)
    return dt.strftime("%Y-%m-%d_%H%M%S")


def create_timestamped_run_dir(base_dir: str = "deliverables", timestamp: Optional[datetime] = None) -> str:
    """Create a new timestamped directory under base_dir (e.g. deliverables/2026-10-31_153000)."""
    ts_str = get_timestamp_string(timestamp)
    run_dir = os.path.abspath(os.path.join(base_dir, ts_str))
    os.makedirs(run_dir, exist_ok=True)
    return run_dir


def update_latest_pointer(run_dir: str, base_dir: str = "deliverables") -> str:
    """
    Update the 'latest' symlink under base_dir to point to the newest run_dir.
    Falls back to a helper pointer file if symlinks are not permitted.
    """
    base_abs = os.path.abspath(base_dir)
    os.makedirs(base_abs, exist_ok=True)
    latest_path = os.path.join(base_abs, "latest")
    rel_target = os.path.relpath(run_dir, base_abs)

    try:
        if os.path.islink(latest_path):
            os.remove(latest_path)
        elif os.path.exists(latest_path) and os.path.isdir(latest_path):
            # If it was an actual folder rather than a link, do not delete without care
            pass
        os.symlink(rel_target, latest_path)
    except Exception:
        # Fallback for systems without symlink permissions
        pass

    return latest_path


def get_latest_deliverables_dir(base_dir: str = "deliverables") -> Optional[str]:
    """
    Resolve the most recent deliverables directory.
    Checks 'latest' symlink first, then scans for timestamped subdirectories.
    Falls back to base_dir or docs if present.
    """
    base_abs = os.path.abspath(base_dir)
    if not os.path.exists(base_abs):
        if os.path.exists("docs/raw_json"):
            return os.path.abspath("docs")
        return None

    latest_link = os.path.join(base_abs, "latest")
    if os.path.exists(latest_link):
        return os.path.realpath(latest_link)

    # Scan for timestamped subfolders matching YYYY-MM-DD_HHMMSS
    entries = []
    pattern = re.compile(r"^\d{4}-\d{2}-\d{2}_\d{6}$")
    for item in os.listdir(base_abs):
        full = os.path.join(base_abs, item)
        if os.path.isdir(full) and pattern.match(item):
            entries.append((item, full))

    if entries:
        entries.sort(key=lambda x: x[0], reverse=True)
        return entries[0][1]

    if os.path.exists(os.path.join(base_abs, "raw_json")):
        return base_abs

    if os.path.exists("docs/raw_json"):
        return os.path.abspath("docs")

    return None


def record_run_in_catalog(
    base_dir: str,
    run_dir: str,
    summary: Dict[str, Any],
    tenant_hint: str = "",
    audit_count: int = 0,
    run_type: str = "Documentation",
) -> str:
    """
    Record this execution into deliverables/README.md catalog table.
    Ensures table rows adhere to ASD-STE100 and line length limits.
    """
    base_abs = os.path.abspath(base_dir)
    os.makedirs(base_abs, exist_ok=True)
    catalog_path = os.path.join(base_abs, "README.md")

    folder_name = os.path.basename(run_dir)
    stats = summary.get("stats", {})
    tot = stats.get("total_policies", summary.get("total_policies", 0))
    assigned = stats.get("assigned_policies", 0)
    unassigned = stats.get("unassigned_policies", 0)

    # Format human-readable UTC timestamp
    try:
        parts = folder_name.split("_")
        ts_display = f"{parts[0]} {parts[1][:2]}:{parts[1][2:4]}:{parts[1][4:6]} UTC"
    except Exception:
        ts_display = folder_name

    account_display = tenant_hint or "Intune Admin"
    ratio_display = f"`🟢 {assigned}` / `🟡 {unassigned}`"
    link_label = "Open Backup" if run_type == "Backup" else "Open Run"
    link_display = f"[{link_label}]({folder_name}/README.md)"

    new_row = f"| `{ts_display}` | `{account_display}` | `{tot}` | {ratio_display} | `{audit_count}` | {link_display} |\n"

    if not os.path.exists(catalog_path):
        with open(catalog_path, "w", encoding="utf-8") as f:
            f.write(CATALOG_HEADER + new_row)
    else:
        with open(catalog_path, "r", encoding="utf-8") as f:
            content = f.read()

        if folder_name not in content:
            # Insert new row right after the table header
            lines = content.splitlines(keepends=True)
            table_idx = -1
            for idx, line in enumerate(lines):
                if line.startswith("| :---"):
                    table_idx = idx
                    break

            if table_idx != -1:
                lines.insert(table_idx + 1, new_row)
                with open(catalog_path, "w", encoding="utf-8") as f:
                    f.writelines(lines)
            else:
                with open(catalog_path, "a", encoding="utf-8") as f:
                    f.write(new_row)

    return catalog_path


def list_historical_runs(base_dir: str = "deliverables") -> List[Dict[str, Any]]:
    """
    Scan deliverables directory for timestamped subdirectories.
    Returns list of dicts ordered newest first.
    """
    base_abs = os.path.abspath(base_dir)
    if not os.path.exists(base_abs):
        return []

    pattern = re.compile(r"^\d{4}-\d{2}-\d{2}_\d{6}$")
    runs = []
    for item in os.listdir(base_abs):
        full = os.path.join(base_abs, item)
        if os.path.isdir(full) and pattern.match(item):
            p_count = 0
            manifest_path = os.path.join(full, "backup_manifest.json")
            if os.path.exists(manifest_path):
                try:
                    import json
                    with open(manifest_path, "r", encoding="utf-8") as f:
                        m_data = json.load(f)
                    p_count = m_data.get("total_policies", 0)
                except Exception:
                    pass
            runs.append({
                "name": item,
                "timestamp": item.replace("_", " "),
                "path": full,
                "policy_count": p_count,
            })

    runs.sort(key=lambda x: x["name"], reverse=True)
    return runs
