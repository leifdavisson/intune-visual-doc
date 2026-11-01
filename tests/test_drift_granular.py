"""
Unit tests for Granular Configuration Drift Detection and Visual Drift HTML Report.
Licensed under GNU AGPLv3.
"""

import os
import json
import tempfile
import pytest

from intune_visual_doc.audit.drift import (
    SettingDiff,
    PolicyDiff,
    compare_policies_granular,
    compare_backup_runs,
    render_drift_html_report,
)


def test_compare_policies_identical():
    """Verify identical policies report Unchanged with zero setting diffs."""
    p1 = {
        "id": "pol-1",
        "displayName": "BitLocker Enforced",
        "category": "Endpoint Security",
        "settings": {"RequireDeviceEncryption": True, "EncryptionMethod": "XTS-AES-256"},
        "raw": {"id": "pol-1", "name": "BitLocker Enforced", "settings": {"enc": 1}},
    }
    p2 = {
        "id": "pol-1",
        "displayName": "BitLocker Enforced",
        "category": "Endpoint Security",
        "settings": {"RequireDeviceEncryption": True, "EncryptionMethod": "XTS-AES-256"},
        "raw": {"id": "pol-1", "name": "BitLocker Enforced", "settings": {"enc": 1}},
    }

    diffs = compare_policies_granular([p1], [p2])
    assert len(diffs) == 1
    assert diffs[0].status == "Unchanged"
    assert len(diffs[0].setting_diffs) == 0


def test_compare_policies_added_and_removed():
    """Verify added and removed policies are correctly detected."""
    baseline = [
        {
            "id": "pol-old",
            "displayName": "Old WiFi Profile",
            "category": "Devices > Configuration",
            "settings": {"SSID": "CorpNet"},
        }
    ]
    target = [
        {
            "id": "pol-new",
            "displayName": "New 802.1X Profile",
            "category": "Devices > Configuration",
            "settings": {"SSID": "SecureCorp"},
        }
    ]

    diffs = compare_policies_granular(baseline, target)
    assert len(diffs) == 2

    status_map = {d.name: d.status for d in diffs}
    assert status_map["Old WiFi Profile"] == "Removed"
    assert status_map["New 802.1X Profile"] == "Added"


def test_compare_policies_setting_diffs():
    """Verify granular setting diffs: added, removed, and modified setting values."""
    baseline_policy = {
        "id": "pol-fw",
        "displayName": "Host Firewall Rules",
        "category": "Endpoint Security",
        "settings": {
            "DomainFirewallEnabled": True,
            "PrivateFirewallEnabled": True,
            "LegacyRule": "Deprecated",
        },
        "raw": {"version": 1},
    }
    target_policy = {
        "id": "pol-fw",
        "displayName": "Host Firewall Rules",
        "category": "Endpoint Security",
        "settings": {
            "DomainFirewallEnabled": True,
            "PrivateFirewallEnabled": False,  # modified
            "PublicFirewallEnabled": True,    # added
            # LegacyRule removed
        },
        "raw": {"version": 2},
    }

    diffs = compare_policies_granular([baseline_policy], [target_policy])
    assert len(diffs) == 1
    p_diff = diffs[0]
    assert p_diff.status == "Modified"
    assert len(p_diff.setting_diffs) == 3

    diff_map = {sd.name: sd for sd in p_diff.setting_diffs}
    assert "PrivateFirewallEnabled" in diff_map
    assert diff_map["PrivateFirewallEnabled"].change_type == "Modified"
    assert diff_map["PrivateFirewallEnabled"].old_value == "True"
    assert diff_map["PrivateFirewallEnabled"].new_value == "False"

    assert "PublicFirewallEnabled" in diff_map
    assert diff_map["PublicFirewallEnabled"].change_type == "Added"
    assert diff_map["PublicFirewallEnabled"].old_value is None
    assert diff_map["PublicFirewallEnabled"].new_value is True

    assert "LegacyRule" in diff_map
    assert diff_map["LegacyRule"].change_type == "Removed"
    assert diff_map["LegacyRule"].old_value == "Deprecated"
    assert diff_map["LegacyRule"].new_value is None


def test_compare_backup_runs_offline():
    """Verify comparing two backup directories with raw_json payloads."""
    with tempfile.TemporaryDirectory() as temp_root:
        base_dir = os.path.join(temp_root, "run_base")
        base_raw = os.path.join(base_dir, "raw_json")
        os.makedirs(base_raw, exist_ok=True)

        target_dir = os.path.join(temp_root, "run_target")
        target_raw = os.path.join(target_dir, "raw_json")
        os.makedirs(target_raw, exist_ok=True)

        p1_base = {
            "id": "pol-10",
            "displayName": "Defender Baseline",
            "category_label": "Endpoint Security",
            "settings": {"RealTimeProtection": True, "SignatureAge": 7},
        }
        with open(os.path.join(base_raw, "defender-baseline.json"), "w", encoding="utf-8") as f:
            json.dump(p1_base, f)

        p1_target = {
            "id": "pol-10",
            "displayName": "Defender Baseline",
            "category_label": "Endpoint Security",
            "settings": {"RealTimeProtection": True, "SignatureAge": 1},
        }
        with open(os.path.join(target_raw, "defender-baseline.json"), "w", encoding="utf-8") as f:
            json.dump(p1_target, f)

        report = compare_backup_runs(base_dir, target_dir)
        assert report["stats"]["modified"] == 1
        assert report["stats"]["added"] == 0
        assert report["stats"]["removed"] == 0
        assert report["stats"]["total_setting_changes"] == 1


def test_render_drift_html_report():
    """Verify rendering standalone visual drift HTML report."""
    setting_diff = SettingDiff(
        name="DefaultInboundAction",
        full_definition="DefaultInboundAction",
        change_type="Modified",
        old_value="0 (Allow)",
        new_value="1 (Block)",
    )
    p_diff = PolicyDiff(
        name="Firewall Profile",
        category="Endpoint Security",
        slug="endpoint_security/firewall-profile",
        status="Modified",
        details="1 setting changes",
        setting_diffs=[setting_diff],
    )

    report_data = {
        "baseline_label": "2026-11-01_100000",
        "target_label": "2026-11-01_110000",
        "baseline_dir": "/tmp/b",
        "target_dir": "/tmp/t",
        "diffs": [p_diff],
        "stats": {
            "total_policies_target": 1,
            "added": 0,
            "removed": 0,
            "modified": 1,
            "unchanged": 0,
            "total_setting_changes": 1,
        },
    }

    with tempfile.TemporaryDirectory() as tmp_dir:
        out_html = os.path.join(tmp_dir, "DRIFT_REPORT.html")
        rendered = render_drift_html_report(report_data, out_html)

        assert os.path.exists(rendered)
        with open(rendered, "r", encoding="utf-8") as f:
            content = f.read()

        assert "<!DOCTYPE html>" in content
        assert "Intune Configuration Drift Report" in content
        assert "Firewall Profile" in content
        assert "DefaultInboundAction" in content
        assert "1 (Block)" in content
        assert "0 (Allow)" in content


def test_drift_html_secret_sanitization():
    """Verify secrets are masked by default and only revealed with unsanitize=True."""
    p_base = {
        "id": "wifi-01",
        "name": "Corporate Wi-Fi Profile",
        "category": "configuration",
        "settings": [
            {"name": "PreSharedKey", "value": "SuperSecretWifiPassphrase123"},
        ],
    }
    p_target = {
        "id": "wifi-01",
        "name": "Corporate Wi-Fi Profile",
        "category": "configuration",
        "settings": [
            {"name": "PreSharedKey", "value": "RotatedSecretKey4567890"},
        ],
    }

    # Default: unsanitize=False -> masked
    diffs_masked = compare_policies_granular([p_base], [p_target], unsanitize=False)
    assert len(diffs_masked) == 1
    sd_masked = diffs_masked[0].setting_diffs[0]
    assert "[MASKED" in str(sd_masked.old_value)
    assert "[MASKED" in str(sd_masked.new_value)
    assert "SuperSecretWifiPassphrase123" not in str(sd_masked.old_value)
    assert "RotatedSecretKey4567890" not in str(sd_masked.new_value)

    # With unsanitize=True -> preserved
    diffs_raw = compare_policies_granular([p_base], [p_target], unsanitize=True)
    assert len(diffs_raw) == 1
    sd_raw = diffs_raw[0].setting_diffs[0]
    assert sd_raw.old_value == "SuperSecretWifiPassphrase123"
    assert sd_raw.new_value == "RotatedSecretKey4567890"

    # HTML render masking test
    report_data = {
        "baseline_label": "base",
        "target_label": "target",
        "baseline_dir": "/tmp/b",
        "target_dir": "/tmp/t",
        "diffs": diffs_masked,
        "stats": {
            "total_policies_target": 1,
            "added": 0,
            "removed": 0,
            "modified": 1,
            "unchanged": 0,
            "total_setting_changes": 1,
        },
    }
    with tempfile.TemporaryDirectory() as tmp_dir:
        out_html = os.path.join(tmp_dir, "DRIFT_REPORT.html")
        render_drift_html_report(report_data, out_html, unsanitize=False)
        with open(out_html, "r", encoding="utf-8") as f:
            html_text = f.read()

        assert "[MASKED" in html_text
        assert "SuperSecretWifiPassphrase123" not in html_text
        assert "RotatedSecretKey4567890" not in html_text

