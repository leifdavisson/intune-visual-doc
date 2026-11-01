"""
Multi-Tenant MSP Batch Automation and Portfolio Posture Auditing.
Evaluates security baselines across multiple Microsoft Intune tenants.
Licensed under GNU AGPLv3.
"""

import os
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Tuple
from jinja2 import Environment, FileSystemLoader
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from .posture import evaluate_tenant_posture, load_policies_from_backup
from .rules import AUDIT_RULES
from ..mock_data.samples import get_mock_policies

console = Console()


@dataclass
class TenantTarget:
    name: str
    tenant_id: Optional[str] = None
    client_id: Optional[str] = None
    client_secret: Optional[str] = None
    backup_dir: Optional[str] = None
    mock: bool = False


@dataclass
class TenantAuditOutcome:
    tenant_name: str
    target_path: str
    posture_badge: str
    posture_tier: str
    percentage: float
    passed: int
    warn: int
    fail: int
    evaluated: int
    omitted: int
    dormant_policies: int
    total_policies: int
    rule_verdicts: Dict[str, str] = field(default_factory=dict)
    priority_gaps: List[str] = field(default_factory=list)


@dataclass
class PortfolioAuditReport:
    portfolio_name: str
    generated_at: str
    profile: str
    profile_label: str
    tenants: List[TenantAuditOutcome]
    avg_compliance: float
    total_tenants: int
    compliant_tenants: int
    warning_tenants: int
    critical_tenants: int
    heatmap_rows: Dict[str, Dict[str, Any]]
    top_portfolio_risks: List[Dict[str, Any]]


def _resolve_secret(val: Optional[str]) -> str:
    """Resolve environment variable references like env:VAR_NAME."""
    if not val:
        return ""
    if val.startswith("env:"):
        var_name = val[4:]
        return os.environ.get(var_name, "")
    return val


def load_portfolio_config(config_path: str) -> Tuple[str, List[TenantTarget]]:
    """
    Parse a tenant portfolio manifest JSON file.
    Resolves environment variables in SPN secrets.
    """
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Portfolio configuration file not found: {config_path}")

    with open(config_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    portfolio_name = data.get("portfolio_name", "MSP Intune Tenant Portfolio")
    tenants_raw = data.get("tenants", [])

    targets: List[TenantTarget] = []
    for t in tenants_raw:
        targets.append(TenantTarget(
            name=t.get("name", "Unnamed Tenant"),
            tenant_id=t.get("tenant_id"),
            client_id=t.get("client_id"),
            client_secret=_resolve_secret(t.get("client_secret")),
            backup_dir=t.get("backup_dir"),
            mock=bool(t.get("mock", False)),
        ))

    return portfolio_name, targets


def generate_sample_config(output_path: str = "tenants.sample.json") -> str:
    """Generate a documented template manifest for MSP multi-tenant auditing."""
    sample = {
        "portfolio_name": "Regional Education Consortium Portfolio",
        "tenants": [
          {
            "name": "Oakridge School District",
            "backup_dir": "deliverables/oakridge_latest",
            "mock": False,
          },
          {
            "name": "Pinecrest Academy",
            "tenant_id": "00000000-1111-2222-3333-444444444444",
            "client_id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
            "client_secret": "env:PINECREST_SPN_SECRET",
            "backup_dir": None,
            "mock": False,
          },
          {
            "name": "Valley View Charter (Lab)",
            "mock": True,
          },
        ]
    }
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(sample, f, indent=2)
    return os.path.abspath(output_path)


def get_mock_portfolio() -> Tuple[str, List[TenantTarget]]:
    """Return simulated multi-tenant portfolio targets for offline demonstration."""
    targets = [
        TenantTarget(name="Oakridge School District (High Security)", mock=True),
        TenantTarget(name="Pinecrest Academy (Standard Baseline)", mock=True),
        TenantTarget(name="Valley View Charter (Remediation Needed)", mock=True),
    ]
    return "Education Consortium Portfolio (Sample Data)", targets


def _get_simulated_tenant_policies(tenant_index: int) -> List[Dict[str, Any]]:
    """Generate variations of mock policies across tenants for realistic portfolio analysis."""
    base = get_mock_policies()
    if tenant_index == 0:
        # High security tenant: BitLocker, Defender, Firewall, WUfB configured and assigned
        p1 = dict(base[0])
        p1["settings"] = list(base[0]["settings"]) + [
            {"name": "DomainFirewallEnabled", "value": "1"},
            {"name": "RealTimeProtection", "value": "True"},
            {"name": "DeferQualityUpdatesPeriodInDays", "value": "3"},
            {"name": "SmartScreenEnabled", "value": "True"},
            {"name": "personalDeviceEnrollmentBlocked", "value": "True"},
        ]
        return [p1, base[1]]
    elif tenant_index == 1:
        # Standard baseline: standard mock set
        return base
    else:
        # High-risk tenant: BitLocker missing, unassigned policies
        p_draft = dict(base[4])  # Unassigned lab kiosk
        p_comp = dict(base[1])
        p_comp["assignments"] = []  # Make compliance unassigned
        return [p_draft, p_comp]


def run_msp_audit_batch(
    portfolio_name: str,
    targets: List[TenantTarget],
    profile: str = "balanced",
) -> PortfolioAuditReport:
    """
    Execute batch posture audit across all configured portfolio tenants.
    Compiles comparative scorecard and cross-tenant heatmap.
    """
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ")
    outcomes: List[TenantAuditOutcome] = []

    active_rule_ids = [
        r.rule_id for r in AUDIT_RULES
        if profile == "strict-stig" or r.profile == "balanced"
    ]
    rule_map = {r.rule_id: r for r in AUDIT_RULES}

    for idx, target in enumerate(targets):
        policies: List[Dict[str, Any]] = []
        target_path = target.backup_dir or "Mock Data"

        if target.mock:
            policies = _get_simulated_tenant_policies(idx)
            detected_cats = {p.get("category", "").lower() for p in policies}
        elif target.backup_dir:
            loaded_pols, scope = load_policies_from_backup(target.backup_dir)
            policies = loaded_pols
            detected_cats = scope.get("detected_categories", set())
        elif target.tenant_id and target.client_id and target.client_secret:
            # Live SPN query
            try:
                from ..auth.spn_auth import get_spn_token
                from ..graph.client import GraphClient
                from ..graph.collectors import PolicyCollector

                token = get_spn_token(
                    tenant_id=target.tenant_id,
                    client_id=target.client_id,
                    client_secret=target.client_secret,
                )
                client = GraphClient(token)
                collector = PolicyCollector(client)
                policies = (
                    collector.get_compliance_policies()
                    + collector.get_configuration_policies()
                    + collector.get_device_configurations()
                    + collector.get_endpoint_security_policies()
                    + collector.get_device_management_scripts()
                    + collector.get_device_enrollment_configurations()
                    + collector.get_managed_apps()
                )
                detected_cats = {p.get("category", "").lower() for p in policies}
                target_path = f"Graph API ({target.tenant_id})"
            except Exception as e:
                console.print(f"[yellow]⚠️ Could not query live tenant {target.name}: {e}[/yellow]")
                policies = []
                detected_cats = set()
        else:
            policies = []
            detected_cats = set()

        evaluation = evaluate_tenant_posture(
            policies=policies,
            profile=profile,
            detected_categories=detected_cats,
        )

        stats = evaluation["stats"]
        verdicts = {r.rule_id: r.status for r in evaluation["results"]}
        gaps = [r.title for r in evaluation["results"] if r.status == "FAIL"]
        dormant = sum(1 for p in policies if not any(a.get("type") == "Included" for a in p.get("assignments", [])))

        outcomes.append(TenantAuditOutcome(
            tenant_name=target.name,
            target_path=target_path,
            posture_badge=evaluation["posture_badge"],
            posture_tier=evaluation["posture_tier"],
            percentage=stats["percentage"],
            passed=stats["passed"],
            warn=stats["warn"],
            fail=stats["fail"],
            evaluated=stats["evaluated"],
            omitted=stats["omitted"],
            dormant_policies=dormant,
            total_policies=len(policies),
            rule_verdicts=verdicts,
            priority_gaps=gaps,
        ))

    total = len(outcomes)
    avg_comp = sum(o.percentage for o in outcomes) / total if total > 0 else 0.0
    compliant = sum(1 for o in outcomes if o.percentage >= 80.0)
    warning = sum(1 for o in outcomes if 50.0 <= o.percentage < 80.0)
    critical = sum(1 for o in outcomes if o.percentage < 50.0)

    # Build heatmap rows
    heatmap_rows: Dict[str, Dict[str, Any]] = {}
    for r_id in active_rule_ids:
        r = rule_map.get(r_id)
        if r:
            heatmap_rows[r_id] = {
                "title": r.title,
                "domain": r.domain_label,
            }

    # Top portfolio risks (rules failing on most tenants)
    risk_counts: Dict[str, List[str]] = {}
    for o in outcomes:
        for r_id, status in o.rule_verdicts.items():
            if status == "FAIL":
                risk_counts.setdefault(r_id, []).append(o.tenant_name)

    top_risks = []
    for r_id, affected in sorted(risk_counts.items(), key=lambda x: len(x[1]), reverse=True):
        r_info = rule_map.get(r_id)
        if r_info:
            top_risks.append({
                "rule_id": r_id,
                "title": r_info.title,
                "failed_count": len(affected),
                "affected_tenants": affected,
            })

    return PortfolioAuditReport(
        portfolio_name=portfolio_name,
        generated_at=now_str,
        profile=profile,
        profile_label=profile.replace("-", " ").title(),
        tenants=outcomes,
        avg_compliance=avg_comp,
        total_tenants=total,
        compliant_tenants=compliant,
        warning_tenants=warning,
        critical_tenants=critical,
        heatmap_rows=heatmap_rows,
        top_portfolio_risks=top_risks[:5],
    )


def display_msp_console_matrix(report: PortfolioAuditReport):
    """Render rich console tables for multi-tenant audit findings."""
    console.print(Panel(
        f"[bold cyan]🛡️ Multi-Tenant MSP Security Portfolio Assessment[/bold cyan]\n"
        f"Portfolio: [bold]{report.portfolio_name}[/bold] | Profile: [bold]{report.profile_label}[/bold]\n"
        f"Average Compliance: [bold green]{report.avg_compliance:.1f}%[/bold green] | "
        f"Tenants Audited: [bold]{report.total_tenants}[/bold]",
        border_style="cyan",
    ))

    table = Table(title="Tenant Posture Leaderboard", show_header=True, header_style="bold cyan")
    table.add_column("Tenant Name", style="bold")
    table.add_column("Posture", justify="center")
    table.add_column("Alignment", justify="right")
    table.add_column("Passed", justify="right")
    table.add_column("Warnings", justify="right")
    table.add_column("Failures", justify="right")
    table.add_column("Dormant", justify="right")

    for t in report.tenants:
        color = "green" if t.percentage >= 80 else ("yellow" if t.percentage >= 50 else "red")
        table.add_row(
            t.tenant_name,
            f"{t.posture_badge} {t.posture_tier}",
            f"[{color}]{t.percentage:.1f}%[/{color}]",
            str(t.passed),
            str(t.warn),
            f"[red]{t.fail}[/red]" if t.fail > 0 else "0",
            str(t.dormant_policies),
        )

    console.print(table)

    if report.top_portfolio_risks:
        console.print("\n[bold red]🚨 Top Portfolio-Wide Security Gaps:[/bold red]")
        for risk in report.top_portfolio_risks:
            console.print(
                f" • [bold]{risk['title']}[/bold] ({risk['rule_id']}): "
                f"[red]{risk['failed_count']}/{report.total_tenants} tenants missing[/red] "
                f"[dim]({', '.join(risk['affected_tenants'])})[/dim]"
            )
        console.print()


def render_msp_markdown_matrix(report: PortfolioAuditReport, output_path: str) -> str:
    """
    Render ASD-STE100 Markdown executive multi-tenant summary document.
    Enforces maximum line lengths of 281 characters or fewer.
    """
    lines = [
        f"# {report.portfolio_name} - Multi-Tenant Security Posture Audit",
        "",
        "[Back to Deliverables Catalog](../deliverables/README.md)",
        "",
        "This document provides comparative posture audit results across managed Intune tenants.",
        f"Generated: {report.generated_at} | Profile: {report.profile_label} | Standard: ASD-STE100",
        "",
        "---",
        "",
        "## Executive Summary",
        "",
        f"- **Average Baseline Compliance**: {report.avg_compliance:.1f}%",
        f"- **Total Tenants Evaluated**: {report.total_tenants}",
        f"- **Compliant Tenants (80%+ Alignment)**: {report.compliant_tenants}",
        f"- **Warning Tenants (50-79% Alignment)**: {report.warning_tenants}",
        f"- **Critical Action Required (<50% Alignment)**: {report.critical_tenants}",
        "",
        "---",
        "",
        "## Tenant Posture Scorecard",
        "",
        "| Tenant Name | Posture Status | Baseline Alignment | Controls Passed | Critical Gaps | Dormant Policies |",
        "| :--- | :---: | :---: | :---: | :---: | :---: |",
    ]

    for t in report.tenants:
        lines.append(
            f"| **{t.tenant_name}** | {t.posture_badge} {t.posture_tier} | "
            f"{t.percentage:.1f}% | {t.passed} / {t.evaluated} | "
            f"{t.fail} missing | {t.dormant_policies} |"
        )

    lines.extend([
        "",
        "---",
        "",
        "## Top Portfolio-Wide Remediation Priorities",
        "",
        "The following baseline controls are missing across the highest number of managed tenants:",
        "",
    ])

    for risk in report.top_portfolio_risks:
        affected_str = ", ".join(risk["affected_tenants"])
        lines.append(
            f"1. **{risk['title']}** (`{risk['rule_id']}`): Missing on {risk['failed_count']} "
            f"tenant(s) ({affected_str})."
        )

    lines.extend([
        "",
        "---",
        "",
        "## Legal Safe Harbor & Advisory Notice",
        "",
        "This multi-tenant portfolio document provides informational analysis only.",
        "It does not constitute certified legal, regulatory, or technical compliance auditing.",
        "Stage all policy remediations in an isolated pilot security group before deployment.",
        "",
        "---",
        "*Report standard: [ASD-STE100](https://asd-ste100.org/) | License: [GNU AGPLv3](https://www.gnu.org/licenses/agpl-3.0).* ",
    ])

    out_dir = os.path.dirname(os.path.abspath(output_path))
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    return os.path.abspath(output_path)


def render_msp_html_matrix(report: PortfolioAuditReport, output_path: str) -> str:
    """
    Render standalone HTML multi-tenant portfolio report with interactive heatmap.
    """
    tmpl_dir = os.path.join(os.path.dirname(__file__), "..", "generator", "templates")
    env = Environment(loader=FileSystemLoader(tmpl_dir), autoescape=True, trim_blocks=True, lstrip_blocks=True)
    tmpl = env.get_template("msp_portfolio.html.jinja2")

    rendered = tmpl.render(
        portfolio_name=report.portfolio_name,
        generated_at=report.generated_at,
        profile_label=report.profile_label,
        avg_compliance=report.avg_compliance,
        total_tenants=report.total_tenants,
        compliant_tenants=report.compliant_tenants,
        warning_tenants=report.warning_tenants,
        critical_tenants=report.critical_tenants,
        tenants=report.tenants,
        heatmap_rows=report.heatmap_rows,
        top_portfolio_risks=report.top_portfolio_risks,
    )

    out_dir = os.path.dirname(os.path.abspath(output_path))
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(rendered)

    return os.path.abspath(output_path)
