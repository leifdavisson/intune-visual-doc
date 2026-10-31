# ADR 0001: Record Architecture Decisions

- **Status**: Accepted
- **Date**: 2026-10-30
- **Author**: Leif Davisson

## Context

We must document Microsoft Intune settings automatically.
Engineers and technicians need clear guides.
Manual documentation drifts from tenant configurations quickly.
We need to record all major technical decisions in a standard format.

## Decision

We will use Architecture Decision Records (ADRs) based on Michael Nygard's format.
We will write all ADRs and generated documentation in **ASD-STE100 (Simplified Technical English)**.
We will keep ADR files in the `docs/adr/` directory in this repository.

## Consequences

- All decisions stay visible in source control.
- Future contributors can read why we selected specific tools.
- Technical prose remains clear, concise, and unambiguous.
