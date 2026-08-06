# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""Centralized governance filtering for Zenzic core and LSP.

Provides DRY governance evaluation for per-file ignores and directory policies,
ensuring 100% parity between CLI check routines and LSP server diagnostics (ADR-084).

v0.28.0: Added PolicyEvaluator for declarative Policy-as-Code (Z610/Z611).
"""

from __future__ import annotations

import dataclasses
import re as _stdlib_re
from fnmatch import fnmatch
from pathlib import Path
from typing import TYPE_CHECKING, Any, TypeVar
from urllib.parse import urlsplit

import zenzic.core.regex as re
from zenzic.core.codes import NON_SUPPRESSIBLE_CODES
from zenzic.core.exclusion import translate_glob_to_re2
from zenzic.models.config import ZenzicConfig


if TYPE_CHECKING:
    from zenzic.core.rules import RuleFinding


T = TypeVar("T")

# ── Frontmatter extraction (re-used from adapters._utils) ────────────────────
# We re-declare the patterns here rather than importing from adapters._utils
# to avoid a circular import (adapters import from core).
_FRONTMATTER_BLOCK_RE = _stdlib_re.compile(r"\A\s*---\s*\n(.*?)\n---", _stdlib_re.DOTALL)
_FM_KEY_VALUE_RE = _stdlib_re.compile(r"^([A-Za-z0-9_-]+)\s*:\s*(.*)$", _stdlib_re.MULTILINE)


def _parse_frontmatter_keys(content: str) -> set[str]:
    """Return the set of top-level frontmatter key names present in *content*.

    Only inspects the leading ``---`` fenced block.  Returns an empty set
    when no frontmatter is present or the block is malformed.
    """
    fm = _FRONTMATTER_BLOCK_RE.match(content)
    if fm is None:
        return set()
    block = fm.group(1)
    return {m.group(1) for m in _FM_KEY_VALUE_RE.finditer(block)}


def _extract_code_and_rel_path(
    finding: Any, repo_root: Path | None = None, docs_root: Path | None = None
) -> tuple[str, str, str | None]:
    """Extract (code, rel_path, docs_rel) from any finding object (Finding, RuleFinding, or ZenzicDiagnostic)."""
    code = getattr(finding, "code", None) or getattr(finding, "rule_id", "")
    code = str(code).upper().strip()

    rel_path = getattr(finding, "rel_path", None)
    file_path = getattr(finding, "file_path", None)

    docs_rel: str | None = None

    if rel_path and isinstance(rel_path, str):
        repo_rel = rel_path
    elif file_path and isinstance(file_path, Path):
        fp = file_path.resolve() if file_path.is_absolute() else file_path
        if repo_root and fp.is_absolute() and fp.is_relative_to(repo_root.resolve()):
            repo_rel = fp.relative_to(repo_root.resolve()).as_posix()
        elif docs_root and fp.is_absolute() and fp.is_relative_to(docs_root.resolve()):
            repo_rel = fp.relative_to(docs_root.resolve()).as_posix()
        else:
            repo_rel = fp.as_posix()

        if docs_root and fp.is_absolute() and fp.is_relative_to(docs_root.resolve()):
            docs_rel = fp.relative_to(docs_root.resolve()).as_posix()
    else:
        repo_rel = str(file_path or "")

    return code, repo_rel, docs_rel


def apply_per_file_ignores(
    findings: list[T],
    config: ZenzicConfig,
    repo_root: Path | None = None,
    docs_root: Path | None = None,
) -> list[T]:
    """Filter findings using governance.per_file_ignores patterns (ADR-084)."""
    if not config.governance.per_file_ignores:
        return findings

    normalized_map: dict[str, set[str]] = {}
    for pattern, codes in config.governance.per_file_ignores.items():
        if not isinstance(pattern, str) or not isinstance(codes, list):
            continue
        normalized_codes = {
            str(code).upper().strip()
            for code in codes
            if isinstance(code, str) and str(code).upper().startswith("Z")
        }
        if normalized_codes:
            normalized_map[pattern] = normalized_codes

    if not normalized_map:
        return findings

    filtered: list[T] = []
    for finding in findings:
        code, rel_path, docs_rel = _extract_code_and_rel_path(
            finding, repo_root=repo_root, docs_root=docs_root
        )
        if code in NON_SUPPRESSIBLE_CODES:
            filtered.append(finding)
            continue

        suppressed = any(
            (fnmatch(rel_path, pattern) or (docs_rel is not None and fnmatch(docs_rel, pattern)))
            and code in codes
            for pattern, codes in normalized_map.items()
        )
        if suppressed:
            continue
        filtered.append(finding)
    return filtered


def apply_directory_policies(
    findings: list[T],
    config: ZenzicConfig,
    repo_root: Path | None = None,
    docs_root: Path | None = None,
    audit_mode: bool = False,
) -> list[T]:
    """Filter or label findings using governance.directory_policies patterns (ADR-084)."""
    if not config.governance.directory_policies:
        return findings

    normalized_map: list[tuple[Any, set[str], str]] = []
    for pattern, codes in config.governance.directory_policies.items():
        if not isinstance(pattern, str) or not isinstance(codes, list):
            continue
        normalized_codes = {
            str(code).upper().strip()
            for code in codes
            if isinstance(code, str) and str(code).upper().startswith("Z")
        }
        if normalized_codes:
            try:
                regex_str = translate_glob_to_re2(pattern)
                compiled = re.compile(regex_str)
                normalized_map.append((compiled, normalized_codes, pattern))
            except Exception:
                pass

    if not normalized_map:
        return findings

    filtered: list[T] = []
    for finding in findings:
        code, rel_path, docs_rel = _extract_code_and_rel_path(
            finding, repo_root=repo_root, docs_root=docs_root
        )
        if code in NON_SUPPRESSIBLE_CODES:
            filtered.append(finding)
            continue

        is_exempt = False
        for compiled, rule_codes, original_pattern in normalized_map:
            matches_repo = bool(compiled.fullmatch(rel_path))
            matches_docs = bool(compiled.fullmatch(docs_rel)) if docs_rel is not None else False

            if (matches_repo or matches_docs) and code in rule_codes:
                is_exempt = True
                tracker = getattr(config, "_global_tracker", None)
                if tracker:
                    tracker.mark_directory_policy_used(original_pattern, code)
                break

        if is_exempt:
            if audit_mode:
                msg = getattr(finding, "message", None)
                if msg and dataclasses.is_dataclass(finding) and not isinstance(finding, type):
                    filtered.append(
                        dataclasses.replace(finding, message=f"[POLICY_EXEMPTION] {msg}")
                    )

                else:
                    filtered.append(finding)

            # else: silently drop
        else:
            filtered.append(finding)
    return filtered


# ── Policy-as-Code Engine (v0.28.0) ─────────────────────────────────────────


class PolicyEvaluator:
    """Stateless, deterministic evaluator for ``[policies]`` declarations (v0.28.0).

    Evaluates Z610 REQUIRED_FRONTMATTER_MISSING and Z611 FORBIDDEN_DOMAIN_REFERENCE
    against a single Markdown file.

    Architectural invariants
    ------------------------
    * **No I/O**: all inputs are passed as arguments; no filesystem reads.
    * **No subprocess**: evaluation occurs entirely in-memory.
    * **Deterministic**: same inputs always produce the same findings.
    * **Stateless per file**: the evaluator holds no per-file state between calls.
    * **Opt-in**: when both policy lists are empty the evaluator is a no-op.
    * **Radical Unawareness**: no VS Code / LSP knowledge inside this class (ADR-075).

    Usage::

        from zenzic.core.governance import PolicyEvaluator
        evaluator = PolicyEvaluator(config)
        findings = evaluator.check(file_path, content, links)
    """

    def __init__(self, config: ZenzicConfig) -> None:
        self._required_keys: list[str] = config.policies.required_frontmatter_keys
        self._forbidden_domains: list[str] = config.policies.forbidden_external_domains

    # ── Public surface ────────────────────────────────────────────────────────

    @property
    def is_active(self) -> bool:
        """Return True when at least one policy rule is configured."""
        return bool(self._required_keys or self._forbidden_domains)

    def check(
        self,
        file_path: Path,
        content: str,
        links: list[str] | None = None,
    ) -> list[RuleFinding]:
        """Run all configured policy checks against a single Markdown file.

        Args:
            file_path: Absolute or relative path to the source file (for
                finding attribution; no I/O performed on this path).
            content:   Raw Markdown source text of the file.
            links:     Optional pre-extracted list of URL strings (both Markdown
                       and HTML) from the file.  When ``None`` the evaluator
                       extracts links from *content* internally.

        Returns:
            A list of :class:`~zenzic.core.rules.RuleFinding` objects.
            Empty when no policies are violated or no policies are configured.
        """
        if not self.is_active:
            return []

        findings: list[RuleFinding] = []

        if self._required_keys:
            findings.extend(self._check_frontmatter(file_path, content))

        if self._forbidden_domains:
            resolved_links = links if links is not None else _extract_links(content)
            findings.extend(self._check_links(file_path, content, resolved_links))

        return findings

    # ── Internal checkers ─────────────────────────────────────────────────────

    def _check_frontmatter(self, file_path: Path, content: str) -> list[RuleFinding]:
        """Z610: Emit one finding per required frontmatter key that is absent."""
        from zenzic.core.rules import RuleFinding

        present_keys = _parse_frontmatter_keys(content)
        findings: list[RuleFinding] = []

        for key in self._required_keys:
            if key not in present_keys:
                findings.append(
                    RuleFinding(
                        rule_id="Z610",
                        severity="warning",
                        file_path=file_path,
                        line_no=1,
                        message=(
                            f"Required frontmatter key '{key}' is absent. "
                            f"Add '{key}: <value>' to the YAML frontmatter block. "
                            f"Declared in [policies].required_frontmatter_keys."
                        ),
                        matched_line="",
                    )
                )

        return findings

    def _check_links(self, file_path: Path, content: str, links: list[str]) -> list[RuleFinding]:
        """Z611: Emit one finding per link whose domain matches a forbidden prefix."""
        from zenzic.core.rules import RuleFinding

        findings: list[RuleFinding] = []
        lines = content.splitlines()

        for url in links:
            try:
                parsed = urlsplit(url)
            except ValueError:
                continue

            if parsed.scheme not in ("http", "https"):
                continue

            host = parsed.netloc.lower()
            matched_domain = next(
                (
                    d
                    for d in self._forbidden_domains
                    if host == d.lower() or host.endswith("." + d.lower())
                ),
                None,
            )
            if matched_domain is None:
                continue

            # Find the first line containing the URL for attribution.
            line_no = 1
            for i, line in enumerate(lines, start=1):
                if url in line:
                    line_no = i
                    break

            findings.append(
                RuleFinding(
                    rule_id="Z611",
                    severity="warning",
                    file_path=file_path,
                    line_no=line_no,
                    message=(
                        f"Link to '{url}' references forbidden domain '{matched_domain}'. "
                        f"Remove or replace the link. "
                        f"Declared in [policies].forbidden_external_domains."
                    ),
                    matched_line=lines[line_no - 1] if line_no <= len(lines) else "",
                )
            )

        return findings


# ── Link extraction helper ────────────────────────────────────────────────────

# Matches Markdown links: [text](url)
_MD_LINK_RE = _stdlib_re.compile(r"\[(?:[^\]]*)\]\(([^)]+)\)")
# Matches HTML href attributes: href="url" or href='url'
_HTML_HREF_RE = _stdlib_re.compile(r"""href\s*=\s*["']([^"']+)["']""", _stdlib_re.IGNORECASE)


def _extract_links(content: str) -> list[str]:
    """Extract all link URLs from raw Markdown content (Markdown + HTML).

    Combines native Markdown link syntax ``[text](url)`` and raw HTML
    ``<a href="url">`` extraction.  Code blocks are not filtered here —
    the Policy Engine intentionally inspects all links in the source,
    including those in code samples, to prevent blind spots.

    Args:
        content: Raw Markdown/MDX source text.

    Returns:
        Deduplicated list of URL strings found in the document.
    """
    urls: list[str] = []
    seen: set[str] = set()

    for url in _MD_LINK_RE.findall(content):
        url = url.strip().split()[0]  # strip optional title attribute
        if url not in seen:
            seen.add(url)
            urls.append(url)

    for url in _HTML_HREF_RE.findall(content):
        url = url.strip()
        if url not in seen:
            seen.add(url)
            urls.append(url)

    return urls


def check_policies(
    file_path: Path,
    content: str,
    config: ZenzicConfig,
    links: list[str] | None = None,
) -> list[RuleFinding]:
    """Convenience wrapper: create a PolicyEvaluator and run all policy checks.

    This is the primary integration surface for the scanner and rule engine.
    Returns an empty list immediately when no policies are configured
    (Zero-Cost opt-in).

    Args:
        file_path: Path to the Markdown source file.
        content:   Raw file content.
        config:    Active ZenzicConfig (provides ``[policies]`` settings).
        links:     Optional pre-extracted link list; extracted from *content*
                   when ``None``.

    Returns:
        List of :class:`~zenzic.core.rules.RuleFinding` (may be empty).
    """
    evaluator = PolicyEvaluator(config)
    return evaluator.check(file_path, content, links)
