# ADR 0010: Agent Documentation and Skill Architecture

- **Status**: Accepted
- **Date**: 2026-10-30
- **Author**: Leif Davisson

## Context

AI coding agents (Antigravity, Claude Code, Codex, Cursor, GitHub Copilot) maintain and extend this open-source repository alongside human engineers.
Bloated agent instructions waste context tokens, while missing invariants cause regressions (such as reintroducing `msal.acquire_token_interactive()` or violating `ASD-STE100` prose rules).

## Decision

1. **Single Source of Truth (`AGENTS.md` + `CLAUDE.md`)**:
   - Maintain concise repository guardrails, non-obvious browser/auth invariants, completion checks, and front-loaded context pointers in root `AGENTS.md`.
   - Point `CLAUDE.md` directly to `AGENTS.md` to eliminate duplicated guidance.
2. **Portable Repository Skill (`.agents/skills/intune-visual-doc/SKILL.md`)**:
   - Ship an Agent Skills specification package inside `.agents/skills/intune-visual-doc/` covering Graph collector extension, Playwright blade updates, sanitization verification, and `ASD-STE100` linting.
3. **ADR Index (`docs/adr/README.md`)**:
   - Maintain a trigger-indexed ADR table so agents load only the specific ADR governing their active task branch.

## Consequences

- AI agents discover hidden platform gotchas immediately without scanning every module.
- Context load stays minimal through progressive disclosure pointers.
- Every agent run verifies `pytest`, `intunedoc lint-ste`, and 281-character line limits before completion.
