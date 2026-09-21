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

import contextlib
import threading
from dataclasses import dataclass
from functools import lru_cache
from importlib.metadata import entry_points
from pathlib import Path
from typing import Any, Final, Literal, cast

from zenzic.core.adapters._mkdocs_config import MKDOCS_CONFIG_NAMES
from zenzic.core.exceptions import CheckError, ZenzicError
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


@dataclass(frozen=True)
class EngineResolution:
    """What engine the run asked for, what it got, and whether those differ.

    The substitution notice has only ever reached stderr, and **stderr reaches
    no CI consumer**: a pipeline reading `--format json` or uploading SARIF sees
    a clean payload and no indication that the engine it declared was not the
    engine that ran. Measured on 2,604 Astro pages, a declared `prebuilt` with
    no manifest produced a run byte-identical to `standalone` -- same total,
    same distribution, same exit code -- and the only signal was a line nobody
    was reading.

    Attached to the adapter the factory returns, so every surface that holds an
    adapter can report it without the factory needing to know which surfaces
    exist.
    """

    declared: str
    resolved: str
    substituted: bool
    reason: str = ""

    def as_payload(self) -> dict[str, object]:
        """The shape both the JSON payload and the SARIF run property carry."""
        out: dict[str, object] = {
            "declared": self.declared,
            "resolved": self.resolved,
            "substituted": self.substituted,
        }
        if self.reason:
            out["reason"] = self.reason
        return out


#: What each engine looks for, so the substitution notice can name the missing
#: file rather than leaving the user to guess which one was wanted.
#: Engines whose adapter reads the documentation generator's **own**
#: configuration, rather than a routing table Zenzic is handed.
#:
#: For these, "which documentation generator is this?" is a question the engine
#: has already answered, and the marker-file detection in
#: ``cli/_standalone.py`` does not apply. Reporting "none detected" there reads
#: as a detection that failed, when nothing was looked for -- which is what a
#: user saw on an MkDocs project until 2026-09-19.
#:
#: ``prebuilt`` and ``vsm`` are deliberately absent: they read a manifest and
#: know nothing about what produced it, so a generator beside them is real
#: information (an Astro site served by ``prebuilt``). ``standalone`` is absent
#: for the same reason.
NATIVE_GENERATOR_ENGINES: Final[frozenset[str]] = frozenset({"mkdocs", "zensical"})

_SUBSTITUTION_HINTS = {
    "prebuilt": "route manifest (.zenzic-vsm.json, read from the repository root)",
    "vsm": "route manifest (.zenzic-vsm.json, read from the repository root)",
    "mkdocs": "mkdocs.yml (or mkdocs.yaml)",
    "zensical": "zensical.toml",
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

    This function is called when ``BuildContext.engine == "auto"`` (the default).
    """
    if (repo_root / ".zenzic-vsm.json").is_file():
        return "prebuilt"
    if (repo_root / "zensical.toml").is_file():
        return "zensical"

    mkdocs_file: Path | None = None
    for name in MKDOCS_CONFIG_NAMES:
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


def manifest_driven_engines() -> frozenset[str]:
    """Engine names whose adapter reads a route manifest instead of a generator config.

    Derived from the registry, never restated. `cli/_shared.py` spelled this as
    the literal ``("prebuilt", "vsm")`` until 2026-09-21, which is the same shape
    as two defects already closed here: ``_INIT_VALID_ENGINES``, where ``--engine``
    refused two engines its own help text advertised, and ``Z503``, where a gate
    covered one call path and not the other.

    The failure mode a literal has here is specific. Register a third adapter that
    reads ``.zenzic-vsm.json`` and the "declared but no manifest" check skips it in
    silence: the project is analysed as something else rather than stopped. The
    registry already holds the fact -- the manifest-driven engines are exactly
    those resolving to :class:`PrebuiltVSMAdapter` -- so an entry-point adapter
    reaches the gate without this module changing.
    """
    # Cached on a fingerprint of the built-in registry rather than unconditionally.
    # Deriving costs ~35 ms -- `list_adapter_engines()` calls `entry_points()`,
    # which scans installed distributions -- and this gate sits on the incremental
    # path. Uncached it pushed `test_engine_latency_benchmark` from under 50 ms to
    # 89.6 ms, which is how the regression was caught rather than shipped.
    #
    # The fingerprint is the built-in registry's keys, so a test that registers a
    # third manifest-driven adapter invalidates the cache and the derivation runs
    # again. Entry points cannot change within a process, so they need no key.
    return _manifest_driven_engines(tuple(sorted(_BUILTIN_ADAPTERS)))


@lru_cache(maxsize=8)
def _manifest_driven_engines(_registry_fingerprint: tuple[str, ...]) -> frozenset[str]:
    """Compute :func:`manifest_driven_engines`; keyed so the registry can change."""
    found = set()
    for name in list_adapter_engines():
        cls = _load_adapter_class(name)
        if cls is not None and isinstance(cls, type) and issubclass(cls, PrebuiltVSMAdapter):
            found.add(name)
    return frozenset(found)


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
    """Return every engine name a user can actually select.

    Union of the ``zenzic.adapters`` entry-point group and the built-in
    registry, matching exactly what :func:`_load_adapter_class` will resolve.
    Entry points alone under-reported: ``prebuilt`` and ``vsm`` are built-in
    only, so ``--engine prebuilt`` was rejected as an "Unknown engine adapter"
    even though the same engine works via ``[build_context] engine`` in config
    and is chosen automatically by :func:`discover_engine` when
    ``.zenzic-vsm.json`` is present. The gate, not the adapter, was the gap.
    """
    eps = entry_points(group="zenzic.adapters")
    return sorted({ep.name for ep in eps} | set(_BUILTIN_ADAPTERS))


# ── Adapter cache ────────────────────────────────────────────────────────────
# Prevents double-instantiation when get_adapter() is called from both
# scanner.py and validator.py in the same CLI session.
# The lock makes writes thread-safe by design, even though the current
# execution model uses ProcessPoolExecutor (each worker has its own cache).
# This eliminates the risk of double-instantiation if a future caller uses
# ThreadPoolExecutor without requiring a code-level change here.
#: (filename, mtime_ns, size) per watched config file; -1/-1 when absent.
_ConfigFingerprint = tuple[tuple[str, int, int], ...]

#: Cached adapter plus the fingerprint of the config files it was built from.
_adapter_cache: dict[tuple[str, Path, Path], tuple[BaseAdapter, _ConfigFingerprint]] = {}
_adapter_cache_lock: threading.Lock = threading.Lock()


def _config_fingerprint(adapter: BaseAdapter, repo_root: Path) -> _ConfigFingerprint:
    """Fingerprint the engine config files *adapter* declares it depends on.

    The cache key is ``(engine, docs_root, repo_root)`` — none of which change
    when the *contents* of ``mkdocs.yml`` change. Without this, staying correct
    was every consumer's own responsibility: each long-running process had to
    remember to call :func:`clear_adapter_cache` at the right trigger. The LSP
    did; ``zenzic-mcp`` did not, and served a stale adapter after a real config
    edit. Fingerprinting makes the cache safe by construction instead.

    Uses ``(mtime_ns, size)`` rather than hashing file contents: it is two
    ``stat()`` calls at most, versus reading every config file on every cache
    hit, and it is what the already-approved design specified. A missing file
    records a distinct sentinel, so deleting a config invalidates rather than
    silently reusing the adapter built when it was present.
    """
    entries: list[tuple[str, int, int]] = []
    for name in sorted(adapter.watched_config_files):
        try:
            stat = (repo_root / name).stat()
        except OSError:
            entries.append((name, -1, -1))
        else:
            entries.append((name, stat.st_mtime_ns, stat.st_size))
    return tuple(entries)


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
    #
    # What the user *declared* is recorded once, on the context itself, because
    # the substitution notice below is a statement about a declaration and the
    # mutation destroys it. Capturing it in a local would not do: one
    # `BuildContext` is shared across every call in a run, so by the second call
    # the field already holds the discovered engine and a local reads that.
    # Reading `context.engine` in the guard made its own `"auto"` exclusion
    # unreachable, and a project that declared nothing was told its declared
    # engine had been replaced. Measured 2026-09-19 on this repository.
    declared_engine = getattr(context, "_zenzic_declared_engine", None)
    if declared_engine is None:
        declared_engine = context.engine
        with contextlib.suppress(Exception):
            object.__setattr__(context, "_zenzic_declared_engine", declared_engine)
    if context.engine == "auto":
        context.engine = discover_engine(repo_root)

    key = (context.engine, docs_root.resolve(), repo_root.resolve())
    # Fast path: read without lock (dict reads are atomic under the GIL), but
    # only reuse the entry while the config it was built from is unchanged.
    cached = _adapter_cache.get(key)
    if cached is not None:
        cached_adapter, cached_fingerprint = cached
        if _config_fingerprint(cached_adapter, repo_root.resolve()) == cached_fingerprint:
            return cached_adapter
        with _adapter_cache_lock:
            _adapter_cache.pop(key, None)

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
    else:
        # A third-party or built-in adapter's constructor/from_repo can raise
        # anything. A ZenzicError subclass is already well-typed (e.g. the
        # real ZensicalAdapter raising ConfigurationError when zensical.toml
        # is absent) and must propagate unchanged. Anything else is an
        # unexpected adapter bug — wrap it as CheckError so cli_main()'s
        # top-level handler renders a clean error instead of a raw traceback.
        try:
            if hasattr(adapter_class, "from_repo"):
                # Prefer the richer from_repo constructor when available.
                adapter = cast(Any, adapter_class).from_repo(context, docs_root, repo_root)
            else:
                adapter = cast(Any, adapter_class)(context, docs_root)
        except ZenzicError:
            raise
        except Exception as exc:
            raise CheckError(
                f"Adapter for engine {context.engine!r} failed to initialize: {exc}",
                context={"engine": context.engine, "cause": str(exc)},
            ) from exc

    if not isinstance(adapter, BaseAdapter):
        raise TypeError(
            f"Adapter instance for engine {context.engine!r} must be a BaseAdapter subclass"
        )

    # If the adapter found no engine config and no locale information, fall
    # back to StandaloneAdapter so nav-dependent checks are skipped cleanly.
    try:
        has_config = adapter.has_engine_config()
    except ZenzicError:
        raise
    except Exception as exc:
        raise CheckError(
            f"Adapter for engine {context.engine!r} failed during has_engine_config(): {exc}",
            context={"engine": context.engine, "cause": str(exc)},
        ) from exc
    messages = []

    if not has_config:
        # A declared engine that finds none of its own configuration is replaced,
        # not defaulted -- the run then reports what StandaloneAdapter reports,
        # which on a site that links by route is an order of magnitude more
        # findings. Measured on a 421-file Starlight tree: 235 with the manifest,
        # 2,443 without it, and byte-identical to declaring "standalone" outright.
        # Said through the same list the offline notice uses rather than through
        # the logger, because the two defects this cycle found hidden behind an
        # invisible notice were both log-only.
        if declared_engine not in ("standalone", "auto"):
            hint = _SUBSTITUTION_HINTS.get(declared_engine, "its own configuration file")
            messages.append(
                f"[bold yellow]NOTICE:[/bold yellow] engine {declared_engine!r} found no "
                f"{hint}, so this run used 'standalone' instead. Findings below are "
                f"StandaloneAdapter's, not {declared_engine!r}'s."
            )
        adapter = StandaloneAdapter()

    # Recorded on the adapter, not only printed. Every surface that holds an
    # adapter can now say what happened -- the JSON payload as a field, SARIF as
    # a run property -- which is what stderr could never do for a CI consumer.
    _resolution = EngineResolution(
        declared=declared_engine,
        resolved="standalone" if not has_config else context.engine,
        substituted=not has_config and declared_engine not in ("standalone", "auto"),
        reason=(
            f"no {_SUBSTITUTION_HINTS.get(declared_engine, 'engine configuration')} found"
            if not has_config and declared_engine not in ("standalone", "auto")
            else ""
        ),
    )
    with contextlib.suppress(Exception):
        object.__setattr__(adapter, "zenzic_resolution", _resolution)

    # `[build_context] base_url` reaches the engine here and nowhere else, so the
    # normalisation exists once. It was declared, written into every generated
    # config and documented as something "the adapter uses ... instead of
    # attempting static extraction" -- and read by nothing, so a project served
    # under `/docs/` set it and got silence rather than an effect.
    #
    # `PrebuiltVSMAdapter` refuses it at construction rather than reaching this
    # line: its routes come from `.zenzic-vsm.json`, which already carries the
    # prefix the real build produced, so a second one would double it.
    # `"/"` is read as *no prefix*, deliberately and for a reason that will not be
    # obvious later: every `.zenzic.toml` this tool has ever generated carried an
    # uncommented `base_url = "/"`, written while nothing read the field. Treating
    # that as a declared base would re-base every absolute link in every existing
    # project the moment the field started working. So `""` and `"/"` both mean the
    # site is served from the root, and the generated template now offers the
    # setting commented out instead of writing a live no-op.
    _declared_base = str(getattr(context, "base_url", "") or "").strip()
    if _declared_base and _declared_base != "/":
        _prefix = "/" + _declared_base.strip("/") + "/"
        with contextlib.suppress(Exception):
            object.__setattr__(adapter, "_zenzic_base_prefixes", [_prefix])

    if getattr(context, "offline_mode", False):
        messages.append("[bold cyan]NOTICE:[/bold cyan] [Offline mode: forcing flat URL structure]")

    if messages:
        from rich.console import Console

        # stderr, not stdout: `--format json` and `--format sarif` write a
        # machine-read payload to stdout, and a notice printed there makes it
        # unparseable. Adding the substitution notice on stdout broke exactly
        # that and the control caught it; the offline notice had the same
        # defect already, which is why `scripts/external_corpus_check.py`
        # searches for the first '{' instead of parsing what it is given.
        Console(highlight=False, stderr=True).print("\n" + "\n".join(messages))

    # Write under lock: prevents double-instantiation if a caller ever uses
    # threads to construct adapters concurrently.
    with _adapter_cache_lock:
        # Re-check after acquiring the lock (double-checked locking pattern).
        if key not in _adapter_cache:
            _adapter_cache[key] = (adapter, _config_fingerprint(adapter, repo_root.resolve()))
    return _adapter_cache[key][0]
