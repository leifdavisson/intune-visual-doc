# ADR 0014: Security Posture and Best-Practice Audit Utility

- **Status**: Accepted
- **Date**: 2026-11-01
- **Author**: Leif Davisson

## Context

Administrators need to evaluate Microsoft Intune tenants against industry best practices.
In educational and enterprise IT environments, settings rarely remain in default states by accident.
They reflect operational friction, legacy software requirements, and helpdesk firefighting.
Pass/fail compliance checklists alienate administrators when they ignore operational trade-offs.
Furthermore, advising security changes creates legal liability if changes cause operational disruptions.
Administrators need pragmatic documentation with actionable steps, operational context, and liability protection.

## Decision

1. **Multi-Profile Baseline Architecture**:
   Implement a declarative rule engine in [`intune_visual_doc/audit/rules.py`](file:///home/leifdavisson/intune_docs/intune_visual_doc/audit/rules.py).
   Default to `--profile balanced` grounded in [CIS Microsoft Intune Benchmark v1.1.0 Level 1](https://www.cisecurity.org/benchmark/microsoft_intune),
   [Microsoft Security Baselines](https://learn.microsoft.com/en-us/mem/intune/protect/security-baselines),
   [NIST SP 800-63B](https://csrc.nist.gov/pubs/sp/800/63/b/final), and
   [CISA Cross-Sector Goals](https://www.cisa.gov/cpg).
   Provide an optional `--profile strict-stig` grounded in [DoD DISA STIGs](https://public.cyber.mil/stigs/).

2. **Offline JSON Engine & Partial Backup Tolerance**:
   Analyze exported `raw_json/` backups without making live network calls.
   Inspect available workload directories before evaluation.
   Parse nested Settings Catalog instances and definitions recursively using [`flattener.py`](file:///home/leifdavisson/intune_docs/intune_visual_doc/graph/flattener.py).
   Differentiate compliance health checks from active device configuration enforcement.
   Compliance checks without an enforcing policy generate a warning (`🟡 WARN`), preventing false positive compliance claims.
   Only count policies with active inclusion assignment targets as assigned.
   If a backup omits specific categories, mark corresponding controls as `⚪ Scope Omitted`.
   Never penalize a tenant for categories omitted from an exported backup.

3. **Triple-Layer Legal Safe Harbor Defense**:
   - Embed a prominent 4-clause legal disclaimer at the top of every `AUDIT_RECOMMENDATIONS.md`.
   - Require explicit safe harbor acknowledgment in interactive TUI sessions.
   - Present findings through neutral "Field Realities & Trade-Offs (For vs. Against)" sections.
   - Clarify that recommendations represent informational analysis, not certified compliance auditing.
   - Detail operational scope boundaries and out-of-scope external portals (such as Defender XDR and Entra ID).

4. **Executive Stop-Light Scorecard & Priority Punch List**:
   Generate `AUDIT_RECOMMENDATIONS.md` using Jinja2 templates.
   Display stop-light badges (`🟢 PASS`, `🟡 WARN`, `🔴 FAIL`, `⚪ OMITTED`).
   Sort findings by operational priority with critical issues first (`🔴 FAIL` -> `🟡 WARN` -> `🟢 PASS`).
   Highlight top 3 priority action items at the top of the findings section.
   Include concrete observed evidence with matched policy names and settings.
   Provide exact Microsoft Intune admin center click paths and phased pilot rollout steps.
   Include direct backlinks to official [Microsoft Intune Guidance](https://learn.microsoft.com/en-us/mem/intune/).

5. **TUI Menu Integration & Post-Backup Hook**:
   Insert `6. Best-Practice & Security Posture Audit` into the chronological TUI sequence.
   Present a confirmation prompt immediately following Step 5 (`Export Backup`).
   Share a unified interactive wizard between main menu and post-backup triggers.
   Provide the standalone CLI command `intunedoc audit [TARGET_DIR]`.

## Consequences

- Administrators can evaluate tenant security posture in seconds without network calls.
- The 4-point legal notice and neutral trade-off framing protect administrators from liability.
- Partial backups are evaluated accurately without false positive failures.
- Non-technical executives receive clear stop-light scorecards while engineers receive actionable pilot steps.
