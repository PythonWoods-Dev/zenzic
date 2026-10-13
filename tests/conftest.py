# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""Shared pytest configuration, Hypothesis profiles, and test helpers.

Hypothesis profiles
───────────────────
- **dev** (default): 50 examples per test — fast local iteration.
- **ci**: 500 examples per test — thorough, used in CI pipelines.
- **purity**: 1 000 examples per test — pre-release exhaustive check.

Select a profile via the ``HYPOTHESIS_PROFILE`` environment variable::

    HYPOTHESIS_PROFILE=ci just test
    HYPOTHESIS_PROFILE=purity just test   # before a release
"""

from __future__ import annotations

import logging
import os

import pytest
from hypothesis import HealthCheck, settings


@pytest.fixture(autouse=True)
def _reset_zenzic_logger():
    """Reset the ``zenzic`` logger after each test.

    CLI-invoking tests call ``setup_cli_logging()``, which installs a
    ``RichHandler`` and sets ``propagate=False`` on the ``zenzic`` root
    logger.  This leaks into subsequent tests that use ``caplog``, which
    relies on propagation reaching the root logger.

    Teardown removes any ``RichHandler`` instances and restores propagation
    so that ``caplog`` captures log records correctly regardless of test
    execution order.
    """
    yield
    zenzic_logger = logging.getLogger("zenzic")
    zenzic_logger.handlers = [
        h for h in zenzic_logger.handlers if h.__class__.__name__ != "RichHandler"
    ]
    if not zenzic_logger.handlers:
        zenzic_logger.propagate = True


@pytest.fixture(autouse=True)
def _strip_color_env_vars(monkeypatch: pytest.MonkeyPatch) -> None:
    """Strip ``FORCE_COLOR``/``NO_COLOR`` and rebuild the CLI console
    singletons clean for every test.

    ``main.py``'s ``--force-color``/``--no-color`` Typer options are bound to
    these env vars (``envvar="FORCE_COLOR"``/``"NO_COLOR"``), so every CLI
    invocation's top-level callback reads them live and calls
    ``configure_console()`` — which, when ``FORCE_COLOR`` is set, rebuilds
    the module-level ``console``/``stderr_console`` singletons with
    ``force_terminal=True``, regardless of whether the real stream (a
    ``CliRunner``-captured buffer) is an actual terminal. Deleting the env
    var stops this from happening *during* the test.

    That alone is not sufficient, though: ``zenzic.cli._shared``'s
    ``console``/``stderr_console`` are also built once at *import* time
    (pytest's collection phase, before any per-test fixture runs) from
    whatever ``FORCE_COLOR``/``NO_COLOR`` happened to be set in the ambient
    shell at that moment. If it was set, both the resulting ``is_terminal``
    resolution *and* the separately-cached ``color_system`` (Rich decides
    color depth once, independent of ``is_terminal``) are poisoned for the
    rest of the process — patching only ``_force_terminal`` on the existing
    objects still leaves ``color_system`` stuck non-``None``, so styled
    numbers/paths keep splitting plain text like ``"1 file"`` across
    separate ANSI color spans even once animation is otherwise disabled.
    Rebuilding both singletons from scratch (matching ``_shared.py``'s own
    constructor exactly, but evaluated fresh) is simpler and fully correct,
    where patching private cached attributes piecemeal was not.

    Confirmed live (reproduced with ``FORCE_COLOR=1 pytest ...``, i.e. set
    in the ambient shell before pytest starts, matching what some CI/mutation
    -testing runners do): without this fixture, a plain
    ``zenzic check all <file>`` invocation's captured stdout contains raw
    ANSI escape sequences and is **missing the ``"N file(s) ..."`` summary
    line entirely** — not merely flaky, a deterministic failure. Any of the
    160+ ``result.stdout`` assertions across the CLI test suite is
    vulnerable to this, not just one test — fixing it once here is the
    single source of truth fix rather than patching each affected assertion.
    """
    monkeypatch.delenv("FORCE_COLOR", raising=False)
    monkeypatch.delenv("NO_COLOR", raising=False)
    from rich.console import Console

    from zenzic.cli import _shared

    monkeypatch.setattr(
        _shared, "console", Console(highlight=False, no_color=False, force_terminal=False)
    )
    monkeypatch.setattr(
        _shared,
        "stderr_console",
        Console(stderr=True, highlight=False, no_color=False, force_terminal=False),
    )


_SUPPRESS = [HealthCheck.too_slow, HealthCheck.differing_executors]


settings.register_profile(
    "ci",
    max_examples=500,
    suppress_health_check=_SUPPRESS,
)
settings.register_profile(
    "dev",
    max_examples=50,
    suppress_health_check=_SUPPRESS,
)
settings.register_profile(
    "purity",
    max_examples=1000,
    suppress_health_check=_SUPPRESS,
)

settings.load_profile(os.getenv("HYPOTHESIS_PROFILE", "dev"))
