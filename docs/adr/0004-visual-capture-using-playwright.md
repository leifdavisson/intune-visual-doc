# ADR 0004: Visual Capture Using Playwright

- **Status**: Accepted
- **Date**: 2026-10-30
- **Author**: Leif Davisson

## Context

Technicians need visual confirmation of settings in the [Microsoft Intune Admin Center](https://intune.microsoft.com).
Text tables alone omit portal navigation layouts and compliance status charts.
Opening dozens of concurrent browser tabs exhausts memory and triggers portal rate limits.

## Decision

1. **Persistent Browser Context (`visual/screenshot.py`)**: Launch headless [Playwright](https://playwright.dev/python/) with `launch_persistent_context` in `.auth/browser_profile` at `1440x900`. This preserves cross-origin Entra ID security cookies (`login.microsoftonline.com`).
2. **Modern Ibiza & ReactView Deep Links**: Build deterministic blade URLs matching the live Intune portal routes:
   - Compliance: `Microsoft_Intune_DeviceSettings/CompliancePolicyOverview.ReactView/policyId/{id}/...`
   - Settings Catalog & Unified Security: `Microsoft_Intune_Workflows/PolicySummaryBlade/policyId/{id}/...`
   - Configuration Templates: `Microsoft_Intune_DeviceSettings/PolicySummaryReportBlade/policyId/{id}/...`
   - Applications: `Microsoft_Intune_Apps/SettingsMenu/~/0/appId/{id}` and `SettingsMenu/~/1/appId/{id}`
   - Scripts: `Microsoft_Intune_DeviceSettings/PowershellScriptMenuBlade/~/overview/policyId/{id}`
   - Enrollment: `Microsoft_Intune_DeviceSettings/DevicesMenu/~/enrollment`
3. **Dual Blade & IFrame Tab Capture**: Capture `overview.png` (`full_page=False`) first. Then click the `Properties` tab or scroll `Configuration settings` into view inside React iframes before capturing `properties.png`.
4. **Login Guard & Visual Hygiene Markup**: Reject screenshots if the browser lands on `login.microsoftonline.com` or an Ibiza error page. Inject a status badge (`ASSIGNED POLICY` or `UNASSIGNED / DORMANT POLICY`) before capture and remove it afterward.
5. **Slug Asset Hierarchy**: Save images to `docs/assets/screenshots/<category>/<policy-slug>/`.
6. **Fault Tolerance**: Catch navigation or timeout errors per blade, insert a clean Markdown notice, and continue processing remaining policies.

## Consequences

- Technicians compare live screens directly against matching `overview.png` and `properties.png` captures.
- Sequential capture with render delays prevents portal crashes.
- Single-blade timeouts never abort full tenant documentation runs.
