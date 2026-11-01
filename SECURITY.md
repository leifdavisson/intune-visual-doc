# Security Policy

[Back to Repository Overview](README.md)

## Supported Versions

We provide security updates and patches for the following versions:

| Version | Supported | Notes |
| :--- | :--- | :--- |
| `0.1.x` | Yes | Active development release |
| `< 0.1.0` | No | Legacy prototypes |

---

## Reporting a Vulnerability

We take the security of enterprise infrastructure and identity systems seriously.
If you find a security vulnerability, do not report it in public GitHub issues.

Please send security reports directly to:
- **Email**: `leifdavisson@users.noreply.github.com`
- **Subject**: `[SECURITY VULNERABILITY] Intune Visual Doc - <Issue Summary>`

Include the following information in your report:
1. Type of vulnerability and affected component.
2. Step-by-step reproduction instructions or proof-of-concept payload.
3. Potential impact on Microsoft Entra or Microsoft Intune tenants.
4. Suggested mitigations if known.

We acknowledge reports within 48 hours and provide status updates regularly.

---

## Architectural Security Invariants

This project adheres to strict architectural security boundaries:

1. **Strict Read-Only Tenant Boundary**:
   The core `intunedoc` tool performs 100% read-only operations against Microsoft Graph.
   Only `intunedoc setup` creates identities, and only when you run it explicitly.

2. **Isolated Restoration Boundary**:
   Tenant restoration is restricted to the standalone `scripts/intune_restore.py` script.
   Restoration strips all assignment targets by default to prevent unexpected policy deployment.

3. **Credential Storage Hardening**:
   The `.auth/` directory uses `0700` permissions.
   Tokens and session profiles use `0600` permissions and remain gitignored at all times.

4. **Secret Sanitization**:
   All sensitive secrets, pre-shared Wi-Fi keys, and credentials are masked by default.
