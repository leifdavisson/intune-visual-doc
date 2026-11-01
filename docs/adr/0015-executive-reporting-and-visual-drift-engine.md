# ADR 0015: Executive Reporting and Visual Drift Engine

- **Status**: Accepted
- **Date**: 2026-11-01
- **Author**: Leif Davisson

## Context

Administrators and security officers need to share tenant security posture with non-technical leaders.
School boards, superintendents, and cyber insurance underwriters do not read markdown files or run console commands.
They require professional, printable PDF documents with clear stop-light scorecards and verifiable evidence.
Installing external PDF rendering utilities (like WeasyPrint or wkhtmltopdf) introduces complex native C-library dependencies.
Furthermore, administrators must track configuration drift across time.
Existing drift utilities only report top-level modified file names rather than specific setting mutations.
Technicians need to see exact parameter changes and side-by-side portal screenshots between two backup runs.

## Decision

1. **Zero-Dependency Executive PDF Engine (`visual/pdf.py`)**:
   - Reuse the existing [Playwright](https://playwright.dev/) Chromium runtime (`page.pdf()`) to generate vector PDFs.
   - Avoid external C-library dependencies.
   - Format print pages using CSS `@page` and `@media print` rules for clean margins and table layouts.
   - Embed dynamic header and footer elements with page numbering and confidentiality notices.
   - Expose export formats via `--format {console,markdown,html,pdf,both}` in `intunedoc audit`.

2. **Standalone Executive HTML Presentation Bundle (`generator/templates/executive_audit.html.jinja2`)**:
   - Render a self-contained HTML document (`EXECUTIVE_AUDIT.html`).
   - Embed CSS styles directly in the document for 100% offline viewing without external CDN requests.
   - Display executive stop-light scorecards, domain cards, and the 4-point legal safe harbor notice.
   - Include screenshot thumbnail galleries linking directly to high-resolution portal captures.

3. **Granular Setting-Level Drift Engine (`audit/drift.py`)**:
   - Upgrade drift detection to parse nested Settings Catalog instances and compliance dictionaries using [`flattener.py`](file:///home/leifdavisson/intune_docs/intune_visual_doc/graph/flattener.py).
   - Support arbitrary run-to-run comparison syntax:
     ```bash
     intunedoc diff --from deliverables/2026-10-01_120000 --to deliverables/2026-11-01_120000
     ```
   - Classify granular setting mutations:
     - `Added`: Setting present in target run but absent in baseline run.
     - `Removed`: Setting present in baseline run but missing in target run.
     - `Modified`: Setting value changed (recording `old_value` and `new_value`).

4. **Visual Side-by-Side Drift Presentation (`generator/templates/drift_report.html.jinja2`)**:
   - Render Rich terminal comparison tables highlighting setting mutations with status badges (`+` Green, `-` Red, `~` Yellow).
   - Generate interactive `DRIFT_REPORT.html` displaying side-by-side property diffs and screenshot proofs.
   - Integrate deep drift inspection into TUI Option 8 ("Drift Diff").

5. **Strict Read-Only Boundary Preservation**:
   - All PDF rendering, HTML generation, and drift calculations operate 100% offline from saved backup folders.
   - The tool issues zero write, update, or delete requests to Microsoft Graph.

## Consequences

- Administrators can generate printable PDF audit packets for leadership in seconds without extra dependencies.
- Technicians can identify exact policy drift between any two historical backups.
- Documentation and drift analysis remain completely offline and read-only.
