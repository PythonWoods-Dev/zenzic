# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from typer.testing import CliRunner

from zenzic.core.validator import LinkValidator, _check_external_links
from zenzic.main import app
from zenzic.models.config import ZenzicConfig

runner = CliRunner()


def test_check_external_links_skips_excluded_urls(tmp_path: Path):
    """Ensure excluded_external_urls are never pinged via HTTP in _check_external_links."""
    config = ZenzicConfig.model_validate(
        {"excluded_external_urls": ["https://github.com", "https://example.com/ignored"]}
    )
    entries = [
        ("https://github.com/zensical/docs/issues/131", "docs/test.md", 10),
        ("https://example.com/ignored/subpage", "docs/test.md", 12),
        ("https://httpbin.org/status/200", "docs/test.md", 15),
    ]

    with patch("zenzic.core.validator._ping_url", new_callable=AsyncMock) as mock_ping:
        mock_ping.return_value = None
        errors = asyncio.run(_check_external_links(entries, config, tmp_path))
        assert errors == []
        # Only httpbin.org should have been pinged
        assert mock_ping.call_count == 1
        assert mock_ping.call_args[0][1] == "https://httpbin.org/status/200"


def test_link_validator_register_filters_excluded_urls(tmp_path: Path):
    """Ensure LinkValidator.register drops excluded URLs before internal registration."""
    config = ZenzicConfig.model_validate(
        {"excluded_external_urls": ["https://github.com"]}
    )
    validator = LinkValidator(config, tmp_path)
    validator.register("https://github.com/PythonWoods/zenzic", tmp_path / "test.md", 1)
    validator.register("https://zenzic.dev/guide", tmp_path / "test.md", 2)

    assert validator.unique_url_count == 1
    assert "https://github.com/PythonWoods/zenzic" not in validator._registrations
    assert "https://zenzic.dev/guide" in validator._registrations


def test_cli_exclude_url_flag_bypasses_external_link(tmp_path: Path):
    """Test --exclude-url on check links/all CLI command."""
    (tmp_path / ".zenzic.toml").write_text("strict = true\n")
    doc = tmp_path / "docs" / "index.md"
    doc.parent.mkdir(parents=True)
    doc.write_text("[GitHub Issue](https://github.com/zensical/docs/issues/131)\n")

    res = runner.invoke(
        app,
        ["check", "links", str(doc), "--exclude-url", "https://github.com", "--strict"],
    )
    assert res.exit_code == 0


def test_baseline_ux_massive_debt_reduction(tmp_path: Path):
    """Test that massive technical debt reduction prints a reassuring message when 0 new errors exist."""
    (tmp_path / ".zenzic.toml").write_text(
        'strict = true\n\n[governance.directory_policies]\n"docs/**" = ["Z411", "Z502"]\n'
    )
    doc = tmp_path / "docs" / "index.md"
    doc.parent.mkdir(parents=True)
    doc.write_text("# Hello World\n\nValid content.\n")

    # Create a baseline with 60 findings
    fake_findings = [
        {"fingerprint": f"fp_{i}", "rule_id": "Z101", "file_path": "docs/old.md", "line_no": i}
        for i in range(60)
    ]
    import json
    baseline_payload = {
        "version": "1.0",
        "created_at": "2026-08-01T00:00:00Z",
        "score": 40.0,
        "findings_count": 60,
        "findings": fake_findings,
    }
    baseline_file = tmp_path / ".zenzic-baseline.json"
    baseline_file.write_text(json.dumps(baseline_payload))

    res = runner.invoke(
        app,
        ["check", "all", str(doc), "--baseline", str(baseline_file), "--no-header"],
    )
    assert res.exit_code == 0
    assert "Massive technical debt reduction detected (60 issues resolved)" in res.output
    assert "Run 'zenzic check all --update-baseline' to lock in this clean state." in res.output
