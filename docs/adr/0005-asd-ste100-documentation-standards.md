# ADR 0005: ASD-STE100 Documentation Standards

- **Status**: Accepted
- **Date**: 2026-10-30
- **Author**: Leif Davisson

## Context

Technicians with different experience levels read documentation.
Complex sentences, passive voice, and jargon create confusion.
We need clear and consistent language across all generated guides.

## Decision

1. Follow the [ASD-STE100 (Simplified Technical English)](https://asd-ste100.org/) specification.
2. Enforce key rules:
   - Keep sentences under 25 words.
   - Use active voice only.
   - Put one instruction per sentence.
   - Use standard terminology.
3. Include visual hygiene badges at the top of each document:
   - 🟢 `Status: Assigned`
   - 🟡 `Status: Unassigned / Draft`
   - 🛡️ `Baseline: Security Recommended`
4. Add reference links to official [Microsoft Learn Intune Guides](https://learn.microsoft.com/en-us/mem/intune/).
5. Build an automated linter (`intunedoc lint-ste`) to verify document compliance.

## Consequences

- Basic technicians and senior engineers can understand documents quickly.
- Unassigned or dormant policies stand out immediately.
- Automated tests ensure consistent quality.
