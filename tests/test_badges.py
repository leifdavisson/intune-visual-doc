import pytest
from intune_visual_doc.generator.badges import get_hygiene_badges, get_learn_link


def test_assigned_badge():
    policy = {
        "name": "General Config",
        "assignments": [{"target": "All Devices"}],
        "platform": "Windows 11",
    }
    badges = get_hygiene_badges(policy)
    assert any("🟢 Status: Assigned" in b for b in badges)
    assert any("💻 Platform: Windows" in b for b in badges)


def test_unassigned_badge():
    policy = {
        "name": "Draft Kiosk",
        "assignments": [],
        "platform": "Windows 11",
    }
    badges = get_hygiene_badges(policy)
    assert any("🟡 Status: Unassigned / Dormant" in b for b in badges)


def test_security_baseline_badge():
    policy = {
        "name": "BitLocker Drive Encryption Baseline",
        "assignments": [{"target": "Laptops"}],
    }
    badges = get_hygiene_badges(policy)
    assert any("🛡️ Security Baseline" in b for b in badges)


def test_learn_link_resolution():
    link = get_learn_link("compliance", "Windows Health")
    assert "learn.microsoft.com" in link["url"]
    assert "Compliance" in link["title"]
