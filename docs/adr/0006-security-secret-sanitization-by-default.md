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
2. **Dual-Layer Redaction (`generator/engine.py`)**:
   - Redact any key matching `password|presharedkey|secret|privatekey|apikey|token|passphrase|credential|wifikey|radiussecret` (case-insensitive) to `[MASKED: ********]`.
   - Redact 30+ character alphanumeric/base64 token strings to `[MASKED: <first4>...<last4>]`.
   - Apply `sanitize_value` recursively to both flattened `settings` tables and raw JSON payloads (`<details>` blocks and `docs/raw_json/<category>/<slug>.json`).
3. **Explicit Opt-Out**: Expose `--unsanitize` only when an administrator explicitly requests raw secret output for an offline audit.

## Consequences

- Markdown guides and `docs/raw_json/` backups remain safe for Git commits by default.
- Drift checks (`intunedoc diff`) compare sanitized structures consistently.
