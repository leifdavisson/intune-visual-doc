# ADR 0002: Dual Authentication and Session Persistence

- **Status**: Accepted
- **Date**: 2026-10-30
- **Author**: Leif Davisson

## Context

The documentation tool needs access to:
1. The [Microsoft Graph API](https://learn.microsoft.com/en-us/graph/overview) for policy data.
2. The [Microsoft Intune Admin Center](https://intune.microsoft.com) portal for browser screenshots.

Users need a simple method to log in on workstations without creating Azure App Registrations first.
Enterprises also require unattended Service Principal (SPN) execution in CI/CD.

## Decision

1. Use Microsoft's well-known Intune client ID (`d1ddf0e0-d672-4503-883e-346669d56585`) as default for interactive browser login.
2. Support custom Client ID, Tenant ID, and Client Secret / Certificate via environment variables.
3. Open a visible Chromium browser window on first login. Save the user session state to `.auth/auth_state.json`.
4. Run subsequent screenshot captures headlessly using the saved session state.

## Consequences

- Workstation users log in quickly through their web browser.
- MFA and Conditional Access work naturally during the first interactive session.
- Session tokens stay local and are excluded from git by `.gitignore`.
