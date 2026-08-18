# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""Centralized regex facade: stdlib-compatible flags + RE2 engine."""

from __future__ import annotations

import functools
import re as stdlib_re  # noqa: TID252
from collections.abc import Callable, Iterator
from typing import TYPE_CHECKING, Any, cast

import re2 as _re2


# 1. Re-export Standard Library Flags & Exceptions (Safe to use with re2)
IGNORECASE = I = stdlib_re.IGNORECASE  # noqa: E741
MULTILINE = M = stdlib_re.MULTILINE
DOTALL = S = stdlib_re.DOTALL
VERBOSE = X = stdlib_re.VERBOSE
ASCII = A = stdlib_re.ASCII
error = stdlib_re.error

# 2. Type Hints
if TYPE_CHECKING:
    RegexPattern = stdlib_re.Pattern[str]
    Match = stdlib_re.Match[str]
else:
    RegexPattern = Any
    Match = Any

# 3. Export RE2 Engine Functions
_SUPPORTED_FLAGS = IGNORECASE | MULTILINE | DOTALL | VERBOSE | ASCII


def _apply_flags(pattern: str, flags: int = 0) -> str:
    unsupported = flags & ~_SUPPORTED_FLAGS
    if unsupported:
        raise error(f"Unsupported regex flags for RE2 facade: {unsupported!r}")

    inline = ""
    if flags & IGNORECASE:
        inline += "i"
    if flags & MULTILINE:
        inline += "m"
    if flags & DOTALL:
        inline += "s"
    if flags & VERBOSE:
        inline += "x"
    # NOTE: ASCII is accepted for stdlib API compatibility, but RE2's Python
    # bindings do not expose a direct equivalent toggle. Semantics remain RE2-default.

    if inline:
        pattern = f"(?{inline}){pattern}"

    # fnmatch.translate() emits the stdlib end-anchor ``\Z``; RE2 expects ``\z``.
    return pattern.replace(r"\Z", r"\z")


@functools.lru_cache(maxsize=4096)
def compile(pattern: str, flags: int = 0) -> RegexPattern:  # noqa: A001
    compiled_pattern = _apply_flags(pattern, flags)
    try:
        return cast(RegexPattern, _re2.compile(compiled_pattern))
    except _re2.error as exc:
        raise stdlib_re.error(str(exc)) from exc


def search(pattern: str, string: str, flags: int = 0) -> Match | None:
    return compile(pattern, flags).search(string)


def match(pattern: str, string: str, flags: int = 0) -> Match | None:
    return compile(pattern, flags).match(string)


def fullmatch(pattern: str, string: str, flags: int = 0) -> Match | None:
    return compile(pattern, flags).fullmatch(string)


def sub(
    pattern: str,
    repl: str | Callable[[Match], str],
    string: str,
    count: int = 0,
    flags: int = 0,
) -> str:
    return compile(pattern, flags).sub(repl, string, count)


def finditer(pattern: str, string: str, flags: int = 0) -> Iterator[Match]:
    return compile(pattern, flags).finditer(string)


def findall(pattern: str, string: str, flags: int = 0) -> list[str] | list[tuple[str, ...]]:
    return compile(pattern, flags).findall(string)


escape = _re2.escape
