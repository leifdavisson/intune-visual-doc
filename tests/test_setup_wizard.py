"""
Tests for setup wizard, script generation, and read-only identity policies.
Licensed under GNU AGPLv3.
"""

import os
import stat
import tempfile
from unittest.mock import patch, MagicMock
from intune_visual_doc.setup_wizard import (
    DEFAULT_SPN_NAME,
    DEFAULT_USER_NAME,
    READ_ONLY_PERMISSIONS,
    generate_spn_bash_script,
    generate_spn_powershell_script,
    generate_screenshot_user_script,
    export_setup_scripts,
    verify_spn_credentials,
)


def test_spn_bash_script_strict_read_only():
    """Verify bash script contains only read permissions and default SPN name."""
    script = generate_spn_bash_script()
    assert DEFAULT_SPN_NAME in script
    assert "00000003-0000-0000-c000-000000000000" in script

    # Check all 5 read-only permissions are present
    for perm in READ_ONLY_PERMISSIONS:
        assert perm["id"] in script

    # Assert no write permissions are included
    assert ".ReadWrite" not in script
    assert ".Create" not in script
    assert "TENANT WRITE NOTICE" in script or "NOTICE" in script


def test_spn_powershell_script_roles():
    """Verify PowerShell script targets read-only roles and default app name."""
    script = generate_spn_powershell_script()
    assert DEFAULT_SPN_NAME in script
    for perm in READ_ONLY_PERMISSIONS:
        assert perm["name"] in script


def test_screenshot_user_script_least_privilege():
    """Verify screenshot maker script enforces least privilege roles and licensing."""
    script = generate_screenshot_user_script(domain="contoso.com")
    assert DEFAULT_USER_NAME in script
    assert "Directory Readers" in script
    assert "Read Only Operator" in script
    assert "Microsoft Intune Plan 1" in script
    assert "Global Administrator" not in script or "Do NOT grant Global Administrator" in script


def test_export_setup_scripts_creates_files():
    """Verify script export writes all files with proper permissions."""
    with tempfile.TemporaryDirectory() as tmpdir:
        exported = export_setup_scripts(tmpdir)
        assert len(exported) == 4
        for fpath in exported:
            assert os.path.exists(fpath)

        # Check bash script is executable
        bash_path = os.path.join(tmpdir, "setup_spn.sh")
        mode = os.stat(bash_path).st_mode
        assert bool(mode & stat.S_IXUSR)


@patch("msal.ConfidentialClientApplication")
def test_spn_credentials_failure(mock_msal):
    """Verify error handling when SPN token acquisition fails."""
    mock_app = MagicMock()
    mock_app.acquire_token_for_client.return_value = {
        "error": "invalid_client",
        "error_description": "Invalid client secret provided.",
    }
    mock_msal.return_value = mock_app

    result = verify_spn_credentials(
        tenant_id="test-tenant",
        client_id="test-client",
        client_secret="bad-secret",
    )
    assert not result["success"]
    assert "Invalid client secret" in result["error"]


@patch("urllib.request.urlopen")
@patch("msal.ConfidentialClientApplication")
def test_spn_credentials_success(mock_msal, mock_urlopen):
    """Verify successful verification and tenant name parsing."""
    mock_app = MagicMock()
    mock_app.acquire_token_for_client.return_value = {
        "access_token": "mock-access-token-12345",
    }
    mock_msal.return_value = mock_app

    mock_resp = MagicMock()
    mock_resp.read.return_value = b'{"value": [{"displayName": "Contoso School District", "id": "guid-123"}]}'
    mock_resp.__enter__.return_value = mock_resp
    mock_resp.__exit__.return_value = False
    mock_urlopen.return_value = mock_resp

    result = verify_spn_credentials(
        tenant_id="test-tenant",
        client_id="test-client",
        client_secret="valid-secret",
    )
    assert result["success"]
    assert result["org_name"] == "Contoso School District"
    assert result["token"] == "mock-access-token-12345"
