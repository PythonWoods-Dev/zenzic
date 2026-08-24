# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""Data models for the Two-Pass Reference Pipeline.

ReferenceMap is the stateful, per-file registry of reference-link definitions.
It follows CommonMark §4.7 exactly: the **first** definition of an ID wins;
subsequent definitions for the same ID are silently ignored (and logged in
``duplicate_ids`` for warning purposes).

Each definition stores both the target URL and its source line number so that
error reports can point users directly to the offending line.

The integrity_score property implements the Zenzic formula:

    Reference Integrity = (|Resolved References| / |Total Reference Definitions|) × 100

When no definitions exist the score is 100.0 by convention (no ZeroDivisionError).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from zenzic.core.credentials import SecurityFinding
    from zenzic.core.rules import RuleFinding
    from zenzic.core.suppressions import SuppressionTracker


# ─── ReferenceMap ─────────────────────────────────────────────────────────────


@dataclass
class ReferenceMap:
    """Archivio dei Reference Links: Case-insensitive, First-Wins, con Metadata.

    State lives entirely inside the instance — each ``ReferenceScanner``
    creates its own ``ReferenceMap``, so there is no global scope pollution
    between documents.

    CommonMark §4.7:
        *"If there are several matching link reference definitions, the first
        one takes precedence."*

    Attributes:
        definitions: Mapping of normalised (lowercased, stripped) ref ID to
            ``(url, line_no)`` tuples.  First definition wins; ``line_no`` is
            the 1-based source line so error messages can point to the exact
            location.
        used_ids: Set of normalised ref IDs resolved at least once during
            Pass 2 (Cross-Check).
        duplicate_ids: Set of normalised ref IDs whose subsequent definitions
            were ignored.  Used to emit warnings only.
    """

    definitions: dict[str, tuple[str, int]] = field(default_factory=dict)
    used_ids: set[str] = field(default_factory=set)
    duplicate_ids: set[str] = field(default_factory=set)

    def _normalize(self, ref_id: str) -> str:
        """Normalize reference ID per CommonMark §4.7: lowercase, stripped, internal whitespace collapsed."""
        if not isinstance(ref_id, str):
            return str(ref_id)
        # Collapse consecutive internal whitespace (including newlines) to a single space
        return " ".join(ref_id.split()).lower()

    def add_definition(self, ref_id: str, url: str, line_no: int) -> bool:
        """Register a reference-link definition (first-wins per CommonMark §4.7).

        Args:
            ref_id: Raw reference identifier — normalised to lowercase + stripped.
            url: Target URL — leading/trailing whitespace stripped.
            line_no: 1-based line number of the definition in the source file.

        Returns:
            ``True`` if the definition was accepted (first occurrence),
            ``False`` if it was a duplicate (already registered, ignored).
        """
        key = self._normalize(ref_id)
        if key in self.definitions:
            self.duplicate_ids.add(key)
            return False  # duplicate ignored — first wins (CommonMark §4.7)
        self.definitions[key] = (url.strip(), line_no)
        return True

    def resolve(self, ref_id: str) -> str | None:
        """Look up a reference ID, mark it as used, and return its URL.

        Args:
            ref_id: Raw reference identifier — normalised to lowercase + stripped.

        Returns:
            The target URL string, or ``None`` if the ID has no definition.
        """
        key = self._normalize(ref_id)
        if key in self.definitions:
            self.used_ids.add(key)
            return self.definitions[key][0]
        return None

    def get_definition_line(self, ref_id: str) -> int | None:
        """Return the source line number for a definition, or ``None``."""
        key = self._normalize(ref_id)
        entry = self.definitions.get(key)
        return entry[1] if entry is not None else None

    def __getitem__(self, ref_id: str) -> str:
        """Case-insensitive item access — returns URL only.  Raises ``KeyError``."""
        key = self._normalize(ref_id)
        return self.definitions[key][0]

    def __contains__(self, ref_id: object) -> bool:
        """Case-insensitive membership test."""
        if not isinstance(ref_id, str):
            return False
        return self._normalize(ref_id) in self.definitions

    @property
    def orphan_definitions(self) -> set[str]:
        """IDs that were defined but never resolved (dangling definitions)."""
        return set(self.definitions.keys()) - self.used_ids

    @property
    def integrity_score(self) -> float:
        """Reference Integrity score in the range 0.0–100.0.

        Formula: (|used_ids| / |definitions|) × 100

        Returns 100.0 when there are no definitions — no ZeroDivisionError.
        """
        if not self.definitions:
            return 100.0
        return (len(self.used_ids) / len(self.definitions)) * 100


# ─── Finding data classes ──────────────────────────────────────────────────────


@dataclass(slots=True)
class ReferenceFinding:
    """A single issue discovered during the reference pipeline.

    Attributes:
        file_path: Source file where the issue was found.
        line_no: 1-based line number (0 if not applicable).
        issue: Machine-readable issue type — one of:
            ``"DANGLING"``       — link uses an undefined reference ID (Dangling Reference)
            ``"DEAD_DEF"``       — definition never used by any link (Dead Definition)
            ``"duplicate-def"``  — same ID defined more than once (first wins)
            ``"missing-alt"``    — image has no alt text
        detail: Human-readable description.
        is_warning: ``True`` for a non-blocking (``--strict``-gated) finding.
            Every code the reference pipeline emits (Z301 DANGLING_REF, Z302
            DEAD_DEF, Z303 DUPLICATE_DEF) is classified ``"warning"`` in
            ``codes.py``'s ``CODE_DEFINITIONS`` — the single source of truth
            — so this is always ``True`` for findings this pipeline produces.
    """

    file_path: Path
    line_no: int
    issue: str
    detail: str
    is_warning: bool = True


# ─── Integrity report ─────────────────────────────────────────────────────────


@dataclass
class IntegrityReport:
    """Aggregated result of the Two-Pass Pipeline for a single file.

    Attributes:
        file_path: The scanned file.
        score: Reference Integrity score (0.0–100.0).
        findings: All reference-quality issues (dangling refs, orphan defs,
            duplicate defs, missing alt-text).
        security_findings: Secrets detected by the credential scanner during Pass 1.
        rule_findings: Issues raised by the AdaptiveRuleEngine (custom rules and
            plugin-registered rules).  Empty when no rules are configured.
    """

    file_path: Path
    score: float
    findings: list[ReferenceFinding] = field(default_factory=list)
    security_findings: list[SecurityFinding] = field(default_factory=list)
    rule_findings: list[RuleFinding] = field(default_factory=list)
    suppression_tracker: SuppressionTracker | None = None

    @property
    def is_secure(self) -> bool:
        """``True`` when the credential scanner found no secrets in this file."""
        return len(self.security_findings) == 0

    @property
    def has_errors(self) -> bool:
        """``True`` when there are hard errors (non-warning findings or rule errors)."""
        ref_errors = any(not f.is_warning for f in self.findings)
        rule_errors = any(f.is_error for f in self.rule_findings)
        return ref_errors or rule_errors
