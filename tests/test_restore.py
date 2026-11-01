"""
Unit tests for the standalone Intune restore utility (scripts/intune_restore.py).
Tests safety gates: assignment stripping, metadata scrubbing, masking sentinel, and dry run.
Licensed under GNU AGPLv3.
"""

import os
import sys
import json
import pytest

sys.path.insert(0, os.path.abspath("."))

from scripts.intune_restore import (
    scan_for_masked_values,
    scrub_policy_payload,
    detect_target_endpoint,
    extract_policy_name,
    set_policy_name,
    execute_restore,
)


def test_scan_for_masked_values_detects_placeholders():
    data = {
        "displayName": "Staff Wi-Fi",
        "preSharedKey": "[SANITIZED: Wi-Fi Pre-Shared Key]",
        "nested": {
            "secret": "[MASKED: ********]",
            "normal": "value",
        },
        "list": ["safe", "[MASKED: 1234]"],
    }
    findings = scan_for_masked_values(data)
    assert len(findings) == 3
    paths = [f[0] for f in findings]
    assert "preSharedKey" in paths
    assert "nested.secret" in paths
    assert "list[1]" in paths


def test_scan_for_masked_values_passes_clean_data():
    data = {
        "displayName": "Clean Policy",
        "version": 1,
        "settings": [{"key": "firewallEnabled", "value": True}],
    }
    findings = scan_for_masked_values(data)
    assert len(findings) == 0


def test_scrub_policy_payload_removes_server_metadata():
    payload = {
        "id": "abc-123",
        "@odata.context": "https://graph.microsoft.com/beta/$metadata",
        "@odata.etag": "W/12345",
        "createdDateTime": "2026-01-01T00:00:00Z",
        "lastModifiedDateTime": "2026-02-01T00:00:00Z",
        "version": 4,
        "displayName": "Test Policy",
        "passwordRequired": True,
    }
    cleaned, stripped = scrub_policy_payload(payload, preserve_assignments=False)
    assert "id" not in cleaned
    assert "@odata.context" not in cleaned
    assert "createdDateTime" not in cleaned
    assert "displayName" in cleaned
    assert cleaned["passwordRequired"] is True
    assert "id" in stripped
    assert "version" in stripped


def test_scrub_policy_payload_strips_assignments_by_default():
    payload = {
        "displayName": "Test Policy",
        "assignments": [
            {"target": {"groupId": "grp-123"}}
        ],
        "deviceStatuses": [{"status": "compliant"}],
    }
    cleaned, stripped = scrub_policy_payload(payload, preserve_assignments=False)
    assert "assignments" not in cleaned
    assert "deviceStatuses" not in cleaned
    assert "assignments" in stripped


def test_scrub_policy_payload_preserve_assignments_when_flagged():
    payload = {
        "displayName": "Test Policy",
        "assignments": [
            {"target": {"groupId": "grp-123"}}
        ],
    }
    cleaned, stripped = scrub_policy_payload(payload, preserve_assignments=True)
    assert "assignments" in cleaned
    assert "assignments" not in stripped


def test_detect_target_endpoint():
    assert detect_target_endpoint({"@odata.type": "#microsoft.graph.windows10CompliancePolicy"}) == "/deviceManagement/deviceCompliancePolicies"
    assert detect_target_endpoint({"@odata.type": "#microsoft.graph.deviceManagementConfigurationPolicy"}) == "/deviceManagement/configurationPolicies"
    assert detect_target_endpoint({"@odata.type": "#microsoft.graph.windows10GeneralConfiguration"}) == "/deviceManagement/deviceConfigurations"
    assert detect_target_endpoint({"fileName": "script.ps1", "scriptContent": "VGVzdA=="}) == "/deviceManagement/deviceManagementScripts"
    assert detect_target_endpoint({"@odata.type": "#microsoft.graph.win32LobApp"}) == "/deviceAppManagement/mobileApps"


def test_name_extraction_and_update():
    payload = {"displayName": "Old Name"}
    assert extract_policy_name(payload) == "Old Name"
    set_policy_name(payload, "New Name")
    assert payload["displayName"] == "New Name"


def test_execute_restore_dry_run_success(tmp_path):
    policy_file = tmp_path / "valid_policy.json"
    data = {
        "@odata.type": "#microsoft.graph.windows10CompliancePolicy",
        "displayName": "Lab Computers Compliance",
        "bitLockerEnabled": True,
        "assignments": [{"id": "123"}],
    }
    policy_file.write_text(json.dumps(data))

    success = execute_restore(str(policy_file), dry_run=True)
    assert success is True


def test_execute_restore_masked_rejection(tmp_path):
    policy_file = tmp_path / "masked_policy.json"
    data = {
        "@odata.type": "#microsoft.graph.windows10CompliancePolicy",
        "displayName": "Sanitized Policy",
        "passwordRequiredType": "[MASKED: ********]",
    }
    policy_file.write_text(json.dumps(data))

    success = execute_restore(str(policy_file), dry_run=True)
    assert success is False
