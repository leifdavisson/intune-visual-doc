# ADR 0004: Visual Capture Using Playwright

- **Status**: Accepted
- **Date**: 2026-10-30
- **Author**: Leif Davisson

## Context

Technicians need visual confirmation of settings in the [Microsoft Intune Admin Center](https://intune.microsoft.com).
Text tables alone omit portal navigation layouts and compliance status charts.
Opening dozens of concurrent browser tabs exhausts memory and triggers portal rate limits.

## Decision

1. **Browser Channel (`visual/screenshot.py`)**: Launch headless [Playwright](https://playwright.dev/python/) with the configured channel (`msedge`, `chrome`, or Chromium) and `.auth/playwright_state.json` at `1440x900`.
2. **Deterministic Deep Links**: Build blade URLs under `https://intune.microsoft.com/#view/Microsoft_Intune_DeviceSettings`:
   - Compliance: `CompliancePolicyDetailsBlade/policyId/{id}` and `CompliancePolicyMenuBlade/~/properties/policyId/{id}`
   - Configuration: `ConfigurationPolicyDetailsBlade/policyId/{id}` and `ConfigurationPolicyMenuBlade/~/properties/policyId/{id}`
   - Applications: `ApplicationDetailsBlade/appId/{id}` and `ApplicationMenuBlade/~/properties/appId/{id}`
3. **Dual Blade Capture**: Capture `overview.png` (`full_page=False`) and `properties.png` (`full_page=True`) sequentially with a 1.5-second render pause after `networkidle`.
4. **Slug Asset Hierarchy**: Save images to `docs/assets/screenshots/<category>/<policy-slug>/`.
5. **Fault Tolerance**: Catch navigation or timeout errors per blade, insert a clean Markdown notice, and continue processing remaining policies.

## Consequences

- Technicians compare live screens directly against matching `overview.png` and `properties.png` captures.
- Sequential capture with render delays prevents portal crashes.
- Single-blade timeouts never abort full tenant documentation runs.
