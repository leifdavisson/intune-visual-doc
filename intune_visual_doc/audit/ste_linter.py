"""
ASD-STE100 (Simplified Technical English) linter for Markdown documentation.
Audits generated documentation for sentence length, voice, and approved structures.
"""

import os
import re
from typing import Dict, Any, List

MAX_SENTENCE_WORDS = 25

PASSIVE_VOICE_REGEX = re.compile(
    r"\b(is|are|was|were|be|been|being)\s+([a-z]+ed)\s+(by)\b", re.IGNORECASE
)

UNAPPROVED_COMPLEX_WORDS = {
    "utilize": "use",
    "utilizes": "uses",
    "utilized": "used",
    "in order to": "to",
    "as well as": "and",
    "prior to": "before",
    "subsequent to": "after",
    "in the event that": "if",
}


def audit_text_ste(text: str, filename: str = "document.md") -> List[Dict[str, Any]]:
    """Audit plain text against ASD-STE100 guidelines."""
    issues = []
    lines = text.splitlines()

    in_code_block = False

    for line_idx, line in enumerate(lines, start=1):
        clean_line = line.strip()
        if clean_line.startswith("```"):
            in_code_block = not in_code_block
            continue
        if in_code_block:
            continue
        # Skip markdown headings, tables, code blocks, badges, HTML details tags
        if not clean_line or clean_line.startswith(("#", "|", "`", ">", "-", "*", "!", "<")):
            continue

        # Split into sentences
        sentences = re.split(r"(?<=[.!?])\s+", clean_line)
        for sent in sentences:
            words = sent.split()
            word_count = len(words)

            # Rule 1: Maximum sentence length (max 25 words)
            if word_count > MAX_SENTENCE_WORDS:
                issues.append({
                    "file": filename,
                    "line": line_idx,
                    "rule": "STE-01: Sentence Length",
                    "severity": "Warning",
                    "message": f"Sentence has {word_count} words (limit is {MAX_SENTENCE_WORDS}): '{sent[:40]}...'",
                })

            # Rule 2: Active voice (avoid passive voice)
            passive_match = PASSIVE_VOICE_REGEX.search(sent)
            if passive_match:
                issues.append({
                    "file": filename,
                    "line": line_idx,
                    "rule": "STE-02: Active Voice",
                    "severity": "Warning",
                    "message": f"Avoid passive voice construct '{passive_match.group(0)}'. Use active voice.",
                })

            # Rule 3: Unapproved complex words
            for unapp, replacement in UNAPPROVED_COMPLEX_WORDS.items():
                if re.search(r"\b" + re.escape(unapp) + r"\b", sent, re.IGNORECASE):
                    issues.append({
                        "file": filename,
                        "line": line_idx,
                        "rule": "STE-03: Simplified Vocabulary",
                        "severity": "Suggestion",
                        "message": f"Replace complex word '{unapp}' with approved word '{replacement}'.",
                    })

    return issues


def lint_markdown_directory(directory: str) -> Dict[str, Any]:
    """Lint all Markdown files in a directory tree."""
    all_issues = []
    file_count = 0

    for root, _, files in os.walk(directory):
        for f in files:
            if f.endswith(".md"):
                file_count += 1
                full_path = os.path.join(root, f)
                with open(full_path, "r", encoding="utf-8", errors="ignore") as fp:
                    content = fp.read()
                rel_path = os.path.relpath(full_path, directory)
                issues = audit_text_ste(content, rel_path)
                all_issues.extend(issues)

    return {
        "files_scanned": file_count,
        "total_issues": len(all_issues),
        "issues": all_issues,
    }
