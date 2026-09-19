# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""Shared CLI infrastructure: console singleton, _ui gateway, and cross-command utilities.

All Console and Panel configuration for the CLI lives here or in ``zenzic.ui``.
No other CLI module may instantiate Console or Panel directly.
"""

from __future__ import annotations

import difflib
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Final

import pathspec.gitignore
import typer
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from zenzic.core.adapters import list_adapter_engines
from zenzic.core.codes import (
    CODE_DEFINITIONS,
    CODE_DESCRIPTIONS,
    CODE_NAMES,
    SECURITY_TIER_CODES,
    get_sarif_name,
)
from zenzic.core.exceptions import ZenzicConfigError
from zenzic.core.exclusion import (
    AdapterLayers,
    LayeredExclusionManager,
    build_exclusion_manager,
)
from zenzic.core.reporter import Finding, FooterNotice
from zenzic.core.ui import ZenzicPalette, ZenzicUI, emoji
from zenzic.core.validator import repo_relative_label
from zenzic.models.config import ZenzicConfig

from ._metadata import COMMAND_BY_NAME


# ── Console singleton & UI gateway ───────────────────────────────────────────


def _auto_consoles() -> tuple[Console, Console]:
    """Build the pair of consoles auto-detection (no CLI flag either way) implies.

    Shared by the module-level singleton construction and by
    :func:`configure_console`'s no-flags branch, so the two can never drift:
    "auto" must mean the same thing whether it is the process's first console
    or a later call resetting away from an explicit ``--no-color``/
    ``--force-color``.
    """
    env_force_color = bool(os.environ.get("FORCE_COLOR") and not os.environ.get("NO_COLOR"))
    env_no_color = os.environ.get("NO_COLOR") is not None
    out = Console(
        highlight=False,
        no_color=env_no_color,
        force_terminal=True if env_force_color else None,
        # Forcing the terminal alone still leaves color *depth* to Rich's own
        # auto-detection from TERM/COLORTERM, which under-detects (falls back to
        # 16-color "standard") in an environment that advertises no truecolor
        # support — silently collapsing distinct severity colors like WARNING's
        # amber and ERROR's rose to the same ANSI code. Forcing "truecolor"
        # alongside force_terminal is what FORCE_COLOR is actually for.
        #
        # The else branch is "auto", NOT None. Rich's own default for this
        # parameter is the string "auto"; passing None explicitly does not mean
        # "detect it" — it means "this console has no color system", which
        # disables color unconditionally. The two are indistinguishable in a
        # conditional expression and equally invisible to any test whose stdout
        # is a pipe, because there is no color either way. Under a real terminal
        # the difference is total: "auto" resolves to 256/truecolor, None emits
        # no escape sequences at all, so every interactive user saw monochrome.
        color_system="truecolor" if env_force_color else "auto",
    )
    err = Console(
        stderr=True,
        highlight=False,
        no_color=env_no_color,
        force_terminal=True if env_force_color else None,
        color_system="truecolor" if env_force_color else "auto",
    )
    return out, err


console, stderr_console = _auto_consoles()

_ui = ZenzicUI(stderr_console)


def configure_console(*, no_color: bool = False, force_color: bool = False) -> None:
    """Reconfigure the module-level console for color control.

    Called by main.py callback when --no-color or --force-color flags are passed.
    CLI flags take priority over environment variables.  Also rebuilds ``_ui``
    so all subsequent command output uses the reconfigured console.
    """
    global console, stderr_console, _ui
    if no_color:
        console = Console(highlight=False, no_color=True)
        stderr_console = Console(stderr=True, highlight=False, no_color=True)
    elif force_color:
        # force_terminal alone leaves color depth to auto-detection, which
        # under-detects (16-color "standard") without an advertised
        # truecolor terminal — see the module-level Console construction
        # above for the full explanation.
        console = Console(highlight=False, force_terminal=True, color_system="truecolor")
        stderr_console = Console(
            stderr=True, highlight=False, force_terminal=True, color_system="truecolor"
        )
    else:
        # Neither flag is an explicit reset to auto, not a no-op: a prior call
        # in the same process (e.g. zenzic-mcp's long-running embed serving
        # multiple invocations) may have left no_color/force_color set, and
        # "no flags this time" must not silently inherit that state.
        console, stderr_console = _auto_consoles()
    _ui = ZenzicUI(stderr_console)


def get_ui() -> ZenzicUI:
    """Return the current centralized :class:`~zenzic.ui.ZenzicUI` instance.

    Always performs a live lookup so callers outside this module always receive
    the instance that is current *after* any ``configure_console()`` call.
    """
    return _ui


def get_console() -> Console:
    """Return the current centralized :class:`rich.console.Console` instance."""
    return console


def make_footer_notice(*lines: str) -> FooterNotice:
    """Return a normalized footer notice contract for text-mode command footers."""
    return FooterNotice(lines=tuple(line for line in lines if line))


def footer_hint(command_name: str) -> str:
    """Return the canonical usage hint line for a top-level command name."""
    meta = COMMAND_BY_NAME.get(command_name)
    if meta is None:
        return f"[{ZenzicPalette.DIM}]Try 'zenzic --help' for options.[/]"
    return f"[{ZenzicPalette.DIM}]{meta.usage_hint}[/]"


def print_footer_hint(
    command_name: str,
    *,
    output_format: str = "text",
    quiet: bool = False,
) -> None:
    """Emit a canonical footer navigation hint for human-readable command output."""
    if output_format != "text" or quiet:
        return
    console.print(Text.from_markup(footer_hint(command_name)))


def create_app(*, name: str, long_help: str) -> typer.Typer:
    """Create a Typer sub-app with the standard Zenzic CLI defaults."""
    return typer.Typer(
        name=name,
        help=long_help,
        no_args_is_help=True,
        rich_markup_mode="rich",
    )


# ── Info hint panel ──────────────────────────────────────────────────────────

_NO_CONFIG_HINT = Panel(
    "Using built-in defaults — no [bold].zenzic.toml[/] found.\n"
    "Run [bold cyan]zenzic init[/] to create a project configuration file.\n"
    "Customise docs directory, excluded paths, engine adapter, and lint rules.",
    title=f"[bold yellow]{emoji('info')} Zenzic Tip[/]",
    border_style="yellow",
    expand=False,
)


#: Formats whose stdout must stay valid against a schema -- no Rich panels, no
#: hints, nothing but the document. ``gitlab-codequality`` belongs here for the
#: same reason ``json`` does: a single stray line makes the artifact
#: unparseable, and GitLab reports that as "no results" rather than as an error.
_MACHINE_FORMATS: frozenset[str] = frozenset({"json", "sarif", "gitlab-codequality"})

#: Formats every ``check`` subcommand renders. ``check all`` and ``check links``
#: additionally emit ``github-annotations``; the rest genuinely do not implement
#: it, so accepting it there produced plain text with no error.
_BASE_FORMATS: tuple[str, ...] = ("text", "json", "sarif")
_ANNOTATION_FORMATS: tuple[str, ...] = (*_BASE_FORMATS, "github-annotations")
#: ``check all`` only. A GitLab Code Quality report describes a whole pipeline
#: job, and the per-aspect subcommands each see one slice of the findings --
#: uploading one of those as the job's report would silently shrink the merge
#: request's view to that slice.
_CODEQUALITY_FORMATS: tuple[str, ...] = (*_ANNOTATION_FORMATS, "gitlab-codequality")


def _validate_output_format(output_format: str, supported: tuple[str, ...]) -> None:
    """Reject an ``--format`` value the invoked command does not render.

    ``--only`` has always rejected an unknown finding code; ``--format`` accepted
    anything and fell through to text. The dangerous case was not a typo but a
    value valid on a *different* subcommand: a CI step asking ``check assets``
    for ``github-annotations`` received prose on stdout and a success-shaped
    exit, with nothing indicating the requested format was never produced.
    """
    if output_format in supported:
        return
    options = ", ".join(f"[bold]{f}[/]" for f in supported)
    hint = ""
    if output_format in _CODEQUALITY_FORMATS:
        hint = (
            f"\n\n  [dim]{output_format!r} is a valid format for other commands, "
            f"but this one does not render it.[/]"
        )
    console.print(
        f"[red]ERROR:[/] Unsupported output format [bold]{output_format!r}[/] "
        f"for this command.\n  Valid options: {options}{hint}"
    )
    raise typer.Exit(1)


def _print_no_config_hint(output_format: str = "text") -> None:
    """Print a one-time informational panel when running without .zenzic.toml.

    Suppressed for machine-readable formats (json, sarif) — Rule R20 Machine Silence:
    stdout must remain 100% valid against the target schema; no Rich panels allowed.
    """
    if output_format in _MACHINE_FORMATS:
        return
    console.print(_NO_CONFIG_HINT)
    console.print()


# ── Engine override ───────────────────────────────────────────────────────────


def _apply_engine_override(config: ZenzicConfig, engine: str | None) -> ZenzicConfig:
    """Return *config* with ``build_context.engine`` replaced by *engine*.

    When *engine* is ``None`` or ``"auto"``, the original config is returned
    unchanged.  When *engine* is not a registered adapter, a Rich error is
    printed to stderr and the process exits with code 1.
    """
    if not engine or engine == "auto":
        return config
    known = list_adapter_engines()
    if engine not in known:
        engines_fmt = ", ".join(f"[bold]{e}[/]" for e in known) if known else "(none installed)"
        hint = ""
        suggestions = difflib.get_close_matches(engine, known, n=1, cutoff=0.5)
        if suggestions:
            hint = f"\n\n  Did you mean [bold cyan]{suggestions[0]}[/]?"
        # stderr, not stdout: this is a diagnosis, and a caller redirecting
        # stderr to a log -- which is what CI does -- was keeping `ERROR: 1`
        # and discarding the half that says what actually went wrong.
        stderr_console.print(
            f"[red]ERROR:[/] Unknown engine adapter [bold]{engine!r}[/].\n"
            f"Installed adapters: {engines_fmt}{hint}"
        )
        raise typer.Exit(1)
    new_context = config.build_context.model_copy(update={"engine": engine})
    return config.model_copy(update={"build_context": new_context})


# ── JSON output ───────────────────────────────────────────────────────────────


def _finding_dict(f: Finding) -> dict[str, Any]:
    """One finding, in the shape every ``--format json`` payload uses.

    A helper rather than a literal in each emitter: the aggregate payload and the
    per-check payloads must resolve the same finding to the same file, line and
    code, and two hand-written copies of this dictionary agree until one of them
    gains a field.
    """
    return {
        "rel_path": f.rel_path,
        "line_no": f.line_no,
        "code": f.code,
        "severity": f.severity,
        "message": f.message,
        # 0-based, matching the engine's own `col_start` and the caret the text
        # output draws. Carried because two findings can share a line and differ
        # only here -- an unknown attribute and a jump link on the same tag -- and
        # a consumer given only the line cannot tell them apart. 0 means "no
        # column was determined", not "column zero".
        "col_start": f.col_start,
        "fixable": bool(getattr(CODE_DEFINITIONS.get(f.code), "fixable", False)),
    }


def _sarif_region(f: Finding) -> dict[str, int]:
    """A SARIF ``region`` for *f*, carrying the column when one is known.

    ``startColumn`` is **1-based** in SARIF while the engine's ``col_start`` is
    0-based, so the conversion is explicit here rather than left to a caller.
    Omitted entirely when no column was determined: SARIF treats a missing
    ``startColumn`` as "the whole line", which is the honest answer, whereas
    emitting 1 would claim the finding starts at the first character.

    This matters more than the JSON equivalent. GitHub Code Scanning renders the
    region as an underline, so a line-only region shows two findings about two
    different attributes of the same tag as the same highlight -- a plausible
    interface rather than a visible failure.
    """
    region: dict[str, int] = {"startLine": max(f.line_no, 1)}
    if f.col_start > 0:
        region["startColumn"] = f.col_start + 1
    return region


def _output_json_findings(
    findings: list[Finding], elapsed: float, suppression_audit: Any | None = None
) -> None:
    """Serialize findings list to JSON and print to stdout."""
    report = {
        "findings": [_finding_dict(f) for f in findings],
        "summary": {
            "errors": sum(1 for f in findings if f.severity == "error"),
            "warnings": sum(1 for f in findings if f.severity == "warning"),
            "info": sum(1 for f in findings if f.severity == "info"),
            "security_incidents": sum(1 for f in findings if f.severity == "security_incident"),
            "security_breaches": sum(1 for f in findings if f.severity == "security_breach"),
            "elapsed_seconds": round(elapsed, 3),
        },
    }
    if suppression_audit is not None:
        report["suppression"] = {
            "suppression_count": suppression_audit.total,
            "suppression_cap": suppression_audit.cap,
            "suppression_debt_pts": suppression_audit.excess,
            "debt_status": suppression_audit.debt_status,
        }
    print(json.dumps(report, indent=2))


def _engine_payload(repo_root: Path, docs_root: Path, config: ZenzicConfig) -> dict[str, object]:
    """What engine this run asked for, what it used, and whether those differ.

    Reads the record the adapter factory attaches rather than recomputing it, so
    the payload cannot disagree with the notice printed on stderr. The adapter
    is already built and cached by the time any payload is written, so asking
    for it again costs nothing.

    Falls back to the declared engine alone if the record is absent -- an
    adapter from a third-party entry point may not carry one, and a missing
    field is a better answer than a guessed one.
    """
    from zenzic.core.adapters import get_adapter

    declared = getattr(config.build_context, "engine", "auto")
    try:
        adapter = get_adapter(config.build_context, docs_root, repo_root)
    except Exception:
        return {"declared": declared, "resolved": declared, "substituted": False}
    resolution = getattr(adapter, "zenzic_resolution", None)
    if resolution is None:
        return {"declared": declared, "resolved": declared, "substituted": False}
    payload: dict[str, object] = resolution.as_payload()
    return payload


def _output_check_all_json_findings(
    results: Any,
    all_findings: list[Finding],
    repo_root: Path,
    docs_root: Path,
    config: ZenzicConfig,
    suppression_audit: Any | None = None,
) -> None:
    """Format and print the checkAllReport JSON payload."""

    def _rel(path: Path) -> str:
        # Delegates rather than repeating the four lines: this function and
        # `repo_relative_label` were character-for-character identical, which is
        # two copies that agree today and drift the day one grows a case.
        return repo_relative_label(path, repo_root)

    allowed_keys = {(f.rel_path, f.line_no, f.code) for f in all_findings}

    def _is_allowed(rel_path: str, line_no: int, code: str) -> bool:
        return (rel_path, line_no, code) in allowed_keys

    ref_errors = []
    for r in results.reference_reports:
        rel = _rel(r.file_path)
        try:
            rel_d = r.file_path.relative_to(repo_root / config.docs_dir)
        except ValueError:
            rel_d = r.file_path
        # Both loops below deliberately include every severity (error AND
        # warning) — the field is named "references", not "reference_errors",
        # and text/SARIF output already report both. Filtering by severity
        # here alone would make this field inconsistent with itself
        # (Z1xx warnings dropped, Z5xx/Z6xx warnings kept) as well as with
        # every other output format.
        for f in r.findings:
            if _is_allowed(rel, f.line_no, f.issue):
                ref_errors.append(f"{rel_d}:{f.line_no} [{f.issue}] — {f.detail}")
        # rule_findings (Z1xx-Z6xx AST/content/editorial rules, e.g. Z502
        # SHORT_CONTENT, Z512 HEADING_SECTION_EMPTY) is a separate attribute
        # from findings (Z1xx/Z3xx reference-pipeline output) — previously
        # never read here, so any rule-engine finding was silently absent
        # from this field regardless of severity.
        for rf in r.rule_findings:
            if _is_allowed(rel, rf.line_no, rf.rule_id):
                ref_errors.append(f"{rel_d}:{rf.line_no} [{rf.rule_id}] — {rf.message}")

    # The six grouped arrays -- links[], orphans[], snippets[], unused_assets[],
    # nav_contract[], references[] -- were removed in v0.31.0. Every finding they
    # carried is in findings[] in the canonical shape, re-verified per array
    # across the whole example gallery immediately before removal: 216 items,
    # 216 covered, 0 missing. They were also not machine-readable -- links[] and
    # nav_contract[] held pre-formatted prose with no code in it, and orphans[]
    # and unused_assets[] held bare paths -- so a consumer could not resolve a
    # finding to a file and a code from them at all.
    report: dict[str, Any] = {
        # `engine` first, because it qualifies everything under it. A consumer
        # that reads `findings` without knowing which adapter produced them is
        # reading an answer to a question it did not ask: a declared `prebuilt`
        # with no manifest once produced a run byte-identical to `standalone`
        # -- same total, same distribution, same exit -- and the only signal was
        # a notice on stderr, where no CI consumer reads.
        "engine": _engine_payload(repo_root, docs_root, config),
        "findings": [_finding_dict(f) for f in all_findings],
        "security_breaches": sum(1 for f in all_findings if f.severity == "security_breach"),
        "security_incidents": sum(1 for f in all_findings if f.severity == "security_incident"),
        "suppression_count": suppression_audit.total if suppression_audit else 0,
        "suppression_cap": suppression_audit.cap if suppression_audit else 0,
        "suppression_debt_pts": suppression_audit.excess if suppression_audit else 0,
        "debt_status": suppression_audit.debt_status if suppression_audit else "CLEAN",
    }
    print(json.dumps(report, indent=2))


# ── SARIF output ──────────────────────────────────────────────────────────────
# Rule metadata (names, descriptions, levels, helpUri) is derived dynamically
# from zenzic.core.codes — the single source of truth.  Do NOT add hardcoded
# rule dicts here; update codes.py instead.

_SARIF_SCHEMA = "https://json.schemastore.org/sarif-2.1.0.json"

_SARIF_SECURITY_SEVERITY: dict[str, str] = {
    "security_breach": "9.5",
    "security_incident": "9.0",
}


#: Zenzic severity -> GitLab Code Quality severity.
#:
#: GitLab's documented enum is exactly ``info``, ``minor``, ``major``,
#: ``critical``, ``blocker`` (lowercase; nothing states it is case-insensitive,
#: so it is treated as case-sensitive). A value outside that set does not
#: degrade to a default -- it makes the whole report unparseable, taking every
#: other finding in the run down with it. That is why the fallback below is a
#: legal value rather than the input, and why a test asserts the table's own
#: values are a subset of the enum.
_GITLAB_SEVERITY: dict[str, str] = {
    "security_breach": "blocker",
    "security_incident": "critical",
    "error": "major",
    "warning": "minor",
    "info": "info",
}


def _codequality_fingerprint(finding: Finding, occurrence: int) -> str:
    """A stable, unique identifier for one violation.

    GitLab identifies a violation *by* this value: two findings sharing one
    fingerprint are one violation to GitLab, and one of them silently
    disappears from the merge request.

    The line number is deliberately **not** hashed. GitLab uses the fingerprint
    to recognise the same violation across commits, so hashing the line would
    report every finding below an inserted paragraph as newly introduced. What
    disambiguates two identical findings in one file is instead ``occurrence``,
    their index among identical siblings in a deterministically sorted list --
    stable under edits elsewhere in the file, unique where it has to be.

    ``match_text`` is included because it distinguishes two genuinely different
    violations that share a message, and it is safe to include *because it is
    hashed*: the digest is emitted, never the matched text, which for a
    credential finding is the secret itself.
    """
    material = "\x00".join(
        (
            finding.rel_path.replace("\\", "/"),
            finding.code,
            finding.message,
            finding.match_text,
            str(occurrence),
        )
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def _codequality_payload(findings: list[Finding]) -> list[dict[str, Any]]:
    """Build GitLab's Code Quality report: a single array of violation objects.

    Pure and deterministic -- it returns the structure rather than printing it,
    so the schema can be asserted directly instead of through parsed stdout.
    """
    sorted_findings = sorted(
        findings,
        key=lambda f: (f.rel_path.replace("\\", "/"), max(f.line_no, 1), f.code, f.message),
    )

    seen: dict[tuple[str, str, str, str], int] = {}
    entries: list[dict[str, Any]] = []
    for f in sorted_findings:
        # Path must be relative to the repository root with no "./" prefix --
        # GitLab's troubleshooting guide names that prefix as a cause of a
        # report that parses but displays nothing.
        path = f.rel_path.replace("\\", "/")
        while path.startswith("./"):
            path = path[2:]

        key = (path, f.code, f.message, f.match_text)
        occurrence = seen.get(key, 0)
        seen[key] = occurrence + 1

        entries.append(
            {
                "description": f.message,
                # The stable rule id, not the message: GitLab groups and filters
                # on check_name, and a message carrying a path or a count would
                # make every occurrence its own "check".
                "check_name": f.code,
                "fingerprint": _codequality_fingerprint(f, occurrence),
                "severity": _GITLAB_SEVERITY.get(f.severity, "minor"),
                "location": {
                    "path": path,
                    # line_no == 0 means "the file itself" internally. Zero is
                    # not a line number; clamp as the SARIF emitter does.
                    "lines": {"begin": max(f.line_no, 1)},
                },
            }
        )
    return entries


def _output_codequality_findings(findings: list[Finding]) -> None:
    """Print the Code Quality report to stdout. Nothing else may be printed."""
    print(json.dumps(_codequality_payload(findings), indent=2))


def _sarif_level(severity: str) -> str:
    return {
        "security_breach": "error",
        "security_incident": "error",
        "error": "error",
        "warning": "warning",
        "info": "note",
    }.get(severity, "note")


#: GitHub Code Scanning's published limits for one SARIF upload: it rejects a
#: file carrying more than 25,000 results, and of the results it accepts it
#: **includes only the first 5,000**, ordered by severity. The rest are
#: discarded without any message to the user. Verified at docs.github.com on
#: 2026-09-19. Measured against a real run: this project's own Astro corpus
#: produces 15,254 findings, so a consumer uploading it sees 5,000 and loses
#: 10,254 with nothing saying so.
GITHUB_SARIF_RESULT_LIMIT: Final[int] = 25_000
GITHUB_SARIF_INCLUDED_LIMIT: Final[int] = 5_000


def _output_sarif_findings(
    findings: list[Finding],
    version: str,
    rules_map: dict[str, Any] | None = None,
    engine: dict[str, object] | None = None,
) -> None:
    """Serialize findings list to deterministic SARIF 2.1.0 JSON and print to stdout."""
    seen_rule_ids: set[str] = set()

    sorted_findings = sorted(
        findings,
        key=lambda f: (f.rel_path, f.line_no, f.code, f.message),
    )

    sarif_results: list[dict[str, object]] = []
    # Occurrence index among identical siblings, computed exactly as the GitLab
    # emitter computes it, so `zenzicFindingV1` below and `fingerprint` there are
    # the same value for the same finding. Two formats deriving one identity
    # separately is how they come to disagree.
    sarif_seen: dict[tuple[str, str, str, str], int] = {}
    for f in sorted_findings:
        seen_rule_ids.add(f.code)
        result: dict[str, object] = {
            "ruleId": f.code,
            "level": _sarif_level(f.severity),
            "message": {"text": f.message},
            "locations": [
                {
                    "physicalLocation": {
                        "artifactLocation": {
                            "uri": f.rel_path.replace("\\", "/"),
                            "uriBaseId": "%SRCROOT%",
                        },
                        "region": _sarif_region(f),
                    }
                }
            ],
        }
        # How GitHub Code Scanning decides whether two results are the same alert
        # across commits. Absent, it computes its own identity, and an alert can be
        # closed and reopened as a duplicate when unrelated lines shift above it --
        # so a finding nobody touched loses its history and its triage.
        #
        # `primaryLocationLineHash` is GitHub's own documented key, and it hashes
        # the *line*, not the position, which is exactly why it survives a line
        # moving. Omitted rather than faked when the source line is unknown: a
        # fingerprint over an empty string would give every such finding the same
        # identity, which is worse than having none -- GitHub would merge unrelated
        # alerts instead of failing to track one.
        #
        # MEASURED, because the paragraph above is only half the story. Executing
        # it confirmed `primaryLocationLineHash` does survive a line shift: the
        # same two findings moved from lines 11 and 12 to 14 and 15 and kept
        # identical hashes. But it hashes the line and *only* the line, so three
        # genuinely distinct findings -- the same broken-link text twice in one
        # file and once in another -- all came back with one fingerprint.
        # Cross-file identity may be rescued by GitHub pairing the hash with the
        # artifact URI, and that is precisely the kind of platform behaviour this
        # project has twice concluded wrongly by inference rather than reading.
        #
        # So a second key is added rather than the first being changed:
        # `primaryLocationLineHash` keeps GitHub's documented semantics, and
        # `zenzicFindingV1` carries an identity that does not depend on any of
        # it -- relative path, code, message, match text and occurrence index,
        # with the line number deliberately absent. It reuses the GitLab
        # emitter's function so the two formats cannot drift.
        sarif_key = (f.rel_path.replace("\\", "/"), f.code, f.message, f.match_text)
        occurrence = sarif_seen.get(sarif_key, 0)
        sarif_seen[sarif_key] = occurrence + 1
        fingerprints: dict[str, str] = {"zenzicFindingV1": _codequality_fingerprint(f, occurrence)}
        # Omitted rather than faked when the source line is unknown: a hash over
        # an empty string would give every such finding the same identity, which
        # is worse than having none -- GitHub would merge unrelated alerts
        # instead of failing to track one.
        if f.source_line:
            fingerprints["primaryLocationLineHash"] = hashlib.sha256(
                f.source_line.strip().encode("utf-8")
            ).hexdigest()
        result["partialFingerprints"] = fingerprints

        properties: dict[str, object] = {}
        if f.severity in _SARIF_SECURITY_SEVERITY:
            properties["security-severity"] = _SARIF_SECURITY_SEVERITY[f.severity]
        if f.is_likely_placeholder:
            properties["is_likely_placeholder"] = True
        if properties:
            result["properties"] = properties
        sarif_results.append(result)

    rules: list[dict[str, object]] = []
    for rule_id in sorted(seen_rule_ids):
        rule_def = CODE_DEFINITIONS.get(rule_id)
        # fixable is only ever True for Core/Governance codes with a real,
        # wired Mutation class (see tests/test_fixable_code_wiring_structural.py) --
        # plugin and custom (ZZ-) rules have no Zenzic-built-in auto-fix engine.
        fixable = False
        if rule_def is not None:
            category = rule_def.category or (
                "governance" if rule_id.startswith("Z6") else "uncategorized"
            )
            penalty = rule_def.penalty
            level = rule_def.severity
            help_uri = f"https://zenzic.dev/reference/finding-codes/#{rule_id.lower()}"
            short_desc = CODE_DESCRIPTIONS.get(rule_id, CODE_NAMES.get(rule_id, rule_id))
            fixable = bool(getattr(rule_def, "fixable", False))
        elif rules_map and rule_id in rules_map:
            rule_obj = rules_map[rule_id]
            meta = getattr(rule_obj, "metadata", None)
            if meta:
                category = getattr(meta, "category", "custom")
                penalty = getattr(meta, "penalty", 1.0)
                level = _sarif_level(getattr(meta, "severity", "warning"))
                help_uri = (
                    getattr(meta, "docs_url", None)
                    or f"https://zenzic.dev/reference/finding-codes/#{rule_id.lower()}"
                )
                short_desc = getattr(meta, "description", getattr(meta, "title", rule_id))
            else:
                category = "custom"
                penalty = 1.0
                level = "warning"
                help_uri = f"https://zenzic.dev/reference/finding-codes/#{rule_id.lower()}"
                short_desc = rule_id
        else:
            category = "custom" if rule_id.startswith("ZZ-") else "uncategorized"
            penalty = 1.0 if rule_id.startswith("ZZ-") else 0.0
            level = "warning"
            help_uri = f"https://zenzic.dev/reference/finding-codes/#{rule_id.lower()}"
            short_desc = CODE_DESCRIPTIONS.get(rule_id, CODE_NAMES.get(rule_id, rule_id))

        rule_entry: dict[str, object] = {
            "id": rule_id,
            "name": get_sarif_name(rule_id),
            "shortDescription": {"text": short_desc},
            "fullDescription": {"text": short_desc},
            "defaultConfiguration": {"level": level},
            "helpUri": help_uri,
            "properties": {
                "category": category,
                "penalty": penalty,
                "fixable": fixable,
            },
        }
        rules.append(rule_entry)

    run_obj: dict[str, Any] = {
        "tool": {
            "driver": {
                "name": "zenzic",
                "version": version,
                "informationUri": "https://zenzic.dev",
                "rules": rules,
            }
        },
        # SARIF's default column unit is UTF-16 code units; Zenzic counts Python
        # string indices, which are Unicode code points. The two differ on any line
        # containing a non-BMP character -- an emoji in a heading is enough -- so a
        # consumer would underline the wrong span without being told. Declared
        # rather than converted: the engine's own caret uses code points too, and a
        # single honest declaration keeps every surface consistent.
        "columnKind": "unicodeCodePoints",
        "results": sarif_results,
    }

    # The engine that produced these results, as a run-level property. GitHub
    # ignores properties it does not know, so this costs a consumer nothing and
    # gives one that reads it the thing stderr could never deliver: whether the
    # adapter named in the configuration is the adapter that ran.
    run_properties: dict[str, object] = {}
    if engine is not None:
        run_properties["engine"] = engine

    # And what this file will lose on upload, decided here because this is the
    # only place that knows the count before the file is written. Saying it is
    # the whole point: a user who uploads 15,254 results and sees 5,000 has no
    # way to tell a clean tail from a discarded one.
    if len(sarif_results) > GITHUB_SARIF_INCLUDED_LIMIT:
        truncation: dict[str, object] = {
            "resultCount": len(sarif_results),
            "githubIncludedLimit": GITHUB_SARIF_INCLUDED_LIMIT,
            "githubRejectedAbove": GITHUB_SARIF_RESULT_LIMIT,
            "githubWillDiscard": len(sarif_results) - GITHUB_SARIF_INCLUDED_LIMIT,
            "githubWillReject": len(sarif_results) > GITHUB_SARIF_RESULT_LIMIT,
        }
        run_properties["githubTruncation"] = truncation
        # Also on stderr, because a run property is read by whoever went looking
        # and this is a fact the person running the command should not have to
        # go looking for. stderr rather than stdout: stdout is the SARIF.
        _over = len(sarif_results) - GITHUB_SARIF_INCLUDED_LIMIT
        _note = (
            f"NOTICE: this SARIF carries {len(sarif_results):,} results. "
            f"GitHub Code Scanning includes only the first {GITHUB_SARIF_INCLUDED_LIMIT:,}, "
            f"so {_over:,} would not appear there."
        )
        if len(sarif_results) > GITHUB_SARIF_RESULT_LIMIT:
            _note += f" Above {GITHUB_SARIF_RESULT_LIMIT:,} the upload is rejected outright."
        Console(stderr=True, no_color=True, highlight=False, markup=False).print(_note)

    if run_properties:
        run_obj["properties"] = run_properties

    execution_successful = True
    notifications = []
    for f in findings:
        if f.code in SECURITY_TIER_CODES:
            execution_successful = False
            notifications.append(
                {
                    "descriptor": {"id": f.code},
                    "level": "error",
                    "message": {"text": f"Critical security finding detected: {f.code}"},
                }
            )

    if not execution_successful:
        run_obj["invocations"] = [
            {
                "executionSuccessful": False,
                "toolExecutionNotifications": notifications,
            }
        ]

    report = {
        "$schema": _SARIF_SCHEMA,
        "version": "2.1.0",
        "runs": [run_obj],
    }
    print(json.dumps(report, indent=2))


# ── GitHub Annotations output ─────────────────────────────────────────────────


def _output_github_annotations(findings: list[Finding]) -> None:
    """Print findings as GitHub Actions workflow commands to stdout."""
    for f in findings:
        if f.severity in {"error", "security_breach", "security_incident"}:
            level = "error"
        elif f.severity == "warning":
            level = "warning"
        else:
            level = "notice"

        props = []
        if f.rel_path:
            props.append(f"file={f.rel_path.replace(os.sep, '/')}")
        if f.line_no > 0:
            props.append(f"line={f.line_no}")
        if f.col_start > 0:
            props.append(f"col={f.col_start}")
        if f.code:
            props.append(f"title={f.code}")

        prop_str = ",".join(props)
        msg = f.message.replace("\n", "%0A")
        if prop_str:
            print(f"::{level} {prop_str}::{msg}")
        else:
            print(f"::{level}::{msg}")


# ── Link error renderer ───────────────────────────────────────────────────────


def _render_link_error(err: object, docs_root: Path) -> None:
    """Print a single LinkError with a Visual Snippet when source context is available."""
    from zenzic.core.validator import LinkError

    if not isinstance(err, LinkError):
        return
    try:
        rel = err.file_path.relative_to(docs_root)
        location = f"[{ZenzicPalette.DIM}]{rel}:{err.line_no}[/]"
    except ValueError:
        location = f"[{ZenzicPalette.DIM}]{err.file_path.name}:{err.line_no}[/]"

    raw_msg = err.message
    prefix = f"{err.file_path.relative_to(docs_root).as_posix() if err.file_path != docs_root else ''}:{err.line_no}: "
    body = raw_msg[len(prefix) :] if raw_msg.startswith(prefix) else raw_msg

    type_badge = f"[[bold red]{err.code}[/]]"
    header = f"  {type_badge} {location} — {body}"
    console.print(header)

    if err.source_line:
        console.print(f"    [{ZenzicPalette.DIM}]│[/] [italic]{err.source_line}[/]")


# ── Exclusion manager factory ─────────────────────────────────────────────────


def _z111(message: str) -> ZenzicConfigError:
    """Build a `Z111` that reports itself as one.

    `ZenzicConfigError` hardcodes `code="Z001"`, so a `Z111` raised through it
    reached the JSON payload as `"code": "Z001"` beside a message reading
    `[Z111]` -- a contract contradicting itself, and the payload is what the
    action's wrapper reads. `tier` and `severity` are pinned to the values that
    path already produced, so this corrects the identifier and nothing else.
    """
    exc = ZenzicConfigError(message, context={"tier": "Core", "severity": "fatal"})
    exc.code = "Z111"
    return exc


def docs_dir_missing_error(
    config: Any, docs_root: Path, repo_root: Path, *, because: str
) -> ZenzicConfigError:
    """Return the `Z111` raised when `docs_dir` names a directory that is not there.

    One question -- *what does this command do when the documentation directory
    is absent?* -- and until 2026-09-19 it had five answers across the CLI, of
    which four said nothing about having chosen. `check all` raised; `audit`
    rescoped to the whole repository and reported on a corpus nobody named;
    **`guard scan` returned zero targets and exited 0, a passing secret scan
    over a tree it never read**; the language server widened to the repository;
    the telemetry counter reported zero pages.

    The three that must fail now fail through this function, so the wording,
    the generator-aware advice and the code cannot drift apart between them.
    ``because`` is the one part that varies, because what is lost differs: an
    analysis, an audit, or a credential scan.

    A directory that **exists** and holds nothing scannable is a different
    statement and keeps its own, quieter answer at each call site.
    """
    declared = "docs_dir" in getattr(config, "model_fields_set", set())
    return _z111(
        f"[Z111] docs_dir '{config.docs_dir}' does not exist "
        + (
            "(declared in your configuration).\n"
            if declared
            else "(the default, which this project does not use).\n"
        )
        + f"  Looked in: {docs_root}\n"
        + f"  {because}\n"
        + _docs_dir_advice(repo_root)
    )


def manifest_missing_error(config: Any, repo_root: Path) -> ZenzicConfigError | None:
    """Return the `Z111` for a declared `prebuilt` with no route manifest, or
    ``None`` when the configuration is fine.

    **The declaration has no effect without the artefact.** Measured on Astro's
    own documentation, 2,604 pages, same commit: `prebuilt` with no manifest and
    `standalone` declared outright produce the *same total, the same
    distribution and the same exit code*. The engine the user asked for is not
    the engine that ran, and the only signal was a notice on stderr, where no CI
    consumer reads it — 98% of the 15,254 findings came from three codes, all
    derived from routing that was never resolved.

    That is the shape `Z111` closed for a missing `docs_dir` and `Z906` was
    corrected on in the same week: a run that did not do what it was asked,
    reporting as though it had.

    The separation holds, as it does there. A manifest that **exists** and is
    empty is a different statement — a generator that published nothing — and
    is not this error; it produces `Z115` for every source instead, which names
    the file to regenerate.

    Returns the exception rather than raising, because the language server calls
    this too and must turn it into a diagnostic: it has no channel to fail
    through, and going dark would leave the author with nothing.
    """
    engine = getattr(getattr(config, "build_context", None), "engine", None)
    if engine not in ("prebuilt", "vsm"):
        return None
    manifest = repo_root / ".zenzic-vsm.json"
    if manifest.is_file():
        return None

    from zenzic.cli._standalone import detect_generator

    found = detect_generator(repo_root)
    if found is not None:
        generator, _docs_dir, marker = found
        how = f"  {marker} is present, so this is {generator.capitalize()}.\n" + (
            "  Derive the manifest from the source tree — Astro's routing is "
            "positional, so no build is needed.\n"
            if generator == "astro"
            else "  Generate the manifest from `npm run build`: Docusaurus routing "
            "is not derivable from filenames.\n"
        )
    else:
        how = (
            "  The manifest maps each source path to the URL it publishes at, and "
            "you generate it from your own build.\n"
        )

    return _z111(
        f'[Z111] engine = "{engine}" is declared and .zenzic-vsm.json is not there.\n'
        f"  Looked in: {manifest}\n"
        "  Without it this run would analyse with 'standalone' instead — the same "
        "findings, from a site map that is not your site's.\n"
        + how
        + "  How to write it: https://zenzic.dev/how-to/configure-adapter/"
        "#prebuilt-route-manifest\n"
        '  Or declare engine = "standalone" if this project has no manifest to give.'
    )


def _docs_dir_advice(repo_root: Path) -> str:
    """Return the second half of the Z111 message: where this project's
    sources actually are.

    Offering a menu -- "Astro keeps them here, Docusaurus there" -- leaves the
    reader to work out which sentence is about them, in a repository where the
    answer is a marker file away. ``GENERATOR_MARKERS`` already holds the
    convention for each generator, and ``zenzic init`` already writes it into
    the config; this makes the error name the same directory that setup would
    have. The menu remains for a project nothing detects, where it is the
    honest answer rather than a hedge.
    """
    from zenzic.cli._standalone import detect_generator

    found = detect_generator(repo_root)
    if found is not None:
        generator, docs_dir, marker = found
        return (
            f"  {marker} is present, so this is {generator.capitalize()}, "
            f"which keeps Markdown sources under '{docs_dir}'.\n"
            f'  Set docs_dir = "{docs_dir}" in your configuration.'
        )
    return (
        "  Set docs_dir to the directory holding your Markdown sources. "
        "Astro/Starlight keeps them under 'src/content/docs'; "
        "Docusaurus under 'docs'."
    )


def _build_exclusion_manager(
    config: ZenzicConfig,
    repo_root: Path,
    docs_root: Path,
    *,
    exclude_dirs: list[str] | None = None,
    include_dirs: list[str] | None = None,
    adapter_metadata_files: frozenset[str] = frozenset(),
    adapter_output_dirs: frozenset[str] = frozenset(),
    adapter_excluded_docs: pathspec.gitignore.GitIgnoreSpec | None = None,
) -> LayeredExclusionManager:
    """Construct a :class:`LayeredExclusionManager` from config + CLI flags.

    This is the **single factory** for exclusion managers in the CLI layer.
    Every command must call this and pass the result down the pipeline.

    Includes F4-1 jailbreak protection: rejects ``docs_root`` paths that
    escape the repository root via path traversal (``../``).
    """
    _validate_docs_root(repo_root, docs_root)
    # The three adapter layers arrive here already separated, because several CLI
    # commands compute them from an adapter they built for another reason. Passed
    # straight through to the one constructor in `core.exclusion`.
    return build_exclusion_manager(
        config,
        repo_root,
        docs_root,
        AdapterLayers(adapter_metadata_files, adapter_output_dirs, adapter_excluded_docs),
        cli_exclude=exclude_dirs,
        cli_include=include_dirs,
    )


def _validate_docs_root(repo_root: Path, docs_root: Path) -> None:
    """Reject a **config-derived** ``docs_root`` that escapes the repository root.

    Scope, stated precisely because this function reads like a general guard and
    is not one: it only ever sees the root the CLI computed from
    ``(repo_root / config.docs_dir)``. A root resolved by an *adapter* —
    ``mkdocs.yml``'s own ``docs_dir``, a monorepo ``!include``, ``zensical.toml``,
    a prebuilt VSM route — never passes through here, so this raises nothing for
    any of them.

    That is not a gap, because it is not the boundary. The boundary is
    ``discovery.walk_files``/``iter_files_within``, which resolve every candidate
    path against the repository root on the way out; adapters report roots and
    never construct an exclusion manager, so they cannot move it. See the Single
    Traversal Primitive invariant, and
    ``tests/test_adapter_roots_cannot_escape_the_repo.py``, which probes all five
    adapter vectors with a live credential and a positive control.

    What this function adds is an *early, legible* failure for the one case a
    user can fix by editing their own ``.zenzic.toml``: raising
    :class:`typer.Exit` with code 3 beats letting discovery silently yield
    nothing and reporting an empty corpus.
    """
    resolved_repo = repo_root.resolve()
    resolved_docs = docs_root.resolve()
    try:
        resolved_docs.relative_to(resolved_repo)
    except ValueError:
        console.print(
            f"[bold {ZenzicPalette.FATAL}]PATH TRAVERSAL:[/] docs_dir resolves to "
            f"[bold]{resolved_docs}[/] which is outside the repository root "
            f"[bold]{resolved_repo}[/]. Path traversal blocked."
        )
        raise typer.Exit(3) from None


# ── Telemetry counter ─────────────────────────────────────────────────────────


def _count_docs_assets(
    docs_root: Path,
    repo_root: Path,
    exclusion_mgr: LayeredExclusionManager,
    config: ZenzicConfig | None = None,
) -> tuple[int, int, int]:
    """Return ``(pages_count, config_count, assets_count)`` for the telemetry line.

    Split three ways rather than two because the second figure is not what a
    reader assumes. This previously returned a single ``docs_count`` that summed
    Markdown pages *and* configuration files (``.yml``/``.yaml``/``.toml`` under
    the docs root, plus root-level ``.yml``/``.yaml``), which put it in direct
    conflict with the parsing progress line a few rows above it: the same run
    would report "Parsing 263 files" and "268 docs" and explain neither. Pages
    and config are now counted separately so each label means exactly one thing.

    ``pages_count`` covers ``.md``/``.mdx`` — the documents actually fed through
    the analysis pipeline, matching what the parsing line counts. When *config*
    is provided and the adapter exposes ``get_locale_source_roots()``, locale
    translation trees (e.g. MkDocs or Zensical ``docs-it/``) count as pages too.
    ``config_count`` covers the engine/config files discovered alongside them.
    """
    from zenzic.core.discovery import DOC_SUFFIXES, walk_files
    from zenzic.models.config import SYSTEM_EXCLUDED_DIRS

    _INERT = {".css", ".js"}
    _CONFIG = {".yml", ".yaml", ".toml"}
    _DOC_EXT = DOC_SUFFIXES
    if not docs_root.is_dir():
        return 0, 0, 0
    pages_count = sum(
        1
        for p in walk_files(docs_root, SYSTEM_EXCLUDED_DIRS, exclusion_mgr)
        if p.suffix.lower() in _DOC_EXT
    )
    config_count = sum(
        1
        for p in walk_files(docs_root, SYSTEM_EXCLUDED_DIRS, exclusion_mgr)
        if p.suffix.lower() in _CONFIG
    )
    config_count += sum(
        1 for p in repo_root.iterdir() if p.is_file() and p.suffix.lower() in {".yml", ".yaml"}
    )
    assets_count = sum(
        1
        for p in walk_files(docs_root, SYSTEM_EXCLUDED_DIRS, exclusion_mgr)
        if p.suffix.lower() not in _INERT
        and p.suffix.lower() not in _CONFIG
        and p.suffix.lower() not in _DOC_EXT
    )
    if config is not None:
        from zenzic.core.adapters import get_adapter

        adapter = get_adapter(config.build_context, docs_root, repo_root)
        for locale_root, _ in adapter.get_locale_source_roots(repo_root):
            pages_count += sum(
                1
                for p in walk_files(locale_root, SYSTEM_EXCLUDED_DIRS, exclusion_mgr)
                if p.suffix.lower() in _DOC_EXT
            )
    return pages_count, config_count, assets_count
