# Contributing to Intune Visual Doc

[Back to Repository Overview](README.md)

We welcome contributions to **Intune Visual Doc** (`intunedoc`).
Please read this guide before you open issues or submit pull requests.

---

## Code of Conduct

All contributors must follow our [Code of Conduct](CODE_OF_CONDUCT.md).
Please treat everyone with respect and professional courtesy.

---

## Development Environment Setup

Follow these steps to set up a local development environment:

1. **Clone Repository**:
   ```bash
   git clone https://github.com/leifdavisson/intune-visual-doc.git
   cd intune-visual-doc
   ```

2. **Create Python Virtual Environment**:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install --upgrade pip
   pip install -e ".[dev]"
   ```

3. **Install Playwright Browsers**:
   ```bash
   playwright install chromium
   ```

---

## Architectural & Writing Standards

Every contribution must satisfy the following quality gates:

1. **ASD-STE100 Compliance**:
   All Markdown documentation and user-facing messages must follow the [ASD-STE100](https://asd-ste100.org/) standard.
   Write active-voice sentences of 25 words or fewer using clear, approved vocabulary.

2. **Line Length Limit**:
   Keep lines in Markdown files and Mermaid diagrams at 281 characters or fewer.

3. **License Requirement**:
   All new code, templates, and scripts must be licensed under the [GNU AGPLv3](LICENSE).

---

## Verification Before Pull Request

Before you submit a pull request, run the test and compliance suite:

```bash
# 1. Run Unit Tests
.venv/bin/pytest

# 2. Run ASD-STE100 Linter
.venv/bin/intunedoc lint-ste --directory docs

# 3. Verify Line Lengths
awk 'length > 281 {print FILENAME ":" FNR ":" length; found=1} END {exit found}' \
  README.md AGENTS.md CLAUDE.md docs/WORKFLOW.md docs/PARANOID_ADMIN_SETUP.md docs/adr/*.md
```
