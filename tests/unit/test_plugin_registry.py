# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""Plugin registry namespace contract tests (ADR-012 Batch 2).

Real-plugin reproduction: entry points are constructed with
``importlib.metadata.EntryPoint`` and loaded via genuine dotted-path import
resolution (``ep.load()``), not a pre-held class reference — the same
mechanism a real installed plugin package uses. Rule fixtures below implement
only ``BaseRule``'s actual contract (``rule_id`` + ``check``); none carries a
``code`` or ``primary_exit`` attribute, because no real ``BaseRule``
subclass — core or third-party — has ever had one. A prior version of
``_validate_plugin_code`` read ``rule.code``/``rule.primary_exit`` via
``getattr(..., None)``, which is why fixtures written *for that check* used
to set those attributes themselves: the tests were validating the checking
*logic* against a shape no real plugin has, not the real contract.
"""

from __future__ import annotations

from importlib.metadata import EntryPoint
from pathlib import Path

import pytest

from zenzic.core.exceptions import PluginContractError
from zenzic.core.rules import BaseRule, PluginRegistry, RuleFinding


class _CoreNamespaceRule(BaseRule):
    @property
    def rule_id(self) -> str:
        return "Z777"

    def check(self, file_path: Path, text: str) -> list[RuleFinding]:
        return []


class _WrongPrefixRule(BaseRule):
    @property
    def rule_id(self) -> str:
        return "other:001"

    def check(self, file_path: Path, text: str) -> list[RuleFinding]:
        return []


class _SecurityTierImpersonatorRule(BaseRule):
    """A rule whose *unprefixed* declared code names a real security-tier code."""

    @property
    def rule_id(self) -> str:
        return "Z201"

    def check(self, file_path: Path, text: str) -> list[RuleFinding]:
        return []


class _ProperlyPrefixedRule(BaseRule):
    """Control: a real conforming plugin rule, prefixed as required."""

    @property
    def rule_id(self) -> str:
        return "acme:001"

    def check(self, file_path: Path, text: str) -> list[RuleFinding]:
        return []


class _AcmeZ201(BaseRule):
    """Control: a properly prefixed code that merely contains a security code."""

    @property
    def rule_id(self) -> str:
        return "acme:Z201"

    def check(self, file_path: Path, text: str) -> list[RuleFinding]:
        return []


def _real_entry_point(name: str, cls: type[BaseRule]) -> EntryPoint:
    """A genuine ``EntryPoint``, loaded by real dotted-path import — not a stub."""
    return EntryPoint(
        name=name,
        value=f"{cls.__module__}:{cls.__qualname__}",
        group="zenzic.rules",
    )


def test_plugin_registry_rejects_core_z_namespace(monkeypatch: pytest.MonkeyPatch) -> None:
    reg = PluginRegistry()
    monkeypatch.setattr(
        reg, "_entry_points", lambda: [_real_entry_point("acme", _CoreNamespaceRule)]
    )

    with pytest.raises(
        PluginContractError,
        match="Third-party plugins must use '<plugin-id>:<code>' format",
    ):
        reg.load_selected_rules(["acme"])


def test_plugin_registry_rejects_wrong_plugin_prefix(monkeypatch: pytest.MonkeyPatch) -> None:
    reg = PluginRegistry()
    monkeypatch.setattr(reg, "_entry_points", lambda: [_real_entry_point("acme", _WrongPrefixRule)])

    with pytest.raises(PluginContractError, match="must start with 'acme:'"):
        reg.load_selected_rules(["acme"])


def test_plugin_registry_rejects_security_tier_impersonation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A plugin cannot declare its code as a bare security-tier code either.

    Regression for the second half of the same defect: the prior check read
    ``rule.primary_exit``, an attribute no ``BaseRule`` has ever set, so this
    case was never actually rejected by *that* branch. It is rejected here by
    the namespace check instead — the code is still a bare ``Z\\d{3}`` string,
    which the namespace check forbids regardless of which specific digits it
    is. That is the real, load-bearing mechanism (see the control test below).
    """
    reg = PluginRegistry()
    monkeypatch.setattr(
        reg,
        "_entry_points",
        lambda: [_real_entry_point("acme", _SecurityTierImpersonatorRule)],
    )

    with pytest.raises(
        PluginContractError,
        match="Third-party plugins must use '<plugin-id>:<code>' format",
    ):
        reg.load_selected_rules(["acme"])


def test_a_properly_prefixed_code_that_merely_contains_a_security_code_still_loads(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Control: prefixing is what's forbidden from being absent, not the substring.

    Proves the namespace check is not over-broad: ``acme:Z201`` never reaches
    the core severity table (only bare codes are recognised there), so it is
    not a genuine security-tier collision and must not be rejected.
    """
    reg = PluginRegistry()
    monkeypatch.setattr(reg, "_entry_points", lambda: [_real_entry_point("acme", _AcmeZ201)])

    loaded = reg.load_selected_rules(["acme"])
    assert [r.rule_id for r in loaded] == ["acme:Z201"]


def test_a_conforming_plugin_still_loads(monkeypatch: pytest.MonkeyPatch) -> None:
    """Control: the namespace check must not reject a genuinely valid plugin."""
    reg = PluginRegistry()
    monkeypatch.setattr(
        reg, "_entry_points", lambda: [_real_entry_point("acme", _ProperlyPrefixedRule)]
    )

    loaded = reg.load_selected_rules(["acme"])
    assert [r.rule_id for r in loaded] == ["acme:001"]
