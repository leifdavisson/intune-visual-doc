# ADR 0007: Interactive Terminal User Interface

- **Status**: Accepted (Amended by ADR 0011, ADR 0013, and ADR 0014)
- **Date**: 2026-10-30
- **Author**: Leif Davisson

## Context

Administrators want an interactive menu to inspect prerequisites, choose browser profiles, and toggle run flags without memorizing CLI arguments.
They also want to copy the exact CLI command for future scheduled scripts.

## Decision

1. Build an interactive TUI (`intune_visual_doc/tui.py`) with [Rich](https://github.com/Textualize/rich) and [InquirerPy](https://github.com/kazhala/InquirerPy), launched when running `intunedoc` (TTY with no arguments) or `intunedoc tui`.
2. Order the menu items into logical operational sections with single-digit aligned numbers:
   - **Setup**:
     - `1. Check prerequisites and browser profile`
     - `2. Set up read-only identities (CI/CD, optional)`
     - `3. Sign in to Microsoft Graph`
   - **Collect**:
     - `4. Generate documentation with screenshots`
     - `5. Export backup (raw JSON, fast)`
   - **Analyze**:
     - `6. Run security posture audit (CIS & MS Baselines)`
     - `7. Verify ASD-STE100 compliance (Linter)`
     - `8. Compare configuration drift (Diff)`
   - **Session**:
     - `9. Sign out and purge credentials`
     - `0. Exit`
3. Render a live **Command Preview** panel showing the equivalent `intunedoc run ...`, `intunedoc backup ...`, or `intunedoc audit ...` CLI invocation before execution.
4. Keep `--mock` as an explicit CLI-only test flag for `run`, `diff`, `backup`, and `audit` commands.
   This guarantees interactive TUI sessions always target real tenants.

## Consequences

- Operators follow a predictable numbered workflow in local terminals and SSH sessions.
- Every TUI run teaches the equivalent non-interactive CLI command for automation.
