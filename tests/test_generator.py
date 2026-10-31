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
    assert os.path.exists(output_dir / "audit" / "ADMIN_AUDIT_LOG.md")
    assert summary["stats"]["total_policies"] == 5
    assert summary["stats"]["assigned_policies"] == 4
    assert summary["stats"]["unassigned_policies"] == 1


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
