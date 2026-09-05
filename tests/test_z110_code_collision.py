# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""Regression coverage for V031_Z110_CODE_COLLISION_REMEDIATION.

Before this fix, two live, semantically unrelated findings shared the literal
code ``"Z110"``:

- ``src/zenzic/models/config.py`` emitted ``Z110`` for CONFIG_SYNTAX_ERROR
  (malformed ``.zenzic.toml``, a non-suppressible pre-scan guard).
- ``src/zenzic/core/scanner.py`` emitted ``Z110`` for STALE_ALLOWLIST_ENTRY
  (an unused ``absolute_path_allowlist`` entry, a suppressible warning).

Because ``Z110`` is in ``NON_SUPPRESSIBLE_CODES``, and
``compute_score()``'s security override collapses the DQS to 0/100 for *any*
finding whose code is in that set, a stale allowlist entry — an ordinary
configuration-hygiene nit — silently zeroed the entire document score exactly
like a credential leak would.

The fix renumbers STALE_ALLOWLIST_ENTRY to the previously-reserved ``Z112``
slot (``status="inactive"`` before this fix, no live emission anywhere),
leaving ``Z110`` = CONFIG_SYNTAX_ERROR untouched (it already matched
``codes.py``'s ``CODE_DEFINITIONS``/``NON_SUPPRESSIBLE_CODES``/``CODE_NAMES``
dicts pre-fix; only the STALE_ALLOWLIST_ENTRY meaning was the drifted one).
"""

from __future__ import annotations

from pathlib import Path

from zenzic.core import regex as re
from zenzic.core.codes import CODE_DEFINITIONS, CODE_NAMES, NON_SUPPRESSIBLE_CODES
from zenzic.core.scorer import compute_score


REPO_ROOT = Path(__file__).resolve().parents[1]
CODES_PY_PATH = REPO_ROOT / "src" / "zenzic" / "core" / "codes.py"

DOCSTRING_ENTRY_PATTERN = re.compile(r"^\s+(Z\d{3})\s+(\S+)\s+—", flags=re.MULTILINE)


def test_stale_allowlist_entry_no_longer_shares_code_with_config_syntax_error(
    tmp_path: Path,
) -> None:
    """The two finding types that used to collide under "Z110" must use distinct codes."""
    from zenzic.core.validator import validate_links_structured
    from zenzic.models.config import ZenzicConfig

    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "index.md").write_text(
        "[Allowed](/allowed/foo.html) [Not Allowed](/notallowed/foo.html)\n"
    )
    (tmp_path / ".zenzic.toml").write_text("[project]\n")

    config = ZenzicConfig(absolute_path_allowlist=["/allowed/", "/unused/"])
    from _helpers import make_mgr

    mgr = make_mgr(config, repo_root=tmp_path)

    errors = validate_links_structured(
        docs,
        mgr,
        repo_root=tmp_path,
        config=config,
        strict=False,
        check_external=False,
    )
    stale_allowlist_codes = {e.error_type for e in errors if "/unused/" in e.message}
    assert stale_allowlist_codes == {"Z112"}, (
        f"STALE_ALLOWLIST_ENTRY should emit Z112, got {stale_allowlist_codes}"
    )

    config_syntax_error_code = "Z110"
    assert config_syntax_error_code not in stale_allowlist_codes, (
        "STALE_ALLOWLIST_ENTRY must not share a code with CONFIG_SYNTAX_ERROR (Z110)"
    )


def test_stale_allowlist_entry_does_not_collapse_dqs_to_zero() -> None:
    """A stale-allowlist warning alone must not trigger the NON_SUPPRESSIBLE_CODES
    security override that collapses the score to 0/100 (that override is reserved
    for genuine security breaches, not configuration hygiene warnings)."""
    report = compute_score({"Z112": 1})
    assert report.security_override is False
    assert report.score > 0


def test_z110_z111_z112_code_definitions_match_expected_meanings() -> None:
    assert CODE_NAMES["Z110"] == "CONFIG_SYNTAX_ERROR"
    assert CODE_NAMES["Z111"] == "CONFIG_SCHEMA_ERROR"
    assert CODE_NAMES["Z112"] == "STALE_ALLOWLIST_ENTRY"

    assert "Z110" in NON_SUPPRESSIBLE_CODES
    assert "Z111" in NON_SUPPRESSIBLE_CODES
    assert "Z112" not in NON_SUPPRESSIBLE_CODES

    z112_defn = CODE_DEFINITIONS["Z112"]
    assert z112_defn.status == "active"
    assert z112_defn.severity == "warning"


def test_codes_py_docstring_matches_registry_dicts() -> None:
    """Permanent guard against the exact root-cause bug found in this directive:
    codes.py's own schema docstring (self-described SSoT) had drifted from its
    own CODE_DEFINITIONS/CODE_NAMES dicts for Z110/Z111/Z112, self-contradicting
    within the same file."""
    docstring = CODES_PY_PATH.read_text(encoding="utf-8").split('"""')[1]
    documented = dict(DOCSTRING_ENTRY_PATTERN.findall(docstring))
    assert documented, "Failed to parse any Zxxx entries from codes.py's schema docstring"

    mismatches = []
    for code, documented_name in documented.items():
        if documented_name in ("(reserved)",):
            continue
        actual_name = CODE_NAMES.get(code)
        if actual_name != documented_name:
            mismatches.append(
                f"{code}: docstring says {documented_name!r}, CODE_NAMES says {actual_name!r}"
            )

    assert not mismatches, "codes.py docstring drifted from its own registry:\n" + "\n".join(
        mismatches
    )
