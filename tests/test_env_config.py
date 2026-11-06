"""
Unit tests for environment variable overrides, .env loading, and portability.
Licensed under GNU AGPLv3.
"""

import os
import tempfile
import pytest

from intune_visual_doc.prerequisites import load_dotenv, evaluate_dependencies_and_supersedences


def test_load_dotenv_custom_path():
    """Verify load_dotenv reads KEY=VALUE pairs into os.environ without overriding existing keys."""
    with tempfile.NamedTemporaryFile("w+", delete=False, encoding="utf-8") as tmp:
        tmp.write("# Sample comment\n")
        tmp.write("TEST_ENV_KEY_1=ValueAlpha\n")
        tmp.write("TEST_ENV_KEY_2=\"QuotedBeta\"\n")
        tmp.write("TEST_ENV_EXISTING=NewValue\n")
        tmp_path = tmp.name

    try:
        os.environ["TEST_ENV_EXISTING"] = "OriginalValue"
        load_dotenv(tmp_path)

        assert os.environ.get("TEST_ENV_KEY_1") == "ValueAlpha"
        assert os.environ.get("TEST_ENV_KEY_2") == "QuotedBeta"
        assert os.environ.get("TEST_ENV_EXISTING") == "OriginalValue"
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        os.environ.pop("TEST_ENV_KEY_1", None)
        os.environ.pop("TEST_ENV_KEY_2", None)
        os.environ.pop("TEST_ENV_EXISTING", None)


def test_intune_alias_environment_variables(monkeypatch):
    """Verify INTUNE_* alias variables are recognized alongside AZURE_* variables."""
    monkeypatch.setenv("INTUNE_CLIENT_ID", "11111111-2222-3333-4444-555555555555")
    monkeypatch.setenv("INTUNE_CLIENT_SECRET", "super-secret-intune-key")
    monkeypatch.delenv("AZURE_CLIENT_ID", raising=False)
    monkeypatch.delenv("AZURE_CLIENT_SECRET", raising=False)

    eval_res = evaluate_dependencies_and_supersedences()
    assert eval_res["has_spn"] is True
    assert eval_res["can_skip_login"] is True
    assert "Unattended SPN Active" in eval_res["token_msg"]
