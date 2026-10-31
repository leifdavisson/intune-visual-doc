# ADR 0002: Dual Authentication and Session Persistence

- **Status**: Accepted (Amended by [ADR 0008](0008-browser-detection-and-credential-security.md))
- **Date**: 2026-10-30
- **Author**: Leif Davisson

## Context

The documentation tool requires access to two Microsoft surfaces:
1. The [Microsoft Graph API](https://learn.microsoft.com/en-us/graph/overview) for policy JSON payloads and Entra ID group names.
2. The [Microsoft Intune Admin Center](https://intune.microsoft.com) portal for live blade screenshots.

Workstation administrators need browser login without creating an Azure App Registration first.
CI/CD pipelines need unattended Service Principal (SPN) execution.

### Non-Obvious Broker Gotcha

Microsoft Edge on Linux and Windows ships a native SSO extension (`ceffpgmgaoapphfijfinjppigbfibnnp.chromiumapp.org`).
When [MSAL Python](https://github.com/AzureAD/microsoft-authentication-library-for-python) calls
`acquire_token_interactive()` with Client ID `d1ddf0e0-d672-4503-883e-346669d56585`, Entra ID redirects
the authorization code to `chromiumapp.org` instead of `http://localhost`.
That redirect leaves local HTTP loopback listeners waiting forever.

## Decision

Implement a four-tier authentication priority cascade in `intune_visual_doc/auth/`:

1. **Service Principal (CI/CD)**: When `AZURE_CLIENT_SECRET` exists, authenticate headlessly via `msal.ConfidentialClientApplication` (`AZURE_CLIENT_ID`, `AZURE_TENANT_ID`).
2. **Cached Live Token**: Reuse `.auth/live_token.json` while token age remains under 3000 seconds (50 minutes).
3. **Playwright Network Hook (Primary Workstation Mode)**:
   - Launch the selected browser (`msedge` or `chrome`) via [Playwright](https://playwright.dev/python/) in `.auth/browser_profile`.
   - Intercept outgoing requests to `graph.microsoft.com` and `manage.microsoft.com` to capture the live `Authorization: Bearer` token into `.auth/live_token.json`.
   - Save portal cookies and storage state to `.auth/playwright_state.json` for subsequent headless screenshot runs.
   - Trap `SIGINT` and browser `close` events so user cancellation exits cleanly without stack traces.
4. **Device Code Flow Fallback**: Fall back to `msal.PublicClientApplication.acquire_token_by_device_flow()` with Client ID `d1ddf0e0-d672-4503-883e-346669d56585` (`https://microsoft.com/devicelogin`), which avoids loopback redirects.

## Consequences

- Workstation logins bypass the `chromiumapp.org` loopback hang completely.
- One interactive browser login populates both the Graph Bearer token and the Playwright screenshot session.
- Closing the browser window cancels authentication cleanly.
