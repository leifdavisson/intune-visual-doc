"""
Mock and sample data generator based on school district Intune configurations.
Allows instant offline verification without requiring live Microsoft credentials.
"""

import os
import shutil
from typing import Dict, Any, List, Tuple
from ..generator.engine import slugify


def get_mock_policies() -> List[Dict[str, Any]]:
    return [
        {
            "id": "c71a39f0-6101-49b8-a611-38e8e7b3952a",
            "name": "BitLocker - Windows 11 Enterprise Baseline",
            "description": "Enforces XTS-AES 256-bit BitLocker encryption on OS and fixed data drives with Entra ID recovery key backup.",
            "category": "configuration",
            "category_label": "Settings Catalog",
            "platform": "Windows 11",
            "created": "2026-08-15T09:30:00Z",
            "last_modified": "2026-10-12T14:15:22Z",
            "assignments": [
                {"type": "Included", "target": "Intune_Devices"},
                {"type": "Included", "target": "Staff Laptops"},
                {"type": "Excluded", "target": "Legacy Lab Machines"},
            ],
            "settings": [
                {"name": "RequireDeviceEncryption", "value": "1 (Enabled)"},
                {"name": "EncryptionMethodWithXtsOs", "value": "XtsAes256"},
                {"name": "EncryptionMethodWithXtsFdv", "value": "XtsAes256"},
                {"name": "OsRecoveryKeyBackupToEntraID", "value": "Allowed"},
                {"name": "RequireStorageCardEncryption", "value": "1 (Enabled)"},
                {"name": "InternalRecoveryPassphrase", "value": "SuperSecretKey992!"},
            ],
            "raw": {
                "id": "c71a39f0-6101-49b8-a611-38e8e7b3952a",
                "name": "BitLocker - Windows 11 Enterprise Baseline",
                "platforms": "windows11",
                "technologies": "mdm,microsoftSense",
            },
        },
        {
            "id": "e81d48c1-7202-4ab9-b722-49f9f8c4063b",
            "name": "Staff and Student Device Compliance Policy",
            "description": "Baseline health requirements for Windows devices accessing M365 district resources.",
            "category": "compliance",
            "category_label": "Device Compliance",
            "platform": "Windows 10/11",
            "created": "2026-09-01T11:00:00Z",
            "last_modified": "2026-10-20T16:45:10Z",
            "assignments": [
                {"type": "Included", "target": "All Devices"},
            ],
            "settings": [
                {"name": "osMinimumVersion", "value": "10.0.22631.3000"},
                {"name": "bitLockerEnabled", "value": "True"},
                {"name": "firewallEnabled", "value": "True"},
                {"name": "antivirusEnabled", "value": "True"},
                {"name": "tpmRequired", "value": "True (TPM 2.0)"},
                {"name": "passwordMinimumLength", "value": "8"},
            ],
            "raw": {
                "id": "e81d48c1-7202-4ab9-b722-49f9f8c4063b",
                "displayName": "Staff and Student Device Compliance Policy",
                "scheduledActionsForRule": [{"ruleName": "MarkNonCompliant", "gracePeriodInHours": 24}],
            },
        },
        {
            "id": "f92e59d2-8313-4bc0-c833-50a0a9d5174c",
            "name": "Windows Autopilot Deployment Profile - District Desktops",
            "description": "User-driven hybrid Microsoft Entra join enrollment profile for KCSOS district machines.",
            "category": "configuration",
            "category_label": "Enrollment Profile",
            "platform": "Windows 11",
            "created": "2026-07-10T08:00:00Z",
            "last_modified": "2026-10-05T12:00:00Z",
            "assignments": [
                {"type": "Included", "target": "Intune_Devices"},
            ],
            "settings": [
                {"name": "DeploymentMode", "value": "UserDriven"},
                {"name": "JoinType", "value": "AzureADJoined"},
                {"name": "UserAccountType", "value": "StandardUser"},
                {"name": "HideEULA", "value": "True"},
                {"name": "HidePrivacySettings", "value": "True"},
                {"name": "OobeUserSelectLocale", "value": "False (Auto US-English)"},
            ],
            "raw": {
                "id": "f92e59d2-8313-4bc0-c833-50a0a9d5174c",
                "displayName": "Windows Autopilot Deployment Profile - District Desktops",
            },
        },
        {
            "id": "a13f60e3-9424-4cd1-d944-61b1b0e6285d",
            "name": "Company Portal App (Offline)",
            "description": "Self-service application portal required on all enrolled district endpoints.",
            "category": "apps",
            "category_label": "Mobile Application",
            "platform": "Windows",
            "created": "2026-06-20T10:00:00Z",
            "last_modified": "2026-09-18T15:30:00Z",
            "assignments": [
                {"type": "Included", "target": "Intune_Devices"},
            ],
            "settings": [
                {"name": "Publisher", "value": "Microsoft Corporation"},
                {"name": "App Version", "value": "11.1.1873.0"},
                {"name": "Install Context", "value": "Device"},
            ],
            "raw": {
                "id": "a13f60e3-9424-4cd1-d944-61b1b0e6285d",
                "displayName": "Company Portal App (Offline)",
                "publisher": "Microsoft Corporation",
            },
        },
        {
            "id": "b24a71f4-0535-4de2-ea55-72c2c1f7396e",
            "name": "Draft Lab Kiosk Restrictions (Unassigned)",
            "description": "Experimental multi-app kiosk configuration profile currently undergoing pilot evaluation.",
            "category": "configuration",
            "category_label": "Configuration Template",
            "platform": "Windows 11",
            "created": "2026-10-25T14:00:00Z",
            "last_modified": "2026-10-28T09:20:00Z",
            "assignments": [],  # Intentionally empty to test Dormant/Unassigned badge!
            "settings": [
                {"name": "KioskMode", "value": "MultiApp"},
                {"name": "DefaultBrowser", "value": "MicrosoftEdge"},
            ],
            "raw": {
                "id": "b24a71f4-0535-4de2-ea55-72c2c1f7396e",
                "displayName": "Draft Lab Kiosk Restrictions (Unassigned)",
            },
        },
    ]


def get_mock_audit_events() -> List[Dict[str, Any]]:
    return [
        {
            "id": "aud-001",
            "timestamp": "2026-10-28T09:20:00Z",
            "actor": "leif.davisson@kcsos.org",
            "action": "Update",
            "category": "Device Configuration",
            "target": "Draft Lab Kiosk Restrictions (Unassigned)",
        },
        {
            "id": "aud-002",
            "timestamp": "2026-10-20T16:45:10Z",
            "actor": "admin@school.k12.ca.us",
            "action": "Update",
            "category": "Device Compliance",
            "target": "Staff and Student Device Compliance Policy",
        },
        {
            "id": "aud-003",
            "timestamp": "2026-10-12T14:15:22Z",
            "actor": "leif.davisson@kcsos.org",
            "action": "Update",
            "category": "Settings Catalog",
            "target": "BitLocker - Windows 11 Enterprise Baseline",
        },
        {
            "id": "aud-004",
            "timestamp": "2026-10-05T12:00:00Z",
            "actor": "sysadmin@kcsos.org",
            "action": "Create",
            "category": "Enrollment",
            "target": "Windows Autopilot Deployment Profile - District Desktops",
        },
    ]


_MOCK_PNG_BYTES = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\rIDATx\x9cc`\x00\x00\x00\x02"
    b"\x00\x01H\xaf\xa4q\x00\x00\x00\x00IEND\xaeB`\x82"
)


def setup_mock_screenshots(output_dir: str, policies: List[Dict[str, Any]]) -> Dict[str, Dict[str, str]]:
    """
    Generate synthetic placeholder PNG screenshots for mock policies.
    """
    shots_map = {}

    for p in policies:
        p_id = p["id"]
        slug = p.get("slug") or slugify(p.get("name", p_id))
        cat = p.get("category", "configuration")

        target_dir = os.path.join(output_dir, "assets", "screenshots", cat, slug)
        os.makedirs(target_dir, exist_ok=True)

        ov_dest = os.path.join(target_dir, "overview.png")
        pr_dest = os.path.join(target_dir, "properties.png")

        with open(ov_dest, "wb") as f:
            f.write(_MOCK_PNG_BYTES)
        with open(pr_dest, "wb") as f:
            f.write(_MOCK_PNG_BYTES)

        shots_map[p_id] = {
            "overview": ov_dest,
            "properties": pr_dest,
        }

    return shots_map
