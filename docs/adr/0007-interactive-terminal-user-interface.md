# ADR 0007: Interactive Terminal User Interface

- **Status**: Accepted (Amended by ADR 0011 and ADR 0013)
- **Date**: 2026-10-30
- **Author**: Leif Davisson

## Context

Administrators want an interactive menu to inspect prerequisites, choose browser profiles, and toggle run flags without memorizing CLI arguments.
They also want to copy the exact CLI command for future scheduled scripts.

## Decision

1. Build an interactive TUI (`intune_visual_doc/tui.py`) with [Rich](https://github.com/Textualize/rich) and [InquirerPy](https://github.com/kazhala/InquirerPy), launched when running `intunedoc` (TTY with no arguments) or `intunedoc tui`.
2. Order the 9 menu items in strict operational sequence:
   - `1. Check Prerequisites & Select Browser / Profile`
   - `2. Setup Read-Only SPN & Screenshot Maker (Optional: Server / CI/CD)`
   - `3. Authenticate & Hook Session (Interactive Browser Login)`
   - `4. Run Documentation Generator (Extract & Screenshot)`
   - `5. Export Backup (Raw Configs Only — Fast, No Screenshots)`
   - `6. Verify ASD-STE100 Compliance (Linter)`
   - `7. Audit Configuration Drift (Diff)`
   - `8. Logout (Purge Stored Credentials)`
   - `9. Exit`
3. Render a live **Command Preview** panel showing the equivalent `intunedoc run ...` or `intunedoc backup ...` CLI invocation before execution.
4. Keep `--mock` as an explicit CLI-only test flag (`intunedoc run --mock`, `intunedoc diff --mock`, `intunedoc backup --mock`) so interactive TUI runs always target real tenants.

## Consequences

- Operators follow a predictable numbered workflow in local terminals and SSH sessions.
- Every TUI run teaches the equivalent non-interactive CLI command for automation.
