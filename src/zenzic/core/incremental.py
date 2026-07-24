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

from pathlib import Path
from typing import TYPE_CHECKING
from urllib.parse import unquote, urlsplit

from zenzic.core.rules import (
    AdaptiveRuleEngine,
    ResolutionContext,
    RuleFinding,
    _extract_inline_links_with_lines,
)
from zenzic.core.suppressions import SuppressionTracker
from zenzic.core.validator import (
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
        self._initialized: bool = False

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
            # Full read
            for md_file in iter_markdown_sources(self.docs_root, self.config, exclusion_manager):
                uri = f"file://{md_file.resolve()}"
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

            # Static asset files (HTML, images, etc.) under docs_root
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
                    resolved_path = file_path.resolve()
                    if resolved_path not in self.md_contents_cache:
                        self.md_contents_cache[resolved_path] = ""

            # Process open buffers not already cached (virtual or out-of-bounds)
            from urllib.parse import unquote

            for buf_uri, buf_text in overlay.buffers.items():
                if buf_uri.startswith("file://"):
                    buf_path = Path(unquote(buf_uri[7:])).resolve()
                    if buf_path.suffix.lower() not in DOC_SUFFIXES:
                        continue
                    if buf_path not in self.md_contents_cache:
                        self.md_contents_cache[buf_path] = buf_text
                        self.anchors_cache[buf_path] = anchors_in_file(buf_text)
                        files_to_process.add(buf_path)
        else:
            # Incremental read
            from urllib.parse import unquote

            for uri in changed_uris:
                if not uri.startswith("file://"):
                    continue
                path = Path(unquote(uri[7:])).resolve()
                if path.suffix.lower() not in DOC_SUFFIXES:
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
            uri = f"file://{path}"
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
                vsm.remove_outgoing_links(path)
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
            try:
                if path.is_relative_to(self.docs_root):
                    rel_obj = path.relative_to(self.docs_root)
                else:
                    rel_obj = path
                meta = self.adapter.get_route_info(rel_obj)
                canonical = meta.canonical_url
            except Exception:
                pass

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

        # Atomic Rules
        findings.extend(self.rule_engine.run_with_tracker(path, text, tracker))

        # VSM-aware Rules
        context = ResolutionContext(docs_root=self.docs_root, source_file=path)
        findings.extend(self.rule_engine.run_vsm(path, text, vsm, self.anchors_cache, context))

        # Snippet Checks
        for s_err in check_snippet_content(text, path, self.config):
            findings.append(
                RuleFinding(
                    file_path=path,
                    line_no=s_err.line_no,
                    rule_id=s_err.code,
                    message=s_err.message,
                    severity="error",
                )
            )

        # URP Checks
        findings.extend(self._run_urp_checks(vsm, path, text))

        # Dead suppression detection
        findings.extend(tracker.get_dead_suppressions())

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
            line_no = max(0, f.line_no - 1)
            matched_line = lines[line_no] if 0 <= line_no < len(lines) else ""

            col_start = getattr(f, "col_start", 0)
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
                    code=getattr(f, "rule_id", "Unknown"),
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
    ) -> list[RuleFinding]:
        """Run the Uniform Resolver Pipeline checks on a single file.

        Covers: Z120, Z121, Z122, Z123, Z124, Z205, Z102, Z105, Z202, Z203.

        Args:
            vsm: The active Virtual Site Map instance.
            path: Resolved absolute path of the file.
            text: Raw Markdown content.

        Returns:
            List of ``RuleFinding`` instances.
        """
        findings: list[RuleFinding] = []
        lines = text.splitlines()

        def _source_line(lineno: int) -> str:
            idx = lineno - 1
            return lines[idx].strip() if 0 <= idx < len(lines) else ""

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
                        severity="error",
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
                        severity="error",
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
                        severity="error",
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
                        severity="error",
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
                        severity="error",
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
                        severity="info",
                        matched_line=ctx,
                        col_start=0,
                        match_text=node.raw_tag,
                    )
                )

        # Markdown Links
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

        for url, lineno, raw_line in _extract_inline_links_with_lines(text):
            if url.startswith(_bypass_schemes) or url == "#":
                continue

            parsed = urlsplit(url)

            # Z202 / Z203
            if "../" in url and url.count("../") > len(path.parents):
                _intent = _classify_traversal_intent(url)
                findings.append(
                    RuleFinding(
                        path,
                        lineno,
                        "Z203" if _intent == "suspicious" else "Z202",
                        f"Path traversal escape detected: '{url}'",
                        severity="error",
                        matched_line=raw_line,
                    )
                )
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
                            severity="error",
                            matched_line=raw_line,
                        )
                    )
                else:
                    findings.append(
                        RuleFinding(
                            path,
                            lineno,
                            "Z105",
                            f"Absolute path '{url}' found.",
                            severity="error",
                            matched_line=raw_line,
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
                                severity="error",
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
                        findings.append(
                            RuleFinding(
                                path,
                                lineno,
                                "Z102",
                                f"anchor '#{anchor}' not found in '{parsed.path}'",
                                severity="error",
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
