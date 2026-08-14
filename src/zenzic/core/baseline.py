# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""Baseline & Regression Tracking Engine for Zenzic.

Enables capturing existing technical debt into a deterministic baseline file
(.zenzic-baseline.json), matching subsequent run findings against the baseline,
and flagging baselined vs new findings without line-number sensitivity.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

from zenzic.core import regex as re


if TYPE_CHECKING:
    from zenzic.core.reporter import Finding

BASELINE_SCHEMA_VERSION = "1.0"
DEFAULT_BASELINE_FILE = ".zenzic-baseline.json"


def compute_finding_signature(
    code: str,
    rel_path: str,
    match_text: str = "",
    message: str = "",
) -> str:
    """Compute a deterministic SHA-256 signature for a finding.

    Resilient to line-number shifts. Computed as SHA-256 over:
    Normalized(RuleCode) + ":" + PosixRelativePath + ":" + ContextTarget

    Target context extraction:
    1. Uses match_text if non-empty.
    2. Otherwise extracts quoted entities from message (e.g., target URLs or file paths).
    3. Falls back to normalized message if no quoted entities are found.

    Args:
        code: Rule code (e.g. "Z410", "Z101").
        rel_path: POSIX relative file path.
        match_text: Explicit matched text snippet if available.
        message: Diagnostic finding message.

    Returns:
        16-character hex hash string.
    """
    norm_code = code.strip().upper()
    norm_path = Path(rel_path).as_posix().lstrip("./")

    if match_text and match_text.strip():
        context_target = match_text.strip()
    else:
        quotes = re.findall(r"['\"]([^'\"]+)['\"]", message)
        if quotes:
            context_target = ":".join(str(q) for q in quotes)
        else:
            context_target = message.strip()

    payload = f"{norm_code}:{norm_path}:{context_target}".encode()
    return hashlib.sha256(payload).hexdigest()[:16]


@dataclass
class BaselineData:
    """Container for parsed baseline data."""

    version: str = BASELINE_SCHEMA_VERSION
    created_at: str = ""
    score: float = 100.0
    findings_count: int = 0
    signatures: set[str] = field(default_factory=set)
    metadata: dict[str, Any] = field(default_factory=dict)


class BaselineManager:
    """Manager for loading, creating, and matching baseline snapshots."""

    @staticmethod
    def create_baseline(
        score: float,
        findings: list[Finding],
        version_str: str = "",
    ) -> BaselineData:
        """Create a BaselineData instance from current score and findings."""
        sigs: set[str] = set()
        for f in findings:
            sig = compute_finding_signature(f.code, f.rel_path, f.match_text, f.message)
            sigs.add(sig)

        return BaselineData(
            version=BASELINE_SCHEMA_VERSION,
            created_at=datetime.now(timezone.utc).isoformat(),
            score=round(score, 2),
            findings_count=len(sigs),
            signatures=sigs,
            metadata={"zenzic_version": version_str},
        )

    @staticmethod
    def save_baseline(baseline: BaselineData, file_path: Path) -> None:
        """Save BaselineData to a JSON file."""
        data = {
            "$schema": "https://zenzic.dev/schemas/zenzic-baseline.schema.json",
            "version": baseline.version,
            "created_at": baseline.created_at,
            "score": baseline.score,
            "findings_count": len(baseline.signatures),
            "signatures": sorted(baseline.signatures),
            "metadata": baseline.metadata,
        }
        file_path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")

    @staticmethod
    def load_baseline(file_path: Path) -> BaselineData:
        """Load BaselineData from a JSON file."""
        if not file_path.is_file():
            raise FileNotFoundError(f"Baseline file '{file_path}' does not exist.")

        raw = json.loads(file_path.read_text(encoding="utf-8"))
        signatures = set(raw.get("signatures", []))
        return BaselineData(
            version=raw.get("version", BASELINE_SCHEMA_VERSION),
            created_at=raw.get("created_at", ""),
            score=float(raw.get("score", 100.0)),
            findings_count=int(raw.get("findings_count", len(signatures))),
            signatures=signatures,
            metadata=raw.get("metadata", {}),
        )

    @staticmethod
    def apply_baseline(findings: list[Finding], baseline: BaselineData) -> tuple[int, int]:
        """Mark findings as is_baselined=True if their signature is in the baseline.

        Returns:
            (baselined_count, new_findings_count)
        """
        baselined_count = 0
        new_count = 0
        for f in findings:
            sig = compute_finding_signature(f.code, f.rel_path, f.match_text, f.message)
            if sig in baseline.signatures:
                f.is_baselined = True
                baselined_count += 1
            else:
                f.is_baselined = False
                new_count += 1
        return baselined_count, new_count
