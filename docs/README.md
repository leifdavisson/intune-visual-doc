# Intune Visual Doc — Software Documentation

[Back to Repository Root](../README.md)

Welcome to the internal software documentation for **Intune Visual Doc** (`intunedoc`).
This project extracts Microsoft Intune configurations via Microsoft Graph and captures visual portal screenshots using Playwright.
All documentation and code in this repository follow the [ASD-STE100](https://asd-ste100.org/) specification under the GNU AGPLv3 license.

---

## Documentation Sections

1. **[Architecture Decision Records](adr/README.md)**:
   Review all architectural decisions (ADR 0001 through ADR 0013) governing authentication, security, and extraction models.
2. **[End-to-End Workflow Guide](WORKFLOW.md)**:
   Understand the 9-stage interactive TUI sequence and CLI automation pipelines.
3. **[Least-Privilege Security Setup](PARANOID_ADMIN_SETUP.md)**:
   Review read-only service principal roles and screenshot account permissions.
4. **[Tenant Deliverables Catalog](../deliverables/README.md)**:
   View generated tenant documentation snapshots, visual screenshots, and audit drift logs.
5. **[Disaster Recovery & Safe Restore](../scripts/intune_restore.py)**:
   Review safety controls in `scripts/intune_restore.py` for restoring JSON backups into Intune safely.
6. **[Codebase Improvement Backlog](PROJECT_IMPROVEMENT_BACKLOG.md)**:
   Review planned software improvements, collector expansion tasks, and deliverable quality fixes.

---

## Directory Organization

```text
├── docs/                      # Program & developer documentation (ADRs, workflows, setup guides)
│   ├── adr/                   # Architecture Decision Records (Michael Nygard format)
│   ├── WORKFLOW.md            # Interactive TUI & CLI execution flow
│   ├── PARANOID_ADMIN_SETUP.md# Zero-trust read-only identity setup
│   └── README.md              # Software documentation index (this document)
├── deliverables/              # Generated customer/tenant documentation deliverables
│   ├── latest -> <timestamp> # Symbolic link pointing to most recent run
│   ├── README.md              # Historical deliverables catalog
│   └── <timestamp>/           # Timestamped extraction (e.g. 2026-10-31_153000)
│       ├── README.md          # Tenant documentation overview & Table of Contents
│       ├── TENANT_WARNINGS.md # Active tenant alerts and hygiene review checklist
│       ├── assets/screenshots/# Dual overview and properties visual captures
│       ├── audit/             # Administrative audit logs
│       ├── raw_json/          # Full Microsoft Graph JSON backups for drift audit
│       └── <category>/        # Individual policy Markdown documentation
```

---

*Licensed under the [GNU Affero General Public License v3.0](https://www.gnu.org/licenses/agpl-3.0.en.html).*
