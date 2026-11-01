"""
Unit tests for Executive Presentation HTML Bundle and Vector PDF Generation.
Licensed under GNU AGPLv3.
"""

import os
import tempfile
import pytest

from intune_visual_doc.audit.posture import (
    evaluate_tenant_posture,
    render_executive_html_report,
    render_executive_pdf_report,
)
from intune_visual_doc.mock_data.samples import get_mock_policies
from intune_visual_doc.visual.pdf import render_html_to_pdf, is_pdf_generation_available


def test_render_executive_html_report():
    """Verify standalone executive HTML report generation and structure."""
    policies = get_mock_policies()
    detected_cats = {p.get("category", "").lower() for p in policies}
    evaluation = evaluate_tenant_posture(
        policies=policies,
        profile="balanced",
        detected_categories=detected_cats,
    )

    with tempfile.TemporaryDirectory() as tmp_dir:
        out_html = os.path.join(tmp_dir, "EXECUTIVE_AUDIT.html")
        rendered_path = render_executive_html_report(
            evaluation=evaluation,
            profile="balanced",
            output_path=out_html,
        )

        assert os.path.exists(rendered_path)
        with open(rendered_path, "r", encoding="utf-8") as f:
            content = f.read()

        assert "<!DOCTYPE html>" in content
        assert "Microsoft Intune Security Posture Assessment" in content
        assert "Executive Scorecard" in content or "scorecard-table" in content
        assert "Baseline Alignment" in content
        assert "@media print" in content
        assert "@page" in content


def test_is_pdf_generation_available():
    """Check that PDF generation availability check executes without error."""
    avail = is_pdf_generation_available()
    assert isinstance(avail, bool)


def test_render_executive_pdf_report():
    """Verify executive PDF generation with real or fallback behavior."""
    policies = get_mock_policies()
    detected_cats = {p.get("category", "").lower() for p in policies}
    evaluation = evaluate_tenant_posture(
        policies=policies,
        profile="balanced",
        detected_categories=detected_cats,
    )

    with tempfile.TemporaryDirectory() as tmp_dir:
        out_pdf = os.path.join(tmp_dir, "EXECUTIVE_AUDIT.pdf")
        rendered_path = render_executive_pdf_report(
            evaluation=evaluation,
            profile="balanced",
            output_path=out_pdf,
        )

        assert os.path.exists(rendered_path)
        if rendered_path.endswith(".pdf"):
            assert os.path.getsize(rendered_path) > 1000
            with open(rendered_path, "rb") as f:
                header = f.read(5)
                assert header == b"%PDF-"
        else:
            # Fallback to HTML if no browser executable is installed
            assert rendered_path.endswith(".html")
