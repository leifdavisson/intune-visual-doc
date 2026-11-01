"""
Unit tests for Multi-Tenant MSP Batch Automation and Portfolio Posture Auditing.
Licensed under GNU AGPLv3.
"""

import os
import json
import tempfile
import pytest

from intune_visual_doc.audit.batch import (
    TenantTarget,
    _resolve_secret,
    load_portfolio_config,
    generate_sample_config,
    get_mock_portfolio,
    run_msp_audit_batch,
    render_msp_markdown_matrix,
    render_msp_html_matrix,
)


def test_resolve_secret(monkeypatch):
    """Verify environment variable resolution in SPN secrets."""
    monkeypatch.setenv("TEST_SPN_SECRET", "SuperSecretVal123!")

    assert _resolve_secret("raw_plain_secret") == "raw_plain_secret"
    assert _resolve_secret("env:TEST_SPN_SECRET") == "SuperSecretVal123!"
    assert _resolve_secret("env:NON_EXISTENT_VAR") == ""
    assert _resolve_secret(None) == ""


def test_load_portfolio_config(monkeypatch):
    """Verify loading and parsing portfolio configuration JSON."""
    monkeypatch.setenv("DISTRICT_SECRET", "ResolvedSecretVal99")

    config_data = {
        "portfolio_name": "Test Regional Consortium",
        "tenants": [
            {
                "name": "District Alpha",
                "tenant_id": "tid-alpha",
                "client_id": "cid-alpha",
                "client_secret": "env:DISTRICT_SECRET",
            },
            {
                "name": "District Beta",
                "backup_dir": "/tmp/beta_backup",
                "mock": False,
            },
            {
                "name": "District Gamma",
                "mock": True,
            },
        ],
    }

    with tempfile.TemporaryDirectory() as tmp_dir:
        cfg_path = os.path.join(tmp_dir, "tenants.json")
        with open(cfg_path, "w", encoding="utf-8") as f:
            json.dump(config_data, f)

        name, targets = load_portfolio_config(cfg_path)
        assert name == "Test Regional Consortium"
        assert len(targets) == 3
        assert targets[0].name == "District Alpha"
        assert targets[0].client_secret == "ResolvedSecretVal99"
        assert targets[1].backup_dir == "/tmp/beta_backup"
        assert targets[2].mock is True


def test_generate_sample_config():
    """Verify generating sample tenants.sample.json template."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        sample_path = os.path.join(tmp_dir, "sample.json")
        generated = generate_sample_config(sample_path)

        assert os.path.exists(generated)
        with open(generated, "r", encoding="utf-8") as f:
            data = json.load(f)

        assert "portfolio_name" in data
        assert "tenants" in data
        assert len(data["tenants"]) >= 2


def test_run_msp_audit_batch_mock():
    """Verify batch audit execution across simulated mock portfolio."""
    p_name, targets = get_mock_portfolio()
    report = run_msp_audit_batch(portfolio_name=p_name, targets=targets, profile="balanced")

    assert report.total_tenants == 3
    assert len(report.tenants) == 3
    assert report.avg_compliance > 0
    assert len(report.heatmap_rows) >= 8
    assert len(report.top_portfolio_risks) > 0

    first_tenant = report.tenants[0]
    assert first_tenant.tenant_name == "Oakridge School District (High Security)"
    assert first_tenant.evaluated >= 8
    assert "SEC-ENC-001" in first_tenant.rule_verdicts


def test_render_msp_markdown_matrix():
    """Verify generating ASD-STE100 Markdown portfolio summary."""
    p_name, targets = get_mock_portfolio()
    report = run_msp_audit_batch(portfolio_name=p_name, targets=targets, profile="balanced")

    with tempfile.TemporaryDirectory() as tmp_dir:
        out_md = os.path.join(tmp_dir, "MSP_PORTFOLIO_AUDIT.md")
        rendered = render_msp_markdown_matrix(report, out_md)

        assert os.path.exists(rendered)
        with open(rendered, "r", encoding="utf-8") as f:
            content = f.read()

        assert "# " in content
        assert "Multi-Tenant Security Posture Audit" in content
        assert "Tenant Posture Scorecard" in content
        assert "Top Portfolio-Wide Remediation Priorities" in content
        assert "Legal Safe Harbor & Advisory Notice" in content
        assert "Oakridge School District" in content


def test_render_msp_html_matrix():
    """Verify generating standalone HTML portfolio dashboard with heatmap."""
    p_name, targets = get_mock_portfolio()
    report = run_msp_audit_batch(portfolio_name=p_name, targets=targets, profile="balanced")

    with tempfile.TemporaryDirectory() as tmp_dir:
        out_html = os.path.join(tmp_dir, "MSP_PORTFOLIO_AUDIT.html")
        rendered = render_msp_html_matrix(report, out_html)

        assert os.path.exists(rendered)
        with open(rendered, "r", encoding="utf-8") as f:
            content = f.read()

        assert "<!DOCTYPE html>" in content
        assert "Multi-Tenant Security Posture Assessment" in content
        assert "Tenant Posture Leaderboard" in content
        assert "Cross-Tenant Security Heatmap" in content
        assert "Oakridge School District" in content
        assert "@media print" in content


def test_run_msp_audit_batch_connection_error(monkeypatch):
    """Verify live SPN connection errors are gracefully reported as Connection Error."""
    def mock_get_token(*args, **kwargs):
        raise ConnectionResetError("TLS handshake terminated by remote host")

    monkeypatch.setattr("intune_visual_doc.auth.graph_auth.get_graph_token", mock_get_token)

    live_target = TenantTarget(
        name="Failing Live Tenant",
        tenant_id="00000000-0000-0000-0000-000000000001",
        client_id="11111111-1111-1111-1111-111111111111",
        client_secret="test-secret",
    )

    report = run_msp_audit_batch(
        portfolio_name="Fault Tolerant Consortium",
        targets=[live_target],
        profile="balanced",
    )

    assert report.total_tenants == 1
    t = report.tenants[0]
    assert t.tenant_name == "Failing Live Tenant"
    assert t.posture_tier == "Connection Error"
    assert t.posture_badge == "⚠️"
    assert any("Connection failed" in g for g in t.priority_gaps)

