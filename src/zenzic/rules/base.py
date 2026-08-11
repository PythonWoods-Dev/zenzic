# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""Base custom rule for AST-based analysis (API v2 - DEPRECATED/REMOVED)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from zenzic.core.exceptions import PluginContractError
from zenzic.core.rules import BaseRule


if TYPE_CHECKING:
    from pathlib import Path

    from zenzic.core.rules import RuleFinding


class BaseASTRule(BaseRule):
    """[DEPRECATED & REMOVED in v0.28.0] Custom Rules API v2 base class.

    TODO(v0.30.0): Remove this stub entirely. It exists in v0.28.x and v0.29.x
    only to provide a graceful migration error message for legacy plugins.

    Custom Rules API v2 (BaseASTRule) has been hard deprecated and removed in Zenzic v0.28.0.
    All custom rules must migrate to Custom Rule SDK v3 by subclassing
    `zenzic.sdk.ZenzicRuleV3` and defining a `RuleMetadata` instance.
    """

    def __init__(self, *args: object, **kwargs: object) -> None:
        raise PluginContractError(
            "Custom Rules API v2 (BaseASTRule) was removed in Zenzic v0.28.0. "
            "Please migrate your custom rule to Custom Rule SDK v3 by subclassing "
            "'zenzic.sdk.ZenzicRuleV3' and defining a 'RuleMetadata' instance."
        )

    @property
    def rule_id(self) -> str:
        return "DEPRECATED_V2_RULE"

    def check(self, file_path: Path, text: str) -> list[RuleFinding]:
        raise PluginContractError(
            "Custom Rules API v2 (BaseASTRule) was removed in Zenzic v0.28.0. "
            "Please migrate to Custom Rule SDK v3 ('zenzic.sdk.ZenzicRuleV3')."
        )
