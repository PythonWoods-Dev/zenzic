# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""Models for Zenzic Rule Metadata and SDK v3 definitions."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator


TaxonomyCategory = Literal["structural", "navigation", "content", "brand", "governance"]
RuleSeverity = Literal["error", "warning", "info"]


class RuleMetadata(BaseModel):
    """Metadata definition for Custom Rule SDK v3 rules.

    Enforces typed attributes for identification, taxonomy classification,
    DQS penalty weighting, and documentation links.
    """

    code: str = Field(description="Unique rule code identifier (e.g. 'ZZ-NO-TODO', 'MY_RULE_001').")

    @field_validator("code")
    @classmethod
    def _reject_reserved_zenzic_code(cls, v: str) -> str:
        # CustomRuleConfig.id (regex-flavor custom rules) already requires the
        # "ZZ-" prefix for this exact reason (ADR-012 code-namespace
        # collision). An SDK v3 rule had no equivalent guard: it could claim a
        # real Zenzic-owned code (e.g. "Z201") and have its own findings
        # silently discarded by _check.py's _RULE_FINDING_SKIP_CODES, which
        # assumes any Z201 rule-finding is a duplicate of the credential-
        # scanner bridge's dedicated path. Deferred import: codes.py has no
        # internal imports, but importing it at module load time here would
        # make models/rules.py load the full code registry just to define
        # this class, for every import of this lightweight metadata model.
        from zenzic.core.codes import CODE_DEFINITIONS

        if v in CODE_DEFINITIONS:
            raise ValueError(
                f"RuleMetadata.code {v!r} is a reserved Zenzic finding code "
                "(see codes.py's CODE_DEFINITIONS) and cannot be claimed by a "
                "custom SDK v3 rule. Use the 'ZZ-' prefix convention instead."
            )
        return v

    title: str = Field(description="Short human-readable title of the rule.")
    description: str = Field(description="Detailed explanation of what the rule checks.")
    severity: RuleSeverity = Field(default="warning", description="Finding severity level.")
    category: TaxonomyCategory = Field(
        default="content", description="Taxonomy category for DQS weighting."
    )
    penalty: float = Field(default=1.0, description="DQS penalty points applied per finding.")
    docs_url: str | None = Field(default=None, description="Optional URL to rule documentation.")
    supports_autofix: bool = Field(
        default=False, description="Whether the rule supports automated quick-fixes."
    )
