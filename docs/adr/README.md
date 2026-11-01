# Architecture Decision Records (ADR Index)

[Back to Main Documentation](../README.md)

This index lists all Architecture Decision Records for **Intune Visual Doc**.
Every ADR follows Michael Nygard's format and obeys the [ASD-STE100](https://asd-ste100.org/) standard.

| ADR | Title | Status | Read When Modifying |
| :--- | :--- | :--- | :--- |
| [ADR 0001](0001-record-architecture-decisions.md) | Record Architecture Decisions | Accepted | Adding or amending an ADR in `docs/adr/` |
| [ADR 0002](0002-dual-authentication-and-session-persistence.md) | Dual Authentication and Session Persistence | Accepted (Amended by 0008) | Changing `auth/graph_auth.py`, `auth/portal_auth.py`, MSAL flows, or token caching |
| [ADR 0003](0003-data-extraction-via-microsoft-graph.md) | Data Extraction via Microsoft Graph | Accepted | Adding Graph endpoints, scopes, pagination, group resolution, or audit events in `graph/` |
| [ADR 0004](0004-visual-capture-using-playwright.md) | Visual Capture Using Playwright | Accepted | Updating Intune blade deep-link URLs, screenshot sizes, or `visual/screenshot.py` |
| [ADR 0005](0005-asd-ste100-documentation-standards.md) | ASD-STE100 Documentation Standards | Accepted | Editing `generator/templates/`, `generator/badges.py`, `audit/ste_linter.py`, or `docs/` prose |
| [ADR 0006](0006-security-secret-sanitization-by-default.md) | Security Secret Sanitization by Default | Accepted | Modifying `generator/sanitizer.py`, `raw_json` output, or `--unsanitize` behavior |
| [ADR 0007](0007-interactive-terminal-user-interface.md) | Interactive Terminal User Interface | Accepted | Changing TUI menu order, CLI flags, or `tui.py` / `cli.py` command previews |
| [ADR 0008](0008-browser-detection-and-credential-security.md) | Browser Detection and Credential Security | Accepted | Editing cross-platform browser paths, `Local State` parsing, `.auth/` permissions, or `logout` |
| [ADR 0009](0009-default-prerequisites-and-dependency-gates.md) | Default Prerequisites and Dependency Gates | Accepted | Changing startup dependency checks, `--skip-prereqs`, token supersedence, or app relationships |
| [ADR 0010](0010-agent-documentation-and-skill-architecture.md) | Agent Documentation and Skill Architecture | Accepted | Updating `AGENTS.md`, `CLAUDE.md`, or `.agents/skills/intune-visual-doc/` |
| [ADR 0011](0011-read-only-spn-and-service-account-setup.md) | Read-Only Service Principal and Service Account Setup | Accepted | Setting up `intunedoc-reader-spn`, `svc-intunedoc-screenshot`, Graph permissions, or `setup_wizard.py` |
| [ADR 0012](0012-deliverables-folder-and-timestamped-runs.md) | Deliverables Folder and Timestamped Runs | Accepted | Changing deliverable paths, run timestamps, `latest` pointer, or historical catalog |
| [ADR 0013](0013-configuration-backups-and-safe-restore-utility.md) | Configuration Backups and Safe Restore Utility | Accepted | Modifying fast backup exports in `cli.py`/`tui.py` or restore safeguards in `scripts/intune_restore.py` |
