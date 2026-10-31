import pytest
from intune_visual_doc.generator.sanitizer import sanitize_value, sanitize_settings_list


def test_sanitize_secret_keys():
    assert sanitize_value("wifiPresharedKey", "Secret12345") == "[MASKED: ********]"
    assert sanitize_value("radiusSecret", "CorporatePass") == "[MASKED: ********]"
    assert sanitize_value("password", "MyP@ssw0rd") == "[MASKED: ********]"


def test_unsanitize_flag_leaves_values():
    assert sanitize_value("wifiPresharedKey", "Secret12345", unsanitize=True) == "Secret12345"


def test_non_secret_values_remain_intact():
    assert sanitize_value("RequireDeviceEncryption", "1") == "1"
    assert sanitize_value("osMinimumVersion", "10.0.22631") == "10.0.22631"


def test_sanitize_settings_list():
    settings = [
        {"name": "RequireDeviceEncryption", "value": "1"},
        {"name": "AdminPassword", "value": "Winter2026!"},
    ]
    cleaned = sanitize_settings_list(settings, unsanitize=False)
    assert cleaned[0]["value"] == "1"
    assert cleaned[1]["value"] == "[MASKED: ********]"
