"""
Unit tests for unattended Service Principal (SPN) authentication and CI/CD operations.
Verifies token acquisition, SPN precedence over cached tokens, and headless CI runs.
Licensed under GNU AGPLv3.
"""

import os
from unittest.mock import patch, MagicMock
from intune_visual_doc.auth.graph_auth import get_graph_token
from intune_visual_doc.cli import cmd_backup, cmd_run, cmd_setup


@patch("msal.ConfidentialClientApplication")
def test_get_graph_token_with_spn_env_vars(mock_msal_class):
    """Verify get_graph_token acquires token via ConfidentialClientApplication when secret is present."""
    mock_app = MagicMock()
    mock_app.acquire_token_for_client.return_value = {
        "access_token": "mock-spn-bearer-token-123",
    }
    mock_msal_class.return_value = mock_app

    with patch.dict(os.environ, {
        "AZURE_CLIENT_ID": "app-guid-111",
        "AZURE_TENANT_ID": "tenant-guid-222",
        "AZURE_CLIENT_SECRET": "secret-value-333",
    }):
        token = get_graph_token()
        assert token == "mock-spn-bearer-token-123"

        mock_msal_class.assert_called_once_with(
            client_id="app-guid-111",
            client_credential="secret-value-333",
            authority="https://login.microsoftonline.com/tenant-guid-222",
        )
        mock_app.acquire_token_for_client.assert_called_once_with(
            scopes=["https://graph.microsoft.com/.default"]
        )


@patch("msal.ConfidentialClientApplication")
def test_get_graph_token_spn_failure_raises(mock_msal_class):
    """Verify RuntimeError is raised when SPN credentials fail."""
    mock_app = MagicMock()
    mock_app.acquire_token_for_client.return_value = {
        "error": "invalid_client",
        "error_description": "Client secret is invalid or expired.",
    }
    mock_msal_class.return_value = mock_app

    with patch.dict(os.environ, {
        "AZURE_CLIENT_ID": "app-guid-111",
        "AZURE_TENANT_ID": "tenant-guid-222",
        "AZURE_CLIENT_SECRET": "expired-secret",
    }):
        import pytest
        with pytest.raises(RuntimeError, match="Service principal authentication failed"):
            get_graph_token()


@patch("intune_visual_doc.cli.get_graph_token")
@patch("intune_visual_doc.cli.GraphClient")
@patch("intune_visual_doc.cli.PolicyCollector")
def test_cmd_backup_with_spn_unattended(mock_collector_class, mock_client_class, mock_token, tmp_path):
    """Verify intunedoc backup executes cleanly in unattended SPN mode."""
    mock_token.return_value = "mock-spn-token"
    mock_collector = MagicMock()
    mock_collector.get_compliance_policies.return_value = [
        {"id": "comp-1", "name": "Compliance Policy 1", "category": "compliance", "settings": [], "assignments": []}
    ]
    mock_collector_class.return_value = mock_collector

    class BackupArgs:
        category = "compliance"
        mock = False
        unsanitize = True
        output_dir = str(tmp_path / "deliverables")
        no_timestamp = False

    cmd_backup(BackupArgs())

    # Check deliverables folder was created with raw_json
    deliv_dir = tmp_path / "deliverables"
    assert os.path.exists(deliv_dir)
    subdirs = [
        os.path.join(deliv_dir, d)
        for d in os.listdir(deliv_dir)
        if d != "latest" and os.path.isdir(os.path.join(deliv_dir, d))
    ]
    assert len(subdirs) >= 1

    manifest = os.path.join(subdirs[0], "backup_manifest.json")
    assert os.path.exists(manifest)


@patch("intune_visual_doc.setup_wizard.verify_spn_credentials")
def test_cmd_setup_test_spn_success(mock_verify):
    """Verify cmd_setup --test-spn calls verify_spn_credentials with env vars."""
    mock_verify.return_value = {"success": True, "org_name": "Test Unified School District"}

    class SetupArgs:
        export_scripts = False
        test_spn = True
        spn = False
        screenshot_user = False
        output_dir = "setup"

    with patch.dict(os.environ, {
        "AZURE_CLIENT_ID": "cid-123",
        "AZURE_TENANT_ID": "tid-456",
        "AZURE_CLIENT_SECRET": "sec-789",
    }):
        cmd_setup(SetupArgs())
        mock_verify.assert_called_once_with("tid-456", "cid-123", "sec-789")
