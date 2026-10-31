# AGENTS.md — `intune-visual-doc` (`intunedoc`)

Repository guide for AI coding agents working on `intune-visual-doc` (licensed under **GNU AGPLv3**).

## Invariants & Platform Gotchas

- **Authentication (`intune_visual_doc/auth/`)**:
  Authenticate workstation runs via the Playwright network hook (`authenticate_via_browser_hook()` in `portal_auth.py`),
  with `msal.PublicClientApplication.acquire_token_by_device_flow()` as CLI fallback and
  `msal.ConfidentialClientApplication` (`AZURE_CLIENT_SECRET`) for CI/CD.
  Avoid `msal.acquire_token_interactive()` with Client ID `d1ddf0e0-d672-4503-883e-346669d56585`:
  Microsoft Edge redirects that ID to its native broker (`ceffpgmgaoapphfijfinjppigbfibnnp.chromiumapp.org`)
  instead of `http://localhost`, hanging local loopback servers.
- **Profile Lock Isolation (`portal_auth.py`)**:
  Launch Playwright persistent contexts in `.auth/browser_profile` passing `--profile-directory=<dir>`
  and `channel` (`msedge` or `chrome`). Pointing `user_data_dir` directly at the live OS browser directory
  (`~/.config/microsoft-edge`, etc.) triggers a Chromium `SingletonLock` crash whenever the browser is open.
- **Credential Vault Hardening (`prerequisites.py`)**:
  Create `.auth/` via `ensure_secure_auth_dir()` (`0700` permissions) and write `.auth/config.json`,
  `.auth/live_token.json`, and `.auth/playwright_state.json` via `write_secure_file()` (`0600` permissions).
  Keep `.auth/` gitignored.
- **Secret Sanitization (`generator/sanitizer.py`, `generator/engine.py`)**:
  Keep `unsanitize=False` as the default across all CLI and TUI paths.
  Pass both flattened `settings` rows and `raw` Graph payloads (`<details>` blocks and `docs/raw_json/*.json`)
  through `sanitize_value()`.
- **Workflow Order & Tenant Modification Boundary (`tui.py`, `cli.py`, `setup_wizard.py`)**:
  Run `display_prerequisites_table()` on TUI startup unless `--skip-prereqs` is set.
  `intunedoc setup` is the ONLY operation that creates or modifies objects in the Microsoft Entra tenant.
  All other workflows are strictly 100% read-only.
  Preserve the 8-step chronological TUI sequence (`1. Prerequisites` -> `2. Setup Read-Only Identities` ->
  `3. Authenticate` -> `4. Run Generator` -> `5. Lint STE` -> `6. Drift Diff` -> `7. Logout` -> `8. Exit`).
  Keep `--mock` as an explicit CLI-only test flag (`intunedoc run --mock`, `intunedoc diff --mock`).
- **Read-Only Service Identities (`setup_wizard.py`, ADR 0011)**:
  Configure `intunedoc-reader-spn` with strictly read-only Graph application roles
  (`DeviceManagementConfiguration.Read.All`, `DeviceManagementApps.Read.All`,
  `DeviceManagementServiceConfig.Read.All`, `Directory.Read.All`, `AuditLog.Read.All`).
  Configure `svc-intunedoc-screenshot` with Entra `Directory Readers` and Intune RBAC `Read Only Operator`.
  Never grant `.ReadWrite` roles, `Global Administrator`, or `Intune Administrator`.
- **ASD-STE100 Prose (`docs/`, `generator/templates/*.jinja2`)**:
  Write active-voice prose with sentences of 25 words or fewer using approved vocabulary
  (`use`, `to`, `and`, `before`, `after`, `if`).
  Keep Markdown and Mermaid lines at 281 characters or fewer, and include official backlinks
  when referencing external tools or APIs.

## Context Pointers

Load only the ADR or skill matching your active task branch:

- **ADR Index**: [`docs/adr/README.md`](docs/adr/README.md) —
  full decision table (`ADR 0001`–`ADR 0011`) when adding or amending architectural decisions.
- **Service Principals & Screenshot Service Account**:
  [`docs/adr/0011-read-only-spn-and-service-account-setup.md`](docs/adr/0011-read-only-spn-and-service-account-setup.md) —
  when updating `setup_wizard.py`, script generators, SPN Graph permissions, or dedicated user roles.
- **Auth & Token Hook**:
  [`docs/adr/0002-dual-authentication-and-session-persistence.md`](docs/adr/0002-dual-authentication-and-session-persistence.md)
  and [`docs/adr/0008-browser-detection-and-credential-security.md`](docs/adr/0008-browser-detection-and-credential-security.md) —
  when modifying `auth/`, browser profile discovery, `.auth/` permissions, or `logout`.
- **Graph Collectors & App Supersedence**:
  [`docs/adr/0003-data-extraction-via-microsoft-graph.md`](docs/adr/0003-data-extraction-via-microsoft-graph.md)
  and [`docs/adr/0009-default-prerequisites-and-dependency-gates.md`](docs/adr/0009-default-prerequisites-and-dependency-gates.md) —
  when adding Graph endpoints, OData `$expand` queries, Entra group resolution, or prerequisite gates.
- **Playwright Blade Screenshots**:
  [`docs/adr/0004-visual-capture-using-playwright.md`](docs/adr/0004-visual-capture-using-playwright.md) —
  when updating Intune portal deep-link blade URLs or `visual/screenshot.py`.
- **Templates, Badges, Sanitization & STE100**:
  [`docs/adr/0005-asd-ste100-documentation-standards.md`](docs/adr/0005-asd-ste100-documentation-standards.md)
  and [`docs/adr/0006-security-secret-sanitization-by-default.md`](docs/adr/0006-security-secret-sanitization-by-default.md) —
  when editing `generator/`, `audit/ste_linter.py`, or Markdown docs.
- **Workflow & TUI**: [`docs/WORKFLOW.md`](docs/WORKFLOW.md) and
  [`docs/adr/0007-interactive-terminal-user-interface.md`](docs/adr/0007-interactive-terminal-user-interface.md) —
  when updating TUI/CLI subcommands or architecture diagrams.
- **Extension Skill**: [`.agents/skills/intune-visual-doc/SKILL.md`](.agents/skills/intune-visual-doc/SKILL.md) —
  step-by-step recipe when adding a new Intune policy category end-to-end.

## Completion Criteria

Every code, template, or documentation change is complete only when all checks pass with zero errors:

```bash
.venv/bin/pytest
.venv/bin/intunedoc lint-ste --directory docs
awk 'length > 281 {print FILENAME ":" FNR ":" length; found=1} END {exit found}' \
  README.md AGENTS.md CLAUDE.md .agents/skills/intune-visual-doc/SKILL.md docs/WORKFLOW.md docs/adr/*.md
```
