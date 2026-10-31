# ADR 0008: Browser Detection and Credential Security

- **Status**: Accepted
- **Date**: 2026-10-30
- **Author**: Leif Davisson

## Context

Users operate across Linux, macOS, and Windows workstations.
Each operating system stores Chromium, Microsoft Edge, and Google Chrome profiles in different locations.
When we share this project as open source, the tool must detect installed browsers and user profiles across all platforms.

Security is critical:
- Stored tokens give access to Microsoft Graph.
- We must protect session tokens from other local processes and prevent accidental git commits.

## Decision

1. **Cross-Platform Detection**:
   Scan standard paths for Linux (`~/.config`), macOS (`~/Library/Application Support`), and Windows (`%LOCALAPPDATA%`).
   Parse `Local State` JSON files to identify profile names and attached account emails.
2. **Strict Filesystem Permissions**:
   Set `0700` (`rwx------`) permissions on the `.auth/` directory on creation.
   Set `0600` (`rw-------`) permissions on all token files (`live_token.json`, `playwright_state.json`).
3. **Source Control Exclusion**:
   Strictly exclude `.auth/`, `*.token`, `*.json` inside `.auth/`, and environment secrets in `.gitignore`.
4. **Credential Purge**:
   Provide an explicit `intunedoc logout` command that deletes the `.auth/` directory and clears memory immediately.

## Consequences

- The project runs on Linux, macOS, and Windows without manual path configuration.
- Users can choose their corporate account profile before logging in.
- Cached credentials stay protected from unauthorized local user access and repository leaks.
