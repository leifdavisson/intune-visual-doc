# ADR 0013: Configuration Backups and Safe Restore Utility

- **Status**: Accepted
- **Date**: 2026-10-31
- **Author**: Leif Davisson

## Context

Administrators need to backup Microsoft Intune configurations quickly without capturing visual screenshots.
Full visual documentation generation takes minutes because Playwright captures web blades.
In disaster recovery or configuration rollback scenarios, administrators need raw JSON backups.
Restoring backups into a live tenant creates operational risks.
If a tool auto-applies assignments during restore, new policies target production devices immediately.
If a tool overwrites policies without checks, it can destroy working configurations.
Furthermore, the core `intunedoc` tool must remain strictly read-only by design.

## Decision

1. **Fast Backup Mode in CLI and TUI**:
   Add an explicit backup action in the TUI menu and CLI (`intunedoc backup`).
   Export raw JSON configuration files into `deliverables/<timestamp>/raw_json/`.
   Generate a machine-readable `backup_manifest.json` inventory.
   Skip Playwright screenshot capture to complete backups in seconds.

2. **Standalone Out-of-TUI Restore Script (`scripts/intune_restore.py`)**:
   Keep restoration workflows completely outside the read-only `intunedoc` TUI.
   Provide a standalone Python CLI script licensed under GNU AGPLv3 for policy recovery.

3. **Multi-Layered Restore Safety Controls**:
   - **Assignment Stripping by Default**:
     Remove the `assignments` array and targets from restored payloads.
     Create restored policies in a dormant, unassigned state.
     Require administrators to test and assign policies deliberately.
   - **Collision and Overwrite Protection**:
     Query Microsoft Graph before creating a policy.
     If a policy with the same name exists, append a safe suffix (for example, ` - Restored`).
     Require explicit typed confirmation (`CONFIRM OVERWRITE`) if the operator uses `--overwrite`.
   - **Sanitization Sentinel**:
     Reject backups that contain masked or sanitized strings (such as `[MASKED:` or `[SANITIZED:`).
     Protect the tenant against corrupted placeholder values.
   - **Server Metadata Scrubbing**:
     Strip immutable server keys (`id`, `@odata.context`, `@odata.etag`, `createdDateTime`, `version`).
     Prevent Microsoft Graph HTTP 400 Bad Request errors.
   - **Dry-Run Simulation (`--dry-run`)**:
     Validate JSON schemas and display the execution plan without modifying the tenant.
   - **Audit Receipt Generation**:
     Write `restore_receipt_<timestamp>.json` with the new Graph object ID and rollback instructions.

## Consequences

- Administrators can export fast configuration backups from the TUI in seconds.
- The `intunedoc` core program remains 100% read-only.
- Restored policies cannot disrupt active production devices because assignments are stripped.
- Overwrite checks prevent accidental loss of live configurations.
