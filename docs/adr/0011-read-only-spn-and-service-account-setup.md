# ADR 0011: Read-Only Service Principal and Service Account Setup

- **Status**: Accepted
- **Date**: 2026-10-31
- **Author**: Leif Davisson

## Context

Organizations require unattended documentation runs and automated disaster recovery backups.
Security teams demand least-privilege access for documentation tools.
The tool must never modify production tenant configurations during documentation extraction.
Visual screenshot capture in Microsoft Intune requires a user identity with blade access.
We must provide clear guidance to configure dedicated identities for both tasks.

## Decision

1. **Tenant Modification Boundary**:
   The `intunedoc setup` command is the only workflow that creates or modifies tenant objects.
   All documentation generator, diff, and audit routines are strictly read-only.

2. **Unattended Service Principal (`intunedoc-reader-spn`)**:
   Configure a dedicated [Microsoft Entra App Registration](https://learn.microsoft.com/en-us/entra/identity-platform/quickstart-register-app).
   Assign only five read-only [Microsoft Graph Application Permissions](https://learn.microsoft.com/en-us/graph/permissions-reference):
   - `DeviceManagementConfiguration.Read.All`
   - `DeviceManagementApps.Read.All`
   - `DeviceManagementServiceConfig.Read.All`
   - `Directory.Read.All`
   - `AuditLog.Read.All`
   Do not assign write permissions or Entra directory administrative roles.

3. **Screenshot Maker Service Account (`svc-intunedoc-screenshot`)**:
   Create a dedicated cloud user for Playwright browser capture.
   Assign the Microsoft Entra directory role `Directory Readers`.
   Assign the built-in [Intune RBAC Role](https://learn.microsoft.com/en-us/mem/intune/fundamentals/role-based-access-control) named `Read Only Operator`.
   Assign a Microsoft Intune Plan 1 license to load Intune portal blades.
   Do not assign `Global Administrator` or `Intune Administrator` roles.

4. **Automated Setup Provisioning**:
   Provide interactive setup in the TUI workflow menu.
   Generate ready-to-run scripts in `setup/` for Azure CLI and PowerShell.
   Save credentials into `.auth/config.json` with strict `0600` file permissions.

## Consequences

- Documentation and backup operations cannot modify tenant configurations.
- Unattended CI/CD pipelines run safely without interactive user login.
- Security and compliance audits approve the least-privilege permission model.
- Dedicated service identities isolate documentation activity in tenant audit logs.
