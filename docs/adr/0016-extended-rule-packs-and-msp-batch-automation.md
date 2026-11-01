# ADR 0016: Extended Rule Packs and MSP Batch Automation

[Back to ADR Index](README.md)

## Context

Educational institutions and commercial organizations require deep compliance coverage across device security domains.
The initial eight posture rules in [ADR 0014](0014-security-posture-and-best-practice-audit-utility.md) evaluate core encryption, antivirus, firewall, updates, and local administrator password management.
However, security frameworks like CIS Microsoft Intune Benchmark v1.1.0 and Microsoft Enterprise Baselines require additional controls:
1. Attack Surface Reduction (ASR) rules in block mode for LSASS credential protection and ransomware prevention.
2. Device enrollment restrictions blocking personal, unmanaged Windows devices (BYOD) from enrolling into MDM.
3. Microsoft Edge enterprise security baselines enforcing Defender SmartScreen and browser hardening.
4. Mobile Application Management (MAM) App Protection policies preventing data leakage to unmanaged applications.
5. Virtualization-Based Security (VBS) and Credential Guard protecting authentication credentials in memory.

Furthermore, Managed Service Providers (MSPs), school consortia, and enterprise groups manage multiple distinct Intune tenants.
Executing manual terminal user interface (TUI) runs tenant-by-tenant requires excessive administrator time.
Administrators require a headless batch processing engine that audits multiple tenants and compiles a consolidated executive matrix across the portfolio.

## Decision

We will implement extended posture audit rule packs and a multi-tenant MSP batch runner with the following architecture:

### 1. Extended Security Rule Catalog (`intune_visual_doc/audit/rules.py`)

We add five specialized audit rules to the declarative rule registry:
- `SEC-ASR-001` (Balanced): CIS Attack Surface Reduction (ASR) Essential Rules (LSASS protection, ransomware mitigation, and script abuse blocking).
- `SEC-ENR-001` (Balanced): Enrollment Restrictions (Blocking unmanaged personal Windows devices).
- `SEC-EDGE-001` (Balanced): Microsoft Edge Enterprise Security Baseline (SmartScreen and password protection).
- `SEC-MAM-001` (Balanced): Mobile Application Management (MAM) App Protection (Prevent cut/copy/paste to unmanaged apps, enforce PIN and encryption).
- `SEC-ID-003` (Strict STIG): Virtualization-Based Security and Windows Defender Credential Guard enforcement.

Every rule evaluates normalized policy settings and provides ASD-STE100 remediation guidance and benchmark citations.

### 2. Multi-Tenant MSP Batch Automation (`intune_visual_doc/audit/batch.py`)

We introduce an automated batch evaluation engine:
- **Tenant Manifest**: Reads `tenants.json` specifying tenant names, directory paths, and optional read-only SPN credentials (`env:VAR` resolution).
- **Offline & Mock Mode**: Evaluates saved JSON backup folders or mock portfolio tenants without network calls.
- **Cross-Tenant Heatmap**: Computes a control-by-control security heatmap comparing compliance across all portfolio tenants.
- **Multi-Format Reporting**: Generates interactive Rich terminal matrices, ASD-STE100 Markdown summaries (`MSP_PORTFOLIO_AUDIT.md`), and standalone HTML dashboards (`MSP_PORTFOLIO_AUDIT.html`).

### 3. Read-Only Boundary Preservation

Batch execution is strictly read-only against Microsoft Graph.
All operations evaluate offline backup files or make read-only Graph API calls.

## Consequences

### Positive
- Deepens compliance verification across mobile, browser, and enrollment surfaces.
- Enables MSPs and multi-academy trusts to audit dozens of tenants in a single automated CLI command.
- Produces cross-tenant executive comparison dashboards for leadership, insurance underwriters, and auditors.

### Negative
- Evaluating multiple tenants sequentially increases memory usage during large batch runs.
- Requires maintenance of additional benchmark rule mappings when upstream baselines update.
