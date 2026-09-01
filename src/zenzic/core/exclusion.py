# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""Layered Exclusion system: VCS-aware file exclusion with 4-level hierarchy.

This module implements the core exclusion logic for the Zenzic exclusion scope
architecture.  All functions are **pure** — no I/O after construction except
for the ``VCSIgnoreParser.from_file()`` factory.

Exclusion Hierarchy (processed top-to-bottom, first match wins):

1. **System Guardrails (L1):** Hardcoded ``SYSTEM_EXCLUDED_DIRS`` — immutable.
2. **Forced Inclusions (L2):** ``included_dirs`` / ``included_file_patterns``
   from config — overrides VCS and Config exclusions (but NOT L1).
3. **CLI Overrides (L4):** ``--exclude-dir`` / ``--include-dir`` flags.
4. **VCS Discovery (L2-VCS):** ``.gitignore`` patterns when
   ``respect_vcs_ignore = true`` (default).
5. **Config Overrides (L3):** ``excluded_dirs`` / ``excluded_file_patterns``
   from ``.zenzic.toml``.
6. **Default:** Included.

Public API
----------
* :class:`VCSIgnoreParser` — pure-Python gitignore pattern engine.
* :class:`LayeredExclusionManager` — 4-level exclusion orchestrator.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

import pathspec

from zenzic.core import regex as re


if TYPE_CHECKING:
    pass  # PEP 673; typing.Self requires Python 3.11+

from zenzic.models.config import (
    SYSTEM_EXCLUDED_DIRS,
    SYSTEM_EXCLUDED_FILE_NAMES,
    SYSTEM_EXCLUDED_FILE_PATTERNS,
)


if TYPE_CHECKING:
    from zenzic.models.config import ZenzicConfig


# ── VCS Ignore Parser (pathspec-based) ──────────────────────────────────────


def _load_vcs_pathspec(
    repo_root: Path | None, docs_root: Path | None
) -> pathspec.PathSpec[Any] | None:
    """Load a pathspec.PathSpec from .gitignore files in repo_root and docs_root."""
    patterns = []
    for root in (repo_root, docs_root):
        if root is not None:
            gitignore = root / ".gitignore"
            if gitignore.is_file():
                try:
                    patterns.extend(gitignore.read_text(encoding="utf-8-sig").splitlines())
                except (OSError, UnicodeDecodeError):
                    continue
    if patterns:
        return pathspec.PathSpec.from_lines("gitignore", patterns)
    return None


def translate_glob_to_re2(pattern: str) -> str:
    """Translate a shell PATTERN to a regular expression compatible with Google RE2.

    RE2 does not support atomic groups (?>...) or lookarounds.
    We convert standard glob patterns (like *.md, build/*) into strict RE2-compatible
    regex strings without using atomic groups or lookarounds.
    """
    i, n = 0, len(pattern)
    res = []
    while i < n:
        c = pattern[i]
        i += 1
        if c == "*":
            res.append(".*")
        elif c == "?":
            res.append(".")
        elif c == "[":
            j = i
            if j < n and pattern[j] == "!":
                j += 1
            if j < n and pattern[j] == "]":
                j += 1
            while j < n and pattern[j] != "]":
                j += 1
            if j >= n:
                res.append("\\[")
            else:
                stuff = pattern[i:j]
                if stuff.startswith("!"):
                    stuff = "^" + stuff[1:]
                elif stuff.startswith("^"):
                    stuff = "\\^" + stuff[1:]

                escaped_stuff = []
                for char in stuff:
                    if char in ("\\", "[", "]"):
                        escaped_stuff.append("\\" + char)
                    else:
                        escaped_stuff.append(char)
                res.append("[" + "".join(escaped_stuff) + "]")
                i = j + 1
        else:
            res.append(re.escape(c))
    return r"(?s:\A" + "".join(res) + r"\Z)"


# Pre-compiled RE2 patterns for system-level file guardrails (L1a).
# Built once at import time so the hot path in should_exclude_file is O(1).
_SYSTEM_EXCLUDED_FILE_PATTERNS_RE: tuple[re.RegexPattern, ...] = tuple(
    re.compile(translate_glob_to_re2(p)) for p in SYSTEM_EXCLUDED_FILE_PATTERNS
)


# ── Layered Exclusion Manager ────────────────────────────────────────────────


class LayeredExclusionManager:
    """Orchestrates 4-level exclusion with pre-compiled patterns.

    Resolution order per directory (``should_exclude_dir``):
    1. System Guardrails → excluded (immutable)
    2. ``included_dirs`` (config) → included
    3. CLI ``--exclude-dir`` → excluded
    4. CLI ``--include-dir`` → included
    5. VCS ignore → excluded (if ``respect_vcs_ignore``)
    6. ``excluded_dirs`` (config) → excluded
    7. Default → included

    File-level checks (``should_exclude_file``) additionally evaluate
    ``included_file_patterns``, ``excluded_file_patterns``, and VCS patterns
    against the filename.
    """

    __slots__ = (
        "_global_tracker",
        "_system_dirs",
        "_adapter_metadata_files",
        "_config_excluded_dirs",
        "_config_included_dirs",
        "_cli_exclude_dirs",
        "_cli_include_dirs",
        "_config_excluded_patterns",
        "_config_included_patterns",
        "_vcs_pathspec",
        "_respect_vcs",
        "_repo_root",
    )

    def __init__(
        self,
        config: ZenzicConfig,
        *,
        repo_root: Path | None = None,
        docs_root: Path | None = None,
        cli_exclude: list[str] | None = None,
        cli_include: list[str] | None = None,
        adapter_metadata_files: frozenset[str] = frozenset(),
    ) -> None:
        self._system_dirs: frozenset[str] = SYSTEM_EXCLUDED_DIRS
        self._adapter_metadata_files: frozenset[str] = adapter_metadata_files
        self._repo_root: Path | None = repo_root

        # Config-level dirs — strip system guardrails to keep layers clean
        raw_excluded = getattr(config, "excluded_dirs", []) or []
        raw_included = getattr(config, "included_dirs", []) or []
        # When config comes from normal ZenzicConfig(), model_post_init merges
        # SYSTEM_EXCLUDED_DIRS into excluded_dirs. Strip them to avoid L1/L3 confusion.
        self._config_excluded_dirs: frozenset[str] = frozenset(raw_excluded) - self._system_dirs
        self._config_included_dirs: frozenset[str] = frozenset(raw_included) - self._system_dirs

        # CLI overrides
        self._cli_exclude_dirs: frozenset[str] = frozenset(cli_exclude or [])
        self._cli_include_dirs: frozenset[str] = frozenset(cli_include or []) - self._system_dirs

        # File patterns — pre-compiled for performance
        raw_excl_patterns = getattr(config, "excluded_file_patterns", []) or []
        raw_incl_patterns = getattr(config, "included_file_patterns", []) or []
        self._config_excluded_patterns: list[tuple[re.RegexPattern, str]] = [
            (re.compile(translate_glob_to_re2(p)), p) for p in raw_excl_patterns
        ]
        self._config_included_patterns: list[re.RegexPattern] = [
            re.compile(translate_glob_to_re2(p)) for p in raw_incl_patterns
        ]

        # VCS
        self._respect_vcs: bool = getattr(config, "respect_vcs_ignore", False)
        self._vcs_pathspec: pathspec.PathSpec[Any] | None = None
        if self._respect_vcs:
            self._vcs_pathspec = _load_vcs_pathspec(repo_root, docs_root)

        self._global_tracker = getattr(config, "_global_tracker", None)

    def security_view(self) -> LayeredExclusionManager:
        """A copy of this manager with every user-configurable layer stripped.

        The credential/forbidden-term tier (Z201/Z204/Z205) must scan every
        file that ships, so its discovery pass ignores ``excluded_dirs``,
        ``excluded_file_patterns``, CLI ``--exclude-dir`` **and ``.gitignore``**
        — configuration can scope a file out of quality analysis, never out of
        the secret scan.

        The VCS layer used to be retained here, on the rationale that
        gitignored content is outside the published corpus. That rationale was
        wrong twice over. ``pathspec`` implements gitignore *pattern matching*;
        it does not implement git's rule that an **already-tracked file is
        never ignored**, so adding one line to ``.gitignore`` hid a file from
        Zenzic while git kept tracking it — the file still shipped and still
        rendered, which is the exact opposite of the boundary this docstring
        claimed. And ``.gitignore`` is user-editable and reviewer-invisible,
        which made it a suppression mechanism for a tier three separate code
        paths call non-suppressible.

        Adapter-supplied metadata filenames are stripped for the same reason.
        That set exists so an engine's own config is not analysed as
        documentation, but ``ZensicalAdapter`` folds in every string under
        ``extra_css``/``extra_javascript``/``theme.logo``/``theme.favicon`` with
        no extension filter, and the manager matches it by **basename anywhere
        in the tree** as an L1a guardrail — so ``extra_css = ["leak.md"]`` in a
        project's own config hid every ``leak.md`` from the credential scan.
        A guardrail the scanned project can write into is user-controllable by
        definition. Nothing is lost by dropping it here: this view only walks
        ``DOC_SUFFIXES`` files, and a real engine config is not one.

        Only the system guardrails survive: they are the engine's own
        internals (``.git``, ``node_modules``, build output), fixed in code and
        not editable by the project under scan. That is the whole boundary now.
        """
        view = object.__new__(LayeredExclusionManager)
        view._system_dirs = self._system_dirs
        # Stripped: config-driven, basename-matched tree-wide, and writable by
        # the project under scan -- see the docstring above.
        view._adapter_metadata_files = frozenset()
        view._repo_root = self._repo_root
        view._config_excluded_dirs = frozenset()
        view._config_included_dirs = frozenset()
        view._cli_exclude_dirs = frozenset()
        view._cli_include_dirs = frozenset()
        view._config_excluded_patterns = []
        view._config_included_patterns = []
        # Stripped, not retained: see the docstring above. A user-editable file
        # must not be able to decide what the security tier looks at.
        view._respect_vcs = False
        view._vcs_pathspec = None
        # A read-only discovery pass must not consume tracker state (CQS).
        view._global_tracker = None
        return view

    def should_exclude_dir(self, dir_name: str, rel_path: str | None = None) -> bool:
        """Return True if a directory should be excluded during walk.

        Fast path: checks directory name against all layers.
        """
        # L1: System guardrails — immutable, absolute priority
        if dir_name in self._system_dirs:
            return True

        # L2 forced: Config included_dirs override config exclusions
        if dir_name in self._config_included_dirs:
            return False

        # L4: CLI --exclude-dir
        if dir_name in self._cli_exclude_dirs:
            return True

        # L4: CLI --include-dir
        if dir_name in self._cli_include_dirs:
            return False

        # L2 VCS: VCS ignore (for directories)
        if self._vcs_pathspec is not None:
            check_path = rel_path if rel_path else dir_name
            if self._vcs_pathspec.match_file(check_path + "/"):
                return True

        # L3: Config excluded_dirs
        if dir_name in self._config_excluded_dirs:
            return True
        if rel_path and rel_path in self._config_excluded_dirs:
            return True

        # L7: Default — included
        return False

    def should_exclude_file(self, file_path: Path, docs_root: Path) -> bool:
        """Return True if a file should be excluded from scanning.

        Full 5-layer evaluation for individual files.

        Path normalisation (LSP-FIX-008):
            The incoming *file_path* may be either an absolute path (from the
            LSP server, which resolves URIs to ``Path`` objects) or a relative
            path (from the CLI ``os.walk`` loop).  To guarantee deterministic
            exclusion results regardless of the caller, a single canonical
            ``eval_path`` is derived at the L2-VCS / L3-Config boundary:

            1. If *file_path* is absolute and inside ``self._repo_root``, it
               is made repo-relative — the authoritative form for VCS patterns
               and full-depth config exclusions.
            2. Otherwise the docs-relative *rel_path* is used as fallback.

            All L2 VCS and L3 Config path-prefix checks operate on
            ``eval_str`` (the ``as_posix()`` of ``eval_path``), so patterns
            such as ``docs/tutorials/examples`` match correctly even when the
            caller passes an absolute path like
            ``/repo/docs/tutorials/examples/file.md``.
        """
        filename = file_path.name
        try:
            rel_path = file_path.relative_to(docs_root).as_posix()
        except ValueError:
            rel_path = filename

        # L1a: System file guardrails — immutable (infrastructure + adapter metadata)
        if (
            filename in SYSTEM_EXCLUDED_FILE_NAMES
            or any(p.match(filename) for p in _SYSTEM_EXCLUDED_FILE_PATTERNS_RE)
            or filename in self._adapter_metadata_files
        ):
            return True

        # L1: System guardrails — check path components (docs-relative scope)
        for part in Path(rel_path).parts[:-1]:  # directories only, not filename
            if part in self._system_dirs:
                return True

        # L2 forced: included_file_patterns (override everything except L1)
        if self._config_included_patterns:
            if any(p.match(filename) for p in self._config_included_patterns):
                return False

        # L2 forced: included_dirs (docs-relative scope)
        for part in Path(rel_path).parts[:-1]:
            if part in self._config_included_dirs:
                return False

        # L4: CLI --exclude-dir (docs-relative scope)
        for part in Path(rel_path).parts[:-1]:
            if part in self._cli_exclude_dirs:
                return True

        # L4: CLI --include-dir (docs-relative scope)
        for part in Path(rel_path).parts[:-1]:
            if part in self._cli_include_dirs:
                return False

        # ── Path normalisation for L2-VCS and L3-Config checks ──────────────
        # Derive a repo-relative path so that absolute paths delivered by the
        # LSP server produce the same exclusion result as CLI-relative paths.
        # Priority: repo-relative > docs-relative > filename-only.
        try:
            eval_path = (
                file_path.relative_to(self._repo_root)
                if (file_path.is_absolute() and self._repo_root is not None)
                else Path(rel_path)
            )
        except ValueError:
            # file_path is absolute but outside the repo — fall back to docs-relative
            eval_path = Path(rel_path)

        eval_str = eval_path.as_posix()

        # L2 VCS: .gitignore patterns (evaluated against repo-relative path)
        if self._vcs_pathspec is not None:
            if self._vcs_pathspec.match_file(eval_str):
                return True

        # L3: Config excluded_file_patterns (filename match — path-independent)
        if self._config_excluded_patterns:
            for p, original_str in self._config_excluded_patterns:
                if p.match(filename):
                    if self._global_tracker:
                        self._global_tracker.mark_excluded_file_pattern_used(original_str)
                    return True

        # L3: Config excluded_dirs — individual component match (e.g. "examples")
        for part in eval_path.parts[:-1]:
            if part in self._config_excluded_dirs:
                return True

        # L3: Config excluded_dirs — full-depth prefix match
        # Handles patterns like "docs/tutorials/examples" which are repo-relative
        # and thus never matched by a single-component scan.
        for i in range(1, len(eval_path.parts)):
            prefix = "/".join(eval_path.parts[:i])
            if prefix in self._config_excluded_dirs:
                return True

        # L7: Default — included
        return False

    @property
    def excluded_dirs(self) -> frozenset[str]:
        """Backward-compatible property: all excluded directory names.

        Returns the union of system guardrails, config exclusions, and CLI
        exclusions.  Used by callers that need a flat set (e.g. ``walk_files``
        fallback path).
        """
        return self._system_dirs | self._config_excluded_dirs | self._cli_exclude_dirs
