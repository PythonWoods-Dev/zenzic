# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, patch

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
    config = ZenzicConfig.model_validate({"excluded_external_urls": ["https://github.com"]})
    validator = LinkValidator(config, tmp_path)
    validator.register("https://github.com/PythonWoods/zenzic", tmp_path / "test.md", 1)
    validator.register("https://zenzic.dev/guide", tmp_path / "test.md", 2)

    assert validator.unique_url_count == 1
    assert "https://github.com/PythonWoods/zenzic" not in validator._registrations
    assert "https://zenzic.dev/guide" in validator._registrations


def test_check_external_links_prefix_match_rejects_host_spoofing(tmp_path: Path):
    """CWE-20 regression: a declared 'https://trusted.com' exclusion must not
    also match 'https://trusted.com.evil.com/...' — the host must be parsed
    and compared exactly, not treated as a raw string prefix of the URL."""
    config = ZenzicConfig.model_validate({"excluded_external_urls": ["https://trusted.com"]})
    entries = [
        # Legitimate sub-path of the declared host — must still be excluded.
        ("https://trusted.com/real/path", "docs/test.md", 10),
        # Spoofed host embedding the declared prefix — must NOT be excluded.
        ("https://trusted.com.evil.com/malicious", "docs/test.md", 12),
    ]

    with patch("zenzic.core.validator._ping_url", new_callable=AsyncMock) as mock_ping:
        mock_ping.return_value = None
        asyncio.run(_check_external_links(entries, config, tmp_path))
        # Only the spoofed-host URL should have been pinged; the real
        # trusted.com sub-path must have been excluded as before.
        assert mock_ping.call_count == 1
        assert mock_ping.call_args[0][1] == "https://trusted.com.evil.com/malicious"


def test_link_validator_register_prefix_match_rejects_host_spoofing(tmp_path: Path):
    """CWE-20 regression, LinkValidator.register side: same host-spoofing bypass."""
    config = ZenzicConfig.model_validate({"excluded_external_urls": ["https://trusted.com"]})
    validator = LinkValidator(config, tmp_path)
    validator.register("https://trusted.com/real/path", tmp_path / "test.md", 1)
    validator.register("https://trusted.com.evil.com/malicious", tmp_path / "test.md", 2)

    assert "https://trusted.com/real/path" not in validator._registrations
    assert "https://trusted.com.evil.com/malicious" in validator._registrations


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


def test_update_baseline_verdict_message_matches_real_exit_code(tmp_path: Path) -> None:
    """`--update-baseline` marks every current finding as baselined in the same

    run, so the real exit code is 0 (nothing unbaselined, no regression) — the
    printed verdict must not claim "Exit code 1 is mandatory" when the actual
    exit code is 0. Regression for reporter.py's has_hard_failures, which was
    computed from raw finding counts with no reference to is_baselined, while
    the real exit-code decision in _check.py is baseline-aware.
    """
    (tmp_path / ".zenzic.toml").write_text('docs_dir = "docs"\n')
    doc = tmp_path / "docs" / "index.md"
    doc.parent.mkdir(parents=True)
    doc.write_text("# Home\n\n[broken link](nonexistent.md)\n\nTODO: write this section\n")

    res = runner.invoke(app, ["check", "all", str(tmp_path), "--update-baseline", "--no-header"])

    assert res.exit_code == 0, res.output
    assert "Exit code 1 is mandatory" not in res.output, (
        f"Verdict claimed Exit 1 is mandatory while the real exit code was 0:\n{res.output}"
    )


def test_update_baseline_dqs_line_shows_gate_passed_not_failed(tmp_path: Path) -> None:
    """`--update-baseline`'s "DQS Final Score" line must say "(Gate Passed)", not "(Gate Failed)".

    Same scenario and same root cause as
    test_update_baseline_verdict_message_matches_real_exit_code, in a
    different function: _check.py's _gate_failed (used only for the DQS
    line's "Gate Failed"/"Gate Passed" label) was computed from raw
    all_findings counts with no is_baselined filter — one screen away from
    reporter.py's already-fixed has_hard_failures, the identical bug shape.
    """
    (tmp_path / ".zenzic.toml").write_text('docs_dir = "docs"\n')
    doc = tmp_path / "docs" / "index.md"
    doc.parent.mkdir(parents=True)
    doc.write_text("# Home\n\n[broken link](nonexistent.md)\n\nTODO: write this section\n")

    res = runner.invoke(app, ["check", "all", str(tmp_path), "--update-baseline", "--no-header"])

    assert res.exit_code == 0, res.output
    assert "(Gate Passed)" in res.output, (
        f"DQS line should say Gate Passed (real exit code is 0):\n{res.output}"
    )
    assert "(Gate Failed)" not in res.output, (
        f"DQS line claimed Gate Failed while the real exit code was 0:\n{res.output}"
    )
