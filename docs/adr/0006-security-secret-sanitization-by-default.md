# ADR 0006: Security Secret Sanitization by Default

- **Status**: Accepted
- **Date**: 2026-10-30
- **Author**: Leif Davisson

## Context

Intune policies often contain confidential secrets:
- Wi-Fi pre-shared keys and RADIUS secrets
- Passwords, passphrases, and private keys
- API tokens and long base64 or hex credential strings

Committing unsanitized exports to Git repositories risks credential leaks.

## Decision

1. **Sanitize by Default (`generator/sanitizer.py`)**: Keep `unsanitize=False` as the mandatory default across all runs.
2. **Dual-Layer Redaction (`generator/sanitizer.py`, `generator/engine.py`)**:
   - Redact any key matching secret patterns (such as `presharedkey`, `privatekey`, `radiussecret`, `wifikey`, or exact `password`) to `[MASKED: ********]`.
   - Redact 30+ character high-entropy mystery tokens to `[MASKED: <first4>...<last4>]`.
   - **Structural Exemption Gate**: Never mask GUIDs, OData types, or Settings Catalog definition identifiers (`device_vendor_msft_*`, `settingDefinitionId`).
   - **Schema Parameter Exemption**: Never mask administrative policy setting names ending in metadata suffixes (such as `Type`, `Required`, `Length`, `Days`).
   - Apply `sanitize_value` recursively to flattened `settings` tables and raw JSON payloads (`<details>` blocks and `deliverables/<run>/raw_json/<category>/<slug>.json`, amended by ADR 0012).
3. **Explicit Opt-Out**: Expose `--unsanitize` only when an administrator explicitly requests raw secret output for an offline audit or 1-to-1 disaster recovery backup (ADR 0013).

## Consequences

- Markdown guides and `deliverables/` backups remain safe for Git commits by default.
- Drift checks (`intunedoc diff`) compare sanitized structures consistently.
