# ADR 0005: ASD-STE100 Documentation Standards

- **Status**: Accepted
- **Date**: 2026-10-30
- **Author**: Leif Davisson

## Context

Support technicians and security auditors with varied experience read our generated guides.
Long sentences, passive voice, and inconsistent terms slow troubleshooting.
AI agents and contributors editing templates or ADRs need deterministic, machine-checkable prose rules.

## Decision

1. Follow the [ASD-STE100 (Simplified Technical English)](https://asd-ste100.org/) standard across all files in `docs/` and [Jinja2](https://jinja.palletsprojects.com/) templates in `intune_visual_doc/generator/templates/`.
2. Enforce three automated rules in `intune_visual_doc/audit/ste_linter.py` (`intunedoc lint-ste`):
   - **`STE-01` (Sentence Length)**: Keep every prose sentence at 25 words or fewer.
   - **`STE-02` (Active Voice)**: Write in active voice; avoid passive constructs matching `(is|are|was|were|be|been|being) <verb>ed by`.
   - **`STE-03` (Approved Vocabulary)**: Use simple words (`use` instead of `utilize`, `to` instead of `in order to`, `and` instead of `as well as`, `before` instead of `prior to`, `after` instead of `subsequent to`, `if` instead of `in the event that`).
   - **Structural Exemptions**: The linter skips headings (`#`), tables (`|`), code blocks (```` ``` ````), inline badges (`` ` ``), callouts (`>`), lists (`-`, `*`), and images (`!`).
3. Render visual hygiene badges (`generator/badges.py`) at the top of each policy guide:
   - `🟢 Status: Assigned` or `🟡 Status: Unassigned / Dormant`
   - `🛡️ Security Baseline: Recommended`
   - Platform and `👤 Modified By` attribution badges
4. Attach category-level [Microsoft Learn Intune](https://learn.microsoft.com/en-us/mem/intune/) reference links.

## Consequences

- Tier-1 technicians and auditors read concise, unambiguous instructions.
- CI pipelines enforce `intunedoc lint-ste --directory docs` on every pull request.
