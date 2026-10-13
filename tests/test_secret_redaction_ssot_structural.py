# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""Raw secret material is formatted for human eyes in exactly one function.

`core/reporter.py`'s `_obfuscate_secret` says so in its own docstring -- *"the
only place where raw secret material is allowed to be formatted for human
consumption. It **must never** be bypassed."* `zenzic guard scan` bypassed it:
`cli/_guard.py` carried its own `_mask_secret`, used for the `match` and
`context` fields of the JSON payload and for the terminal table.

The two did not leak the secret body -- both revealed the first four and last
four characters -- but they disagreed on everything else, and only one of them
was tested. `_obfuscate_secret` is pinned by mutation-killing tests in
`test_redteam_remediation.py` down to `_obfuscate_secret("X") == "*"`;
`_mask_secret` had no test at all. A second redaction path on the credential
surface, untested, is the shape this module exists to prevent.

Structural rather than behavioural: a test that only compared outputs would pass
again the moment someone adds a third implementation that happens to agree
today.
"""

from __future__ import annotations

import inspect

from zenzic.cli import _guard
from zenzic.core.reporter import _obfuscate_secret


def test_the_guard_path_uses_the_declared_authority() -> None:
    """`guard scan` must redact through the same function the reporter does."""
    source = inspect.getsource(_guard)
    assert "_obfuscate_secret" in source, (
        "cli/_guard.py must redact through core.reporter._obfuscate_secret, which "
        "declares itself the only place raw secret material is formatted."
    )
    assert "def _mask_secret" not in source, (
        "cli/_guard.py defines a second redaction function. The authority's "
        "docstring says it must never be bypassed, and only the authority is "
        "covered by the mutation-killing tests in test_redteam_remediation.py."
    )


def test_no_other_module_defines_its_own_redaction() -> None:
    """The sweep, not just the one instance that was found."""
    import pathlib

    root = pathlib.Path(_guard.__file__).resolve().parent.parent
    offenders = []
    for path in sorted(root.rglob("*.py")):
        if path.name == "reporter.py":
            continue
        text = path.read_text(encoding="utf-8")
        for name in ("def _mask_secret", "def _redact_secret", "def _obfuscate_secret"):
            if name in text:
                offenders.append(f"{path.relative_to(root)} defines {name[4:]}")
    assert not offenders, "a second secret-redaction implementation exists: " + "; ".join(offenders)


def test_the_guard_surface_does_not_leak_the_secret_length() -> None:
    """The consolidation must close a property, not relocate one.

    `_obfuscate_secret` pads with one asterisk per hidden character, so its output
    is exactly as long as the secret. That is pinned deliberately by the
    mutation-killing tests (`test_total_length_preserved`,
    `test_star_count_is_length_minus_8`) -- and the reason was looked for and not
    found: the caret in the gutter is sized from `len(match_text)` against the
    source line, not from this string, which is printed on its own "Credential:"
    line with no alignment requirement. Absence of a found reason is not proof of
    absence, so the default is left exactly as it was and pinned.

    `guard scan` has no such constraint: its output is a JSON field and a table
    cell. It takes `preserve_length=False`, which is strictly stronger than the
    `_mask_secret` it replaced -- that one still revealed the length of any secret
    of eight characters or fewer by returning that many asterisks.
    """
    for n in (1, 4, 8):
        raw = "A" * n
        assert len(_obfuscate_secret(raw, preserve_length=False)) != n or n == len("[redacted]"), (
            f"a {n}-character secret still reveals its length on the guard surface"
        )
    long_secret = "AKIA" + "B" * 20 + "WXYZ"
    short_form = _obfuscate_secret(long_secret, preserve_length=False)
    assert len(short_form) < len(long_secret), "the guard form must not encode the length"
    assert short_form.startswith("AKIA") and short_form.endswith("WXYZ")
    assert "B" not in short_form

    # E il default resta quello fissato dai test anti-mutazione.
    assert len(_obfuscate_secret(long_secret)) == len(long_secret)


def test_the_authority_still_redacts() -> None:
    """Positive control: a structural test that cannot fail on behaviour proves little."""
    assert _obfuscate_secret("AKIAIOSFODNN7EXAMPLE") != "AKIAIOSFODNN7EXAMPLE"
    assert "IOSFODNN7" not in _obfuscate_secret("AKIAIOSFODNN7EXAMPLE")
    assert _obfuscate_secret("short") == "*" * 5
