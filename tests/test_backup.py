"""
Unit tests for the intunedoc backup command.
Verifies raw JSON config export, backup manifest, and catalog registration.
Licensed under GNU AGPLv3.
"""

import os
import json
import pytest
from intune_visual_doc.cli import cmd_backup


def test_cmd_backup_mock(tmp_path):
    output_base = str(tmp_path / "deliverables")

    class BackupArgs:
        category = "compliance,configuration"
        mock = True
        unsanitize = True
        output_dir = output_base
        no_timestamp = False

    cmd_backup(BackupArgs())

    # Verify latest pointer or timestamped run folder exists
    assert os.path.exists(output_base)
    subdirs = [os.path.join(output_base, d) for d in os.listdir(output_base) if os.path.isdir(os.path.join(output_base, d)) and d != "latest"]
    assert len(subdirs) >= 1

    run_dir = subdirs[0]
    raw_json_dir = os.path.join(run_dir, "raw_json")
    manifest_path = os.path.join(run_dir, "backup_manifest.json")
    catalog_path = os.path.join(output_base, "README.md")

    assert os.path.exists(raw_json_dir)
    assert os.path.exists(manifest_path)
    assert os.path.exists(catalog_path)

    # Validate backup manifest
    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    assert manifest["version"] == "1.0"
    assert manifest["unsanitized"] is True
    assert manifest["total_policies"] > 0
    assert len(manifest["policies"]) > 0

    # Validate catalog has Backup entry
    with open(catalog_path, "r", encoding="utf-8") as f:
        catalog_text = f.read()

    assert "Open Backup" in catalog_text
