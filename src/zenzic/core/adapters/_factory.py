# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""Adapter factory — dynamic entry-point discovery with StandaloneAdapter fallback.

Adapter registration
--------------------
Adapters are discovered via the ``zenzic.adapters`` entry-point group.  Any
installed package can contribute an adapter by declaring it in ``pyproject.toml``::

    [project.entry-points."zenzic.adapters"]
    myengine = "my_package.adapter:MyEngineAdapter"

The **key** (e.g. ``myengine``) is the engine name users declare in
``.zenzic.toml`` or pass via ``--engine``.

Adapter construction protocol
------------------------------
The factory prefers a ``from_repo(context, docs_root, repo_root)`` classmethod
when it exists on the loaded class.  This lets adapters perform their own config
discovery and enforcement (e.g. raising ``ConfigurationError`` when a required
engine config file is missing).

When ``from_repo`` is absent the factory falls back to calling
``AdapterClass(context, docs_root)``.

Fallback
--------
When no entry point matches the requested engine, :class:`StandaloneAdapter` is
returned.  This keeps Zenzic functional as a standalone document integrity analyzer even when
the docs engine is not installed.
"""

from __future__ import annotations

import threading
from importlib.metadata import entry_points
from pathlib import Path
from typing import Any, Literal, cast

from zenzic.models.config import BuildContext

from ._base import BaseAdapter
from ._mkdocs import MkDocsAdapter
from ._prebuilt import PrebuiltVSMAdapter
from ._standalone import StandaloneAdapter
from ._zensical import ZensicalAdapter


# Built-in adapters registered by engine name.  Entry-point discovery can
# override these, but they are always available even when the package is
# installed in a venv that pre-dates the ``zenzic.adapters`` entry-point group.
_BUILTIN_ADAPTERS: dict[str, type[Any]] = {
    "mkdocs": MkDocsAdapter,
    "zensical": ZensicalAdapter,
    "standalone": StandaloneAdapter,
    "prebuilt": PrebuiltVSMAdapter,
    "vsm": PrebuiltVSMAdapter,
}


def _is_zensical_theme(mkdocs_content: str) -> bool:
    """Inspect mkdocs.yml content for theme: zensical without full YAML parsing.

    Robust against false positives in comments, nav items, or plugins.
    """
    lines = mkdocs_content.splitlines()
    in_theme_block = False
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        if not line.startswith((" ", "\t")):
            if line.startswith("theme:"):
                remainder = line[6:].strip()
                remainder_clean = remainder.split("#", 1)[0].strip().strip("\"'")
                if remainder_clean == "zensical":
                    return True
                in_theme_block = True
                continue
            else:
                in_theme_block = False
        elif in_theme_block:
            clean_indented = stripped.split("#", 1)[0].strip()
            if clean_indented.startswith("name:"):
                val = clean_indented[5:].strip().strip("\"'")
                if val == "zensical":
                    return True
            elif clean_indented.strip("\"'") == "zensical":
                return True
    return False


def discover_engine(repo_root: Path) -> Literal["prebuilt", "mkdocs", "zensical", "standalone"]:
    """Probe *repo_root* for known engine config files and return the canonical engine name.

    Priority order (Engine Discovery Logic):

    1. ``.zenzic-vsm.json``   → ``"prebuilt"``
    2. ``zensical.toml``      → ``"zensical"``
    3. ``mkdocs.yml`` / ``mkdocs.yaml`` with theme: zensical → ``"zensical"`` (compat input)
    4. ``mkdocs.yml`` / ``mkdocs.yaml`` → ``"mkdocs"``
    5. No marker found        → ``"standalone"`` (universal fallback mode)

    This function is called when ``BuildContext.engine == "auto"`` (the default),
    replacing the previous implicit assumption that the engine was MkDocs.
    """
    if (repo_root / ".zenzic-vsm.json").is_file():
        return "prebuilt"
    if (repo_root / "zensical.toml").is_file():
        return "zensical"

    mkdocs_file: Path | None = None
    for name in ("mkdocs.yml", "mkdocs.yaml"):
        candidate = repo_root / name
        if candidate.is_file():
            mkdocs_file = candidate
            break

    if mkdocs_file is not None:
        try:
            content = mkdocs_file.read_text(encoding="utf-8", errors="replace")
            if _is_zensical_theme(content):
                return "zensical"
        except OSError:
            pass
        return "mkdocs"

    return "standalone"


def _load_adapter_class(engine: str) -> type[Any] | None:
    """Return the adapter class registered for *engine*, or ``None``.

    Resolution order:
    1. ``zenzic.adapters`` entry-point group (allows third-party overrides).
    2. Built-in adapter registry (always available regardless of install state).

    """
    eps = entry_points(group="zenzic.adapters")
    for ep in eps:
        if ep.name == engine:
            return ep.load()  # type: ignore[no-any-return]
    return _BUILTIN_ADAPTERS.get(engine)


def list_adapter_engines() -> list[str]:
    """Return sorted list of engine names registered in ``zenzic.adapters``."""
    eps = entry_points(group="zenzic.adapters")
    return sorted(ep.name for ep in eps)


# ── Adapter cache ────────────────────────────────────────────────────────────
# Prevents double-instantiation when get_adapter() is called from both
# scanner.py and validator.py in the same CLI session.
# The lock makes writes thread-safe by design, even though the current
# execution model uses ProcessPoolExecutor (each worker has its own cache).
# This eliminates the risk of double-instantiation if a future caller uses
# ThreadPoolExecutor without requiring a code-level change here.
_adapter_cache: dict[tuple[str, Path, Path], BaseAdapter] = {}
_adapter_cache_lock: threading.Lock = threading.Lock()


def clear_adapter_cache() -> None:
    """Clear the adapter instance cache.

    Call this in test teardown or when configuration changes invalidate
    cached adapter instances.
    """
    with _adapter_cache_lock:
        _adapter_cache.clear()


def get_adapter(
    context: BuildContext,
    docs_root: Path,
    repo_root: Path,
) -> BaseAdapter:
    """Return the adapter for the declared build engine via entry-point discovery.

    Resolution order:

    1. Query the ``zenzic.adapters`` entry-point group for an adapter whose
       name matches ``context.engine``.
    2. If found: instantiate via ``from_repo(context, docs_root, repo_root)``
       classmethod when present; otherwise call
       ``AdapterClass(context, docs_root)``.
    3. If not found: return :class:`StandaloneAdapter` (neutral no-op behaviour).

    Adapter instances are cached by ``(engine, docs_root, repo_root)`` key
    to prevent redundant construction when called from multiple modules in
    the same CLI session.

    This design means adding a new engine adapter **never requires modifying
    Zenzic core** — only installing an adapter package is required.

    Args:
        context: Build context from ``.zenzic.toml``.
        docs_root: Resolved absolute path to the ``docs/`` directory.
        repo_root: Resolved absolute path to the repository root (passed to
            ``from_repo`` when the adapter supports it).

    Returns:
        A concrete adapter instance satisfying the
        :class:`~zenzic.core.adapters.BaseAdapter` protocol.

    Raises:
        :class:`~zenzic.core.exceptions.ConfigurationError`: When the
            discovered adapter's ``from_repo`` raises one (e.g.
            ``ZensicalAdapter`` raises when ``zensical.toml`` is absent).
    """
    # Engine auto-discovery: resolve "auto" to a concrete engine name by probing
    # repo_root for known engine config files.  Mutating context.engine here
    # propagates to the reporter (telemetry line) and _collect_all_results
    # (Z404 config-asset checks) without any additional wiring.
    if context.engine == "auto":
        context.engine = discover_engine(repo_root)

    key = (context.engine, docs_root.resolve(), repo_root.resolve())
    # Fast path: read without lock (dict reads are atomic under the GIL).
    if key in _adapter_cache:
        return _adapter_cache[key]

    adapter_class = _load_adapter_class(context.engine)

    if adapter_class is not None:
        try:
            if not issubclass(adapter_class, BaseAdapter):
                raise TypeError(
                    f"Adapter class for engine {context.engine!r} must subclass BaseAdapter"
                )
        except TypeError as exc:
            if "issubclass" in str(exc):
                raise TypeError(
                    f"Adapter entry-point for engine {context.engine!r} did not resolve to a class"
                ) from exc
            raise

    if adapter_class is None or adapter_class is StandaloneAdapter:
        adapter: BaseAdapter = StandaloneAdapter()
    elif hasattr(adapter_class, "from_repo"):
        # Prefer the richer from_repo constructor when available.
        adapter = cast(Any, adapter_class).from_repo(context, docs_root, repo_root)
    else:
        adapter = cast(Any, adapter_class)(context, docs_root)

    if not isinstance(adapter, BaseAdapter):
        raise TypeError(
            f"Adapter instance for engine {context.engine!r} must be a BaseAdapter subclass"
        )

    # If the adapter found no engine config and no locale information, fall
    # back to StandaloneAdapter so nav-dependent checks are skipped cleanly.
    if not adapter.has_engine_config():
        adapter = StandaloneAdapter()

    messages = []
    if getattr(context, "offline_mode", False):
        messages.append("[bold cyan]NOTICE:[/bold cyan] [Offline mode: forcing flat URL structure]")

    if messages:
        from rich.console import Console

        Console(highlight=False).print("\n" + "\n".join(messages))

    # Write under lock: prevents double-instantiation if a caller ever uses
    # threads to construct adapters concurrently.
    with _adapter_cache_lock:
        # Re-check after acquiring the lock (double-checked locking pattern).
        if key not in _adapter_cache:
            _adapter_cache[key] = adapter
    return _adapter_cache[key]
