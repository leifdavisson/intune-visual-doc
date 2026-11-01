"""
Security Posture & Best-Practice Audit engine for Microsoft Intune.
Licensed under GNU AGPLv3.

Inspects exported configuration backups offline without network calls.
Evaluates configurations against CIS Benchmarks, Microsoft Baselines, and NIST guidelines.
"""

import os
import json
from datetime import datetime, timezone
from typing import Dict, Any, List, Set, Tuple, Optional
from jinja2 import Environment, FileSystemLoader

from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from .rules import (
    AUDIT_RULES,
    AuditRule,
    RuleEvaluationResult,
    EvaluationVerdict,
    LEGAL_SAFE_HARBOR_NOTICE,
    get_legal_disclaimer_text,
)
from ..graph.flattener import (
    flatten_settings_catalog,
    flatten_compliance_settings,
    is_effective_assignment,
)
from ..deliverables import get_latest_deliverables_dir

console = Console()


def detect_backup_scope(target_dir: str) -> Dict[str, Any]:
    """
    Detect available categories and policy counts from a backup directory.
    Supports either deliverables root, timestamped run dir, or raw_json dir.
    """
    resolved_dir = os.path.abspath(target_dir)

    if not os.path.exists(os.path.join(resolved_dir, "raw_json")) and not os.path.exists(os.path.join(resolved_dir, "backup_manifest.json")):
        latest = get_latest_deliverables_dir(resolved_dir)
        if latest:
            resolved_dir = latest

    raw_json_dir = os.path.join(resolved_dir, "raw_json") if os.path.exists(os.path.join(resolved_dir, "raw_json")) else resolved_dir
    manifest_path = os.path.join(resolved_dir, "backup_manifest.json")

    detected_categories: Set[str] = set()
    policy_count = 0

    if os.path.exists(raw_json_dir):
        for entry in os.scandir(raw_json_dir):
            if entry.is_dir():
                json_files = [f for f in os.scandir(entry.path) if f.name.endswith(".json")]
                if json_files:
                    detected_categories.add(entry.name.lower())
                    policy_count += len(json_files)

    if not detected_categories and os.path.exists(manifest_path):
        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                manifest_data = json.load(f)
            for p in manifest_data.get("policies", []):
                cat = p.get("category")
                if cat:
                    detected_categories.add(cat.lower())
            policy_count = len(manifest_data.get("policies", []))
        except Exception:
            pass

    return {
        "run_dir": resolved_dir,
        "raw_json_dir": raw_json_dir,
        "manifest_path": manifest_path if os.path.exists(manifest_path) else None,
        "detected_categories": detected_categories,
        "policy_count": policy_count,
        "is_valid": len(detected_categories) > 0 or policy_count > 0,
    }


def load_policies_from_backup(target_dir: str) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    Load raw JSON policies from a backup directory without network calls.
    Properly flattens Settings Catalog and Compliance settings instances.
    """
    scope = detect_backup_scope(target_dir)
    policies: List[Dict[str, Any]] = []

    raw_json_dir = scope["raw_json_dir"]
    if not os.path.exists(raw_json_dir):
        return policies, scope

    for root, _, files in os.walk(raw_json_dir):
        cat = os.path.basename(root).lower()
        for fname in files:
            if not fname.endswith(".json"):
                continue
            fpath = os.path.join(root, fname)
            try:
                with open(fpath, "r", encoding="utf-8") as f:
                    raw_data = json.load(f)
            except Exception as exc:
                console.print(f"[yellow]⚠️ Could not parse JSON file {fpath}: {exc}[/yellow]")
                continue

            name = (
                raw_data.get("displayName") or
                raw_data.get("name") or
                fname[:-5].replace("-", " ").title()
            )
            desc = raw_data.get("description") or ""

            # Resolve assignments with inclusion/exclusion check
            assignments_raw = raw_data.get("assignments") or []
            assignments = []
            if isinstance(assignments_raw, list):
                for a in assignments_raw:
                    target_info = a.get("target") or {}
                    t_group = target_info.get("groupId") or a.get("groupId") or "Target Group"
                    if is_effective_assignment(a):
                        assignments.append({"type": "Included", "target": t_group})
                    else:
                        assignments.append({"type": "Excluded", "target": t_group})

            # Settings Catalog recursive flattener
            o_type = str(raw_data.get("@odata.type", "")).lower()
            settings = []
            if "devicecompliance" in o_type:
                settings = flatten_compliance_settings(raw_data)
            elif "settings" in raw_data and isinstance(raw_data["settings"], list):
                settings = flatten_settings_catalog(raw_data["settings"])
            elif isinstance(raw_data.get("settings"), list):
                settings = raw_data["settings"]
            else:
                for k, v in raw_data.items():
                    if isinstance(v, (str, int, float, bool)):
                        settings.append({"name": k, "full_definition": k, "value": str(v)})

            policies.append({
                "id": raw_data.get("id", fname[:-5]),
                "name": name,
                "description": desc,
                "category": cat,
                "category_label": cat.replace("_", " ").title(),
                "platform": str(raw_data.get("platforms") or raw_data.get("@odata.type", "Windows")),
                "assignments": assignments,
                "settings": settings,
                "raw": raw_data,
            })

    return policies, scope


def evaluate_tenant_posture(
    policies: List[Dict[str, Any]],
    profile: str = "balanced",
    detected_categories: Optional[Set[str]] = None,
    selected_domains: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Evaluate policy set against posture audit rules.
    Combines rule metadata with evaluation verdicts.
    """
    if detected_categories is None:
        detected_categories = {p.get("category", "").lower() for p in policies if p.get("category")}

    meta = {
        "detected_categories": detected_categories,
        "policy_count": len(policies),
    }

    active_rules: List[AuditRule] = []
    for r in AUDIT_RULES:
        if profile == "strict-stig":
            active_rules.append(r)
        elif r.profile == "balanced":
            active_rules.append(r)

    results: List[RuleEvaluationResult] = []
    for r in active_rules:
        if selected_domains is not None and r.domain not in selected_domains:
            results.append(RuleEvaluationResult(
                rule_id=r.rule_id,
                domain=r.domain,
                domain_label=r.domain_label,
                title=r.title,
                status="OMITTED",
                badge="⚪",
                observed_state="Domain was not selected for this audit run.",
                benchmark_ref=r.benchmark_ref,
                benchmark_intent=r.benchmark_intent,
                field_context=r.field_context,
                remediation_guidance=r.remediation_guidance,
                learn_url=r.learn_url,
                profile=r.profile,
                evidence="Domain omitted by operator selection.",
                findings=[],
            ))
            continue

        verdict = r.evaluator(policies, meta)
        results.append(RuleEvaluationResult(
            rule_id=r.rule_id,
            domain=r.domain,
            domain_label=r.domain_label,
            title=r.title,
            status=verdict.status,
            badge=verdict.badge,
            observed_state=verdict.observed_state,
            benchmark_ref=r.benchmark_ref,
            benchmark_intent=r.benchmark_intent,
            field_context=r.field_context,
            remediation_guidance=r.remediation_guidance,
            learn_url=r.learn_url,
            profile=r.profile,
            evidence=verdict.evidence,
            findings=verdict.findings,
        ))

    evaluated_rules = [r for r in results if r.status != "OMITTED"]
    passed = sum(1 for r in evaluated_rules if r.status == "PASS")
    warn = sum(1 for r in evaluated_rules if r.status == "WARN")
    fail = sum(1 for r in evaluated_rules if r.status == "FAIL")
    omitted = sum(1 for r in results if r.status == "OMITTED")
    total_eval = len(evaluated_rules)

    pct = round((passed / total_eval * 100), 1) if total_eval > 0 else 0.0

    if fail == 0 and warn <= 1:
        posture_tier = "Strong Baseline Alignment"
        posture_badge = "🟢"
    elif fail <= 1:
        posture_tier = "Operational Gaps Identified"
        posture_badge = "🟡"
    else:
        posture_tier = "Baseline Controls Missing"
        posture_badge = "🔴"

    stats = {
        "evaluated": total_eval,
        "passed": passed,
        "warn": warn,
        "fail": fail,
        "omitted": omitted,
        "percentage": pct,
    }

    return {
        "profile": profile,
        "posture_tier": posture_tier,
        "posture_badge": posture_badge,
        "stats": stats,
        "results": results,
    }


def display_posture_table(
    evaluation: Dict[str, Any],
    profile_name: str = "Balanced Baseline",
) -> None:
    """Print rich stop-light console summary for administrators and executives."""
    stats = evaluation["stats"]
    badge = evaluation["posture_badge"]
    tier = evaluation["posture_tier"]

    console.print(Panel(
        f"[bold cyan]🛡️  Microsoft Intune Security Posture & Best-Practice Audit[/bold cyan]\n"
        f"Profile: [bold]{profile_name}[/bold] | Score: [bold green]{stats['passed']}/{stats['evaluated']} ({stats['percentage']}%) [/bold green]\n"
        f"Overall Posture: {badge} [bold]{tier}[/bold]\n\n"
        f"[dim]Legal Notice: Informational advisory only. Always validate changes in a pilot group.[/dim]",
        border_style="cyan"
    ))

    table = Table(title="Executive Stop-Light Audit Scorecard", border_style="cyan")
    table.add_column("Status", justify="center", style="bold")
    table.add_column("Domain", style="cyan")
    table.add_column("Control Title", style="bold")
    table.add_column("Framework Citation", style="dim")
    table.add_column("Observed Status / Action Summary", style="yellow")

    for r in evaluation["results"]:
        status_display = f"{r.badge} {r.status}"
        table.add_row(
            status_display,
            r.domain_label,
            r.title,
            r.benchmark_ref,
            r.observed_state,
        )

    console.print(table)
    console.print("")


def render_audit_report(
    evaluation: Dict[str, Any],
    output_path: str,
    generator_user: str = "Intune Security Auditor",
) -> str:
    """
    Render AUDIT_RECOMMENDATIONS.md using Jinja2 template with legal disclaimer.
    Orders findings: 🔴 FAIL first, then 🟡 WARN, then 🟢 PASS, then ⚪ OMITTED.
    """
    tmpl_dir = os.path.join(os.path.dirname(__file__), "..", "generator", "templates")
    env = Environment(loader=FileSystemLoader(tmpl_dir), autoescape=False, trim_blocks=True, lstrip_blocks=True)
    tmpl = env.get_template("audit_recommendations.md.jinja2")

    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ")

    # Order findings by severity for executive punch list
    severity_order = {"FAIL": 0, "WARN": 1, "PASS": 2, "OMITTED": 3}
    sorted_results = sorted(evaluation["results"], key=lambda r: severity_order.get(r.status, 99))
    top_actions = [r for r in sorted_results if r.status in ("FAIL", "WARN")][:3]

    rendered = tmpl.render(
        generated_at=now_str,
        generator_user=generator_user,
        profile_name=evaluation["profile"].replace("-", " ").title(),
        posture_badge=evaluation["posture_badge"],
        posture_tier=evaluation["posture_tier"],
        stats=evaluation["stats"],
        results=evaluation["results"],
        sorted_results=sorted_results,
        top_actions=top_actions,
        disclaimer=LEGAL_SAFE_HARBOR_NOTICE,
    )

    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(rendered)

    return output_path
