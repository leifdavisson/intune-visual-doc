import os
import shutil
import pytest
from intune_visual_doc.generator.engine import DocGenerator
from intune_visual_doc.mock_data.samples import get_mock_policies, get_mock_audit_events


def test_generator_renders_markdown_tree(tmp_path):
    output_dir = tmp_path / "test_docs"
    generator = DocGenerator(output_dir=str(output_dir), unsanitize=False)

    policies = get_mock_policies()
    audit_events = get_mock_audit_events()

    summary = generator.render_all(
        policies=policies,
        audit_events=audit_events,
        generator_user="Test Admin",
    )

    assert os.path.exists(output_dir / "README.md")
    assert os.path.exists(output_dir / "audit" / "ADMIN_AUDIT_LOG.md")
    assert summary["stats"]["total_policies"] == 5
    assert summary["stats"]["assigned_policies"] == 4
    assert summary["stats"]["unassigned_policies"] == 1
