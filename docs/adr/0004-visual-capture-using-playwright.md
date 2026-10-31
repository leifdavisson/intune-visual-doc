# ADR 0004: Visual Capture Using Playwright

- **Status**: Accepted
- **Date**: 2026-10-30
- **Author**: Leif Davisson

## Context

Technicians need visual confirmation of settings in the [Microsoft Intune Admin Center](https://intune.microsoft.com).
Text tables alone do not show portal layouts or monitoring charts.
Opening too many browser tabs at one time can freeze the system or trigger portal anti-bot blocks.

## Decision

1. Use [Playwright](https://playwright.dev/) with Chromium.
2. Capture two screenshots for each policy:
   - The **Overview** dashboard (assignment status and device check-in charts).
   - The **Properties** blade (configured settings).
3. Process screenshots sequentially with short render pauses.
4. Save screenshots to `docs/assets/screenshots/<category>/<policy-slug>/`.
5. If a blade times out, insert a placeholder and continue documenting the rest.

## Consequences

- Documents provide visual context matching the real Intune portal.
- Technicians can compare their screens directly against the documentation.
- Browser automation runs safely without crashing.
