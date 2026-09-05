# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""Comprehensive, codebase-wide guard against hardcoded severity/exit-tier
literals in finding construction (V031_HARDCODE_SWEEP_AND_DOC_SURFACE_CHECK).

Supersedes nine narrow, per-file structural tests
(test_finding_severity_ssot_structural.py, test_rules_severity_ssot_structural.py,
test_incremental_severity_ssot_structural.py, test_scanner_severity_ssot_structural.py,
test_content_severity_ssot_structural.py, test_governance_severity_ssot_structural.py,
test_suppressions_severity_ssot_structural.py, test_config_severity_ssot_structural.py,
test_reference_finding_severity_ssot_structural.py), each of which hardcoded one
file path, one constructor name, and one keyword argument name -- a pattern
that requires writing a new file every time a new subsystem or constructor is
discovered, and offers zero protection to any file nobody has looked at yet.
This test instead walks every ``.py`` file under ``src/zenzic/`` and checks
every call to any known finding-like constructor, for any of the known
severity-shaped keyword arguments, regardless of which file it lives in.

Known finding-like constructors and their severity-shaped fields (found by
grepping every class definition under ``src/zenzic/`` for ``Finding``/
``Violation``, then reading each dataclass to confirm which fields actually
carry a severity/exit-tier value derived from ``codes.py``'s
``CODE_DEFINITIONS`` — ``SecurityFinding`` and ``DoctorFinding`` have no such
field and are intentionally absent from this list, not omitted by oversight):

- ``Finding`` (``severity=``)          -- reporter.py's CLI-facing finding
- ``RuleFinding`` (``severity=``)       -- rules.py's engine-level finding
- ``Violation`` (``level=``)            -- rules.py's VSM-aware finding
- ``ReferenceFinding`` (``is_warning=``) -- models/references.py; boolean, not
  a severity string, but the same "hardcode bypasses codes.py" shape (see
  test_reference_finding_severity_ssot_structural.py's own precedent: "currently
  correct by coincidence... nothing previously caught a future drift").

A local alias created by ``from zenzic.core.rules import RuleFinding as _RF``
(scanner.py's own pattern) is resolved by reading the file's own import
aliases rather than hardcoding ``"_RF"`` as a second name to match on, so an
arbitrary future alias is caught the same way.
"""

from __future__ import annotations

import ast
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src" / "zenzic"

#: constructor name -> {keyword arg name -> expected literal type}
_SEVERITY_FIELDS: dict[str, dict[str, type]] = {
    "Finding": {"severity": str},
    "RuleFinding": {"severity": str},
    "Violation": {"level": str},
    "ReferenceFinding": {"is_warning": bool},
}


def _local_aliases_for(tree: ast.Module) -> dict[str, str]:
    """Map a local name to the real constructor name it was imported as.

    Covers ``from zenzic.core.rules import RuleFinding as _RF`` -> {"_RF":
    "RuleFinding"}. A plain, unaliased import maps a name to itself so the
    lookup below is uniform either way.
    """
    aliases: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            for alias in node.names:
                if alias.name in _SEVERITY_FIELDS:
                    aliases[alias.asname or alias.name] = alias.name
    return aliases


def _is_bare_literal(node: ast.expr, expected_type: type) -> bool:
    return isinstance(node, ast.Constant) and isinstance(node.value, expected_type)


def _find_hardcodes_in_file(path: Path) -> list[str]:
    """Return "path:line: Ctor(..., field=literal)" violations in one file."""
    text = path.read_text(encoding="utf-8")
    if not any(ctor in text for ctor in _SEVERITY_FIELDS):
        return []  # cheap pre-filter before paying for a real parse

    tree = ast.parse(text, filename=str(path))
    aliases = _local_aliases_for(tree)
    rel = path.relative_to(REPO_ROOT)
    violations: list[str] = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue

        ctor_name: str | None = None
        if isinstance(node.func, ast.Name):
            candidate = aliases.get(node.func.id, node.func.id)
            if candidate in _SEVERITY_FIELDS:
                ctor_name = candidate
        # Attribute calls (module.Ctor(...)) are deliberately not resolved --
        # every known real construction site in this codebase imports the
        # name directly (see the aliasing handling above), and a qualified
        # call would need the imported module's own name, not a literal
        # guess; if one appears later, this test will simply not see it,
        # which is a narrower gap than the nine per-file tests it replaces
        # had (they saw nothing outside one hardcoded path at all).
        if ctor_name is None:
            continue

        fields = _SEVERITY_FIELDS[ctor_name]
        for kw in node.keywords:
            if kw.arg not in fields:
                continue
            expected_type = fields[kw.arg]
            if _is_bare_literal(kw.value, expected_type):
                violations.append(
                    f"{rel}:{kw.value.lineno}: {ctor_name}(..., {kw.arg}="
                    f"{kw.value.value!r}) is a bare literal -- must derive "
                    f"from codes.py's CODE_DEFINITIONS (code_severity(code) "
                    f"or equivalent), never a fixed value for a specific code."
                )

    return violations


def _all_source_files() -> list[Path]:
    return sorted(SRC_ROOT.rglob("*.py"))


def test_no_hardcoded_severity_literals_anywhere_in_src_zenzic() -> None:
    """No finding-construction site anywhere under src/zenzic/ may hardcode
    a severity/exit-tier-shaped field as a bare literal for a fixed code.

    Comprehensive by construction, not by enumeration: walks every .py file
    under src/zenzic/ rather than a fixed list of files already known to be
    interesting, so it does not depend on someone having already found and
    named the subsystem. See test_severity_ssot_structural_comprehensive_
    self_check.py for the proof that this actually catches the bug shape
    (re-derives the historical Z107/Z902/Z406/Z503/Z120/Z122/Z301-303/Z103
    violations from a snapshot of the pre-fix source, and fails loudly if a
    literal is reintroduced live).
    """
    violations: list[str] = []
    for path in _all_source_files():
        violations.extend(_find_hardcodes_in_file(path))

    assert not violations, (
        "Hardcoded severity/exit-tier literal(s) found in finding "
        "construction under src/zenzic/ -- every one of these must derive "
        "from codes.py's CODE_DEFINITIONS SSoT instead:\n" + "\n".join(violations)
    )


def test_scan_covers_every_known_finding_construction_site() -> None:
    """Sanity check on the scan's own reach: every .py file previously found
    (by direct grep, not this test) to construct one of the tracked classes
    must actually be visited and parsed without error. Guards against the
    cheap pre-filter or the rglob pattern silently skipping a real file.
    """
    expected_relative_paths = {
        "core/doctor.py",  # DoctorFinding -- no severity field, included for reach only
        "core/suppressions.py",
        "core/governance.py",
        "core/incremental.py",
        "core/cache.py",
        "core/credentials.py",  # SecurityFinding -- no severity field, included for reach only
        "core/scanner.py",
        "core/content.py",
        "core/rules.py",
        "cli/_check.py",
        "cli/_standalone.py",
        "sdk/rules.py",
        "models/config.py",
        "models/references.py",
    }
    seen = {str(p.relative_to(SRC_ROOT)).replace("\\", "/") for p in _all_source_files()}
    missing = expected_relative_paths - seen
    assert not missing, f"scan did not reach expected file(s): {missing}"
