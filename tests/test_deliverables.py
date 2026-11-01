"""
Tests for deliverables management: timestamped directories, latest pointer, and catalog.
Licensed under GNU AGPLv3.
"""

import os
from datetime import datetime, timezone
from intune_visual_doc.deliverables import (
    create_timestamped_run_dir,
    update_latest_pointer,
    record_run_in_catalog,
    get_latest_deliverables_dir,
    get_timestamp_string,
)


def test_timestamp_string_format():
    dt = datetime(2026, 10, 31, 15, 30, 0, tzinfo=timezone.utc)
    ts = get_timestamp_string(dt)
    assert ts == "2026-10-31_153000"


def test_create_timestamped_run_dir(tmp_path):
    base_dir = tmp_path / "deliverables"
    dt = datetime(2026, 10, 31, 15, 30, 0, tzinfo=timezone.utc)
    run_dir = create_timestamped_run_dir(base_dir=str(base_dir), timestamp=dt)
    assert os.path.exists(run_dir)
    assert os.path.basename(run_dir) == "2026-10-31_153000"


def test_update_latest_pointer_and_resolution(tmp_path):
    base_dir = tmp_path / "deliverables"
    dt1 = datetime(2026, 10, 31, 12, 0, 0, tzinfo=timezone.utc)
    dt2 = datetime(2026, 10, 31, 15, 0, 0, tzinfo=timezone.utc)

    run_dir1 = create_timestamped_run_dir(base_dir=str(base_dir), timestamp=dt1)
    update_latest_pointer(run_dir1, base_dir=str(base_dir))

    resolved = get_latest_deliverables_dir(str(base_dir))
    assert resolved == os.path.realpath(run_dir1)

    run_dir2 = create_timestamped_run_dir(base_dir=str(base_dir), timestamp=dt2)
    update_latest_pointer(run_dir2, base_dir=str(base_dir))

    resolved2 = get_latest_deliverables_dir(str(base_dir))
    assert resolved2 == os.path.realpath(run_dir2)


def test_record_run_in_catalog(tmp_path):
    base_dir = tmp_path / "deliverables"
    dt = datetime(2026, 10, 31, 15, 30, 0, tzinfo=timezone.utc)
    run_dir = create_timestamped_run_dir(base_dir=str(base_dir), timestamp=dt)

    summary = {
        "stats": {
            "total_policies": 48,
            "assigned_policies": 47,
            "unassigned_policies": 1,
        }
    }

    catalog = record_run_in_catalog(
        base_dir=str(base_dir),
        run_dir=run_dir,
        summary=summary,
        tenant_hint="admin@test.org",
        audit_count=456,
    )

    assert os.path.exists(catalog)
    content = open(catalog, encoding="utf-8").read()
    assert "2026-10-31_153000" in content
    assert "admin@test.org" in content
    assert "48" in content
