"""
Hygiene and status badge generator for Intune policy documentation.
Helps technicians identify assignment health, security baselines, and platforms.
"""

from typing import Dict, Any, List


def get_hygiene_badges(policy: Dict[str, Any]) -> List[str]:
    """
    Generate markdown status badges for a policy.
    Includes assignment state, security baseline alignment, and platform.
    """
    badges = []

    # 1. Assignment status badge
    assignments = policy.get("assignments", [])
    if assignments:
        badges.append("`🟢 Status: Assigned`")
    else:
        badges.append("`🟡 Status: Unassigned / Dormant`")

    # 2. Security Baseline badge
    name_lower = policy.get("name", "").lower()
    desc_lower = policy.get("description", "").lower()
    is_baseline = any(keyword in name_lower or keyword in desc_lower for keyword in [
        "baseline", "bitlocker", "encryption", "antivirus", "firewall", "defender", "compliance"
    ])
    if is_baseline:
        badges.append("`🛡️ Security Baseline: Recommended`")

    # 3. Platform badge
    platform = policy.get("platform", "Universal")
    if "windows" in platform.lower():
        badges.append("`💻 Platform: Windows 10/11`")
    elif "ios" in platform.lower():
        badges.append("`📱 Platform: iOS / iPadOS`")
    elif "android" in platform.lower():
        badges.append("`🤖 Platform: Android Enterprise`")
    elif "mac" in platform.lower():
        badges.append("`🍎 Platform: macOS`")
    else:
        badges.append(f"`🌐 Platform: {platform}`")

    # 4. Audit stamp badge if actor exists
    actor = policy.get("last_modified_by")
    if actor:
        badges.append(f"`👤 Modified By: {actor}`")

    return badges


def get_learn_link(category: str, policy_name: str) -> Dict[str, str]:
    """
    Return relevant Microsoft Learn reference documentation links based on policy category.
    """
    cat_lower = category.lower()
    name_lower = policy_name.lower()

    if "compliance" in cat_lower:
        return {
            "title": "Microsoft Learn: Device Compliance Policies Overview",
            "url": "https://learn.microsoft.com/en-us/mem/intune/protect/device-compliance-get-started",
        }
    elif "bitlocker" in name_lower or "encrypt" in name_lower:
        return {
            "title": "Microsoft Learn: BitLocker Policy Management in Intune",
            "url": "https://learn.microsoft.com/en-us/mem/intune/protect/encrypt-devices",
        }
    elif "antivirus" in name_lower or "defender" in name_lower:
        return {
            "title": "Microsoft Learn: Microsoft Defender Antivirus in Intune",
            "url": "https://learn.microsoft.com/en-us/mem/intune/protect/endpoint-security-antivirus-policy",
        }
    elif "apps" in cat_lower:
        return {
            "title": "Microsoft Learn: Manage Apps with Microsoft Intune",
            "url": "https://learn.microsoft.com/en-us/mem/intune/apps/app-management",
        }
    else:
        return {
            "title": "Microsoft Learn: Device Configuration and Settings Catalog",
            "url": "https://learn.microsoft.com/en-us/mem/intune/configuration/settings-catalog",
        }
