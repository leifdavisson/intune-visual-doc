# ADR 0007: Interactive Terminal User Interface

- **Status**: Accepted
- **Date**: 2026-10-30
- **Author**: Leif Davisson

## Context

Administrators want an interactive menu to inspect prerequisites, choose browser profiles, and toggle run flags without memorizing CLI arguments.
They also want to copy the exact CLI command for future scheduled scripts.

## Decision

1. Build an interactive TUI (`intune_visual_doc/tui.py`) with [Rich](https://github.com/Textualize/rich) and [InquirerPy](https://github.com/kazhala/InquirerPy), launched when running `intunedoc` (TTY with no arguments) or `intunedoc tui`.
2. Order the 7 menu items in strict operational sequence:
   - `1. Check Prerequisites & Select Browser / Profile`
   - `2. Authenticate & Hook Session (Graph + Portal)`
   - `3. Run Documentation Generator (Extract & Screenshot)`
   - `4. Verify ASD-STE100 Compliance (Linter)`
   - `5. Audit Configuration Drift (Diff)`
   - `6. Logout (Purge Stored Credentials)`
   - `7. Exit`
3. Render a live **Command Preview** panel showing the equivalent `intunedoc run ...` CLI invocation before execution.
4. Keep `--mock` as an explicit CLI-only test flag (`intunedoc run --mock`, `intunedoc diff --mock`) so interactive TUI runs always target real tenants.

## Consequences

- Operators follow a predictable numbered workflow in local terminals and SSH sessions.
- Every TUI run teaches the equivalent non-interactive CLI command for automation.
