# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""Documentation quality scoring engine.

Computes a deterministic 0–100 score from the results of all Zenzic checks.
Each category carries a fixed weight; per-code penalties are deducted up to a
category cap so that minor issues never collapse the entire score.

Zenzic Weight Matrix (5-Tier)
------------------------------------------
Tier            Codes          Weight   Notes
─────────────── ────────────── ──────── ──────────────────────────────────────
Security Gate   Z2xx           CRITICAL Score collapses to 0. Non-suppressible.
Structural      Z1xx           30 pts   Link graph and reference integrity.
Navigation      Z3xx, Z4xx     25 pts   Ref-graph logic and page navigation.
Content         Z5xx           20 pts   Text quality and code block accuracy.
Governance      Z4xx (Z405,    25 pts   Brand compliance and asset hygiene.
                Z406), Z6xx

Scoring formula: total = Σ max(0, cap_i − Σ penalty_code × count_code)

Governance Escalation (Z6xx threshold = 10):
  Z6xx violations beyond 10 trigger exponential amplification on the
  governance bucket — doubling every 5 excess findings — until 0.

Suppression Debt (ADR-061): flat-cost model.
    Every inline or per-file suppression costs exactly 1 point, with no free
    allowance.  The ``suppression_cap`` is a hard-fail threshold enforced by
    the CLI layer: exceeding it causes Exit 1 regardless of the computed score.

Security Override (Zero-Tolerance Floor)
-----------------------------------------
If any Z2xx finding is present, the score collapses to 0 unconditionally.
Z204 (FORBIDDEN_TERM) is included: confidential-term exposure is a binary
failure condition — no quality score is meaningful for such a document.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from zenzic.core.codes import CODE_DEFINITIONS, NON_SUPPRESSIBLE_CODES
from zenzic.core.exceptions import ConfigurationError


# ─── Weights ──────────────────────────────────────────────────────────────────

_WEIGHTS: dict[str, float] = {
    "structural": 0.30,  # Z101, Z102, Z104, Z105, Z107, Z108 — Structural Integrity
    "navigation": 0.25,  # Z301–303 (Ref-Graph) + Z401, Z402 — Navigation & Logic
    "content": 0.20,  # Z403, Z501, Z502, Z503, Z505 — Content Quality
    "brand": 0.25,  # Z404, Z405, Z406, Z601 — Governance & Brand
}

# ─── Penalty Table — derived from CODE_DEFINITIONS (SSoT) ────────────────────
# Do NOT edit these dicts manually.  Add or change a code in codes.py instead.
# Category cap = weight × 100  (e.g. structural cap = 30 pts).
# Formula per category:  max(0, cap − Σ penalty_i × count_i)
_CODE_PENALTY: dict[str, float] = {
    code: defn.penalty for code, defn in CODE_DEFINITIONS.items() if defn.penalty > 0.0
}

_CODE_CATEGORY: dict[str, str] = {
    code: defn.category for code, defn in CODE_DEFINITIONS.items() if defn.category is not None
}

# Security Override codes — imported from codes.py (NON_SUPPRESSIBLE_CODES).

# Governance escalation: Z6xx violations above this threshold trigger exponential
# penalty on the brand bucket — doubles every 5 excess findings until 0.
_Z6XX_GOVERNANCE_THRESHOLD: int = 10
_Z6XX_CODES: frozenset[str] = frozenset({"Z601", "Z603", "Z610", "Z611", "Z612", "Z613", "Z614", "Z615", "Z616", "Z620"})

_SOVEREIGN_SUPPRESSION_CAP: int = 30
_DEBT_STATUS_VALUES: frozenset[str] = frozenset({"CLEAN", "MANAGED", "EXTENDED", "CRITICAL"})


def classify_suppression_debt_status(suppression_count: int, suppression_cap: int) -> str:
    """Classify suppression debt posture for machine-readable contract consumers."""
    if suppression_count <= 0:
        return "CLEAN"
    if suppression_count > suppression_cap:
        return "CRITICAL"
    if suppression_cap > _SOVEREIGN_SUPPRESSION_CAP:
        return "EXTENDED"
    return "MANAGED"


# ─── Data structures ──────────────────────────────────────────────────────────


@dataclass
class CategoryScore:
    """Score and issue count for a single check category."""

    name: str
    weight: float
    issues: int
    category_score: float  # 0.0–1.0 before weight is applied
    contribution: float  # category_score * weight
    raw_penalty: float = 0.0  # post-escalation deduction before the category cap (positive value)
    is_capped: bool = False  # True if raw_penalty was truncated by the category cap


@dataclass
class ScoreReport:
    """Full scoring report produced by :func:`compute_score`."""

    score: int  # 0–100 (rounded)
    threshold: int = 0  # fail_under value at save time; 0 means no threshold
    security_override: bool = False  # True when score collapsed to 0 by a security violation
    security_findings: int = 0  # count of Z2xx findings triggering the Security Gate
    suppression_count: int = 0
    suppression_cap: int = _SOVEREIGN_SUPPRESSION_CAP
    debt_status: str = "CLEAN"
    suppression_debt_pts: int = 0  # points deducted for inline/per-file suppressions
    categories: list[CategoryScore] = field(default_factory=list)
    findings_counts: dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        if self.security_override:
            status = "security_breach"
        elif self.score >= self.threshold:
            status = "success"
        else:
            status = "failing"
        d: dict[str, object] = {
            "project": "zenzic",
            "score": self.score,
            "threshold": self.threshold,
            "status": status,
            "timestamp": datetime.now(tz=timezone.utc).isoformat(timespec="seconds"),
            "categories": [asdict(c) for c in self.categories],
            "suppression_count": self.suppression_count,
            "suppression_cap": self.suppression_cap,
            "suppression_debt_pts": self.suppression_debt_pts,
            "debt_status": self.debt_status,
        }
        if self.security_override:
            d["security_override"] = True
        if self.security_findings > 0:
            d["security_findings"] = self.security_findings
        return d


# ─── Pure scoring logic ───────────────────────────────────────────────────────


def compute_score(
    findings_counts: dict[str, int],
    suppression_count: int = 0,
    suppression_cap: int = 30,
) -> ScoreReport:
    """Compute a 0–100 documentation quality score using the Zenzic Penalty Table.

    Each finding code carries a per-occurrence point deduction.  Deductions are
    accumulated per category and capped at the category's maximum contribution
    (Structural 30, Navigation 25, Content 20, Brand 25).  Total score is the
    sum of remaining category points (0–100).

    Security Override: any Z2xx finding collapses the score to 0 unconditionally.

    Category Cap Invariant: 1 000 occurrences of Z505 (1.0 pt each) cap out
    the content category at 20 pts deducted, leaving structural (30)
    + navigation (25) + brand (25) = **80 / 100** before Gravity Cap.

    Governance Escalation: Z6xx violations beyond 10 trigger an exponential
    multiplier on brand bucket deductions (doubles every 5 excess findings).

    Gravity Cap (ADR-031): if the brand category score reaches 0.00, total
    score is capped at 70 — a document with uncontrolled governance violations
    cannot score above 70/100.

    Suppression Debt (ADR-061): flat-cost model — every suppression costs
    exactly 1 point. ``suppression_cap`` is a hard-fail exit threshold only;
    it does not grant any free allowance.
    Debt is applied after all category calculations and after the Gravity Cap.

    Args:
        findings_counts: Mapping of ``Zxxx`` code → occurrence count.
            Unknown codes contribute zero deduction.
        suppression_count: Total number of active suppressions (inline + per-file).
            Each suppression costs exactly 1 point (flat-cost model).
        suppression_cap: Hard-fail threshold (default 30). When
            ``suppression_count`` exceeds this value the build fails regardless
            of the computed score.  The cap does not grant a free allowance —
            all suppressions are penalised at the flat rate.

    Returns:
        A :class:`ScoreReport` with the total 0–100 score and per-category breakdown.
    """
    normalized_suppression_count = max(0, suppression_count)
    normalized_suppression_cap = max(0, suppression_cap)
    debt_status = classify_suppression_debt_status(
        normalized_suppression_count,
        normalized_suppression_cap,
    )

    # Security override: any Z2xx finding collapses the score to 0.
    sec_count = sum(findings_counts.get(code, 0) for code in NON_SUPPRESSIBLE_CODES)
    if sec_count > 0:
        categories = [
            CategoryScore(
                name=n,
                weight=w,
                issues=0,
                category_score=0.0,
                contribution=0.0,
                raw_penalty=0.0,
                is_capped=False,
            )
            for n, w in _WEIGHTS.items()
        ]
        return ScoreReport(
            score=0,
            security_override=True,
            security_findings=sec_count,
            suppression_count=normalized_suppression_count,
            suppression_cap=normalized_suppression_cap,
            debt_status=debt_status,
            categories=categories,
            findings_counts=findings_counts,
        )

    categories: list[CategoryScore] = []  # type: ignore[no-redef]
    total_pts = 0.0

    for name, weight in _WEIGHTS.items():
        cap_pts = weight * 100  # e.g. structural: 35.0
        deduction = sum(
            _CODE_PENALTY.get(code, 0.0) * count
            for code, count in findings_counts.items()
            if _CODE_CATEGORY.get(code) == name and count > 0
        )
        # Governance Escalation: Z6xx violations beyond the threshold receive
        # exponential amplification on the brand bucket — doubling every 5
        # excess findings until the bucket is fully zeroed.
        if name == "brand":
            z6xx_total = sum(findings_counts.get(c, 0) for c in _Z6XX_CODES)
            if z6xx_total > _Z6XX_GOVERNANCE_THRESHOLD:
                excess = z6xx_total - _Z6XX_GOVERNANCE_THRESHOLD
                z6xx_multiplier = 2.0 ** (excess / 5.0)
                deduction = deduction * z6xx_multiplier  # post-escalation, pre-cap
        raw_penalty_val = deduction  # post-escalation deduction, pre-cap
        is_capped_val = deduction > cap_pts
        cat_pts = max(0.0, cap_pts - deduction)
        cat_score_norm = cat_pts / cap_pts  # 0.0–1.0
        issues = sum(
            count
            for code, count in findings_counts.items()
            if _CODE_CATEGORY.get(code) == name and count > 0
        )
        total_pts += cat_pts
        categories.append(
            CategoryScore(
                name=name,
                weight=weight,
                issues=issues,
                category_score=round(cat_score_norm, 4),
                contribution=round(cat_pts / 100, 4),
                raw_penalty=round(raw_penalty_val, 4),
                is_capped=is_capped_val,
            )
        )

    # Gravity Cap (ADR-031): a fully zeroed brand bucket limits total to 70/100.
    # A document with uncontrolled governance violations cannot score above 70.
    brand_cat = next((c for c in categories if c.name == "brand"), None)
    if brand_cat is not None and brand_cat.category_score == 0.0:
        total_pts = min(total_pts, 70.0)

    # Suppression Debt (ADR-061): flat-cost model — every suppression costs 1 pt.
    # The cap is a hard-fail threshold enforced by the CLI, not a free allowance.
    debt_pts = normalized_suppression_count
    total_pts = max(0.0, total_pts - debt_pts)

    return ScoreReport(
        score=round(total_pts),
        suppression_count=normalized_suppression_count,
        suppression_cap=normalized_suppression_cap,
        debt_status=debt_status,
        suppression_debt_pts=debt_pts,
        categories=categories,
        findings_counts=findings_counts,
    )


# ─── Snapshot persistence ─────────────────────────────────────────────────────

_SNAPSHOT_FILENAME = ".zenzic-score.json"


def save_snapshot(repo_root: Path, report: ScoreReport) -> Path:
    """Write the score report to ``.zenzic-score.json`` in *repo_root*.

    Returns the path to the written file.
    """
    snapshot_path = repo_root / _SNAPSHOT_FILENAME
    data = report.to_dict()
    data["schema_version"] = 2  # D092 — Zenzic Penalty Scorer
    snapshot_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return snapshot_path


def load_snapshot(repo_root: Path) -> ScoreReport | None:
    """Read the last saved score report from *repo_root*.

    Returns ``None`` if no snapshot file is present or the file cannot be parsed.
    Raises ``ConfigurationError`` if the snapshot was written by Zenzic v0.6.x
    (decay model, schema_version < 2) and is incompatible with the Zenzic scorer.
    """
    snapshot_path = repo_root / _SNAPSHOT_FILENAME
    if not snapshot_path.is_file():
        return None
    try:
        data = json.loads(snapshot_path.read_text(encoding="utf-8"))
        if data.get("schema_version", 1) < 2:
            raise ConfigurationError(
                "Incompatible baseline (v0.6.x decay model). "
                "Run 'zenzic score --save' to create a Zenzic baseline."
            )
        categories = [CategoryScore(**c) for c in data.get("categories", [])]
        score = int(data.get("score", 0))
        threshold = int(data.get("threshold", 0))
        suppression_count = int(data.get("suppression_count", 0))
        suppression_cap = int(data.get("suppression_cap", _SOVEREIGN_SUPPRESSION_CAP))
        debt_status = str(
            data.get(
                "debt_status",
                classify_suppression_debt_status(suppression_count, suppression_cap),
            )
        ).upper()
        if debt_status not in _DEBT_STATUS_VALUES:
            debt_status = classify_suppression_debt_status(suppression_count, suppression_cap)
        suppression_debt_pts = int(
            data.get("suppression_debt_pts", max(0, suppression_count - suppression_cap))
        )
        return ScoreReport(
            score=score,
            threshold=threshold,
            suppression_count=suppression_count,
            suppression_cap=suppression_cap,
            debt_status=debt_status,
            suppression_debt_pts=suppression_debt_pts,
            categories=categories,
        )
    except ConfigurationError:
        raise
    except Exception:
        return None
