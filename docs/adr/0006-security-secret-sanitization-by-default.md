# ADR 0006: Security Secret Sanitization by Default

- **Status**: Accepted
- **Date**: 2026-10-30
- **Author**: Leif Davisson

## Context

Intune policies can contain confidential data:
- Internal Wi-Fi pre-shared keys
- SCEP / PKCS Certificate Authority URLs
- Custom VPN server addresses
- Entra ID Tenant GUIDs

If teams commit documentation to git, exposed secrets cause security incidents.

## Decision

1. Enable secret sanitization by default.
2. Mask sensitive strings (e.g. `Wi-Fi Key: [MASKED: ********]`, `CA Server: ca.***.internal`).
3. Add the `--unsanitize` CLI flag for internal, trusted audits that need full values.

## Consequences

- Documentation is safe for source control by default.
- Accidental leaks are prevented.
- Administrators can still view complete values when required with explicit intent.
