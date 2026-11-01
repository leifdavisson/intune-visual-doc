"""
Configuration drift detector comparing policies against saved raw_json backups.
Provides setting-level granularity and visual screenshot comparison.
Licensed under GNU AGPLv3.
"""

import os
import json
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Tuple
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.tree import Tree

from ..generator.engine import slugify
from ..generator.sanitizer import sanitize_value
from ..deliverables import get_latest_deliverables_dir

console = Console()


@dataclass
class SettingDiff:
    name: str
    full_definition: str
    change_type: str  # "Added", "Removed", "Modified"
    old_value: Any
    new_value: Any


@dataclass
class PolicyDiff:
    name: str
    category: str
    slug: str
    status: str  # "Added", "Removed", "Modified", "Unchanged"
    details: str
    setting_diffs: List[SettingDiff] = field(default_factory=list)
    assignment_diffs: List[str] = field(default_factory=list)
    screenshots: Dict[str, Optional[str]] = field(default_factory=dict)


def _normalize_settings(settings_val: Any) -> List[Dict[str, Any]]:
    """Convert settings into a list of standardized setting dictionaries."""
    if not settings_val:
        return []
    if isinstance(settings_val, dict):
        return [
            {"name": str(k), "full_definition": str(k), "value": v}
            for k, v in settings_val.items()
        ]
    if isinstance(settings_val, list):
        norm = []
        for item in settings_val:
            if isinstance(item, dict):
                norm.append(item)
            else:
                norm.append({"name": str(item), "full_definition": str(item), "value": item})
        return norm
    return []


def _index_settings(settings: Any) -> Dict[str, Dict[str, Any]]:
    """Index settings list by full_definition or name for fast lookup."""
    index = {}
    for s in _normalize_settings(settings):
        key = s.get("full_definition") or s.get("name") or "unknown"
        index[key] = s
    return index


def _policy_key(p: Dict[str, Any]) -> str:
    """Generate unique compound key for policy comparison."""
    pid = p.get("id")
    if pid:
        return f"id:{pid}"
    cat = p.get("category", "configuration")
    name = p.get("displayName") or p.get("name", "policy")
    slug = p.get("slug") or slugify(name)
    return f"{cat}:{slug}"


def compare_policies_granular(
    baseline_policies: List[Dict[str, Any]],
    target_policies: List[Dict[str, Any]],
    baseline_dir: Optional[str] = None,
    target_dir: Optional[str] = None,
) -> List[PolicyDiff]:
    """
    Compare two lists of policies at the individual setting and assignment level.
    Identifies added, removed, and modified parameters.
    """
    diffs: List[PolicyDiff] = []
    base_by_key: Dict[str, Dict[str, Any]] = {}

    for p in baseline_policies:
        base_by_key[_policy_key(p)] = p

    target_seen = set()

    for p in target_policies:
        pkey = _policy_key(p)
        target_seen.add(pkey)
        slug = p.get("slug") or slugify(p.get("displayName") or p.get("name", str(p.get("id", "policy"))))
        p_name = p.get("displayName") or p.get("name", slug)
        cat = p.get("category", "configuration")

        shots: Dict[str, Optional[str]] = {}
        if target_dir:
            shots["new_overview"] = os.path.join(target_dir, "assets", "screenshots", cat, slug, "overview.png")
            shots["new_properties"] = os.path.join(target_dir, "assets", "screenshots", cat, slug, "properties.png")

        if pkey not in base_by_key:
            # Policy added in target
            diffs.append(PolicyDiff(
                name=p_name,
                category=cat,
                slug=slug,
                status="Added",
                details="Policy present in target run but missing in baseline.",
                setting_diffs=[
                    SettingDiff(
                        name=s.get("name", "setting"),
                        full_definition=s.get("full_definition", s.get("name", "")),
                        change_type="Added",
                        old_value=None,
                        new_value=s.get("value"),
                    )
                    for s in _normalize_settings(p.get("settings"))
                ],
                screenshots=shots,
            ))
            continue

        base_p = base_by_key[pkey]
        if baseline_dir:
            shots["old_overview"] = os.path.join(baseline_dir, "assets", "screenshots", cat, slug, "overview.png")
            shots["old_properties"] = os.path.join(baseline_dir, "assets", "screenshots", cat, slug, "properties.png")

        # Check raw JSON equality if available
        base_raw = sanitize_value("raw", base_p.get("raw", {})) if base_p.get("raw") else None
        target_raw = sanitize_value("raw", p.get("raw", {})) if p.get("raw") else None

        if base_raw is not None and target_raw is not None and base_raw == target_raw:
            diffs.append(PolicyDiff(
                name=p_name,
                category=cat,
                slug=slug,
                status="Unchanged",
                details="Configuration and assignments match exactly.",
                screenshots=shots,
            ))
            continue

        # Compare settings
        base_settings = _index_settings(base_p.get("settings", []))
        targ_settings = _index_settings(p.get("settings", []))

        s_diffs: List[SettingDiff] = []
        all_keys = sorted(set(base_settings.keys()) | set(targ_settings.keys()))

        for k in all_keys:
            if k not in base_settings:
                s = targ_settings[k]
                s_diffs.append(SettingDiff(
                    name=s.get("name", k),
                    full_definition=k,
                    change_type="Added",
                    old_value=None,
                    new_value=s.get("value"),
                ))
            elif k not in targ_settings:
                s = base_settings[k]
                s_diffs.append(SettingDiff(
                    name=s.get("name", k),
                    full_definition=k,
                    change_type="Removed",
                    old_value=s.get("value"),
                    new_value=None,
                ))
            else:
                old_v = str(base_settings[k].get("value", ""))
                new_v = str(targ_settings[k].get("value", ""))
                if old_v != new_v:
                    s_diffs.append(SettingDiff(
                        name=targ_settings[k].get("name", k),
                        full_definition=k,
                        change_type="Modified",
                        old_value=old_v,
                        new_value=new_v,
                    ))

        # Compare assignments
        base_targets = {
            f"{a.get('type', 'Included')}:{a.get('target', '')}"
            for a in base_p.get("assignments", [])
        }
        targ_targets = {
            f"{a.get('type', 'Included')}:{a.get('target', '')}"
            for a in p.get("assignments", [])
        }
        assign_diffs = []
        for t in sorted(targ_targets - base_targets):
            assign_diffs.append(f"+ Added target: {t}")
        for t in sorted(base_targets - targ_targets):
            assign_diffs.append(f"- Removed target: {t}")

        changed_raw_keys = []
        if base_raw is not None and target_raw is not None:
            changed_raw_keys = sorted([
                k for k in set(base_raw.keys()) | set(target_raw.keys())
                if base_raw.get(k) != target_raw.get(k)
            ])

        if s_diffs or assign_diffs or changed_raw_keys:
            details_parts = []
            if changed_raw_keys and not s_diffs and not assign_diffs:
                details_parts.append(f"Changed fields: {', '.join(changed_raw_keys)}")
            else:
                if s_diffs:
                    details_parts.append(f"{len(s_diffs)} setting changes")
                if assign_diffs:
                    details_parts.append(f"{len(assign_diffs)} assignment changes")
                if changed_raw_keys:
                    details_parts.append(f"Fields: {', '.join(changed_raw_keys)}")
            diffs.append(PolicyDiff(
                name=p_name,
                category=cat,
                slug=slug,
                status="Modified",
                details=", ".join(details_parts),
                setting_diffs=s_diffs,
                assignment_diffs=assign_diffs,
                screenshots=shots,
            ))
        else:
            diffs.append(PolicyDiff(
                name=p_name,
                category=cat,
                slug=slug,
                status="Unchanged",
                details="Configuration and assignments match exactly.",
                screenshots=shots,
            ))

    # Detect removed policies
    for pkey, base_p in base_by_key.items():
        if pkey not in target_seen:
            name = base_p.get("displayName") or base_p.get("name", "policy")
            slug = base_p.get("slug") or slugify(name)
            cat = base_p.get("category", "configuration")
            shots = {}
            if baseline_dir:
                shots["old_overview"] = os.path.join(baseline_dir, "assets", "screenshots", cat, slug, "overview.png")
                shots["old_properties"] = os.path.join(baseline_dir, "assets", "screenshots", cat, slug, "properties.png")
            diffs.append(PolicyDiff(
                name=name,
                category=cat,
                slug=slug,
                status="Removed",
                details="Policy present in baseline run but missing in target.",
                setting_diffs=[
                    SettingDiff(
                        name=s.get("name", "setting"),
                        full_definition=s.get("full_definition", s.get("name", "")),
                        change_type="Removed",
                        old_value=s.get("value"),
                        new_value=None,
                    )
                    for s in _normalize_settings(base_p.get("settings"))
                ],
                screenshots=shots,
            ))

    return diffs


def compare_backup_runs(baseline_dir: str, target_dir: str) -> Dict[str, Any]:
    """
    Compare two historical backup directories offline at the individual setting level.
    """
    from .posture import load_policies_from_backup

    base_policies, base_scope = load_policies_from_backup(baseline_dir)
    targ_policies, targ_scope = load_policies_from_backup(target_dir)

    diffs = compare_policies_granular(
        base_policies,
        targ_policies,
        baseline_dir=base_scope.get("run_dir"),
        target_dir=targ_scope.get("run_dir"),
    )

    added = sum(1 for d in diffs if d.status == "Added")
    removed = sum(1 for d in diffs if d.status == "Removed")
    modified = sum(1 for d in diffs if d.status == "Modified")
    unchanged = sum(1 for d in diffs if d.status == "Unchanged")
    total_setting_changes = sum(len(d.setting_diffs) for d in diffs if d.status == "Modified")

    return {
        "baseline_dir": baseline_dir,
        "target_dir": target_dir,
        "baseline_label": os.path.basename(os.path.abspath(baseline_dir)),
        "target_label": os.path.basename(os.path.abspath(target_dir)),
        "diffs": diffs,
        "stats": {
            "total_policies_target": len(targ_policies),
            "added": added,
            "removed": removed,
            "modified": modified,
            "unchanged": unchanged,
            "total_setting_changes": total_setting_changes,
        },
    }


def compare_with_backups(
    policies: List[Dict[str, Any]],
    output_dir: str = "deliverables",
    unsanitize: bool = False,
) -> List[Dict[str, str]]:
    """
    Compare extracted policies against saved JSON backups in <output_dir>/raw_json/.
    Preserves backward compatibility while providing setting-level granularity.
    """
    target_dir = os.path.abspath(output_dir)
    if not os.path.exists(os.path.join(target_dir, "raw_json")):
        latest = get_latest_deliverables_dir(output_dir)
        if latest and os.path.exists(os.path.join(latest, "raw_json")):
            target_dir = latest

    from .posture import load_policies_from_backup
    saved_policies, _ = load_policies_from_backup(target_dir)

    diffs = compare_policies_granular(saved_policies, policies)
    findings: List[Dict[str, str]] = []

    for d in diffs:
        if d.status != "Unchanged":
            findings.append({
                "policy": d.name,
                "category": d.category,
                "status": d.status,
                "details": d.details,
            })

    return findings


def display_granular_drift_table(drift_report: Dict[str, Any]) -> None:
    """
    Render Rich colorized terminal tree and table of configuration drift.
    """
    stats = drift_report["stats"]
    base_lbl = drift_report["baseline_label"]
    targ_lbl = drift_report["target_label"]

    console.print(Panel(
        f"[bold cyan]🔍 Configuration Drift Analysis[/bold cyan]\n"
        f"Baseline: [bold white]{base_lbl}[/bold white]  ➔  Target: [bold white]{targ_lbl}[/bold white]\n"
        f"Summary: [green]+{stats['added']} Added[/green] | "
        f"[red]-{stats['removed']} Removed[/red] | "
        f"[yellow]~{stats['modified']} Modified ({stats['total_setting_changes']} settings)[/yellow] | "
        f"[dim]{stats['unchanged']} Unchanged[/dim]",
        title="Drift Overview",
        border_style="cyan",
    ))

    active_diffs = [d for d in drift_report["diffs"] if d.status != "Unchanged"]
    if not active_diffs:
        console.print("[green]✨ Zero configuration drift detected. All policies match baseline.[/green]\n")
        return

    table = Table(title="Policy Drift Summary", border_style="dim", header_style="bold magenta")
    table.add_column("Status", width=12, justify="center")
    table.add_column("Category", width=18)
    table.add_column("Policy Name", width=36)
    table.add_column("Change Details")

    for d in active_diffs:
        if d.status == "Added":
            badge = "[green]+ Added[/green]"
        elif d.status == "Removed":
            badge = "[red]- Removed[/red]"
        else:
            badge = "[yellow]~ Modified[/yellow]"

        table.add_row(badge, d.category.replace("_", " ").title(), d.name, d.details)

    console.print(table)

    # Detailed setting mutation tree for modified policies
    modified_policies = [d for d in active_diffs if d.status == "Modified"]
    if modified_policies:
        tree = Tree("\n[bold yellow]📋 Detailed Setting Mutations[/bold yellow]")
        for d in modified_policies:
            p_node = tree.add(f"[bold]{d.name}[/bold] [dim]({d.category})[/dim]")
            for a_diff in d.assignment_diffs:
                p_node.add(f"[cyan]{a_diff}[/cyan]")
            for s in d.setting_diffs:
                if s.change_type == "Modified":
                    p_node.add(
                        f"[yellow]~ {s.name}[/yellow]: "
                        f"[red]{s.old_value}[/red] ➔ [green]{s.new_value}[/green]"
                    )
                elif s.change_type == "Added":
                    p_node.add(f"[green]+ {s.name}: {s.new_value}[/green]")
                elif s.change_type == "Removed":
                    p_node.add(f"[red]- {s.name} (was: {s.old_value})[/red]")
        console.print(tree)
        console.print()


def render_drift_html_report(drift_report: Dict[str, Any], output_path: str) -> str:
    """
    Render standalone HTML drift report with visual side-by-side screenshots.
    """
    from datetime import datetime, timezone
    from jinja2 import Environment, FileSystemLoader

    tmpl_dir = os.path.join(os.path.dirname(__file__), "..", "generator", "templates")
    env = Environment(loader=FileSystemLoader(tmpl_dir), autoescape=True, trim_blocks=True, lstrip_blocks=True)
    template = env.get_template("drift_report.html.jinja2")

    active_diffs = [d for d in drift_report["diffs"] if d.status != "Unchanged"]

    rendered = template.render(
        baseline_label=drift_report["baseline_label"],
        target_label=drift_report["target_label"],
        generated_at=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
        stats=drift_report["stats"],
        active_diffs=active_diffs,
    )

    out_dir = os.path.dirname(os.path.abspath(output_path))
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(rendered)

    return os.path.abspath(output_path)
