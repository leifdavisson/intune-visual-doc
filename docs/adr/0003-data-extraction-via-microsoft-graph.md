# ADR 0003: Data Extraction via Microsoft Graph

- **Status**: Accepted
- **Date**: 2026-10-30
- **Author**: Leif Davisson

## Context

Microsoft Intune policies exist across multiple Graph API endpoints.
These include:
- Device Configuration Profiles (`/deviceManagement/deviceConfigurations`)
- Settings Catalog Policies (`/deviceManagement/configurationPolicies`)
- Compliance Policies (`/deviceManagement/deviceCompliancePolicies`)
- Endpoint Security Policies (Defender, Disk Encryption, Firewall)
- Mobile Applications (`/deviceAppManagement/mobileApps`)
- Intune Admin Audit Logs (`/deviceManagement/auditEvents`)

Large tenants can trigger HTTP 429 throttling limits.

## Decision

1. Query policies with an exponential backoff client that respects `Retry-After` headers.
2. Resolve Entra ID Group IDs to friendly group names (e.g., "All Corporate Laptops").
3. Flatten nested Settings Catalog definitions into structured Markdown tables.
4. Extract the most recent admin audit events to show who modified each policy.

## Consequences

- Documentation contains live policy values and assignment names.
- Throttling protection avoids API failures.
- Group names make documents easy to read.
