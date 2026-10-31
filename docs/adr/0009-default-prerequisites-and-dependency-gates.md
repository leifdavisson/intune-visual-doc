# ADR 0009: Default Prerequisites and Dependency Gates

- **Status**: Accepted
- **Date**: 2026-10-30
- **Author**: Leif Davisson

## Context

Technicians need to know if their system is ready before starting a documentation task.
Running commands without required tokens causes confusing network errors.
We need the tool to check all requirements automatically.

## Decision

1. **Default Prerequisites Check**:
   The TUI now executes the prerequisites and dependency audit automatically on every start.
   Users can pass `--skip-prereqs` to bypass the audit in automated scripts.
2. **Dependency and Supersedence Matrix**:
   Check five layers:
   - Operating system and display server availability.
   - Installed Chromium browsers and active user profile.
   - Filesystem security permissions (`0700` / `0600`).
   - Token freshness: a valid token (< 50 minutes old) supersedes re-authenticating.
   - Portal session presence for automated screenshots.
3. **Workflow Dependency Gate**:
   If an administrator triggers Step 3 (Documentation Generator) without a valid token, the tool prompts to execute Step 2 (Authenticate) first.
4. **Intune App Supersedences**:
   Extract app relationships to document Win32 app supersedences and dependencies.

## Consequences

- Technicians see system readiness immediately upon launching the tool.
- Cryptic authentication failures are prevented.
- Fresh tokens save time by superseding redundant login prompts.
- Application documentation clearly shows prerequisite chains.
