# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""``get_adapter()`` robustness: a crashing third-party/adapter class must not
leak a raw, unhandled exception all the way out to the caller.

Prior to this fix, ``get_adapter()`` (``_factory.py``) had zero exception
handling around adapter class resolution/construction. ``cli_main()``'s
top-level handler (``main.py``) only catches ``ZenzicError``/
``PluginContractError`` — an adapter bug (a broken ``__init__``, a missing
abstract-method implementation, any arbitrary exception) crashed the entire
``zenzic check all`` process with a raw Python traceback instead of a clean,
reported error. This was discovered as an aside while investigating the
(separately closed) Z901/Z903 code-numbering question and logged in
``.claude/state/03-priority-table.md`` as its own robustness item.

``get_adapter()`` is the single choke point used by every CLI command,
``scanner.py``, ``validator.py``, and the LSP server (15 call sites total) —
fixing it here covers all of them without touching any caller.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from zenzic.core.adapters import _factory
from zenzic.core.adapters._base import BaseAdapter
from zenzic.core.exceptions import CheckError, ConfigurationError
from zenzic.models.config import BuildContext


class _BrokenAdapter(BaseAdapter):
    """A structurally valid BaseAdapter subclass whose constructor crashes,
    simulating a real bug in a third-party or built-in adapter."""

    def __init__(self, context: Any, docs_root: Path) -> None:
        raise ValueError("simulated third-party adapter bug")

    def has_engine_config(self) -> bool:
        return True

    def get_entry_points(self, vsm: Any) -> list[Any]:
        return []

    def get_locale_source_roots(self) -> list[Any]:
        return []

    def get_absolute_url_prefixes(self) -> list[str]:
        return []

    def get_extra_content_roots(self) -> list[Path]:
        return []

    def get_ignored_patterns(self) -> list[str]:
        return []

    def get_metadata_files(self) -> list[Path]:
        return []

    def get_nav_paths(self) -> list[Path]:
        return []

    def get_route_info(self, *args: Any, **kwargs: Any) -> Any:
        return None

    def is_locale_dir(self, path: Path) -> bool:
        return False

    def is_shadow_of_nav_page(self, path: Path) -> bool:
        return False

    def provides_index(self, path: Path) -> bool:
        return False

    def resolve_anchor(self, *args: Any, **kwargs: Any) -> Any:
        return None

    def resolve_asset(self, *args: Any, **kwargs: Any) -> Any:
        return None


class _WellTypedFailingAdapter(BaseAdapter):
    """Simulates an adapter that already raises a proper ZenzicError subclass
    (e.g. the real ZensicalAdapter raising ConfigurationError when
    zensical.toml is absent) — this must propagate unchanged, not be
    double-wrapped into a generic CheckError."""

    def __init__(self, context: Any, docs_root: Path) -> None:
        raise ConfigurationError("zensical.toml not found", context={"docs_root": str(docs_root)})

    def has_engine_config(self) -> bool:
        return True

    def get_entry_points(self, vsm: Any) -> list[Any]:
        return []

    def get_locale_source_roots(self) -> list[Any]:
        return []

    def get_absolute_url_prefixes(self) -> list[str]:
        return []

    def get_extra_content_roots(self) -> list[Path]:
        return []

    def get_ignored_patterns(self) -> list[str]:
        return []

    def get_metadata_files(self) -> list[Path]:
        return []

    def get_nav_paths(self) -> list[Path]:
        return []

    def get_route_info(self, *args: Any, **kwargs: Any) -> Any:
        return None

    def is_locale_dir(self, path: Path) -> bool:
        return False

    def is_shadow_of_nav_page(self, path: Path) -> bool:
        return False

    def provides_index(self, path: Path) -> bool:
        return False

    def resolve_anchor(self, *args: Any, **kwargs: Any) -> Any:
        return None

    def resolve_asset(self, *args: Any, **kwargs: Any) -> Any:
        return None


@pytest.fixture(autouse=True)
def _clear_cache() -> Any:
    _factory.clear_adapter_cache()
    yield
    _factory.clear_adapter_cache()


def test_crashing_adapter_class_raises_check_error_not_raw_exception(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A broken adapter's constructor must surface as a clean CheckError,
    not an unhandled ValueError propagating out of get_adapter()."""
    monkeypatch.setattr(_factory, "_load_adapter_class", lambda engine: _BrokenAdapter)

    with pytest.raises(CheckError) as exc_info:
        _factory.get_adapter(BuildContext(engine="standalone"), tmp_path / "docs", tmp_path)

    assert "standalone" in str(exc_info.value)
    assert "simulated third-party adapter bug" in str(exc_info.value)


def test_adapter_missing_abstract_methods_raises_check_error(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A structurally incomplete adapter class (missing abstract method
    implementations) must also surface as CheckError, not a raw TypeError."""

    class _IncompleteAdapter(BaseAdapter):
        def __init__(self, context: Any, docs_root: Path) -> None:
            pass

    monkeypatch.setattr(_factory, "_load_adapter_class", lambda engine: _IncompleteAdapter)

    with pytest.raises(CheckError) as exc_info:
        _factory.get_adapter(BuildContext(engine="standalone"), tmp_path / "docs", tmp_path)

    assert "standalone" in str(exc_info.value)


def test_well_typed_zenzic_error_propagates_unwrapped(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """An adapter that already raises a proper ZenzicError subclass (like the
    real ZensicalAdapter's ConfigurationError) must propagate as-is — not be
    double-wrapped into a generic CheckError, which would lose its specific
    type and message."""
    monkeypatch.setattr(_factory, "_load_adapter_class", lambda engine: _WellTypedFailingAdapter)

    with pytest.raises(ConfigurationError) as exc_info:
        _factory.get_adapter(BuildContext(engine="standalone"), tmp_path / "docs", tmp_path)

    assert "zensical.toml not found" in str(exc_info.value)


def test_healthy_adapter_still_works_normally(tmp_path: Path) -> None:
    """The new try/except boundary must not change behavior for the normal,
    non-crashing case."""
    adapter = _factory.get_adapter(BuildContext(engine="standalone"), tmp_path / "docs", tmp_path)
    assert adapter is not None
    assert adapter.has_engine_config() is False
