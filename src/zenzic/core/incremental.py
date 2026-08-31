# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""Deterministic incremental analysis engine for documentation graphs.

This module implements the ``IncrementalAnalysisEngine``, the transport-agnostic
core of Zenzic's O(K) incremental analysis pipeline.  It is responsible for:

1. Maintaining per-file content and anchor caches.
2. Patching ``Route`` objects in the ``VirtualSiteMap`` on file mutations.
3. Expanding the affected-file set via the VSM's topological reverse index.
4. Running the Adaptive Rule Engine and URP checks on affected files only.
5. Producing strictly typed ``ZenzicDiagnostic`` instances.

Architecture invariants
-----------------------
- **ADR-075 (Radical Unawareness):** This module has zero knowledge of JSON-RPC,
  LSP, VS Code, or any transport layer.  It imports only from ``zenzic.core.*``
  and ``zenzic.models.*``.
- **Determinism:** Cache invalidation is strictly topological — no LRU, TTL,
  or probabilistic eviction.  Identical inputs produce identical outputs.
- **O(K) complexity:** Only modified files plus their direct topological
  dependents are reprocessed.
- **State isolation:** The engine operates on the provided ``VirtualSiteMap``
  and ``VirtualBufferOverlay`` instances.  No global mutable state.
- **Zero Subprocess:** No ``subprocess``, ``os.system``, or shell invocation.
- **ADR-013 (RE2 Discipline):** No ``import re``.  All regex through
  ``zenzic.core.regex``.
- **Thread safety:** No background threads or asynchronous event loops.
"""

from __future__ import annotations

import html
import contextlib
import os
import posixpath
from pathlib import Path
from typing import TYPE_CHECKING, Any
from urllib.parse import unquote, urlsplit
from urllib.request import url2pathname

from zenzic.core.ast import ExtractedLink
from zenzic.core.codes import code_severity
from zenzic.core.resolver import resolve_href_target
from zenzic.core.rules import (
    AdaptiveRuleEngine,
    ResolutionContext,
    RuleFinding,
)
from zenzic.core.suppressions import SuppressionTracker
from zenzic.core.validator import (
    _POLY_CLEAN_URL_RE,
    PolyglotExtractor,
    _classify_traversal_intent,
    anchors_in_file,
    check_snippet_content,
)
from zenzic.models.diagnostics import (
    DiagnosticPosition,
    DiagnosticRange,
    Severity,
    ZenzicDiagnostic,
)
from zenzic.models.vsm import Route, VirtualBufferOverlay, VirtualSiteMap, build_vsm


if TYPE_CHECKING:
    from zenzic.core.adapters._base import BaseAdapter
    from zenzic.models.config import ZenzicConfig


def _uri_to_path(uri: str) -> Path:
    """Convert a file:// URI to a cross-platform pathlib.Path."""
    parsed = urlsplit(uri)
    return Path(url2pathname(parsed.path))


class IncrementalAnalysisEngine:
    """Deterministic incremental analysis engine for documentation graphs.

    Transport-agnostic: zero knowledge of JSON-RPC, LSP, or VS Code (ADR-075).
    Operates strictly on the provided ``VirtualSiteMap`` and
    ``VirtualBufferOverlay`` instances.

    The engine maintains per-file content and anchor caches as instance state.
    Cache invalidation is strictly topological: when a file is modified, its
    AST and anchor caches are atomically replaced before resolving dependents.

    Attributes:
        config: Active Zenzic configuration.
        rule_engine: Adaptive Rule Engine instance.
        adapter: Build-engine adapter (Standalone, MkDocs, or Zensical).
        docs_root: Resolved absolute path to the documentation directory.
        repo_root: Resolved absolute path to the repository root.
        md_contents_cache: Per-file raw Markdown content cache.
        anchors_cache: Per-file anchor slug set cache.
    """

    def __init__(
        self,
        config: ZenzicConfig,
        rule_engine: AdaptiveRuleEngine,
        adapter: BaseAdapter,
        docs_root: Path,
        repo_root: Path,
    ) -> None:
        """Initialize the engine with configuration and subsystem references.

        Args:
            config: Active Zenzic configuration.
            rule_engine: Pre-built Adaptive Rule Engine.
            adapter: Build-engine adapter for routing metadata.
            docs_root: Resolved absolute path to the docs directory.
            repo_root: Resolved absolute path to the repository root.
        """
        self.config = config
        self.rule_engine = rule_engine
        self.adapter = adapter
        self.docs_root = docs_root
        self.repo_root = repo_root
        self.md_contents_cache: dict[Path, str] = {}
        self.anchors_cache: dict[Path, set[str]] = {}
        self._use_directory_urls: bool = self._resolve_use_directory_urls()
        self._initialized: bool = False
        # ADR-075 / LSP-FIX-017: tracks which file URIs currently have at least
        # one active diagnostic in this engine's last analysis cycle.
        # Semantically pure — no knowledge of LSP transport or "publishing".
        self._uris_with_active_diagnostics: set[str] = set()

    def _resolve_use_directory_urls(self) -> bool:
        """Resolve canonical URL mode through the public adapter contract."""
        if self.adapter is None:
            return True
        return self.adapter.use_directory_urls

    # ── Cache management API ──────────────────────────────────────────────────

    def update_file_cache(self, path: Path, text: str) -> None:
        """Atomically update the content and anchor caches for a single file.

        Args:
            path: Resolved absolute path of the file.
            text: Raw Markdown content.
        """
        self.md_contents_cache[path] = text
        self.anchors_cache[path] = anchors_in_file(text)

    def remove_file_cache(self, path: Path) -> None:
        """Remove a file from the content and anchor caches.

        Args:
            path: Resolved absolute path of the file to evict.
        """
        self.md_contents_cache.pop(path, None)
        self.anchors_cache.pop(path, None)

    # ── Primary entry point ───────────────────────────────────────────────────

    def process_changes(
        self,
        vsm: VirtualSiteMap,
        overlay: VirtualBufferOverlay,
        changed_uris: set[str] | None = None,
    ) -> dict[str, list[ZenzicDiagnostic]]:
        """Run incremental or full analysis and return diagnostics per URI.

        When ``changed_uris`` is ``None``, a full workspace sync is performed.
        Otherwise, only the specified files and their topological dependents
        are reprocessed (O(K) complexity).

        The engine writes diagnostics to ``Route.diagnostics`` on the VSM
        (Mirror Law) and returns them keyed by file URI.

        Args:
            vsm: The active Virtual Site Map instance.
            overlay: The active Virtual Buffer Overlay instance.
            changed_uris: Set of ``file://`` URIs that changed, or ``None``
                for full sync.

        Returns:
            Mapping of file URI to list of ``ZenzicDiagnostic`` instances.
        """
        from zenzic.core.discovery import DOC_SUFFIXES, iter_markdown_sources, walk_files
        from zenzic.core.exclusion import LayeredExclusionManager
        from zenzic.models.config import load_config_with_diagnostics

        # 0. Validate .zenzic.toml config
        config_file = self.repo_root / ".zenzic.toml"
        if not config_file.is_file() and (self.repo_root / "pyproject.toml").is_file():
            config_file = self.repo_root / "pyproject.toml"
        config_uri = config_file.resolve().as_uri()
        cfg_override = overlay.buffers.get(config_uri)

        new_config, config_findings = load_config_with_diagnostics(
            self.repo_root, config_file=config_file, content_override=cfg_override
        )
        if config_findings:
            cfg_text = cfg_override if cfg_override is not None else ""
            if not cfg_text:
                try:
                    cfg_text = config_file.read_text(encoding="utf-8")
                except OSError:
                    pass
            diags = self._findings_to_diagnostics(cfg_text, config_findings)
            return {config_uri: diags}
        if new_config:
            self.config = new_config

        # Force full sync on first invocation
        if not self._initialized:
            changed_uris = None
            self._initialized = True

        exclusion_manager = LayeredExclusionManager(
            self.config, repo_root=self.repo_root, docs_root=self.docs_root
        )

        # 1. Update text and anchors for modified files (or all files on full sync)
        files_to_process: set[Path] = set()

        if changed_uris is None:
            valid_paths: set[Path] = set()
            # Full read
            for md_file in iter_markdown_sources(self.docs_root, self.config, exclusion_manager):
                uri = md_file.resolve().as_uri()
                if uri in overlay.buffers:
                    text = overlay.buffers[uri]
                else:
                    try:
                        text = md_file.read_text(encoding="utf-8")
                    except OSError:
                        continue
                path = md_file.resolve()
                self.md_contents_cache[path] = text
                self.anchors_cache[path] = anchors_in_file(text)
                files_to_process.add(path)
                valid_paths.add(path)

            # Static asset files (HTML, images, etc.) under docs_root
            self.static_assets_cache: set[Path] = set()
            if self.docs_root.is_dir():
                for file_path in walk_files(
                    self.docs_root, set(self.config.excluded_dirs), exclusion_manager, self.config
                ):
                    if (
                        file_path.is_dir()
                        or file_path.is_symlink()
                        or file_path.suffix in DOC_SUFFIXES
                    ):
                        continue
                    if exclusion_manager.should_exclude_file(file_path, self.docs_root):
                        continue
                    self.static_assets_cache.add(file_path.resolve())

            # Process open buffers not already cached (virtual or out-of-bounds).
            for buf_uri, buf_text in overlay.buffers.items():
                if buf_uri.startswith("file://"):
                    buf_path = _uri_to_path(buf_uri).resolve()
                    if buf_path.suffix.lower() not in DOC_SUFFIXES:
                        continue
                    if exclusion_manager.should_exclude_file(buf_path, self.docs_root):
                        continue
                    if buf_path not in self.md_contents_cache:
                        self.md_contents_cache[buf_path] = buf_text
                        self.anchors_cache[buf_path] = anchors_in_file(buf_text)
                    files_to_process.add(buf_path)
                    valid_paths.add(buf_path)

            # Atomic cache pruning (LSP-FIX-017 / Zero-DBT):
            # Remove stale deleted paths from caches so phantom routes are not created.
            stale_paths = set(self.md_contents_cache.keys()) - valid_paths
            for stale_path in stale_paths:
                self.md_contents_cache.pop(stale_path, None)
                self.anchors_cache.pop(stale_path, None)
        else:
            # Incremental read
            for uri in changed_uris:
                if not uri.startswith("file://"):
                    continue
                path = _uri_to_path(uri).resolve()
                if path.suffix.lower() not in DOC_SUFFIXES:
                    continue
                if exclusion_manager.should_exclude_file(path, self.docs_root):
                    continue
                if uri in overlay.buffers:
                    text = overlay.buffers[uri]
                    self.md_contents_cache[path] = text
                    self.anchors_cache[path] = anchors_in_file(text)
                files_to_process.add(path)

        # 2. Re-build or patch VSM topology
        if changed_uris is None:
            new_vsm = build_vsm(
                self.adapter,
                self.docs_root,
                self.md_contents_cache,
                anchors_cache=self.anchors_cache,
                repo_root=self.repo_root,
                static_assets=getattr(self, "static_assets_cache", None),
            )
            # Transfer topology into the provided VSM instance
            vsm.clear()
            vsm.update(new_vsm)
            vsm.incoming_links = new_vsm.incoming_links
        else:
            # O(K) in-place patch
            for path in files_to_process:
                self._patch_vsm_route(vsm, path)

        # Update overlay's VSM reference
        overlay.vsm = vsm

        # 2b. Run Topological Analysis
        old_orphans: set[str] = getattr(self, "_orphaned_urls", set())
        old_dead_ends: set[str] = getattr(self, "_dead_end_urls", set())

        if hasattr(self.adapter, "get_entry_points"):
            from zenzic.core.topology import detect_dead_ends, detect_orphans

            entry_points = self.adapter.get_entry_points(vsm)
            self._orphaned_urls = set(detect_orphans(vsm, entry_points))
            self._dead_end_urls = set(detect_dead_ends(vsm))
        else:
            self._orphaned_urls = set()
            self._dead_end_urls = set()

        if changed_uris is not None:
            topo_delta_urls = (old_orphans ^ self._orphaned_urls) | (
                old_dead_ends ^ self._dead_end_urls
            )
            if topo_delta_urls:
                for delta_url in topo_delta_urls:
                    route = vsm.get(delta_url)
                    if route and route.source:
                        delta_path = (self.docs_root / route.source).resolve()
                        if delta_path not in self.md_contents_cache and delta_path.is_file():
                            try:
                                delta_text = delta_path.read_text(encoding="utf-8")
                                self.md_contents_cache[delta_path] = delta_text
                                self.anchors_cache[delta_path] = anchors_in_file(delta_text)
                            except OSError:
                                continue
                        if delta_path in self.md_contents_cache:
                            files_to_process.add(delta_path)

        # 3. Expand files_to_process with dependents via VSM's O(1) reverse index
        if changed_uris is not None:
            dependents: set[Path] = set()
            for path in files_to_process:
                canonical = self._resolve_canonical_url(vsm, path)
                if canonical and hasattr(vsm, "incoming_links"):
                    dependents.update(vsm.incoming_links.get(canonical, set()))
            files_to_process.update(dependents)

        # 4. Add virtual routes for out-of-bounds files (Mirror Law)
        for path in files_to_process:
            if path not in self.md_contents_cache:
                continue  # Deleted files must not get virtual routes
            self._ensure_virtual_route(vsm, path)

        # 5. Run URP & Engine on files_to_process
        results: dict[str, list[ZenzicDiagnostic]] = {}
        for path in files_to_process:
            if path not in self.md_contents_cache:
                continue
            text = self.md_contents_cache[path]
            uri = path.as_uri()
            typed_diags = self._analyze_file(vsm, path, text)

            # Store diagnostics on the VSM route (Mirror Law)
            try:
                rel = path.relative_to(self.docs_root).as_posix()
            except ValueError:
                rel = path.absolute().as_posix()
            for route in vsm.values():
                if route.source == rel:
                    route.diagnostics = typed_diags
                    break

            results[uri] = typed_diags

        # 6. Ghost diagnostic clearing (LSP-FIX-017 — engine side)
        # On a full workspace sync, detect URIs that previously had active
        # diagnostics but whose backing file has since left the VSM (deleted,
        # moved, or excluded).  Injecting an empty list into ``results``
        # signals the transport layer to clear them from the client without
        # any additional logic there.
        # This is intentionally skipped on incremental syncs (changed_uris is
        # not None) because a targeted incremental pass cannot authoritatively
        # determine that an *unrelated* file is gone — only a full rebuild can.
        if changed_uris is None:
            for ghost_uri in list(self._uris_with_active_diagnostics):
                if ghost_uri not in results:
                    ghost_path = _uri_to_path(ghost_uri).resolve()
                    if ghost_path not in self.md_contents_cache:
                        # File is gone from the analysis graph — emit empty list
                        results[ghost_uri] = []

        # Update the active-diagnostic URI set for the next cycle.
        # Only URIs with at least one diagnostic are considered "active".
        self._uris_with_active_diagnostics = {uri for uri, diags in results.items() if diags}

        return results

    # ── Private: VSM patching ─────────────────────────────────────────────────

    def _patch_vsm_route(self, vsm: VirtualSiteMap, path: Path) -> None:
        """Patch a single route in the VSM after a file mutation.

        For deleted files, removes the route and outgoing links.
        For created/modified files, updates the route and reindexes links.

        Args:
            vsm: The active Virtual Site Map instance.
            path: Resolved absolute path of the mutated file.
        """
        if path not in self.md_contents_cache:
            # File was deleted — remove route
            try:
                if path.is_relative_to(self.docs_root):
                    rel_obj = path.relative_to(self.docs_root)
                else:
                    rel_obj = path
                route_meta = self.adapter.get_route_info(rel_obj)
                canonical = route_meta.canonical_url
            except Exception:
                canonical = ""
            if canonical and canonical in vsm:
                del vsm[canonical]
            if hasattr(vsm, "remove_outgoing_links"):
                vsm.remove_outgoing_links(path, canonical_url=canonical)
        else:
            # File was created or modified — update route
            try:
                if path.is_relative_to(self.docs_root):
                    rel_obj = path.relative_to(self.docs_root)
                else:
                    rel_obj = path
                route_meta = self.adapter.get_route_info(rel_obj)
            except Exception:
                route_meta = None

            if route_meta:
                vsm[route_meta.canonical_url] = Route(
                    url=route_meta.canonical_url,
                    source=rel_obj.as_posix(),
                    status=route_meta.status,
                    anchors=self.anchors_cache.get(path, set()),
                )
            if hasattr(vsm, "reindex_outgoing_links"):
                vsm.reindex_outgoing_links(
                    path,
                    self.md_contents_cache[path],
                    self.docs_root,
                    [],
                    self.adapter,
                    canonical_url=route_meta.canonical_url if route_meta else "",
                )

    def _resolve_canonical_url(self, vsm: VirtualSiteMap, path: Path) -> str:
        """Resolve a file path to its canonical URL in the VSM.

        Tries the reverse lookup first (O(N) scan), then falls back to the
        adapter's ``get_route_info``.

        Args:
            vsm: The active Virtual Site Map instance.
            path: Resolved absolute path of the file.

        Returns:
            Canonical URL string, or empty string if not found.
        """
        try:
            rel_posix = path.relative_to(self.docs_root).as_posix()
        except ValueError:
            rel_posix = path.absolute().as_posix()
        canonical = next((url for url, r in vsm.items() if r.source == rel_posix), "")

        if not canonical:
            with contextlib.suppress(Exception):
                if path.is_relative_to(self.docs_root):
                    rel_obj = path.relative_to(self.docs_root)
                else:
                    rel_obj = path
                meta = self.adapter.get_route_info(rel_obj)
                canonical = meta.canonical_url

        return canonical

    def _ensure_virtual_route(self, vsm: VirtualSiteMap, path: Path) -> None:
        """Ensure a file has a route in the VSM, adding a virtual one if needed.

        Files outside ``docs_root`` or not yet registered in the VSM receive a
        virtual route so the Rule Engine can process them (Mirror Law).

        Args:
            vsm: The active Virtual Site Map instance.
            path: Resolved absolute path of the file.
        """
        try:
            rel_posix = path.relative_to(self.docs_root).as_posix()
        except ValueError:
            rel_posix = path.absolute().as_posix()

        route = next((r for r in vsm.values() if r.source == rel_posix), None)
        if not route:
            virtual_url = f"/_virtual/{path.name}"
            vsm[virtual_url] = Route(
                url=virtual_url,
                source=rel_posix,
                status="REACHABLE",
                anchors=self.anchors_cache.get(path, set()),
            )

    # ── Private: Per-file analysis ────────────────────────────────────────────

    def _analyze_file(
        self,
        vsm: VirtualSiteMap,
        path: Path,
        text: str,
    ) -> list[ZenzicDiagnostic]:
        """Run all analysis passes on a single file and return typed diagnostics.

        Analysis passes (deterministic order):
        1. Atomic rules via the Adaptive Rule Engine.
        2. VSM-aware rules (cross-file link validation).
        3. Snippet content checks.
        4. URP checks (Polyglot Extractor + Markdown link analysis).
        5. Dead suppression detection.

        Args:
            vsm: The active Virtual Site Map instance.
            path: Resolved absolute path of the file.
            text: Raw Markdown content.

        Returns:
            List of strictly typed ``ZenzicDiagnostic`` instances.
        """
        findings: list[RuleFinding] = []

        tracker = SuppressionTracker(path, text)

        # Extracted Link Candidates (URP Front-End)
        extracted_links = PolyglotExtractor().extract_all_links(text)

        # Atomic Rules
        findings.extend(self.rule_engine.run_with_tracker(path, text, tracker))

        # Credential scan — single-pass; CredentialScannerRule is excluded from
        # the rule engine to avoid a double-pass in the CLI path (harvest() already
        # scans there). In the LSP path harvest() is not called, so we scan here.
        from zenzic.core.credentials import (
            scan_line_for_forbidden_terms,
            scan_lines_with_lookback,
        )

        lines = text.splitlines(keepends=True)
        secret_line_nos: set[int] = set()
        for _sf in scan_lines_with_lookback(enumerate(lines, 1), path):
            secret_line_nos.add(_sf.line_no)
            findings.append(
                RuleFinding(
                    rule_id="Z201",
                    severity=code_severity("Z201"),
                    file_path=_sf.file_path,
                    line_no=_sf.line_no,
                    message=f"Credential or secret detected: {_sf.secret_type}",
                    match_text=_sf.match_text,
                    matched_line=_sf.url,
                    col_start=_sf.col_start,
                )
            )

        # Forbidden-term scan (Z204) — same first-match-wins semantics as
        # scanner.py's harvest(): skip lines already flagged as a credential.
        fp = self.config.forbidden_patterns
        if fp:
            fp_compiled = self.config.forbidden_patterns_compiled
            for _lineno, _raw_line in enumerate(lines, 1):
                if _lineno in secret_line_nos:
                    continue
                for _tf in scan_line_for_forbidden_terms(
                    _raw_line, fp, path, _lineno, compiled_pattern=fp_compiled
                ):
                    findings.append(
                        RuleFinding(
                            rule_id="Z204",
                            severity=code_severity("Z204"),
                            file_path=_tf.file_path,
                            line_no=_tf.line_no,
                            message=(
                                f"Forbidden term detected — remove from documentation: "
                                f"'{_tf.match_text}'"
                            ),
                            match_text=_tf.match_text,
                            matched_line=_tf.url,
                            col_start=_tf.col_start,
                        )
                    )

        # Policy-as-Code Engine (v0.28.0)
        from zenzic.core.governance import check_policies

        policy_findings = check_policies(
            path, text, self.config, links=[link.url for link in extracted_links]
        )
        for pf in policy_findings:
            if not tracker.is_suppressed(pf.line_no, pf.rule_id):
                findings.append(pf)

        # VSM-aware Rules
        context = ResolutionContext(
            docs_root=self.docs_root,
            source_file=path,
            use_directory_urls=self._use_directory_urls,
        )
        findings.extend(
            self.rule_engine.run_vsm(
                path, text, vsm, self.anchors_cache, context, extracted_links=extracted_links
            )
        )

        # Snippet Checks
        for s_err in check_snippet_content(text, path, self.config):
            findings.append(
                RuleFinding(
                    file_path=path,
                    line_no=s_err.line_no,
                    rule_id=s_err.code,
                    message=s_err.message,
                    severity=code_severity(s_err.code),
                )
            )

        # URP Checks
        findings.extend(
            self._run_urp_checks(vsm, path, text, tracker=tracker, extracted_links=extracted_links)
        )

        # Topological Rules (Z410, Z411)
        canonical_url = self._resolve_canonical_url(vsm, path)
        if canonical_url in getattr(self, "_orphaned_urls", set()):
            findings.append(
                RuleFinding(
                    path,
                    1,
                    "Z410",
                    f"Document is isolated and unreachable from the navigation entry points: '{canonical_url}'",
                    severity=code_severity("Z410"),
                    matched_line="",
                )
            )
        if canonical_url in getattr(self, "_dead_end_urls", set()):
            findings.append(
                RuleFinding(
                    path,
                    1,
                    "Z411",
                    f"Document has no outgoing links and forms a structural dead end: '{canonical_url}'",
                    severity=code_severity("Z411"),
                    matched_line="",
                )
            )

        # Dead suppression detection
        findings.extend(tracker.get_dead_suppressions())

        # Apply Governance filters (per_file_ignores and directory_policies) — DRY LSP Governance
        from zenzic.core.governance import apply_directory_policies, apply_per_file_ignores

        findings = apply_per_file_ignores(
            findings, self.config, repo_root=self.repo_root, docs_root=self.docs_root
        )
        findings = apply_directory_policies(
            findings, self.config, repo_root=self.repo_root, docs_root=self.docs_root
        )

        # Convert findings to strictly typed ZenzicDiagnostic instances
        return self._findings_to_diagnostics(text, findings)

    def _findings_to_diagnostics(
        self, text: str, findings: list[RuleFinding]
    ) -> list[ZenzicDiagnostic]:
        """Convert raw ``RuleFinding`` instances to strictly typed diagnostics.

        Performs UTF-16 column offset conversion for LSP-compatible ranges.

        Args:
            text: Raw Markdown content (for line lookup).
            findings: List of rule findings to convert.

        Returns:
            List of ``ZenzicDiagnostic`` instances.
        """
        lines = text.splitlines()
        typed_diags: list[ZenzicDiagnostic] = []

        for f in findings:
            # Severity parity (LSP-FIX-014): drop INFO-level findings at the
            # transport boundary.  INFO findings (e.g. Z106 non-HTTP scheme hints)
            # carry no actionable remediation and would flood the VS Code PROBLEMS
            # panel with noise.  The authoritative record of INFO findings is the
            # CLI report; the LSP surface is reserved for errors and warnings only.
            if getattr(f, "severity", "error") == "info":
                continue
            line_no = max(0, f.line_no - 1)
            matched_line = lines[line_no] if 0 <= line_no < len(lines) else ""

            # LSP Spec §3.15: Position.character MUST be strictly 0-indexed.
            # Handle finding.column (1-indexed) with - 1 correction, or
            # finding.col_start (0-indexed) safely.
            col = getattr(f, "column", None)
            if col is not None and col > 0:
                col_start = max(0, col - 1)
            else:
                col_start = max(0, getattr(f, "col_start", 0))

            match_text = getattr(f, "match_text", "")
            match_len = len(match_text) if match_text else len(matched_line)

            utf16_start = _to_utf16_col(matched_line, col_start)
            utf16_end = _to_utf16_col(matched_line, col_start + match_len)

            severity_str = getattr(f, "severity", "error")
            severity = {
                "error": Severity.ERROR,
                "warning": Severity.WARNING,
                "info": Severity.INFORMATION,
            }.get(severity_str, Severity.ERROR)

            typed_diags.append(
                ZenzicDiagnostic(
                    range=DiagnosticRange(
                        start=DiagnosticPosition(line=line_no, character=utf16_start),
                        end=DiagnosticPosition(line=line_no, character=utf16_end),
                    ),
                    severity=severity,
                    code=getattr(f, "code", getattr(f, "rule_id", "Unknown")),
                    source="zenzic",
                    message=getattr(f, "message", "Violation"),
                )
            )

        return typed_diags

    # ── Private: URP checks ───────────────────────────────────────────────────

    def _run_urp_checks(
        self,
        vsm: VirtualSiteMap,
        path: Path,
        text: str,
        tracker: SuppressionTracker | None = None,
        extracted_links: list[ExtractedLink] | None = None,
        resolver: Any = None,
    ) -> list[RuleFinding]:
        """Run the Uniform Resolver Pipeline checks on a single file.

        Covers: Z120, Z121, Z122, Z123, Z124, Z205, Z102, Z105, Z202, Z203.
        """
        findings: list[RuleFinding] = []
        lines = text.splitlines()
        _docs_root_str = str(self.docs_root)
        _repo_root_str = str(self.repo_root)

        def _source_line(lineno: int) -> str:
            idx = lineno - 1
            return lines[idx].strip() if 0 <= idx < len(lines) else ""

        # Z205 on Markdown-syntax links. The HTML loop below evaluates the
        # forbidden-scheme gate inside _parse_node(), which only ever sees <a>/
        # <img> tags — so [x](javascript:...) and reference definitions passed a
        # Tier-0, non-suppressible gate entirely, while rendering to the exact
        # same exploitable anchor in the built site. validator.py's own comment
        # already declares syntactic form "un dettaglio di trasporto"; this
        # restores that invariant by checking the shared link representation.
        #
        # Scope decision: the Markdown path checks javascript: ONLY, not the
        # full _POLY_FORBIDDEN_SCHEMES set. data: stays flagged in HTML exactly
        # as before (unchanged), but is deliberately NOT newly flagged here.
        # Z205 is non-suppressible and exits 2, so a false positive hard-fails a
        # build with no escape hatch — and data: in Markdown is overwhelmingly
        # benign (inline base64 images, data:text/plain), which the pre-existing
        # skip-scheme behaviour in validate_links already encodes as deliberate
        # intent. javascript: has no legitimate use in a documentation link, so
        # it carries no comparable false-positive risk. Extending to dangerous
        # data: subtypes (data:text/html) needs MIME-subtype discrimination and
        # is tracked separately rather than guessed at inside a Tier-0 gate.
        _md_links = (
            extracted_links
            if extracted_links is not None
            else PolyglotExtractor().extract_all_links(text)
        )
        for link in _md_links:
            if link.is_html:
                continue  # handled by the HTML loop below; avoids double-reporting
            clean = _POLY_CLEAN_URL_RE.sub("", html.unescape(link.url)).lower()
            scheme = "javascript:" if clean.startswith("javascript:") else None
            if scheme is None:
                continue
            findings.append(
                RuleFinding(
                    path,
                    link.line_no,
                    "Z205",
                    f"forbidden scheme '{scheme}' detected",
                    severity=code_severity("Z205"),
                    matched_line=_source_line(link.line_no),
                    col_start=0,
                    match_text=link.raw_text or link.url,
                )
            )

        # Polyglot Extractor
        for node in PolyglotExtractor().extract(text):
            ctx = _source_line(node.line_no)
            if node.z205_scheme:
                findings.append(
                    RuleFinding(
                        path,
                        node.line_no,
                        "Z205",
                        f"forbidden scheme '{node.z205_scheme}' detected",
                        severity=code_severity("Z205"),
                        matched_line=ctx,
                        col_start=0,
                        match_text=node.raw_tag,
                    )
                )
            for attr in node.blacklisted_attrs:
                findings.append(
                    RuleFinding(
                        path,
                        node.line_no,
                        "Z124",
                        f"opaque attribute '{attr}' detected",
                        severity=code_severity("Z124"),
                        matched_line=ctx,
                        col_start=0,
                        match_text=node.raw_tag,
                    )
                )
            if node.is_missing_href:
                findings.append(
                    RuleFinding(
                        path,
                        node.line_no,
                        "Z121",
                        "missing href or src",
                        severity=code_severity("Z121"),
                        matched_line=ctx,
                        col_start=0,
                        match_text=node.raw_tag,
                    )
                )
            if node.is_jump_link:
                findings.append(
                    RuleFinding(
                        path,
                        node.line_no,
                        "Z122",
                        "href='#' detected",
                        severity=code_severity("Z122"),
                        matched_line=ctx,
                        col_start=0,
                        match_text=node.raw_tag,
                    )
                )
            for attr in node.unknown_attrs:
                findings.append(
                    RuleFinding(
                        path,
                        node.line_no,
                        "Z120",
                        f"unknown attribute '{attr}'",
                        severity=code_severity("Z120"),
                        matched_line=ctx,
                        col_start=0,
                        match_text=node.raw_tag,
                    )
                )
            if node.info_scheme:
                findings.append(
                    RuleFinding(
                        path,
                        node.line_no,
                        "Z123",
                        f"non-HTTP scheme '{node.info_scheme}'",
                        severity=code_severity("Z123"),
                        matched_line=ctx,
                        col_start=0,
                        match_text=node.raw_tag,
                    )
                )

            if node.suppressed and tracker is not None:
                for d in tracker.directives:
                    if d.line_no == node.line_no and d.code == "DATA-ZENZIC-IGNORE":
                        d.consumed = True
                        break

        # Extracted Link Candidates (Markdown, HTML href/src, Ref Defs)
        if extracted_links is None:
            extracted_links = PolyglotExtractor().extract_all_links(text)

        local_anchors = self.anchors_cache.get(path, set())
        _bypass_schemes = (
            "mailto:",
            "tel:",
            "javascript:",
            "data:",
            "irc:",
            "xmpp:",
            "http://",
            "https://",
        )

        for link in extracted_links:
            if link.suppressed:
                continue

            url = link.url
            lineno = link.line_no
            raw_line = link.raw_text

            if url.startswith(_bypass_schemes) or url == "#":
                continue

            parsed = urlsplit(url)

            # Z202 / Z203 — Path Traversal Detection
            if "../" in url:
                try:
                    rel_source = path.relative_to(self.docs_root).parent.as_posix()
                    base = "" if rel_source == "." else rel_source
                    norm_target = posixpath.normpath(posixpath.join(base, parsed.path))
                    if norm_target.startswith(".."):
                        _intent = _classify_traversal_intent(url)
                        _code = "Z203" if _intent == "suspicious" else "Z202"
                        findings.append(
                            RuleFinding(
                                path,
                                lineno,
                                _code,
                                f"'{url}' resolves outside the docs directory",
                                severity=code_severity(_code),
                                matched_line=raw_line,
                            )
                        )
                        continue
                except Exception:
                    resolved_docs_root = getattr(self, "_resolved_docs_root", None)
                    if resolved_docs_root is None:
                        resolved_docs_root = self.docs_root.resolve()
                        self._resolved_docs_root = resolved_docs_root
                    source_dir = path.parent.resolve()
                    target_str = os.path.normpath(str(source_dir / parsed.path))
                    target_path = Path(target_str)
                    if not target_path.is_relative_to(resolved_docs_root):
                        _intent = _classify_traversal_intent(url)
                        _code = "Z203" if _intent == "suspicious" else "Z202"
                        findings.append(
                            RuleFinding(
                                path,
                                lineno,
                                _code,
                                f"'{url}' resolves outside the docs directory",
                                severity=code_severity(_code),
                                matched_line=raw_line,
                            )
                        )
                        continue
                    continue

            # Z105 / Z203
            elif parsed.path.startswith("/"):
                _intent = _classify_traversal_intent(url)
                if _intent == "suspicious":
                    findings.append(
                        RuleFinding(
                            path,
                            lineno,
                            "Z203",
                            f"Path traversal targeting OS system directories: '{url}'",
                            severity=code_severity("Z203"),
                            matched_line=raw_line,
                        )
                    )
                else:
                    allowlist = tuple(
                        list(self.adapter.get_absolute_url_prefixes())
                        + list(self.config.absolute_path_allowlist)
                    )
                    if not any(url.startswith(p) for p in allowlist if p):
                        findings.append(
                            RuleFinding(
                                path,
                                lineno,
                                "Z105",
                                f"absolute path '{url}' found",
                                severity=code_severity("Z105"),
                                matched_line=raw_line,
                            )
                        )
                continue

            # Non-markdown asset validation (Z104)
            url_clean = url.split("?")[0].split("#")[0].lower()
            is_asset = link.node_type in ("image", "html_img") or any(
                url_clean.endswith(ext)
                for ext in (
                    ".png",
                    ".jpg",
                    ".jpeg",
                    ".gif",
                    ".webp",
                    ".svg",
                    ".ico",
                    ".pdf",
                    ".zip",
                    ".tar.gz",
                    ".html",
                )
            )
            if is_asset:
                if self.config.excluded_build_artifacts:
                    import fnmatch

                    if any(
                        fnmatch.fnmatch(url, pat) for pat in self.config.excluded_build_artifacts
                    ):
                        continue

                rel_url = unquote(parsed.path)
                target_path = Path(
                    resolve_href_target(path, rel_url, _docs_root_str, _repo_root_str)
                )
                if not target_path.is_file():
                    if self.adapter.resolve_asset(target_path, self.docs_root) is None:
                        findings.append(
                            RuleFinding(
                                path,
                                lineno,
                                "Z104",
                                f"'{rel_url}' not found in docs",
                                severity=code_severity("Z104"),
                                matched_line=raw_line,
                                col_start=link.col_start,
                                match_text=link.raw_text,
                            )
                        )
                continue

            # Z102 (Local and Cross-file)
            if parsed.fragment:
                anchor = parsed.fragment.lower()
                if not parsed.path:
                    if anchor not in local_anchors:
                        findings.append(
                            RuleFinding(
                                path,
                                lineno,
                                "Z102",
                                f"anchor '#{anchor}' not found",
                                severity=code_severity("Z102"),
                                matched_line=raw_line,
                            )
                        )
                else:
                    target_path = (path.parent / unquote(parsed.path)).resolve()
                    try:
                        if target_path.is_relative_to(self.docs_root):
                            rel_obj = target_path.relative_to(self.docs_root)
                        else:
                            rel_obj = target_path
                        route_meta = self.adapter.get_route_info(rel_obj)
                        route = vsm.get(route_meta.canonical_url)
                    except Exception:
                        route = None

                    if route is not None and anchor not in route.anchors:
                        # Check adapter i18n anchor fallback
                        if not self.adapter.resolve_anchor(
                            target_path, anchor, self.anchors_cache, self.docs_root
                        ):
                            findings.append(
                                RuleFinding(
                                    path,
                                    lineno,
                                    "Z102",
                                    f"anchor '#{anchor}' not found in '{parsed.path}'",
                                    severity=code_severity("Z102"),
                                    matched_line=raw_line,
                                )
                            )

        return findings


# ── Module-level pure functions ───────────────────────────────────────────────


def _to_utf16_col(line: str, py_idx: int) -> int:
    """Convert a Python string index into a UTF-16 code unit offset.

    Args:
        line: The source line text.
        py_idx: Python string index (0-based).

    Returns:
        UTF-16 code unit offset.
    """
    col = 0
    for i, c in enumerate(line):
        if i >= py_idx:
            break
        col += 2 if ord(c) > 0xFFFF else 1
    return col
