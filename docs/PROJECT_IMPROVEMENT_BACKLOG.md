# Intune Visual Doc Project Improvement Backlog

This backlog records planned technical improvements for the `intune-visual-doc` tool.
It documents architectural and collector enhancements identified during deliverable reviews.
This document is licensed under **GNU AGPLv3**.

---

## 1. Microsoft Graph API Collector Gaps

The current collector in [`intune_visual_doc/graph/collectors.py`](../intune_visual_doc/graph/collectors.py) fetches core policies.
It omits several major enterprise Microsoft Intune workloads.

| Intune Workload | Target Graph API Endpoint | Priority | Technical Description |
| :--- | :--- | :--- | :--- |
| **Autopilot Profiles** | `/deviceManagement/windowsAutopilotDeploymentProfiles` | High | Fetch out-of-box experience profiles, Entra join mode, and assignments. |
| **Device Health Scripts** | `/deviceManagement/deviceHealthScripts` | High | Fetch Proactive Remediation script pairs, schedules, and run summaries. |
| **App Protection (MAM)** | `/deviceAppManagement/managedAppPolicies` | High | Fetch mobile application management data protection rules for iOS and Android. |
| **App Configurations** | `/deviceAppManagement/mobileAppConfigurations` | Medium | Fetch OEMConfig and managed app configuration dictionaries. |
| **macOS Shell Scripts** | `/deviceManagement/deviceShellScripts` | Medium | Fetch macOS shell scripts, run intervals, and execution contexts. |
| **macOS Attributes** | `/deviceManagement/deviceCustomAttributeShellScripts` | Medium | Fetch macOS custom attribute discovery scripts. |
| **WUfB Feature Profiles** | `/deviceManagement/windowsFeatureUpdateProfiles` | Medium | Fetch Windows feature update target versions and rollout schedules. |
| **WUfB Driver Profiles** | `/deviceManagement/windowsDriverUpdateProfiles` | Medium | Fetch automated and manual driver approval policies. |
| **RBAC & Scope Tags** | `/deviceManagement/roleScopeTags`, `/deviceManagement/roleDefinitions` | Medium | Fetch administrative scope tags and custom RBAC role assignments. |
| **Terms and Conditions** | `/deviceManagement/termsAndConditions` | Low | Fetch terms of service presented during Company Portal enrollment. |

---

## 2. Generator Engine & Deliverable Quality Fixes

These items target [`intune_visual_doc/generator/engine.py`](../intune_visual_doc/generator/engine.py) and related modules.

### A. Audit Log Date Filtering Fallback
- **Problem**: When Microsoft Graph denies `$filter` or `$orderby`, pagination falls back to unconstrained `/deviceManagement/auditEvents`.
- **Result**: Ingests all historical events, creating oversized files (1.36 MB).
- **Remediation**: Apply a client-side cutoff filter on `activityDateTime` immediately after raw pagination.

### B. Tenant Warnings Deduplication & Noise Reduction
- **Problem**: Routine background events match the `create` keyword (for example, `Create ClientCertificate` by `System / Service`).
- **Result**: `TENANT_WARNINGS.md` expands to over 3,500 lines.
- **Remediation**: Ignore automated enrollment certificates. Limit warning tables to high-impact administrator actions.

### C. Application Platform Field Resolution
- **Problem**: `get_managed_apps()` does not provide a `platform` key.
- **Result**: The platform column remains blank in deliverables index tables.
- **Remediation**: Infer platform names from `@odata.type` (for example, `win32LobApp` -> `Windows (Win32)`).

### D. Settings Table OData Metadata Scrubbing
- **Problem**: Strings like `assignments@odata.context` leak into policy settings tables.
- **Result**: Internal metadata displays as configured tenant policy settings.
- **Remediation**: Exclude any property name that contains `@odata` in compliance and template flatteners.

### E. Markdown Breadcrumb Links
- **Problem**: Breadcrumb links point to non-existent category README files or traverse past root folders.
- **Remediation**: Link directly to `../README.md` using anchor tags (for example, `../README.md#device-compliance-policies`).

### F. Deliverables Subdirectory Architecture
- **Problem**: All configuration profiles, endpoint security policies, and scripts reside in one `configuration/` folder.
- **Remediation**: Create dedicated subdirectories:
  - `compliance/`
  - `configuration/`
  - `endpoint_security/`
  - `scripts/`
  - `enrollment/`
  - `apps/`

---

## 3. Completed Architecture Enhancements

### Security Posture & Best-Practice Audit (ADR 0014) — Completed
- Added declarative audit engine evaluating 6 Golden Baseline domains ([`intune_visual_doc/audit/rules.py`](../intune_visual_doc/audit/rules.py)).
- Implemented dual audit profiles (`--profile balanced` [default] and `--profile strict-stig`).
- Added partial backup tolerance (`⚪ Scope Omitted` for un-exported workloads).
- Embedded 4-point legal safe harbor header and non-prescriptive field context in `AUDIT_RECOMMENDATIONS.md`.
- Integrated dedicated Step 6 in TUI, post-backup prompt, and CLI subcommand (`intunedoc audit`).

---

## 4. Official References & Documentation

- [Microsoft Graph Device Management API](https://learn.microsoft.com/en-us/graph/api/resources/intune-devices-devicemanagement)
- [Microsoft Graph Device App Management API](https://learn.microsoft.com/en-us/graph/api/resources/intune-apps-deviceappmanagement)
- [Microsoft Intune Documentation](https://learn.microsoft.com/en-us/mem/intune/)
- [ASD-STE100 Specification](https://asd-ste100.org/)
