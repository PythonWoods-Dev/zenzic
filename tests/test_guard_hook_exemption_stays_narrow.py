# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""The commit gate's one exemption must stay one exemption.

Two fixtures carry a credential on purpose: ``examples/z201-credentials/``,
which the Z201 tutorial cites, and the ``hero_specimen`` sandbox that backs the
test suite. The scanner therefore detects them and blocks every commit that
touches them, which is the scanner working, not failing.

Those two are the complete set, established by running the guard over all 502
tracked Markdown/MDX files rather than by assuming: it flags exactly these and
nothing else.

That is resolved at the pre-commit layer rather than in the engine. The
security tier is never suppressible by any mechanism (see
``iter_security_scan_sources`` in ``zenzic.core.discovery``), so a config key
that switched it off for one path would be a general bypass shipped with a
narrow default. Excluding the path in ``.pre-commit-config.yaml`` keeps the
engine property intact and puts the exemption in a file every diff shows.

What that trades away is the guarantee that the exclusion stays narrow: a
regex is one character from covering far more than it was written for. These
tests are that guarantee.
"""

from __future__ import annotations

from pathlib import Path

import pytest


yaml = pytest.importorskip("yaml")

REPO_ROOT = Path(__file__).resolve().parents[1]
CONFIG = REPO_ROOT / ".pre-commit-config.yaml"

EXPECTED_EXCLUDE = r"^(examples/z201-credentials/|tests/sandboxes/hero_specimen/docs/secrets\.md$)"


def _guard_hook() -> dict[str, object]:
    data: dict[str, object] = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    repos: list[dict[str, object]] = data["repos"]  # type: ignore[assignment]
    for repo in repos:
        hooks: list[dict[str, object]] = repo.get("hooks", [])  # type: ignore[assignment]
        for hook in hooks:
            if hook.get("id") == "zenzic-guard":
                return hook
    raise AssertionError("the zenzic-guard hook is not declared in .pre-commit-config.yaml")


def test_the_guard_hook_excludes_exactly_the_one_fixture_path() -> None:
    """A widened regex is the failure mode; pin the string, not a match."""
    hook = _guard_hook()
    assert hook.get("exclude") == EXPECTED_EXCLUDE, (
        "the Secret Guard's commit-gate exclusion changed. It exists to carve out "
        "one deliberate fixture, and every character added to it carves out more. "
        f"Expected {EXPECTED_EXCLUDE!r}, found {hook.get('exclude')!r}. If a second "
        "fixture genuinely needs exempting, add a second anchored path and update "
        "this test deliberately -- do not loosen the existing one."
    )


def test_the_guard_hook_receives_filenames_so_the_exclusion_can_apply() -> None:
    """``pass_filenames: false`` would make the exclusion decorative.

    pre-commit's ``exclude`` decides which files reach the hook. With
    ``pass_filenames: false`` the hook ignores that list and re-derives its own
    from git, so the fixture would be scanned again whenever any other Markdown
    file was staged alongside it -- the exclusion would only appear to work, in
    exactly the case nobody tests.
    """
    hook = _guard_hook()
    assert hook.get("pass_filenames") is True, (
        "the Secret Guard hook must receive filenames from pre-commit. With "
        "pass_filenames: false the hook re-derives the staged list itself and the "
        "exclude: key above stops having any effect on what is scanned."
    )
    entry = str(hook.get("entry", ""))
    assert "--staged" not in entry, (
        "--staged makes the guard re-derive the staged list from git, which "
        "bypasses pre-commit's exclude: the same defect as pass_filenames: false."
    )


def test_the_exemption_did_not_leak_into_the_shipped_template() -> None:
    """Users get no exemption -- they have no fixture to exempt."""
    from zenzic.cli._guard import _GUARD_HOOK_BLOCK

    assert "examples/z201-credentials" not in _GUARD_HOOK_BLOCK, (
        "this repository's fixture exemption reached the hook block that "
        "`zenzic guard init` writes into a user's configuration. The exemption is "
        "local to this repository's own dogfooding; shipping it would silently "
        "create a scanning blind spot in every project that runs guard init."
    )
