# ADR 0007: Interactive Terminal User Interface

- **Status**: Accepted
- **Date**: 2026-10-30
- **Author**: Leif Davisson

## Context

Administrators want to customize options before running the documentation tool.
Options include:
- Selecting categories (Compliance, Configuration, Endpoint Security, Apps, Scripts)
- Enabling or skipping browser screenshots
- Setting audit log days
- Toggling sanitization mode

Remembering long CLI flags is inconvenient.

## Decision

1. Build an interactive TUI using [Rich](https://github.com/Textualize/rich) and [InquirerPy](https://github.com/kazhala/InquirerPy).
2. Display a live CLI command preview as the user toggles options.
3. Allow direct execution (`intunedoc run ...`) for scripting and automation.

## Consequences

- Users get an intuitive graphical terminal menu for manual runs.
- Users can see and copy the exact CLI command for future scripted runs.
- The interface functions cleanly over SSH and Linux terminals.
