# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""Repository-health checks behind ``zenzic doctor``.

These sit beside the documentation scan rather than inside it. ``zenzic check``
analyses the content of a docs tree; these check the *repository's own
conventions* — that every architectural decision cited somewhere actually has a
record, that the redirects file has not been silently reshaped, that the config
loads. None of them is per-page, so none belongs in the per-file pipeline.

Every function here is pure over a path plus a :class:`DoctorConfig`, reads only
**public repository content**, and returns findings rather than printing. The
CLI layer owns presentation and exit codes (Radical Unawareness, ADR-075).

`.claude/` and `.human/` are unreachable by construction: the config model
refuses paths into either, and the scan roots below are the published tree plus
``src/``. Both directories are gitignored, so a check reading them would pass for
exactly one developer and be unrunnable everywhere else.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from zenzic.core import regex as re
from zenzic.core.discovery import iter_files_within


if TYPE_CHECKING:
    from zenzic.models.config import DoctorConfig

#: Directories scanned for citations. Deliberately the published documentation
#: tree and the shipped source — never a gitignored control plane.
_CITATION_ROOTS: tuple[str, ...] = ("src", "docs")

#: Suffixes worth reading for citations; anything else is binary or generated.
_CITATION_SUFFIXES: frozenset[str] = frozenset({".py", ".md", ".toml", ".yml", ".yaml"})


@dataclass(frozen=True)
class DoctorFinding:
    """One repository-health problem, with the check that produced it."""

    check: str
    message: str
    location: str | None = None

    def render(self) -> str:
        return f"{self.location}: {self.message}" if self.location else self.message


def _record_ids(vault: Path, pattern: str, repo_root: Path) -> set[str]:
    """Uppercased identifiers of every record present in *vault*.

    A record is identified by its filename or by its title, whichever carries
    the number. Filename alone is not enough: records filed under a purely
    descriptive slug (``adr-regex-acl.md``) title themselves ``# ADR 013`` and
    would otherwise be invisible, reporting a decision that is recorded and
    readable as a phantom citation.

    Only the title line is read, not the body, so a record that merely
    *mentions* another ADR does not claim to be it.
    """
    if not vault.is_dir():
        return set()
    compiled = re.compile(pattern)
    found: set[str] = set()
    for path in iter_files_within(vault, repo_root, suffixes=frozenset({".md"})):
        match = compiled.search(path.name.upper())
        if match:
            found.add(match.group(0).upper())
            continue
        title = _first_heading(path)
        if title is None:
            continue
        # Titles read "# ADR 013"; citations read "ADR-013". Normalise the
        # separator so one pattern recognises both spellings.
        match = compiled.search(title.upper().replace(" ", "-"))
        if match:
            found.add(match.group(0).upper())
    return found


def _first_heading(path: Path) -> str | None:
    """The first Markdown H1 in *path*, or None if it has none."""
    try:
        with path.open(encoding="utf-8") as fh:
            for line in fh:
                if line.startswith("# "):
                    return line[2:].strip()
    except (OSError, UnicodeDecodeError):
        return None
    return None


def check_adr_citations(repo_root: Path, config: DoctorConfig) -> list[DoctorFinding]:
    """Report citations that name a decision record which does not exist.

    A phantom citation is a claim the repository cannot support: prose or a code
    comment asserts that a decision was recorded, and no record is there to read.
    That is the same class of defect as a broken link, one level up.
    """
    vault = repo_root / config.adr_vault_path
    if not vault.is_dir():
        return [
            DoctorFinding(
                check="adr-citations",
                message=(
                    f"ADR vault not found at '{config.adr_vault_path}'. Set "
                    "[doctor].adr_vault_path, or leave it unset if this project "
                    "keeps no decision records."
                ),
            )
        ]

    records = _record_ids(vault, config.adr_citation_pattern, repo_root)
    compiled = re.compile(config.adr_citation_pattern)

    # citation -> first file that cites it, so a finding can point somewhere real
    cited: dict[str, str] = {}
    for root in _CITATION_ROOTS:
        base = repo_root / root
        if not base.is_dir():
            continue
        for path in iter_files_within(base, repo_root, suffixes=_CITATION_SUFFIXES):
            try:
                text = path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            for match in compiled.finditer(text):
                cited.setdefault(match.group(0).upper(), str(path.relative_to(repo_root)))

    return [
        DoctorFinding(
            check="adr-citations",
            message=f"{citation} is cited but has no record in '{config.adr_vault_path}'.",
            location=where,
        )
        for citation, where in sorted(cited.items())
        if citation not in records
    ]


def check_redirects(repo_root: Path, config: DoctorConfig) -> list[DoctorFinding]:
    """Structurally validate the redirects file, if the project has one.

    Absence is not a finding: most projects have no redirects file, and a check
    that fired on every one of them would be noise rather than signal.
    """
    path = repo_root / config.redirects_path
    if not path.is_file():
        return []

    try:
        lines = path.read_text(encoding="utf-8").split("\n")
    except OSError as exc:
        return [
            DoctorFinding(
                check="redirects",
                message=f"could not read: {exc}",
                location=str(config.redirects_path),
            )
        ]
    if lines and lines[-1] == "":
        lines.pop()

    findings: list[DoctorFinding] = []
    where = str(config.redirects_path)

    blanks = sum(1 for line in lines if not line.strip())
    if config.redirects_expected_blanks and blanks != config.redirects_expected_blanks:
        findings.append(
            DoctorFinding(
                check="redirects",
                message=(
                    f"blank-line count is {blanks}, expected "
                    f"{config.redirects_expected_blanks}. If deliberate, update "
                    "[doctor].redirects_expected_blanks in the same commit."
                ),
                location=where,
            )
        )

    for number, line in enumerate(lines, start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        fields = stripped.split()
        if len(fields) != 3:
            findings.append(
                DoctorFinding(
                    check="redirects",
                    message=f"expected 3 fields, found {len(fields)}: {line!r}",
                    location=f"{where}:{number}",
                )
            )
            continue
        source, destination, status = fields
        if not source.startswith("/"):
            findings.append(
                DoctorFinding(
                    check="redirects",
                    message=f"source must start with '/': {source!r}",
                    location=f"{where}:{number}",
                )
            )
        if not (destination.startswith("/") or destination.startswith("http")):
            findings.append(
                DoctorFinding(
                    check="redirects",
                    message=f"destination must start with '/' or 'http': {destination!r}",
                    location=f"{where}:{number}",
                )
            )
        if not status.isdigit():
            findings.append(
                DoctorFinding(
                    check="redirects",
                    message=f"status must be numeric, found {status!r}",
                    location=f"{where}:{number}",
                )
            )
    return findings


def check_config_schema(repo_root: Path) -> list[DoctorFinding]:
    """Surface config load errors (``Z110``/``Z111``) as health findings.

    Reuses the existing loader rather than re-validating: it already emits the
    two fatal config codes, and a second implementation could disagree with it.
    """
    from zenzic.models.config import load_config_with_diagnostics

    _config, diagnostics = load_config_with_diagnostics(repo_root)
    return [
        DoctorFinding(
            check="config-schema",
            message=f"[{getattr(d, 'code', '?')}] {getattr(d, 'message', d)}",
            location=getattr(d, "file_path", None) and str(d.file_path),
        )
        for d in diagnostics
    ]


def run_all(repo_root: Path, config: DoctorConfig) -> dict[str, list[DoctorFinding]]:
    """Every check, keyed by name, in a stable order."""
    return {
        "config-schema": check_config_schema(repo_root),
        "adr-citations": check_adr_citations(repo_root, config),
        "redirects": check_redirects(repo_root, config),
    }


# REUSE-IgnoreStart
# The template below contains SPDX tags destined for the *generated* record,
# not licensing metadata for this file. Without this guard REUSE reads them as
# a second, malformed expression for doctor.py itself.
_ADR_SKELETON = """<!--
SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
SPDX-License-Identifier: Apache-2.0
-->
---
description: "Architectural Decision Record: {title}."
---

# ADR {number:03d}: {title}

---

## Context

<!-- Why did this problem exist? What forced a decision? -->

---

## Decision

<!-- What was chosen, stated in one or two sentences. -->

---

## Rationale

<!-- Why this option and not the alternatives that were considered. -->

---

## Invariants

<!-- What must never change as a consequence of this decision. -->

---

## Consequences

<!-- What this costs, and what it makes possible. -->
"""
# REUSE-IgnoreEnd


def _slugify(title: str) -> str:
    """Lowercase, hyphenated form of *title* for use in a filename."""
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", title).strip("-").lower()
    return slug or "untitled"


def next_adr_number(repo_root: Path, config: DoctorConfig) -> int:
    """One past the highest identifier present, not the record count.

    The vault legitimately has gaps — decisions withdrawn, numbers reserved and
    never used. Reusing a gap would silently repoint every citation that already
    names it at a different decision, so allocation only ever moves forward.
    """
    vault = repo_root / config.adr_vault_path
    highest = 0
    if vault.is_dir():
        for path in iter_files_within(vault, repo_root, suffixes=frozenset({".md"})):
            match = re.search(r"(\d{3,})", path.name)
            if match:
                highest = max(highest, int(match.group(1)))
    return highest + 1


def scaffold_adr(repo_root: Path, config: DoctorConfig, number: int, title: str) -> Path:
    """Write the skeleton for ADR *number* and return its path.

    Refuses to overwrite: an existing record is somebody's decision, and a
    scaffold silently replacing it would destroy the very history the vault is
    for.
    """
    records = repo_root / config.adr_vault_path / "records"
    records.mkdir(parents=True, exist_ok=True)
    target = records / f"adr-{number:03d}-{_slugify(title)}.md"

    # Guard on the *number*, not the filename. Two records with the same number
    # under different slugs is worse than an overwrite: both would answer to the
    # same citation, and nothing would say which one a reference meant.
    existing = sorted(records.glob(f"adr-{number:03d}*.md"))
    if existing:
        raise FileExistsError(
            f"ADR {number:03d} already exists as {existing[0].name}; "
            "refusing to create a second record with the same number."
        )
    target.write_text(_ADR_SKELETON.format(number=number, title=title), encoding="utf-8")
    return target
