---
name: intune-visual-doc
description: >
  Extend, debug, and run the intune-visual-doc (intunedoc) Microsoft Intune documentation generator.
  Use when adding Microsoft Graph Intune policy collectors, updating Playwright Intune Admin Center blade URLs,
  modifying Jinja2 ASD-STE100 Markdown templates or secret sanitization rules, or auditing configuration drift.
---

# Intune Visual Doc Extension & Operations Skill

Deterministic workflow for extending and operating `intune-visual-doc` (`intunedoc`) while preserving
security, authentication, and [ASD-STE100](https://asd-ste100.org/) invariants.

## Task Routing

Read [`AGENTS.md`](../../../AGENTS.md) first for core guardrails, then jump to the matching branch below:

| Task Branch | Primary Files | Governing ADR |
| :--- | :--- | :--- |
| Add Intune category (Scripts, MAM, Autopilot) | `graph/collectors.py`, `visual/screenshot.py`, `generator/`, `cli.py`, `tui.py` | [ADR 0003](../../../docs/adr/0003-data-extraction-via-microsoft-graph.md), [ADR 0004](../../../docs/adr/0004-visual-capture-using-playwright.md) |
| Setup read-only SPN or screenshot user | `setup_wizard.py`, `setup/`, `prerequisites.py`, `cli.py` | [ADR 0011](../../../docs/adr/0011-read-only-spn-and-service-account-setup.md) |
| Debug browser auth or profiles | `prerequisites.py`, `auth/portal_auth.py`, `auth/graph_auth.py` | [ADR 0002](../../../docs/adr/0002-dual-authentication-and-session-persistence.md), [ADR 0008](../../../docs/adr/0008-browser-detection-and-credential-security.md) |
| Edit templates, badges, redaction | `generator/templates/*.jinja2`, `generator/sanitizer.py`, `audit/ste_linter.py` | [ADR 0005](../../../docs/adr/0005-asd-ste100-documentation-standards.md), [ADR 0006](../../../docs/adr/0006-security-secret-sanitization-by-default.md) |
| Audit configuration drift or offline mock | `audit/drift.py`, `mock_data/samples.py` | [ADR 0009](../../../docs/adr/0009-default-prerequisites-and-dependency-gates.md) |

## End-to-End Steps: Adding a New Intune Policy Collector

1. **Collector (`intune_visual_doc/graph/collectors.py`)**:
   - Query the [Microsoft Graph API](https://learn.microsoft.com/en-us/graph/overview) `beta` endpoint via
     `self.client.get_all_pages(..., beta=True)` with `$expand=assignments` (and `relationships` or `settings` where supported).
   - Resolve Entra ID group GUIDs through `self.resolver.parse_assignments()`.
   - Return normalized policy dicts containing `id`, `name`, `description`, `category`, `category_label`,
     `platform`, `created`, `last_modified`, `assignments`, `settings` (`[{"name": ..., "value": ...}]`), and `raw`.
   - **Completion check**: Every extracted field normalizes `None` values cleanly without raising `KeyError`.

2. **Portal Blade Deep Links (`intune_visual_doc/visual/screenshot.py`)**:
   - Add the `overview` and `properties` blade routes in `build_blade_urls()` under
     `https://intune.microsoft.com/#view/Microsoft_Intune_DeviceSettings`.
   - **Completion check**: `ScreenshotManager` saves captures under `docs/assets/screenshots/<category>/<policy-slug>/`
     (`overview.png` and `properties.png`) and catches timeouts without aborting the run.

3. **Sanitization, Badges & Learn Links (`intune_visual_doc/generator/`)**:
   - Add any new secret key patterns to `SENSITIVE_KEY_PATTERNS` in `sanitizer.py`
     (`unsanitize=False` by default across both `settings` and `raw`).
   - Add category metadata in `engine.py` (`categories_dict`) and official
     [Microsoft Learn Intune](https://learn.microsoft.com/en-us/mem/intune/) reference URLs in `badges.py` (`get_learn_link()`).
   - **Completion check**: Sensitive keys in both `settings` and `raw_json` mask to `[MASKED: ********]` when `unsanitize=False`.

4. **CLI, TUI & Drift Wiring (`intune_visual_doc/cli.py`, `tui.py`)**:
   - Register the category key in `cmd_run()`, `cmd_diff()`, and the TUI `categories` checkbox list in `tui.py`.
   - Add unit tests in `tests/` covering flattening, badges, sanitization, and `ASD-STE100` compliance.

5. **Verification Gate**:
   Run all checks in `.venv`:
   ```bash
   .venv/bin/pytest
   .venv/bin/intunedoc run --mock
   .venv/bin/intunedoc diff --mock
   .venv/bin/intunedoc lint-ste --directory docs
   awk 'length > 281 {print FILENAME ":" FNR ":" length; found=1} END {exit found}' \
     README.md AGENTS.md CLAUDE.md .agents/skills/intune-visual-doc/SKILL.md \
     docs/WORKFLOW.md docs/PARANOID_ADMIN_SETUP.md docs/adr/*.md setup/*.md
   ```

## Output Contract

When reporting changes on this repository:
1. Summarize modified modules and any updated or newly added ADRs in `docs/adr/`.
2. Report exact `pytest` pass count, `intunedoc lint-ste` finding count (`0` required), and line-width check status.
3. Provide clickable `file://` links for modified files and Markdown documents.

## When to Use

Use this skill whenever extending `intune-visual-doc` collectors, troubleshooting Microsoft Edge or Chrome
Playwright token hooking, editing `ASD-STE100` Jinja2 templates, or verifying Intune documentation output.

## Limitations

- Requires read-only Microsoft Graph permissions (`DeviceManagementConfiguration.Read.All`, `DeviceManagementApps.Read.All`,
  `DeviceManagementServiceConfig.Read.All`, `Directory.Read.All`) for live tenant runs.
- Never commit `.auth/` tokens, cookies, or `--unsanitize` output containing live tenant secrets to source control.
- Ask for user confirmation before modifying licensing (`GNU AGPLv3`) or altering default secret sanitization behavior.
