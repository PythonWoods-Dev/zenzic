# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""Public API surface for the Zenzic core engine.

Import the resolver and its outcome types from here::

    from zenzic.core import InMemoryPathResolver, Resolved, FileNotFound

Import the incremental analysis engine::

    from zenzic.core import IncrementalAnalysisEngine
"""

from typing import TYPE_CHECKING, Any

from zenzic.core.resolver import (
    AnchorMissing,
    FileNotFound,
    InMemoryPathResolver,
    PathTraversal,
    Resolved,
    ResolveOutcome,
)


if TYPE_CHECKING:
    from zenzic.core.incremental import IncrementalAnalysisEngine


def __getattr__(name: str) -> Any:
    if name == "IncrementalAnalysisEngine":
        from zenzic.core.incremental import IncrementalAnalysisEngine

        return IncrementalAnalysisEngine
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "AnchorMissing",
    "FileNotFound",
    "IncrementalAnalysisEngine",
    "InMemoryPathResolver",
    "PathTraversal",
    "Resolved",
    "ResolveOutcome",
]
