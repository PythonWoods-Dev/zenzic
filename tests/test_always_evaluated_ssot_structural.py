# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""`--only`'s protected set must BE the non-suppressible set, not equal it.

`_ALWAYS_EVALUATED_CODES` began as a literal copy of `NON_SUPPRESSIBLE_CODES`
with nothing enforcing their equality. Both held the same seven codes, so
nothing was wrong *today* — but a set that must be extended in two places will
eventually be extended in one: a future Z2xx added to `NON_SUPPRESSIBLE_CODES`
without the mirror edit would silently hand `--only` back the ability to
silence a non-suppressible security code, regressing the exact defect the
protected set exists to prevent. One authority, aliased — drift impossible.
"""

from __future__ import annotations

from zenzic.cli._check import _ALWAYS_EVALUATED_CODES
from zenzic.core.codes import NON_SUPPRESSIBLE_CODES


def test_always_evaluated_is_the_non_suppressible_set() -> None:
    """Identity, not equality: equality passes for an unenforced copy."""
    assert _ALWAYS_EVALUATED_CODES is NON_SUPPRESSIBLE_CODES, (
        "_ALWAYS_EVALUATED_CODES must alias NON_SUPPRESSIBLE_CODES, not restate "
        "its members — two literals that merely agree today drift tomorrow."
    )
