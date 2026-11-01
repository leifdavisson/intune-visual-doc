"""
Unit and integration tests for Microsoft Intune Security Posture & Best-Practice Audit.
Licensed under GNU AGPLv3.
"""

import os
import json
import pytest

from intune_visual_doc.audit.posture import (
    detect_backup_scope,
    load_policies_from_backup,
    evaluate_tenant_posture,
    render_audit_report,
)
from intune_visual_doc.audit.rules import AUDIT_RULES
from intune_visual_doc.mock_data.samples import get_mock_policies
from intune_visual_doc.audit.ste_linter import audit_text_ste


def test_audit_rules_registry():
    """Verify standard audit rules are registered and have necessary metadata."""
    assert len(AUDIT_RULES) >= 8
    rule_ids = [r.rule_id for r in AUDIT_RULES]
    assert "SEC-ENC-001" in rule_ids
    assert "SEC-AV-001" in rule_ids
    assert "SEC-FW-001" in rule_ids
    assert "SEC-UPD-001" in rule_ids
    assert "SEC-ID-001" in rule_ids
    assert "SEC-HYG-001" in rule_ids
    assert "STIG-ASR-001" in rule_ids


def test_evaluate_mock_policies_balanced():
    """Evaluate mock sample data under balanced profile."""
    policies = get_mock_policies()
    detected_cats = {p.get("category", "").lower() for p in policies}

    evaluation = evaluate_tenant_posture(
        policies=policies,
        profile="balanced",
        detected_categories=detected_cats,
    )

    stats = evaluation["stats"]
    assert stats["evaluated"] == 8
    assert stats["omitted"] == 0
    assert stats["passed"] == 2
    assert stats["warn"] == 4
    assert stats["fail"] == 2  # LAPS & WUfB missing in standard mock set
    assert evaluation["profile"] == "balanced"
    assert evaluation["posture_badge"] == "🔴"  # Baseline controls missing


def test_evaluate_domain_filtering():
    """Verify that specifying selected_domains filters active evaluation."""
    policies = get_mock_policies()
    evaluation = evaluate_tenant_posture(
        policies=policies,
        profile="balanced",
        selected_domains=["endpoint_encryption"],
    )

    stats = evaluation["stats"]
    assert stats["evaluated"] == 1
    assert stats["passed"] == 1
    assert stats["omitted"] == 7


def test_evaluate_mock_policies_strict_stig():
    """Evaluate mock sample data under strict-stig profile."""
    policies = get_mock_policies()
    detected_cats = {p.get("category", "").lower() for p in policies}

    evaluation = evaluate_tenant_posture(
        policies=policies,
        profile="strict-stig",
        detected_categories=detected_cats,
    )

    stats = evaluation["stats"]
    assert stats["evaluated"] == 9  # 8 balanced + 1 STIG rule
    stig_asr = next(r for r in evaluation["results"] if r.rule_id == "STIG-ASR-001")
    assert stig_asr.status == "FAIL"  # ASR not present in mock sample set


def test_partial_backup_omits_unexported_categories():
    """Verify that un-exported categories are labeled OMITTED and not penalized as failures."""
    # Only supply compliance policies
    compliance_only = [p for p in get_mock_policies() if p.get("category") == "compliance"]
    detected_cats = {"compliance"}

    evaluation = evaluate_tenant_posture(
        policies=compliance_only,
        profile="balanced",
        detected_categories=detected_cats,
    )

    results = evaluation["results"]
    omitted_rules = [r for r in results if r.status == "OMITTED"]

    # Update rings (configuration) and Tamper/LAPS (endpoint_security) should be omitted
    omitted_ids = {r.rule_id for r in omitted_rules}
    assert "SEC-UPD-001" in omitted_ids
    assert evaluation["stats"]["omitted"] > 0
    # Omitted rules must use the ⚪ badge
    for r in omitted_rules:
        assert r.badge == "⚪"
        assert "not evaluated" in r.observed_state.lower() or "not in backup" in r.observed_state.lower()


def test_detect_backup_scope_with_subdirs(tmp_path):
    """Verify detector correctly resolves category folders and policy counts."""
    run_dir = tmp_path / "run_20261101_120000"
    raw_dir = run_dir / "raw_json"
    comp_dir = raw_dir / "compliance"
    conf_dir = raw_dir / "configuration"

    comp_dir.mkdir(parents=True)
    conf_dir.mkdir(parents=True)

    with open(comp_dir / "policy1.json", "w", encoding="utf-8") as f:
        json.dump({"name": "Comp 1"}, f)
    with open(conf_dir / "policy2.json", "w", encoding="utf-8") as f:
        json.dump({"name": "Conf 2"}, f)

    scope = detect_backup_scope(str(run_dir))
    assert scope["is_valid"] is True
    assert scope["policy_count"] == 2
    assert "compliance" in scope["detected_categories"]
    assert "configuration" in scope["detected_categories"]
    assert "endpoint_security" not in scope["detected_categories"]


def test_load_policies_from_backup(tmp_path):
    """Verify loading raw JSON files and reconstructing policy objects."""
    run_dir = tmp_path / "run_test"
    raw_dir = run_dir / "raw_json" / "configuration"
    raw_dir.mkdir(parents=True)

    test_pol = {
        "id": "test-uuid-1",
        "displayName": "Test LAPS Policy",
        "description": "LAPS test configuration",
        "assignments": [{"target": {"groupId": "grp-1"}}],
        "settings": [{"name": "LapsAdminAccountName", "value": "LocalAdmin"}],
    }
    with open(raw_dir / "test-laps.json", "w", encoding="utf-8") as f:
        json.dump(test_pol, f)

    policies, scope = load_policies_from_backup(str(run_dir))
    assert len(policies) == 1
    p = policies[0]
    assert p["id"] == "test-uuid-1"
    assert p["name"] == "Test LAPS Policy"
    assert len(p["assignments"]) == 1
    assert p["category"] == "configuration"


def test_render_audit_report_content_and_ste(tmp_path):
    """Verify rendered AUDIT_RECOMMENDATIONS.md contains legal disclaimer and passes STE linting."""
    policies = get_mock_policies()
    evaluation = evaluate_tenant_posture(policies=policies, profile="balanced")

    out_file = tmp_path / "AUDIT_RECOMMENDATIONS.md"
    report_path = render_audit_report(
        evaluation=evaluation,
        output_path=str(out_file),
        generator_user="Unit Test Runner",
    )

    assert os.path.exists(report_path)
    with open(report_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Verify 4 legal disclaimer clauses
    assert "LEGAL SAFE HARBOR & ADVISORY NOTICE" in content
    assert "Non-Regulatory / Advisory Status" in content
    assert "Mandatory Pilot Staging Gate" in content
    assert "Operational Liability Boundary" in content
    assert "GNU Affero General Public License" in content

    # Verify executive scorecard sections
    assert "Executive Stop-Light Scorecard" in content
    assert "Leadership & CISO Review Questionnaire" in content

    # Verify STE compliance on generated report
    ste_issues = audit_text_ste(content)
    assert len(ste_issues) == 0


def test_firewall_rule_evaluates_compliance_active_firewall():
    """Verify Graph activeFirewallRequired compliance triggers WARN, not FAIL."""
    from intune_visual_doc.audit.rules import _eval_host_firewall

    comp_policy = {
        "name": "Device Compliance",
        "category": "compliance",
        "assignments": [{"type": "Included", "target": "Target Group"}],
        "settings": [
            {"name": "activeFirewallRequired", "full_definition": "activeFirewallRequired", "value": "True"}
        ]
    }
    meta = {"detected_categories": {"compliance"}}
    verdict = _eval_host_firewall([comp_policy], meta)
    assert verdict.status == "WARN"
    assert verdict.badge == "🟡"
    assert "Checked by compliance policy" in verdict.observed_state


def test_firewall_rule_evaluates_baseline_enforcers():
    """Verify baseline or defender policies with enablefirewall trigger PASS."""
    from intune_visual_doc.audit.rules import _eval_host_firewall

    baseline = {
        "name": "Windows Baseline - Preconfigured Policy",
        "category": "configuration",
        "assignments": [{"type": "Included", "target": "All Devices"}],
        "settings": [
            {"name": "enablefirewall", "full_definition": "enablefirewall", "value": "true"},
            {"name": "defaultinboundaction", "full_definition": "defaultinboundaction", "value": "1"},
        ]
    }
    meta = {"detected_categories": {"configuration"}}
    verdict = _eval_host_firewall([baseline], meta)
    assert verdict.status == "PASS"
    assert verdict.badge == "🟢"
    assert "Host firewall policy active" in verdict.observed_state


def test_load_policies_recovers_from_markdown_when_raw_masked(tmp_path):
    """Verify loading from backup recovers unmasked names from markdown when raw JSON is masked."""
    run_dir = tmp_path / "run_masked"
    raw_dir = run_dir / "raw_json" / "configuration"
    raw_dir.mkdir(parents=True)
    conf_dir = run_dir / "configuration"
    conf_dir.mkdir(parents=True)

    # Write masked raw JSON
    raw_pol = {
        "id": "pol-1",
        "name": "Windows Baseline",
        "assignments": [{"type": "Included", "target": "All Devices"}],
        "settings": [
            {"settingDefinitionId": "[MASKED: devi...wall]", "choiceSettingValue": {"value": "[MASKED: devi...ll_1]"}}
        ]
    }
    with open(raw_dir / "windows-baseline.json", "w", encoding="utf-8") as f:
        json.dump(raw_pol, f)

    # Write markdown file with unmasked table
    md_content = """# Windows Baseline

## 3. Configured Settings

| Setting Name | Configured Value | Status |
| :--- | :--- | :--- |
| `enablefirewall` | **true** | Configured |
| `defaultinboundaction` | **1** | Configured |
"""
    with open(conf_dir / "windows-baseline.md", "w", encoding="utf-8") as f:
        f.write(md_content)

    policies, scope = load_policies_from_backup(str(run_dir))
    assert len(policies) == 1
    p_settings = policies[0]["settings"]
    names = [s["name"] for s in p_settings]
    assert "enablefirewall" in names
    assert "defaultinboundaction" in names
