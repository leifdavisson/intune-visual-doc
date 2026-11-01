# ADR 0012: Deliverables Folder and Timestamped Runs

- **Status**: Accepted
- **Date**: 2026-10-31
- **Author**: Leif Davisson

## Context

Previous generator runs wrote tenant deliverables directly into the `docs/` repository directory.
This directory clashed with developer and software architecture documentation such as `docs/adr/`.
Generating tenant reports overwrote previous extractions without preserving historical compliance audit records.
Technicians and auditors need distinct, timestamped snapshot archives for change management.
They also need quick access to the most recent run without manual path lookup.

## Decision

1. **Dedicated Deliverables Root (`deliverables/`)**:
   Move all generated tenant documentation from `docs/` into a dedicated `deliverables/` directory.
   Keep `docs/` dedicated to tool documentation (`docs/adr/`, `docs/WORKFLOW.md`, `docs/PARANOID_ADMIN_SETUP.md`).

2. **Timestamped Execution Subdirectories**:
   Generate each documentation run inside `deliverables/<YYYY-MM-DD_HHMMSS>/`.
   Store full Markdown files, Playwright screenshots, and raw Graph JSON payloads in this directory.

3. **Latest Symbolic Link Pointer**:
   Maintain a `deliverables/latest` symbolic link pointing to the most recent timestamped folder.
   Allow technicians, scripts, and CI/CD pipelines to reference `deliverables/latest/README.md` directly.

4. **Master Historical Catalog (`deliverables/README.md`)**:
   Maintain an inventory table recording every extraction run with timestamps, tenant account, and policy ratios.

5. **Automated Drift Detection**:
   Update `intunedoc diff` to resolve `deliverables/latest/raw_json` automatically as the default baseline.

## Consequences

- Program documentation and customer deliverables are cleanly separated.
- Historical compliance snapshots remain preserved across multiple runs.
- Administrators can compare configuration drift between any two historical runs.
- The `deliverables/latest` link provides a stable path for reporting tools and technicians.
