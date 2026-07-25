# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""Centralized governance filtering for Zenzic core and LSP.

Provides DRY governance evaluation for per-file ignores and directory policies,
ensuring 100% parity between CLI check routines and LSP server diagnostics (ADR-084).
"""

from __future__ import annotations

import dataclasses
from fnmatch import fnmatch
from pathlib import Path
from typing import Any, TypeVar

import zenzic.core.regex as re
from zenzic.core.codes import NON_SUPPRESSIBLE_CODES
from zenzic.core.exclusion import translate_glob_to_re2
from zenzic.models.config import ZenzicConfig

T = TypeVar("T")


def _extract_code_and_rel_path(finding: Any, repo_root: Path | None = None, docs_root: Path | None = None) -> tuple[str, str, str | None]:
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
        code, rel_path, docs_rel = _extract_code_and_rel_path(finding, repo_root=repo_root, docs_root=docs_root)
        if code in NON_SUPPRESSIBLE_CODES:
            filtered.append(finding)
            continue

        suppressed = any(
            (fnmatch(rel_path, pattern) or (docs_rel is not None and fnmatch(docs_rel, pattern))) and code in codes
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
        code, rel_path, docs_rel = _extract_code_and_rel_path(finding, repo_root=repo_root, docs_root=docs_root)
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
                    filtered.append(dataclasses.replace(finding, message=f"[POLICY_EXEMPTION] {msg}"))

                else:
                    filtered.append(finding)

            # else: silently drop
        else:
            filtered.append(finding)
    return filtered
