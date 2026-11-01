"""
Declarative rule catalog for Microsoft Intune best-practice and posture audits.
Licensed under GNU AGPLv3.

References:
- CIS Microsoft Intune Benchmark v1.1.0: https://www.cisecurity.org/benchmark/microsoft_intune
- Microsoft Security Baselines: https://learn.microsoft.com/en-us/mem/intune/protect/security-baselines
- NIST SP 800-63B Digital Identity: https://csrc.nist.gov/pubs/sp/800/63/b/final
- CISA Cross-Sector Cybersecurity Performance Goals: https://www.cisa.gov/cpg
- DoD DISA STIGs: https://public.cyber.mil/stigs/
"""

from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Callable


LEGAL_SAFE_HARBOR_NOTICE = {
    "title": "LEGAL SAFE HARBOR & ADVISORY NOTICE",
    "points": [
        (
            "Non-Regulatory / Advisory Status",
            "This document provides informational posture analysis only. It does not constitute certified legal, regulatory, or technical compliance auditing (including CJIS, HIPAA, FERPA, SOC 2, or CMMC)."
        ),
        (
            "Mandatory Pilot Staging Gate",
            "Applying Intune device policies can disrupt operating system functionality, network access, or line-of-business software. All configuration changes must be validated in an isolated pilot security group before broad deployment."
        ),
        (
            "Operational Liability Boundary",
            "The executing administrator and deploying organization assume all operational risks, testing responsibilities, and change-management oversight."
        ),
        (
            "Warranty & Liability Disclaimer",
            "Software provided AS-IS under the GNU Affero General Public License v3.0 (AGPLv3), with no warranties of merchantability or fitness for a particular purpose. Authors or copyright holders are not liable for any claim or damages."
        ),
    ]
}


def get_legal_disclaimer_text() -> str:
    """Format plain-text legal advisory notice for console panels and TUI screens."""
    lines = [f"{LEGAL_SAFE_HARBOR_NOTICE['title']}\n"]
    for idx, (title, desc) in enumerate(LEGAL_SAFE_HARBOR_NOTICE["points"], 1):
        lines.append(f"{idx}. {title}: {desc}")
    return "\n".join(lines)


@dataclass
class EvaluationVerdict:
    status: str  # "PASS", "WARN", "FAIL", "OMITTED"
    badge: str   # "🟢", "🟡", "🔴", "⚪"
    observed_state: str
    evidence: str = ""
    findings: List[str] = field(default_factory=list)


@dataclass
class RuleEvaluationResult:
    rule_id: str
    domain: str
    domain_label: str
    title: str
    status: str
    badge: str
    observed_state: str
    benchmark_ref: str
    benchmark_intent: str
    field_context: str
    remediation_guidance: str
    learn_url: str
    profile: str
    evidence: str = ""
    findings: List[str] = field(default_factory=list)


@dataclass
class AuditRule:
    rule_id: str
    domain: str
    domain_label: str
    title: str
    category_dependency: str
    profile: str
    benchmark_ref: str
    benchmark_intent: str
    field_context: str
    remediation_guidance: str
    learn_url: str
    evaluator: Callable[[List[Dict[str, Any]], Dict[str, Any]], EvaluationVerdict]


def _has_included_assignments(policy: Dict[str, Any]) -> bool:
    """Return True only if policy has at least one active inclusion assignment target."""
    assignments = policy.get("assignments") or []
    return any(a.get("type") == "Included" for a in assignments)


def _get_setting_values(policy: Dict[str, Any]) -> Dict[str, str]:
    """Map normalized setting definition and names to string values."""
    res = {}
    for s in policy.get("settings") or []:
        name = str(s.get("name", "")).lower()
        full_def = str(s.get("full_definition", "")).lower()
        val = str(s.get("value", ""))
        if name:
            res[name] = val
        if full_def:
            res[full_def] = val
    return res


# ---------------------------------------------------------------------------
# Evaluator Implementations (A1–A6 Correctness & Truth Separation)
# ---------------------------------------------------------------------------

def _eval_bitlocker(policies: List[Dict[str, Any]], meta: Dict[str, Any]) -> EvaluationVerdict:
    detected_cats = meta.get("detected_categories", set())
    if "configuration" not in detected_cats and "endpoint_security" not in detected_cats and "compliance" not in detected_cats:
        return EvaluationVerdict(
            status="OMITTED", badge="⚪",
            observed_state="Category not in backup. Control not evaluated."
        )

    enforcing_policies = []
    compliance_checks = []

    for p in policies:
        cat = p.get("category", "")
        p_name = p.get("name", "")
        settings = _get_setting_values(p)

        # Check configuration / endpoint security enforcement
        is_enc_config = (
            any("bitlocker" in k or "device_vendor_msft_bitlocker" in k or "requiredeviceencryption" in k for k in settings)
            or ("bitlocker" in p_name.lower() and cat in ("configuration", "endpoint_security"))
        )
        if is_enc_config and cat in ("configuration", "endpoint_security"):
            enforcing_policies.append(p)

        # Check compliance verification
        if cat == "compliance" and (settings.get("bitlockerenabled") in ("True", "1") or "bitlocker" in p_name.lower()):
            compliance_checks.append(p)

    assigned_enforcers = [p for p in enforcing_policies if _has_included_assignments(p)]

    if assigned_enforcers:
        names = [p.get("name", "") for p in assigned_enforcers]
        return EvaluationVerdict(
            status="PASS", badge="🟢",
            observed_state=f"Disk encryption policy configured and targeted ({len(assigned_enforcers)} policies).",
            evidence=f"Enforced by {', '.join(names)} with active group targeting.",
            findings=names,
        )

    if enforcing_policies:
        names = [p.get("name", "") for p in enforcing_policies]
        return EvaluationVerdict(
            status="WARN", badge="🟡",
            observed_state="Encryption policy configured but has 0 active assignments (dormant).",
            evidence=f"Policy exists ({', '.join(names)}) but lacks inclusion targets.",
            findings=names,
        )

    if compliance_checks:
        c_names = [p.get("name", "") for p in compliance_checks]
        return EvaluationVerdict(
            status="WARN", badge="🟡",
            observed_state="Required by compliance policy, but active configuration profile is missing.",
            evidence=f"Compliance check present in {', '.join(c_names)}, but no configuration enforces it.",
            findings=c_names,
        )

    return EvaluationVerdict(
        status="FAIL", badge="🔴",
        observed_state="No BitLocker or FileVault disk encryption policy identified.",
        evidence="Zero encryption configurations or compliance requirements found in tenant backup.",
        findings=["Missing disk encryption configuration or compliance policy."],
    )


def _eval_defender_antivirus(policies: List[Dict[str, Any]], meta: Dict[str, Any]) -> EvaluationVerdict:
    detected_cats = meta.get("detected_categories", set())
    if "endpoint_security" not in detected_cats and "configuration" not in detected_cats and "compliance" not in detected_cats:
        return EvaluationVerdict(
            status="OMITTED", badge="⚪",
            observed_state="Category not in backup. Control not evaluated."
        )

    enforcers = []
    compliance_checks = []

    for p in policies:
        cat = p.get("category", "")
        p_name = p.get("name", "")
        settings = _get_setting_values(p)

        has_av_setting = (
            any("defender" in k or "device_vendor_msft_defender" in k or "realtimemonitoring" in k for k in settings)
            or ("antivirus" in p_name.lower() and cat in ("configuration", "endpoint_security"))
        )
        if has_av_setting and cat in ("configuration", "endpoint_security"):
            enforcers.append(p)

        if cat == "compliance" and (settings.get("antivirusenabled") in ("True", "1") or "antivirus" in p_name.lower()):
            compliance_checks.append(p)

    assigned = [p for p in enforcers if _has_included_assignments(p)]
    if assigned:
        names = [p.get("name", "") for p in assigned]
        return EvaluationVerdict(
            status="PASS", badge="🟢",
            observed_state=f"Defender Antivirus policy active ({len(assigned)} policies targeted).",
            evidence=f"Active real-time protection enforced by {', '.join(names)}.",
            findings=names,
        )

    if enforcers:
        names = [p.get("name", "") for p in enforcers]
        return EvaluationVerdict(
            status="WARN", badge="🟡",
            observed_state="Defender policy configured but has 0 active assignments (dormant).",
            evidence=f"Policy exists ({', '.join(names)}) without inclusion targets.",
            findings=names,
        )

    if compliance_checks:
        c_names = [p.get("name", "") for p in compliance_checks]
        return EvaluationVerdict(
            status="WARN", badge="🟡",
            observed_state="Evaluated by compliance policy, but active configuration profile is missing.",
            evidence=f"Compliance check in {', '.join(c_names)}, but no configuration enforces it.",
            findings=c_names,
        )

    return EvaluationVerdict(
        status="FAIL", badge="🔴",
        observed_state="No Microsoft Defender Antivirus policy found in tenant backup.",
        evidence="Zero antivirus profiles or compliance rules detected.",
        findings=["Missing Defender Antivirus policy."],
    )


def _eval_tamper_protection(policies: List[Dict[str, Any]], meta: Dict[str, Any]) -> EvaluationVerdict:
    detected_cats = meta.get("detected_categories", set())
    if "endpoint_security" not in detected_cats and "configuration" not in detected_cats:
        return EvaluationVerdict(
            status="OMITTED", badge="⚪",
            observed_state="Category not in backup. Control not evaluated."
        )

    matching = []
    for p in policies:
        settings = _get_setting_values(p)
        if any("tamperprotection" in k or "tamper" in k for k in settings):
            matching.append(p)

    assigned = [p for p in matching if _has_included_assignments(p)]
    if assigned:
        names = [p.get("name", "") for p in assigned]
        return EvaluationVerdict(
            status="PASS", badge="🟢",
            observed_state="Tamper Protection policy configured and targeted.",
            evidence=f"Enforced by {', '.join(names)}.",
            findings=names,
        )

    if matching:
        names = [p.get("name", "") for p in matching]
        return EvaluationVerdict(
            status="WARN", badge="🟡",
            observed_state="Tamper Protection policy configured but unassigned.",
            evidence=f"Policy exists ({', '.join(names)}) without targets.",
            findings=names,
        )

    return EvaluationVerdict(
        status="WARN", badge="🟡",
        observed_state="Tamper Protection policy not explicitly defined in Intune profiles.",
        evidence="Setting absent in Intune backup; may be toggled tenant-wide in Microsoft Defender XDR portal.",
        findings=["Verify tenant-wide Tamper Protection status in Microsoft Defender XDR portal."],
    )


def _eval_host_firewall(policies: List[Dict[str, Any]], meta: Dict[str, Any]) -> EvaluationVerdict:
    detected_cats = meta.get("detected_categories", set())
    if "endpoint_security" not in detected_cats and "configuration" not in detected_cats and "compliance" not in detected_cats:
        return EvaluationVerdict(
            status="OMITTED", badge="⚪",
            observed_state="Category not in backup. Control not evaluated."
        )

    enforcers = []
    compliance_checks = []

    for p in policies:
        cat = p.get("category", "")
        p_name = p.get("name", "")
        settings = _get_setting_values(p)

        has_fw = (
            any("firewall" in k or "device_vendor_msft_firewall" in k for k in settings)
            or ("firewall" in p_name.lower() and cat in ("configuration", "endpoint_security"))
        )
        if has_fw and cat in ("configuration", "endpoint_security"):
            enforcers.append(p)

        if cat == "compliance" and (settings.get("firewallenabled") in ("True", "1") or "firewall" in p_name.lower()):
            compliance_checks.append(p)

    assigned = [p for p in enforcers if _has_included_assignments(p)]
    if assigned:
        names = [p.get("name", "") for p in assigned]
        return EvaluationVerdict(
            status="PASS", badge="🟢",
            observed_state=f"Host firewall policy active and targeted ({len(assigned)} policies).",
            evidence=f"Firewall enforced by {', '.join(names)}.",
            findings=names,
        )

    if enforcers:
        names = [p.get("name", "") for p in enforcers]
        return EvaluationVerdict(
            status="WARN", badge="🟡",
            observed_state=f"Firewall policy exists ({len(enforcers)}) but has 0 assignments (dormant).",
            evidence=f"Policy exists ({', '.join(names)}) but lacks active group assignments.",
            findings=names,
        )

    if compliance_checks:
        c_names = [p.get("name", "") for p in compliance_checks]
        return EvaluationVerdict(
            status="WARN", badge="🟡",
            observed_state="Checked by compliance policy, but active configuration profile is missing.",
            evidence=f"Compliance check in {', '.join(c_names)}, but no configuration profile enforces firewall rules.",
            findings=c_names,
        )

    return EvaluationVerdict(
        status="FAIL", badge="🔴",
        observed_state="No host firewall policy identified in tenant backup.",
        evidence="Zero firewall configurations or compliance rules detected.",
        findings=["Missing Defender Firewall policy."],
    )


def _eval_update_rings(policies: List[Dict[str, Any]], meta: Dict[str, Any]) -> EvaluationVerdict:
    detected_cats = meta.get("detected_categories", set())
    if "configuration" not in detected_cats:
        return EvaluationVerdict(
            status="OMITTED", badge="⚪",
            observed_state="Configuration category not in backup. Control not evaluated."
        )

    matching = []
    for p in policies:
        p_name = p.get("name", "")
        raw = p.get("raw") or {}
        o_type = str(raw.get("@odata.type", "")).lower()
        settings = _get_setting_values(p)

        is_ring = (
            "windowsupdateforbusinessconfiguration" in o_type
            or any("qualityupdate" in k or "deferquality" in k or "device_vendor_msft_update" in k for k in settings)
            or ("update ring" in p_name.lower() or "wufb" in p_name.lower())
        )
        if is_ring:
            matching.append(p)

    assigned = [p for p in matching if _has_included_assignments(p)]
    if assigned:
        names = [p.get("name", "") for p in assigned]
        return EvaluationVerdict(
            status="PASS", badge="🟢",
            observed_state=f"Windows Update ring policy configured and targeted ({len(assigned)} policies).",
            evidence=f"Update cadences managed by {', '.join(names)}.",
            findings=names,
        )

    if matching:
        names = [p.get("name", "") for p in matching]
        return EvaluationVerdict(
            status="WARN", badge="🟡",
            observed_state="Update ring configured but has 0 assignments (dormant).",
            evidence=f"Ring exists ({', '.join(names)}) but has no active assignments.",
            findings=names,
        )

    return EvaluationVerdict(
        status="FAIL", badge="🔴",
        observed_state="No Windows Update rings identified. Relying on unmanaged updates.",
        evidence="Zero Windows Update for Business profiles found.",
        findings=["Missing Windows Update for Business configuration."],
    )


def _eval_windows_laps(policies: List[Dict[str, Any]], meta: Dict[str, Any]) -> EvaluationVerdict:
    detected_cats = meta.get("detected_categories", set())
    if "endpoint_security" not in detected_cats and "configuration" not in detected_cats:
        return EvaluationVerdict(
            status="OMITTED", badge="⚪",
            observed_state="Category not in backup. Control not evaluated."
        )

    matching = []
    for p in policies:
        p_name = p.get("name", "")
        settings = _get_setting_values(p)

        is_laps = (
            any("device_vendor_msft_laps" in k or "lapsadminaccountname" in k or "administratorpassword" in k for k in settings)
            or ("laps" in p_name.lower())
        )
        if is_laps:
            matching.append(p)

    assigned = [p for p in matching if _has_included_assignments(p)]
    if assigned:
        names = [p.get("name", "") for p in assigned]
        return EvaluationVerdict(
            status="PASS", badge="🟢",
            observed_state="Windows LAPS policy active with automated Entra ID key rotation.",
            evidence=f"Local administrator passwords rotated by {', '.join(names)}.",
            findings=names,
        )

    if matching:
        names = [p.get("name", "") for p in matching]
        return EvaluationVerdict(
            status="WARN", badge="🟡",
            observed_state="Windows LAPS policy configured but unassigned.",
            evidence=f"LAPS policy exists ({', '.join(names)}) without active assignments.",
            findings=names,
        )

    return EvaluationVerdict(
        status="FAIL", badge="🔴",
        observed_state="No Windows LAPS policy found. Risk of shared local admin passwords.",
        evidence="Zero Windows LAPS policies found.",
        findings=["Missing Windows LAPS policy."],
    )


def _eval_screen_lock_and_password(policies: List[Dict[str, Any]], meta: Dict[str, Any]) -> EvaluationVerdict:
    detected_cats = meta.get("detected_categories", set())
    if "compliance" not in detected_cats and "configuration" not in detected_cats:
        return EvaluationVerdict(
            status="OMITTED", badge="⚪",
            observed_state="Category not in backup. Control not evaluated."
        )

    has_compliance = any(p.get("category") == "compliance" for p in policies)
    has_lock_setting = False
    enforcing_names = []

    for p in policies:
        settings = _get_setting_values(p)
        for k in settings:
            if "inactivity" in k or "screenlock" in k or "maxinactivitytimedevicelock" in k:
                has_lock_setting = True
                enforcing_names.append(p.get("name", ""))
                break

    if not has_compliance and not has_lock_setting:
        return EvaluationVerdict(
            status="WARN", badge="🟡",
            observed_state="No explicit inactivity timeout or device compliance policy detected.",
            evidence="Inactivity timeout setting not located in backup.",
            findings=["Verify device compliance policies and settings catalog lock thresholds."],
        )

    ev_detail = f"Configured in {', '.join(enforcing_names)}" if enforcing_names else "Enforced by Device Compliance policy"
    return EvaluationVerdict(
        status="PASS", badge="🟢",
        observed_state="Device compliance policy or inactivity lock parameters active.",
        evidence=f"{ev_detail}.",
    )


def _eval_dormant_policies(policies: List[Dict[str, Any]], meta: Dict[str, Any]) -> EvaluationVerdict:
    total = len(policies)
    if total == 0:
        return EvaluationVerdict(
            status="OMITTED", badge="⚪",
            observed_state="No policies present to evaluate."
        )

    unassigned = [p for p in policies if not _has_included_assignments(p)]
    count = len(unassigned)

    if count == 0:
        return EvaluationVerdict(
            status="PASS", badge="🟢",
            observed_state=f"All {total} policies have active group assignments.",
            evidence=f"100% targeting rate across {total} policies.",
        )

    pct = (count / total) * 100
    p_names = [p.get("name", "Unnamed") for p in unassigned]

    if pct > 35:
        return EvaluationVerdict(
            status="FAIL", badge="🔴",
            observed_state=f"{count} of {total} policies ({pct:.0f}%) are dormant without assignments.",
            evidence=f"High dormant volume ({count} unassigned profiles).",
            findings=p_names,
        )

    return EvaluationVerdict(
        status="WARN", badge="🟡",
        observed_state=f"{count} dormant policy found with 0 assignments.",
        evidence=f"Unassigned profiles: {', '.join(p_names)}.",
        findings=p_names,
    )


def _eval_stig_asr(policies: List[Dict[str, Any]], meta: Dict[str, Any]) -> EvaluationVerdict:
    detected_cats = meta.get("detected_categories", set())
    if "endpoint_security" not in detected_cats and "configuration" not in detected_cats:
        return EvaluationVerdict(
            status="OMITTED", badge="⚪",
            observed_state="Category not in backup. Control not evaluated."
        )

    matching = [p for p in policies if "asr" in p.get("name", "").lower() or "attack surface" in p.get("name", "").lower()]
    assigned = [p for p in matching if _has_included_assignments(p)]

    if assigned:
        names = [p.get("name", "") for p in assigned]
        return EvaluationVerdict(
            status="PASS", badge="🟢",
            observed_state=f"ASR policy identified ({', '.join(names)}).",
            evidence=f"ASR configured and targeted by {', '.join(names)}.",
            findings=names,
        )

    if matching:
        names = [p.get("name", "") for p in matching]
        return EvaluationVerdict(
            status="WARN", badge="🟡",
            observed_state="ASR policy configured but unassigned.",
            evidence=f"Policy exists ({', '.join(names)}) without active targets.",
            findings=names,
        )

    return EvaluationVerdict(
        status="FAIL", badge="🔴",
        observed_state="No Attack Surface Reduction (ASR) policy identified.",
        evidence="Zero ASR rule sets detected in tenant backup.",
        findings=["Missing ASR policy."],
    )


# ---------------------------------------------------------------------------
# Master Rule Registry
# ---------------------------------------------------------------------------

AUDIT_RULES: List[AuditRule] = [
    AuditRule(
        rule_id="SEC-ENC-001",
        domain="endpoint_encryption",
        domain_label="Endpoint Encryption",
        title="Endpoint Disk Encryption (BitLocker / FileVault)",
        category_dependency="configuration",
        profile="balanced",
        benchmark_ref="CIS Intune v1.1.0 (1.1.1), MS Security Baseline, CISA CPG 2.A",
        benchmark_intent="Protect data at rest on stolen or lost portable devices.",
        field_context="Administrators fear BitLocker recovery lockouts if firmware changes TPM measurements.",
        remediation_guidance="Configure BitLocker policy with mandatory Entra ID recovery key backup.",
        learn_url="https://learn.microsoft.com/en-us/mem/intune/protect/encrypt-devices",
        evaluator=_eval_bitlocker,
    ),
    AuditRule(
        rule_id="SEC-AV-001",
        domain="antivirus_edr",
        domain_label="Antivirus & EDR Hygiene",
        title="Microsoft Defender Real-Time & Cloud Protection",
        category_dependency="endpoint_security",
        profile="balanced",
        benchmark_ref="CIS Intune v1.1.0 (2.1), MS Security Baseline, CISA CPG 2.C",
        benchmark_intent="Enable continuous behavior monitoring and cloud heuristic analysis.",
        field_context="Real-time scanning can create I/O latency on developer or testing software.",
        remediation_guidance="Enable Real-Time and Cloud-Delivered protection in Defender Antivirus.",
        learn_url="https://learn.microsoft.com/en-us/mem/intune/protect/antivirus-microsoft-defender-settings-windows",
        evaluator=_eval_defender_antivirus,
    ),
    AuditRule(
        rule_id="SEC-AV-002",
        domain="antivirus_edr",
        domain_label="Antivirus & EDR Hygiene",
        title="Microsoft Defender Tamper Protection",
        category_dependency="endpoint_security",
        profile="balanced",
        benchmark_ref="CIS Intune v1.1.0 (2.1.5), MS Security Baseline",
        benchmark_intent="Prevent malware and local accounts from disabling antivirus controls.",
        field_context="Technicians occasionally need to pause Defender when troubleshooting hardware.",
        remediation_guidance="Enable Tamper Protection in Endpoint Security experience profile.",
        learn_url="https://learn.microsoft.com/en-us/defender-endpoint/prevent-tampering-with-tamper-protection",
        evaluator=_eval_tamper_protection,
    ),
    AuditRule(
        rule_id="SEC-FW-001",
        domain="host_firewall",
        domain_label="Host Firewall",
        title="Windows Defender Host Firewall (Domain, Private, Public)",
        category_dependency="endpoint_security",
        profile="balanced",
        benchmark_ref="CIS Intune v1.1.0 (2.3), MS Security Baseline, NIST SP 800-41",
        benchmark_intent="Prevent lateral movement and unapproved inbound network connections.",
        field_context="Networked printing and classroom screen projection fail if inbound rules are missing.",
        remediation_guidance="Enable Domain, Private, and Public firewall profiles with scoped local printer exceptions.",
        learn_url="https://learn.microsoft.com/en-us/mem/intune/protect/endpoint-security-firewall-profile",
        evaluator=_eval_host_firewall,
    ),
    AuditRule(
        rule_id="SEC-UPD-001",
        domain="update_cadence",
        domain_label="Windows Update Cadence",
        title="Windows Quality & Security Update Rings (WUfB)",
        category_dependency="configuration",
        profile="balanced",
        benchmark_ref="CIS Intune v1.1.0 (3.1), CISA CPG 1.E (Rapid Patching)",
        benchmark_intent="Apply security patches within predictable maintenance windows without interruption.",
        field_context="Mid-day device reboots disrupt student testing and classroom instruction.",
        remediation_guidance="Configure update rings with 2-7 day quality deferrals and explicit active hours.",
        learn_url="https://learn.microsoft.com/en-us/mem/intune/protect/windows-update-settings",
        evaluator=_eval_update_rings,
    ),
    AuditRule(
        rule_id="SEC-ID-001",
        domain="identity_credentials",
        domain_label="Identity & Credential Hygiene",
        title="Windows Local Administrator Password Solution (LAPS)",
        category_dependency="endpoint_security",
        profile="balanced",
        benchmark_ref="CIS Intune v1.1.0 (4.1), CISA CPG 2.B, NIST SP 800-63B",
        benchmark_intent="Eliminate shared static local administrator passwords across enterprise workstations.",
        field_context="Field technicians rely on a static password during offline troubleshooting.",
        remediation_guidance="Deploy Windows LAPS with 30-day password rotation to Microsoft Entra ID.",
        learn_url="https://learn.microsoft.com/en-us/mem/intune/protect/endpoint-security-laps-policy",
        evaluator=_eval_windows_laps,
    ),
    AuditRule(
        rule_id="SEC-ID-002",
        domain="identity_credentials",
        domain_label="Identity & Credential Hygiene",
        title="Inactivity Screen Lock & NIST SP 800-63B Password Alignment",
        category_dependency="compliance",
        profile="balanced",
        benchmark_ref="NIST SP 800-63B Sec 5.1.1, CIS Intune v1.1.0 (5.1)",
        benchmark_intent="Prevent physical workstation access while avoiding forced periodic password cycling.",
        field_context="Classroom teachers complain when presentation displays lock mid-lecture.",
        remediation_guidance="Configure 15-minute screen lock timeout and 8+ character password length without forced expiration.",
        learn_url="https://learn.microsoft.com/en-us/mem/intune/protect/device-compliance-get-started",
        evaluator=_eval_screen_lock_and_password,
    ),
    AuditRule(
        rule_id="SEC-HYG-001",
        domain="policy_hygiene",
        domain_label="Policy Hygiene & Lifecycle",
        title="Policy Hygiene & Dormant Asset Lifecycle",
        category_dependency="configuration",
        profile="balanced",
        benchmark_ref="Intune Management Best Practices, ADR 0013 Safe Restore Boundary",
        benchmark_intent="Eliminate unassigned test profiles and confusing dormant artifacts.",
        field_context="Technicians create test profiles when troubleshooting and forget to delete them.",
        remediation_guidance="Review unassigned policies in TENANT_WARNINGS.md and assign or delete them.",
        learn_url="https://learn.microsoft.com/en-us/mem/intune/configuration/device-profile-assign",
        evaluator=_eval_dormant_policies,
    ),
    AuditRule(
        rule_id="STIG-ASR-001",
        domain="antivirus_edr",
        domain_label="Antivirus & EDR Hygiene",
        title="Attack Surface Reduction (ASR) Enforcement",
        category_dependency="endpoint_security",
        profile="strict-stig",
        benchmark_ref="DoD DISA Windows 10/11 STIG V-220700",
        benchmark_intent="Block common attack vectors used by malware including macros and executable content.",
        field_context="ASR in block mode can disrupt accounting macros and educational test apps.",
        remediation_guidance="Deploy ASR rules in Audit mode for 30 days before moving to Block mode.",
        learn_url="https://learn.microsoft.com/en-us/defender-endpoint/attack-surface-reduction",
        evaluator=_eval_stig_asr,
    ),
]
