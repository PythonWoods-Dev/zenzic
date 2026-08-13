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
_COMMENT_RE = _stdlib_re.compile(r"<!--.*?-->|\{/\*.*?\*/\}", _stdlib_re.DOTALL)
_FRONTMATTER_BLOCK_RE = _stdlib_re.compile(r"\A\s*---\s*\n(.*?)\n---", _stdlib_re.DOTALL)
_FM_KEY_VALUE_RE = _stdlib_re.compile(r"^([A-Za-z0-9_-]+)\s*:\s*(.*)$", _stdlib_re.MULTILINE)


def _parse_frontmatter_dict(content: str) -> dict[str, str]:
    """Return a dictionary of top-level frontmatter key-value pairs present in *content*.

    Only inspects the leading ``---`` fenced block (after stripping leading comments).
    Returns an empty dict when no frontmatter is present or the block is malformed.
    Values are stripped of leading/trailing whitespace and outer matching quotes.
    """
    clean_content = _COMMENT_RE.sub("", content).lstrip()
    fm = _FRONTMATTER_BLOCK_RE.match(clean_content)
    if fm is None:
        return {}
    block = fm.group(1)
    result: dict[str, str] = {}
    for m in _FM_KEY_VALUE_RE.finditer(block):
        key = m.group(1)
        raw_val = m.group(2).strip()
        if (raw_val.startswith('"') and raw_val.endswith('"')) or (
            raw_val.startswith("'") and raw_val.endswith("'")
        ):
            raw_val = raw_val[1:-1].strip()
        result[key] = raw_val
    return result


def _parse_frontmatter_keys(content: str) -> set[str]:
    """Return the set of top-level frontmatter key names present in *content*."""
    return set(_parse_frontmatter_dict(content).keys())


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

    Evaluates Z610, Z611, Z612, Z613, Z614, Z615, Z616 policies against a single Markdown file.

    Usage::

        from zenzic.core.governance import PolicyEvaluator
        evaluator = PolicyEvaluator(config)
        findings = evaluator.check(file_path, content, links)
    """

    def __init__(self, config: ZenzicConfig) -> None:
        self._required_keys: list[str] = config.policies.required_frontmatter_keys
        self._forbidden_domains: list[str] = config.policies.forbidden_external_domains
        self._forbidden_keys: list[str] = config.policies.forbidden_frontmatter_keys
        self._schema_match: dict[str, str] = config.policies.frontmatter_schema_match
        self._allowed_domains: list[str] = config.policies.allowed_external_domains
        self._required_schemes: list[str] = config.policies.required_url_schemes
        self._cross_namespace: dict[str, list[str]] = config.policies.cross_namespace_restrictions

    # ── Public surface ────────────────────────────────────────────────────────

    @property
    def is_active(self) -> bool:
        """Return True when at least one policy rule is configured."""
        return bool(
            self._required_keys
            or self._forbidden_domains
            or self._forbidden_keys
            or self._schema_match
            or self._allowed_domains
            or self._required_schemes
            or self._cross_namespace
        )

    def check(
        self,
        file_path: Path,
        content: str,
        links: list[str] | None = None,
        resolver: Any | None = None,
        vsm: dict[str, Any] | None = None,
        repo_root: Path | None = None,
        docs_root: Path | None = None,
    ) -> list[RuleFinding]:
        """Run all configured policy checks against a single Markdown file."""
        if not self.is_active:
            return []

        findings: list[RuleFinding] = []

        if self._required_keys or self._forbidden_keys or self._schema_match:
            findings.extend(self._check_frontmatter(file_path, content))

        has_link_policies = (
            self._forbidden_domains
            or self._allowed_domains
            or self._required_schemes
            or self._cross_namespace
        )
        if has_link_policies:
            resolved_links = links if links is not None else _extract_links(content)
            if self._forbidden_domains or self._allowed_domains:
                findings.extend(self._check_links(file_path, content, resolved_links))
            if self._required_schemes:
                findings.extend(self._check_schemes(file_path, content, resolved_links))
            if self._cross_namespace:
                findings.extend(
                    self._check_cross_namespace_links(
                        file_path,
                        content,
                        resolved_links,
                        resolver=resolver,
                        vsm=vsm,
                        repo_root=repo_root,
                        docs_root=docs_root,
                    )
                )

        return findings

    # ── Internal checkers ─────────────────────────────────────────────────────

    def _check_frontmatter(self, file_path: Path, content: str) -> list[RuleFinding]:
        """Z610, Z612, Z613 frontmatter policy checks."""
        if not (self._required_keys or self._forbidden_keys or self._schema_match):
            return []

        from zenzic.core.rules import RuleFinding

        fm_dict = _parse_frontmatter_dict(content)
        findings: list[RuleFinding] = []

        # Z610 REQUIRED_FRONTMATTER_MISSING
        for key in self._required_keys:
            if key not in fm_dict:
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

        # Z612 FORBIDDEN_FRONTMATTER_KEY
        for key in self._forbidden_keys:
            if key in fm_dict:
                findings.append(
                    RuleFinding(
                        rule_id="Z612",
                        severity="warning",
                        file_path=file_path,
                        line_no=1,
                        message=(
                            f"Forbidden frontmatter key '{key}' is present. "
                            f"Remove '{key}' from the YAML frontmatter block. "
                            f"Declared in [policies].forbidden_frontmatter_keys."
                        ),
                        matched_line=f"{key}: {fm_dict[key]}",
                    )
                )

        # Z613 FRONTMATTER_SCHEMA_MISMATCH
        for key, pattern_str in self._schema_match.items():
            if key in fm_dict:
                val = fm_dict[key]
                try:
                    compiled = re.compile(pattern_str)
                    matched = bool(compiled.search(val))
                except Exception:
                    matched = True
                if not matched:
                    findings.append(
                        RuleFinding(
                            rule_id="Z613",
                            severity="error",
                            file_path=file_path,
                            line_no=1,
                            message=(
                                f"Frontmatter key '{key}' value '{val}' does not match required RE2 pattern '{pattern_str}'. "
                                f"Declared in [policies].frontmatter_schema_match."
                            ),
                            matched_line=f"{key}: {val}",
                        )
                    )

        return findings

    def _check_links(self, file_path: Path, content: str, links: list[str]) -> list[RuleFinding]:
        """Z611 & Z614 external domain policy checks."""
        if not (self._forbidden_domains or self._allowed_domains):
            return []

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

            host = parsed.netloc.lower().split(":")[0]

            # Z614: UNAPPROVED_DOMAIN_REFERENCE (Zero-Trust Whitelist)
            if self._allowed_domains:
                is_allowed = any(
                    host == d.lower() or host.endswith("." + d.lower())
                    for d in self._allowed_domains
                )
                if not is_allowed:
                    line_no = 1
                    for i, line in enumerate(lines, start=1):
                        if url in line:
                            line_no = i
                            break
                    findings.append(
                        RuleFinding(
                            rule_id="Z614",
                            severity="error",
                            file_path=file_path,
                            line_no=line_no,
                            message=(
                                f"Link to '{url}' references external domain '{host}' which is not in "
                                f"[policies].allowed_external_domains whitelist. "
                                f"Replace or add to whitelist."
                            ),
                            matched_line=lines[line_no - 1] if line_no <= len(lines) else "",
                        )
                    )
                    continue

            # Z611: FORBIDDEN_DOMAIN_REFERENCE (Blacklist)
            if self._forbidden_domains:
                matched_domain = next(
                    (
                        d
                        for d in self._forbidden_domains
                        if host == d.lower() or host.endswith("." + d.lower())
                    ),
                    None,
                )
                if matched_domain is not None:
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

    def _check_schemes(self, file_path: Path, content: str, links: list[str]) -> list[RuleFinding]:
        """Z615: FORBIDDEN_URL_SCHEME check."""
        if not self._required_schemes:
            return []

        from zenzic.core.rules import RuleFinding

        findings: list[RuleFinding] = []
        lines = content.splitlines()

        for url in links:
            try:
                parsed = urlsplit(url)
            except ValueError:
                continue

            if not parsed.scheme:
                continue

            scheme_lower = parsed.scheme.lower()
            if scheme_lower in ("javascript", "data"):
                continue  # Handled by Z205 security scanner

            if scheme_lower not in self._required_schemes:
                line_no = 1
                for i, line in enumerate(lines, start=1):
                    if url in line:
                        line_no = i
                        break
                findings.append(
                    RuleFinding(
                        rule_id="Z615",
                        severity="warning",
                        file_path=file_path,
                        line_no=line_no,
                        message=(
                            f"Link to '{url}' uses scheme '{parsed.scheme}' which is not permitted "
                            f"by [policies].required_url_schemes ({self._required_schemes}). "
                            f"Change scheme to an allowed protocol."
                        ),
                        matched_line=lines[line_no - 1] if line_no <= len(lines) else "",
                    )
                )

        return findings

    def _check_cross_namespace_links(
        self,
        file_path: Path,
        content: str,
        links: list[str],
        resolver: Any | None = None,
        vsm: dict[str, Any] | None = None,
        repo_root: Path | None = None,
        docs_root: Path | None = None,
    ) -> list[RuleFinding]:
        """Z616: CROSS_NAMESPACE_LINK_FORBIDDEN using VSM / InMemoryPathResolver target resolution."""
        if not self._cross_namespace:
            return []

        from urllib.parse import unquote

        from zenzic.core.resolver import AnchorMissing, Resolved
        from zenzic.core.rules import RuleFinding

        fp = file_path.resolve() if file_path.is_absolute() else file_path
        repo_rel = (
            fp.relative_to(repo_root.resolve()).as_posix()
            if (repo_root and fp.is_absolute() and fp.is_relative_to(repo_root.resolve()))
            else fp.as_posix()
        )
        docs_rel = (
            fp.relative_to(docs_root.resolve()).as_posix()
            if (docs_root and fp.is_absolute() and fp.is_relative_to(docs_root.resolve()))
            else None
        )

        matched_src_prefix: str | None = None
        forbidden_target_prefixes: list[str] = []

        for src_prefix, forbidden_targets in self._cross_namespace.items():
            clean_prefix = src_prefix.strip("/")
            if (
                repo_rel.startswith(clean_prefix + "/")
                or repo_rel == clean_prefix
                or (
                    docs_rel is not None
                    and (docs_rel.startswith(clean_prefix + "/") or docs_rel == clean_prefix)
                )
            ):
                matched_src_prefix = src_prefix
                forbidden_target_prefixes = forbidden_targets
                break

        if not matched_src_prefix or not forbidden_target_prefixes:
            return []

        findings: list[RuleFinding] = []
        lines = content.splitlines()

        for url in links:
            try:
                parsed = urlsplit(url)
            except ValueError:
                continue

            if parsed.scheme or url.startswith("#"):
                continue

            raw_path = parsed.path
            if not raw_path:
                continue

            resolved_target_file: Path | None = None
            if resolver is not None:
                try:
                    outcome = resolver.resolve(file_path, url)
                    if isinstance(outcome, Resolved):
                        resolved_target_file = outcome.target
                    elif isinstance(outcome, AnchorMissing):
                        resolved_target_file = outcome.resolved_file
                except Exception:
                    pass

            if resolved_target_file is None and vsm is not None:
                for route in vsm.values():
                    route_source = getattr(route, "source", None)
                    if route_source and raw_path.strip("/") in route_source:
                        resolved_target_file = (
                            docs_root / route_source if docs_root else Path(route_source)
                        )
                        break

            if resolved_target_file is None:
                try:
                    resolved_target_file = (file_path.parent / unquote(raw_path)).resolve()
                except Exception:
                    continue

            target_fp = (
                resolved_target_file.resolve()
                if resolved_target_file.is_absolute()
                else resolved_target_file
            )
            target_repo_rel = (
                target_fp.relative_to(repo_root.resolve()).as_posix()
                if (repo_root and target_fp.is_absolute() and target_fp.is_relative_to(repo_root.resolve()))
                else target_fp.as_posix()
            )
            target_docs_rel = (
                target_fp.relative_to(docs_root.resolve()).as_posix()
                if (docs_root and target_fp.is_absolute() and target_fp.is_relative_to(docs_root.resolve()))
                else None
            )

            for forbidden_prefix in forbidden_target_prefixes:
                clean_target_prefix = forbidden_prefix.strip("/")
                is_forbidden = (
                    target_repo_rel.startswith(clean_target_prefix + "/")
                    or target_repo_rel == clean_target_prefix
                    or (
                        target_docs_rel is not None
                        and (
                            target_docs_rel.startswith(clean_target_prefix + "/")
                            or target_docs_rel == clean_target_prefix
                        )
                    )
                )
                if is_forbidden:
                    line_no = 1
                    for i, line in enumerate(lines, start=1):
                        if url in line:
                            line_no = i
                            break
                    findings.append(
                        RuleFinding(
                            rule_id="Z616",
                            severity="error",
                            file_path=file_path,
                            line_no=line_no,
                            message=(
                                f"Internal link '{url}' from namespace '{repo_rel}' targets "
                                f"forbidden namespace '{target_repo_rel}' (forbidden boundary '{forbidden_prefix}'). "
                                f"Declared in [policies].cross_namespace_restrictions."
                            ),
                            matched_line=lines[line_no - 1] if line_no <= len(lines) else "",
                        )
                    )
                    break

        return findings


# ── Link extraction helper ────────────────────────────────────────────────────

# Matches Markdown links: [text](url)
_MD_LINK_RE = _stdlib_re.compile(r"\[(?:[^\]]*)\]\(([^)]+)\)")
# Matches HTML href attributes: href="url" or href='url'
_HTML_HREF_RE = _stdlib_re.compile(r"""href\s*=\s*["']([^"']+)["']""", _stdlib_re.IGNORECASE)


def _extract_links(content: str) -> list[str]:
    """Extract all link URLs from raw Markdown content (Markdown + HTML)."""
    urls: list[str] = []
    seen: set[str] = set()

    for url in _MD_LINK_RE.findall(content):
        url = url.strip().split()[0]
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
    resolver: Any | None = None,
    vsm: dict[str, Any] | None = None,
    repo_root: Path | None = None,
    docs_root: Path | None = None,
) -> list[RuleFinding]:
    """Convenience wrapper: create a PolicyEvaluator and run all policy checks."""
    evaluator = PolicyEvaluator(config)
    return evaluator.check(
        file_path,
        content,
        links=links,
        resolver=resolver,
        vsm=vsm,
        repo_root=repo_root,
        docs_root=docs_root,
    )
