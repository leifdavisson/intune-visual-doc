import os
import json
import pytest
from intune_visual_doc.generator.engine import DocGenerator
from intune_visual_doc.audit.drift import compare_with_backups
from intune_visual_doc.mock_data.samples import get_mock_policies, get_mock_audit_events


def test_generator_renders_markdown_tree(tmp_path):
    output_dir = tmp_path / "test_docs"
    generator = DocGenerator(output_dir=str(output_dir), unsanitize=False)

    policies = get_mock_policies()
    audit_events = get_mock_audit_events()

    summary = generator.render_all(
        policies=policies,
        audit_events=audit_events,
        generator_user="Test Admin",
    )

    assert os.path.exists(output_dir / "README.md")
    assert os.path.exists(output_dir / "TENANT_WARNINGS.md")
    assert os.path.exists(output_dir / "audit" / "ADMIN_AUDIT_LOG.md")
    assert summary["stats"]["total_policies"] == 5
    assert summary["stats"]["assigned_policies"] == 4
    assert summary["stats"]["unassigned_policies"] == 1


def test_generator_handles_null_targets_and_names(tmp_path):
    """Verify generator is null-safe when audit events or policies contain None."""
    output_dir = tmp_path / "test_null_safety"
    generator = DocGenerator(output_dir=str(output_dir), unsanitize=False)

    policies = [
        {
            "id": "null-pol-1",
            "name": None,
            "category": "configuration",
            "assignments": [],
            "settings": [],
            "raw": {},
        }
    ]
    audit_events = [
        {
            "id": "ev-1",
            "activity": None,
            "target": None,
            "actor": "admin@contoso.com",
            "timestamp": "2026-10-31T12:00:00Z",
            "status": "success",
        }
    ]

    summary = generator.render_all(
        policies=policies,
        audit_events=audit_events,
        generator_user="Test Admin",
    )
    assert os.path.exists(output_dir / "README.md")
    assert os.path.exists(output_dir / "TENANT_WARNINGS.md")
    assert summary["stats"]["total_policies"] == 1


def test_generator_sanitizes_raw_json_by_default(tmp_path):
    output_dir = tmp_path / "test_raw_sanitize"
    policies = [
        {
            "id": "pol-1",
            "name": "WiFi Profile",
            "category": "configuration",
            "category_label": "Configuration Template",
            "platform": "Windows 11",
            "assignments": [{"type": "Included", "target": "All Devices"}],
            "settings": [{"name": "wifiPresharedKey", "value": "PlainSecret99"}],
            "raw": {"id": "pol-1", "wifiPresharedKey": "PlainSecret99"},
        }
    ]
    generator = DocGenerator(output_dir=str(output_dir), unsanitize=False)
    generator.render_all(policies=policies, audit_events=[])

    raw_backup = json.loads((output_dir / "raw_json" / "configuration" / "wifi-profile.json").read_text())
    assert raw_backup["wifiPresharedKey"] == "[MASKED: ********]"
    md_text = (output_dir / "configuration" / "wifi-profile.md").read_text()
    assert "PlainSecret99" not in md_text


def test_drift_detector_finds_clean_and_modified_states(tmp_path):
    output_dir = tmp_path / "drift_docs"
    policies = get_mock_policies()
    generator = DocGenerator(output_dir=str(output_dir), unsanitize=False)
    generator.render_all(policies=policies, audit_events=[])

    # Zero drift right after generation
    assert compare_with_backups(get_mock_policies(), output_dir=str(output_dir)) == []

    # Mutate one raw property and verify Modified finding
    mutated = get_mock_policies()
    mutated[0]["raw"]["platforms"] = "windows10"
    findings = compare_with_backups(mutated, output_dir=str(output_dir))
    assert len(findings) == 1
    assert findings[0]["status"] == "Modified"


def test_build_blade_urls_uses_modern_ibiza_reactview_routes():
    from intune_visual_doc.visual.screenshot import build_blade_urls

    comp = build_blade_urls({"id": "c-1", "name": "Device Compliance", "category": "compliance"})
    assert "CompliancePolicyOverview.ReactView/policyId/c-1" in comp["overview"]

    sc = build_blade_urls({
        "id": "sc-1",
        "name": "Bitlocker",
        "category": "configuration",
        "category_label": "Settings Catalog",
        "assignments": [{"target": "All Devices"}],
        "raw": {"technologies": "mdm", "platforms": "windows10"},
    })
    assert "Microsoft_Intune_Workflows/PolicySummaryBlade/policyId/sc-1" in sc["overview"]

    tmpl = build_blade_urls({
        "id": "t-1",
        "name": "Block IE11",
        "category": "configuration",
        "category_label": "Configuration Template",
        "raw": {"@odata.type": "#microsoft.graph.windows10CustomConfiguration"},
    })
    assert "PolicySummaryReportBlade/policyId/t-1" in tmpl["overview"]

    app = build_blade_urls({"id": "a-1", "name": "Adobe Reader", "category": "apps"})
    assert "Microsoft_Intune_Apps/SettingsMenu/~/0/appId/a-1" in app["overview"]
    assert "Microsoft_Intune_Apps/SettingsMenu/~/1/appId/a-1" in app["properties"]

