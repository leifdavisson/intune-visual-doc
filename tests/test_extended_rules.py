"""
Unit tests for Extended Posture Audit Rule Packs (CIS v1.1.0 Deepening & Modern Baselines).
Licensed under GNU AGPLv3.
"""

import pytest
from intune_visual_doc.audit.rules import (
    _eval_cis_asr,
    _eval_enrollment_restrictions,
    _eval_edge_security,
    _eval_mam_app_protection,
    _eval_credential_guard,
)


def test_cis_asr_evaluator():
    """Test SEC-ASR-001: Pass when assigned, warn when unassigned, fail when absent."""
    meta = {"detected_categories": {"endpoint_security", "configuration"}}

    # Missing
    verdict_fail = _eval_cis_asr([], meta)
    assert verdict_fail.status == "FAIL"

    # Unassigned
    unassigned_policy = {
        "name": "Endpoint Security - Attack Surface Reduction",
        "category": "endpoint_security",
        "assignments": [],
        "settings": [{"name": "BlockCredentialStealingFromLSASS", "value": "1 (Block)"}],
    }
    verdict_warn = _eval_cis_asr([unassigned_policy], meta)
    assert verdict_warn.status == "WARN"

    # Assigned
    assigned_policy = {
        "name": "Endpoint Security - Attack Surface Reduction",
        "category": "endpoint_security",
        "assignments": [{"type": "Included", "target": "All Devices"}],
        "settings": [{"name": "BlockCredentialStealingFromLSASS", "value": "1 (Block)"}],
    }
    verdict_pass = _eval_cis_asr([assigned_policy], meta)
    assert verdict_pass.status == "PASS"


def test_enrollment_restrictions_evaluator():
    """Test SEC-ENR-001: Pass when personal Windows blocked, warn when unassigned, fail when missing."""
    meta = {"detected_categories": {"enrollment"}}

    # Missing
    verdict_fail = _eval_enrollment_restrictions([], meta)
    assert verdict_fail.status == "FAIL"

    # Permitted (not blocked)
    allow_policy = {
        "name": "Default Enrollment Restriction",
        "category": "enrollment",
        "assignments": [{"type": "Included", "target": "All Users"}],
        "settings": [{"name": "personalDeviceEnrollmentBlocked", "value": "False"}],
        "raw": {"platformRestrictions": {"personalDeviceEnrollmentBlocked": False}},
    }
    verdict_allow = _eval_enrollment_restrictions([allow_policy], meta)
    assert verdict_allow.status == "WARN"

    # Blocked and Assigned
    blocked_policy = {
        "name": "Block Personal Windows Devices",
        "category": "enrollment",
        "assignments": [{"type": "Included", "target": "All Users"}],
        "settings": [{"name": "personalDeviceEnrollmentBlocked", "value": "True"}],
        "raw": {"platformRestrictions": {"personalDeviceEnrollmentBlocked": True}},
    }
    verdict_pass = _eval_enrollment_restrictions([blocked_policy], meta)
    assert verdict_pass.status == "PASS"


def test_edge_security_evaluator():
    """Test SEC-EDGE-001: Pass when Edge SmartScreen enforced, warn when unassigned, fail when missing."""
    meta = {"detected_categories": {"configuration"}}

    # Missing
    verdict_fail = _eval_edge_security([], meta)
    assert verdict_fail.status == "FAIL"

    # Unassigned
    unassigned_policy = {
        "name": "Microsoft Edge Enterprise Security Baseline",
        "category": "configuration",
        "assignments": [],
        "settings": [{"name": "SmartScreenEnabled", "value": "True"}],
    }
    verdict_warn = _eval_edge_security([unassigned_policy], meta)
    assert verdict_warn.status == "WARN"

    # Assigned
    assigned_policy = {
        "name": "Microsoft Edge Enterprise Security Baseline",
        "category": "configuration",
        "assignments": [{"type": "Included", "target": "Staff Laptops"}],
        "settings": [{"name": "SmartScreenEnabled", "value": "True"}],
    }
    verdict_pass = _eval_edge_security([assigned_policy], meta)
    assert verdict_pass.status == "PASS"


def test_mam_app_protection_evaluator():
    """Test SEC-MAM-001: Pass when MAM protection assigned, warn when unassigned, fail when missing."""
    meta = {"detected_categories": {"apps"}}

    # Missing
    verdict_fail = _eval_mam_app_protection([], meta)
    assert verdict_fail.status == "FAIL"

    # Unassigned
    unassigned_policy = {
        "name": "M365 Apps DLP Protection Policy (iOS/Android)",
        "category": "apps",
        "assignments": [],
        "settings": [
            {"name": "allowedDataIngress", "value": "allApps"},
            {"name": "pinRequired", "value": "True"},
        ],
    }
    verdict_warn = _eval_mam_app_protection([unassigned_policy], meta)
    assert verdict_warn.status == "WARN"

    # Assigned
    assigned_policy = {
        "name": "M365 Apps DLP Protection Policy (iOS/Android)",
        "category": "apps",
        "assignments": [{"type": "Included", "target": "All Licensed Users"}],
        "settings": [
            {"name": "allowedDataIngress", "value": "allApps"},
            {"name": "pinRequired", "value": "True"},
        ],
    }
    verdict_pass = _eval_mam_app_protection([assigned_policy], meta)
    assert verdict_pass.status == "PASS"


def test_credential_guard_evaluator():
    """Test SEC-ID-003: Pass when Credential Guard assigned, warn when unassigned, fail when missing."""
    meta = {"detected_categories": {"configuration"}}

    # Missing
    verdict_fail = _eval_credential_guard([], meta)
    assert verdict_fail.status == "FAIL"

    # Assigned
    assigned_policy = {
        "name": "Device Guard & Credential Guard Baseline",
        "category": "configuration",
        "assignments": [{"type": "Included", "target": "Windows 11 Workstations"}],
        "settings": [
            {"name": "VirtualizationBasedSecurity", "value": "Enabled"},
            {"name": "CredentialGuard", "value": "EnabledWithUefiLock"},
        ],
    }
    verdict_pass = _eval_credential_guard([assigned_policy], meta)
    assert verdict_pass.status == "PASS"
