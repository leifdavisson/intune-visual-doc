# ADR 0008: Browser Detection and Credential Security

- **Status**: Accepted
- **Date**: 2026-10-30
- **Author**: Leif Davisson

## Context

Contributors and administrators run `intunedoc` across Linux, macOS, and Windows workstations.
Each operating system stores Microsoft Edge, Google Chrome, and Chromium profiles in distinct paths.
Pointing [Playwright](https://playwright.dev/python/) directly at an active OS browser `User Data` folder crashes with a Chromium `SingletonLock` error whenever that browser is already open.
Furthermore, cached Graph tokens grant tenant read access and require strict local protection.

## Decision

1. **Cross-Platform Discovery (`prerequisites.py`)**:
   - Scan standard paths on Linux (`~/.config/microsoft-edge`, `~/.config/google-chrome`, `~/.config/chromium`), macOS (`~/Library/Application Support/...`), and Windows (`%LOCALAPPDATA%\...`).
   - Parse each browser's `Local State` JSON (`profile.info_cache`) to list profile names, directory keys (`Default`, `Profile 2`), and signed-in corporate email addresses.
2. **SingletonLock Isolation (`auth/portal_auth.py`)**:
   - Launch Playwright persistent contexts inside an isolated `.auth/browser_profile` directory while passing `channel` (`msedge` or `chrome`) and `--profile-directory=<dir>`, avoiding lock collisions with open desktop browsers.
3. **Filesystem Hardening**:
   - Enforce `0700` (`rwx------`) permissions on `.auth/` via `ensure_secure_auth_dir()`.
   - Enforce `0600` (`rw-------`) permissions on `.auth/config.json`, `.auth/live_token.json`, and `.auth/playwright_state.json` via `write_secure_file()`.
4. **Git Exclusion & Purge**:
   - Exclude `.auth/`, `*.token`, and `.env*` in `.gitignore`.
   - Provide `intunedoc logout` (`wipe_all_credentials()`) to delete `.auth/` on demand.

## Consequences

- Profile discovery works out of the box across Linux, macOS, and Windows without `SingletonLock` crashes.
- Cached tokens remain unreadable by other local OS accounts and never enter Git history.
