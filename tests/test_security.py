# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""Security and robustness tests for Zenzic core."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from zenzic.cli._governance import count_per_file_ignores
from zenzic.core.suppressions import SuppressionTracker
from zenzic.models.config import ZenzicConfig


def test_ghost_policy_leading_space_remediation() -> None:
    """Vulnerability 1: Ensure leading/trailing spaces in per_file_ignores are counted in DQS."""
    # dict[str, Any], not the narrower nested type mypy would otherwise infer:
    # ZenzicConfig's real fields are heterogeneously typed, and an inferred
    # dict[str, dict[str, dict[str, list[str]]]] makes every ** unpacked key
    # fail against every other field's type (mypy's dict is invariant; see
    # "Consider using Mapping instead, which is covariant").
    config_data: dict[str, Any] = {"governance": {"per_file_ignores": {"docs/index.md": [" Z101"]}}}
    config = ZenzicConfig(**config_data)

    # Verify the space-prefixed code is properly counted as a suppression
    per_file_count = count_per_file_ignores(config)
    assert per_file_count == 1, (
        "The leading-space ignore must be counted as a suppression to avoid DQS bypass"
    )


def test_toml_bomb_mixed_type_array_remediation() -> None:
    """Vulnerability 2: Ensure mixed-type arrays in configuration tables do not crash the swallowed root validator."""
    data = {"custom_rules": [{"id": "ZZ-TEST", "pattern": "test", "message": "test"}, 42]}

    # This should not raise an AttributeError crash
    try:
        ZenzicConfig._validate_no_swallowed_root_keys(data)
    except AttributeError:
        pytest.fail("Swallowed root validator crashed on mixed-type array item.")


def test_duplicate_inline_suppressions_remediation() -> None:
    """Vulnerability 3: Ensure duplicate inline suppressions are not fully consumed by a single finding."""
    # We have two ignore comments for Z101 on line 1, but only one Z101 finding
    text = "<!-- zenzic:ignore: Z101 --> <!-- zenzic:ignore: Z101 -->\n"
    tracker = SuppressionTracker(Path("dummy.md"), text)

    assert len(tracker.directives) == 2

    # First Z101 finding is suppressed and consumes one directive
    assert tracker.is_suppressed(1, "Z101")

    # One of the two Z101 directives should be dead (unconsumed)
    dead = tracker.get_dead_suppressions()
    assert len(dead) == 1, "The duplicate inline ignore must remain unconsumed and trigger Z603"
    assert dead[0].rule_id == "Z603"
