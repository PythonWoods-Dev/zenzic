# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""Sovereign runtime context shared across governance-sensitive execution paths.

A single context switch (``force_audit``) can disable all suppressible
bypass mechanisms during truth-seeking audits.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar, Token
from dataclasses import dataclass


@dataclass(frozen=True)
class SovereignContext:
    """Execution context for governance-sensitive policy switches."""

    force_audit: bool = False


_SOVEREIGN_CONTEXT: ContextVar[SovereignContext | None] = ContextVar(
    "_SOVEREIGN_CONTEXT", default=None
)


def get_sovereign_context() -> SovereignContext:
    """Return the active sovereign execution context."""
    return _SOVEREIGN_CONTEXT.get() or SovereignContext()


@contextmanager
def sovereign_context(*, force_audit: bool = False) -> Iterator[SovereignContext]:
    """Temporarily activate a sovereign execution context for the current flow."""
    token: Token[SovereignContext | None] = _SOVEREIGN_CONTEXT.set(
        SovereignContext(force_audit=force_audit)
    )
    try:
        yield _SOVEREIGN_CONTEXT.get() or SovereignContext()
    finally:
        _SOVEREIGN_CONTEXT.reset(token)
