# ADR 0003: Data Extraction via Microsoft Graph

- **Status**: Accepted
- **Date**: 2026-10-30
- **Author**: Leif Davisson

## Context

Microsoft Intune policies span multiple [Microsoft Graph API](https://learn.microsoft.com/en-us/graph/overview) `beta` endpoints:
- Device Compliance Policies (`/deviceManagement/deviceCompliancePolicies?$expand=assignments`)
- Settings Catalog Policies (`/deviceManagement/configurationPolicies?$expand=settings,assignments`)
- Configuration Templates (`/deviceManagement/deviceConfigurations?$expand=assignments`)
- Mobile Applications (`/deviceAppManagement/mobileApps?$expand=assignments,relationships`)
- Intune Admin Audit Logs (`/deviceManagement/auditEvents`)
- Entra ID Groups (`/groups/{id}?$select=id,displayName`)

Large tenants trigger HTTP `429` throttling or `503`/`504` transient errors and paginate responses via `@odata.nextLink`.

## Decision

1. **Required Read Scopes**: Request read-only permissions (`DeviceManagementConfiguration.Read.All`, `DeviceManagementApps.Read.All`, `DeviceManagementServiceConfig.Read.All`, `Directory.Read.All`).
2. **Resilient Graph Client (`graph/client.py`)**:
   - Send `ConsistencyLevel: eventual` headers on every request.
   - Retry HTTP `429`, `503`, and `504` responses up to 5 times, honoring `Retry-After` headers with exponential backoff.
   - Follow `@odata.nextLink` automatically until all pages finish loading.
3. **Group Target Resolution (`graph/resolver.py`)**: Cache Entra ID group GUID lookups in memory and fall back gracefully to the raw GUID when directory permissions are absent.
4. **Relationship & Audit Correlation (`graph/collectors.py`)**:
   - Flatten nested Settings Catalog `settingInstance` trees into tabular key-value rows.
   - Extract Win32 app `relationships` to record app supersedences and dependencies.
   - Match `/deviceManagement/auditEvents` targets to attribute `last_modified_by` on each policy.

## Consequences

- Documentation reflects live policy settings, group names, app supersedences, and admin actors.
- Pagination and rate-limit retries prevent partial exports on large tenants.
