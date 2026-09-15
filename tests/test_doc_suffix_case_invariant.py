# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""Every DOC_SUFFIXES comparison is case-insensitive (V031_FIX_SUFFIX_CASE_BYPASS).

`discovery.py` compared `path.suffix` verbatim while the LSP, the adapters and
the scanner compared `path.suffix.lower()`. A credential in `notes.MD` was
therefore analysed by the editor and invisible to `zenzic check all`: exit 1
where the Exit Code Contract owes exit 2, on a file whose extension spelling is
ordinary on a case-insensitive filesystem.

Why this is a structural test and not a fixture. The CLI/LSP parity guard cannot
see this class: both paths call the same `iter_markdown_sources`, so a defect
inside shared discovery moves both sides together and the comparison still finds
agreement. The divergence lived between that shared function and the LSP's own
`_is_supported_doc_uri` -- two independent comparisons of the same thing. What
protects against that is an invariant over every comparison site, which is what
this asserts. Same instrument as the `url2pathname` single-implementation test.
"""

from __future__ import annotations

import re
from pathlib import Path


SRC = Path(__file__).resolve().parents[1] / "src" / "zenzic"

#: `.suffix` compared against DOC_SUFFIXES without a `.lower()` in between.
CASE_SENSITIVE = re.compile(r"\.suffix(?!\.lower\(\))[^\n]{0,40}?\bDOC_SUFFIXES\b")


def test_every_doc_suffix_comparison_is_case_insensitive() -> None:
    offenders: list[str] = []
    for path in sorted(SRC.rglob("*.py")):
        for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if CASE_SENSITIVE.search(line):
                offenders.append(f"{path.relative_to(SRC.parent.parent)}:{n}: {line.strip()}")
    assert not offenders, (
        "DOC_SUFFIXES compared against a case-sensitive `.suffix`; use `.suffix.lower()`.\n"
        "A file named `NOTES.MD` is then invisible to one path and visible to another, and "
        "the credential scanner is on the invisible side:\n  " + "\n  ".join(offenders)
    )


def test_the_detector_actually_detects() -> None:
    """Positive control: the pattern must match the exact form that shipped."""
    assert CASE_SENSITIVE.search("        if md_file.suffix not in DOC_SUFFIXES:")
    assert CASE_SENSITIVE.search("if fp.is_dir() or fp.suffix in DOC_SUFFIXES:")
    assert not CASE_SENSITIVE.search("        if md_file.suffix.lower() not in DOC_SUFFIXES:")
