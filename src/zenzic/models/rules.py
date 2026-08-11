# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""Models for Zenzic Rule Metadata and SDK v3 definitions."""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field


TaxonomyCategory = Literal["structural", "navigation", "content", "brand", "governance"]
RuleSeverity = Literal["error", "warning", "info"]


class RuleMetadata(BaseModel):
    """Metadata definition for Custom Rule SDK v3 rules.

    Enforces typed attributes for identification, taxonomy classification,
    DQS penalty weighting, and documentation links.
    """

    code: str = Field(description="Unique rule code identifier (e.g. 'ZZ-NO-TODO', 'MY_RULE_001').")
    title: str = Field(description="Short human-readable title of the rule.")
    description: str = Field(description="Detailed explanation of what the rule checks.")
    severity: RuleSeverity = Field(default="warning", description="Finding severity level.")
    category: TaxonomyCategory = Field(
        default="content", description="Taxonomy category for DQS weighting."
    )
    penalty: float = Field(default=1.0, description="DQS penalty points applied per finding.")
    docs_url: Optional[str] = Field(default=None, description="Optional URL to rule documentation.")
    supports_autofix: bool = Field(
        default=False, description="Whether the rule supports automated quick-fixes."
    )
