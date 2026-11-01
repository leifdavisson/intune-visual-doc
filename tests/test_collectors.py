"""
Tests for Graph PolicyCollector covering comprehensive DeviceManagement objects.
Licensed under GNU AGPLv3.
"""

from unittest.mock import MagicMock
from intune_visual_doc.graph.collectors import PolicyCollector


def test_collectors_endpoint_security_policies():
    """Verify endpoint security policies (intents) extraction and normalization."""
    mock_client = MagicMock()
    mock_client.get_all_pages.return_value = [
        {
            "id": "intent-1",
            "displayName": "Defender Antivirus Profile",
            "description": "Antivirus policy",
            "lastModifiedDateTime": "2026-10-30T10:00:00Z",
            "createdDateTime": "2026-10-01T10:00:00Z",
            "assignments": [],
            "settings": [
                {"definitionId": "deviceConfiguration--antivirus_realTimeProtection", "value": True},
            ],
        }
    ]

    collector = PolicyCollector(mock_client)
    policies = collector.get_endpoint_security_policies()
    assert len(policies) == 1
    pol = policies[0]
    assert pol["id"] == "intent-1"
    assert pol["category"] == "configuration"
    assert pol["category_label"] == "Endpoint Security"
    assert pol["settings"][0]["name"] == "deviceConfiguration--antivirus_realTimeProtection"
    assert pol["settings"][0]["value"] == "True"


def test_collectors_device_management_scripts():
    """Verify PowerShell and Shell device management script extraction."""
    mock_client = MagicMock()
    mock_client.get_all_pages.return_value = [
        {
            "id": "script-1",
            "displayName": "Configure Timezone",
            "description": "Sets local timezone to UTC",
            "fileName": "Set-Timezone.ps1",
            "runAsAccount": "system",
            "enforceSignatureCheck": False,
            "runAs32Bit": False,
            "assignments": [],
        }
    ]

    collector = PolicyCollector(mock_client)
    scripts = collector.get_device_management_scripts()
    assert len(scripts) == 1
    sc = scripts[0]
    assert sc["id"] == "script-1"
    assert sc["category_label"] == "Device Script"
    assert any(s["name"] == "FileName" and s["value"] == "Set-Timezone.ps1" for s in sc["settings"])


def test_collectors_device_enrollment_configurations():
    """Verify device enrollment and Autopilot configuration extraction."""
    mock_client = MagicMock()
    mock_client.get_all_pages.return_value = [
        {
            "@odata.type": "#microsoft.graph.windowsAutopilotDeploymentProfile",
            "id": "enroll-1",
            "displayName": "Autopilot User-Driven Entra Join",
            "description": "Autopilot deployment profile",
            "assignments": [],
        }
    ]

    collector = PolicyCollector(mock_client)
    profiles = collector.get_device_enrollment_configurations()
    assert len(profiles) == 1
    p = profiles[0]
    assert p["id"] == "enroll-1"
    assert p["category_label"] == "Enrollment Configuration"


def test_collectors_recursive_settings_catalog_flattening():
    """Verify nested choiceSettingValue children and collection values are recursively extracted."""
    mock_client = MagicMock()
    mock_client.get_all_pages.return_value = [
        {
            "id": "sc-nested-1",
            "name": "Defender Security Baseline",
            "templateReference": {"templateFamily": "baseline"},
            "assignments": [],
            "settings": [
                {
                    "settingInstance": {
                        "settingDefinitionId": "device_vendor_msft_policy_config_deviceinstallation_prevent",
                        "choiceSettingValue": {
                            "value": "device_vendor_msft_policy_config_deviceinstallation_prevent_1",
                            "children": [
                                {
                                    "settingDefinitionId": "device_vendor_msft_policy_config_deny_list",
                                    "simpleSettingCollectionValue": [
                                        {"value": "{d48179be-ec20-11d1-b6b8-00c04fa372a7}"}
                                    ],
                                }
                            ],
                        },
                    }
                }
            ],
        }
    ]

    collector = PolicyCollector(mock_client)
    policies = collector.get_configuration_policies()
    assert len(policies) == 1
    pol = policies[0]
    assert pol["category_label"] == "Endpoint Security"
    assert len(pol["settings"]) == 2
    assert pol["settings"][0]["value"] == "1"
    assert pol["settings"][1]["value"] == "{d48179be-ec20-11d1-b6b8-00c04fa372a7}"

