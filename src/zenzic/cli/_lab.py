# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""``zenzic lab`` — interactive showcase of bundled documentation examples.

Each scenario runs a fresh check against one of the bundled Z-code gallery
projects using Zenzic's internal Python APIs (zero subprocess).  Examples are
resolved from the installed wheel via :func:`importlib.resources.files`, or
from the repository checkout when running in editable mode.
"""

from __future__ import annotations

import importlib.resources as _ilr
import time
from dataclasses import dataclass
from pathlib import Path

import typer
from rich import box
from rich.console import Group
from rich.table import Table
from rich.text import Text

from zenzic import __version__
from zenzic.cli._check import (
    _collect_all_results,
    _to_findings,
)
from zenzic.cli._shared import (
    _count_docs_assets,
    get_console,
    get_ui,
)
from zenzic.cli._target_resolver import _apply_target
from zenzic.core.exclusion import LayeredExclusionManager
from zenzic.core.reporter import Finding, ZenzicReporter
from zenzic.core.ui import ZenzicPalette, emoji
from zenzic.models.config import ZenzicConfig


# ── Path resolution ──────────────────────────────────────────────────────────


def _examples_root() -> Path:
    """Locate the bundled examples directory.

    Resolution order:

    1. **Installed wheel** — ``zenzic/examples/`` inside the package tree, as
       populated by the ``force-include`` hatchling directive.
    2. **Editable / source checkout** — four directories above ``_lab.py``
       (``<repo>/examples/``).

    Raises :exc:`FileNotFoundError` when neither location resolves to a
    directory.
    """
    pkg_root = Path(str(_ilr.files("zenzic")))
    installed = pkg_root / "examples"
    if installed.is_dir():
        return installed
    # _lab.py is at src/zenzic/cli/_lab.py; the repo root is four levels above.
    dev = Path(__file__).resolve().parent.parent.parent.parent / "examples"
    if dev.is_dir():
        return dev
    raise FileNotFoundError(
        "Cannot locate examples/ — reinstall zenzic or run from the repository root."
    )


# ── Scenario definitions ─────────────────────────────────────────────────────


@dataclass(frozen=True)
class _Act:
    code: str
    title: str
    description: str
    example_dir: str
    expected_pass: bool
    expected_breach: bool = False
    show_info: bool = False
    docs_root_override: str | None = None
    single_file: str | None = None


_GALLERY: dict[str, _Act] = {
    "z001": _Act(
        code="z001",
        title="Config Structure",
        description="Z001 CORE_CONFIG_STRUCTURE — invalid configuration structure; ZenzicConfigError before analysis",
        example_dir="z001-config-error",
        expected_pass=False,
    ),
    "z110": _Act(
        code="z110",
        title="Config Syntax Error",
        description="Z110 CONFIG_SYNTAX_ERROR — malformed TOML syntax in .zenzic.toml; exit 1",
        example_dir="z110-config-syntax-error",
        expected_pass=False,
    ),
    "z111": _Act(
        code="z111",
        title="Config Schema Error",
        description="Z111 CONFIG_SCHEMA_ERROR — invalid schema structure or type in .zenzic.toml; exit 1",
        example_dir="z111-config-schema-error",
        expected_pass=False,
    ),
    "z620": _Act(
        code="z620",
        title="Stale Global Suppression",
        description="Z620 STALE_GLOBAL_SUPPRESSION — unused directory_policies in .zenzic.toml; exit 0 (warning)",
        example_dir="z620-stale-global-suppression",
        expected_pass=True,
    ),
    "z101": _Act(
        code="z101",
        title="Link Integrity",
        description="Z101 LINK_BROKEN — file references that resolve to missing pages",
        example_dir="z101-broken-links",
        expected_pass=False,
    ),
    "z109": _Act(
        code="z109",
        title="External Link Broken",
        description="Z109 EXTERNAL_LINK_BROKEN — external URL references that resolve to missing pages",
        example_dir="z109-external-link-broken",
        expected_pass=False,
    ),
    "z201": _Act(
        code="z201",
        title="Credential Scanner",
        description="Z201 CREDENTIAL_SECRET — AWS key in docs; security_breach severity, exit 2",
        example_dir="z201-credentials",
        expected_pass=False,
        expected_breach=True,
    ),
    "z405": _Act(
        code="z405",
        title="Asset Integrity",
        description="Z405 UNREFERENCED_ASSET — image file exists on disk but is never linked",
        example_dir="z405-unused-assets",
        expected_pass=False,
    ),
    "z601": _Act(
        code="z601",
        title="Brand Obsolescence",
        description="Z601 BRAND_OBSOLESCENCE — deprecated release name detected in content",
        example_dir="z601-brand-obsolescence",
        expected_pass=False,
    ),
    "z102": _Act(
        code="z102",
        title="Anchor Integrity",
        description="Z102 ANCHOR_MISSING — fragment #anchor target not defined on the linked page",
        example_dir="z102-anchor-missing",
        expected_pass=False,
    ),
    "z103": _Act(
        code="z103",
        title="Orphan Link",
        description="Z103 ORPHAN_LINK — link target exists but is not reachable via site navigation (zensical engine)",
        example_dir="z103-orphan-link",
        expected_pass=False,
    ),
    "z105": _Act(
        code="z105",
        title="Absolute Path",
        description="Z105 ABSOLUTE_PATH — link uses a site-absolute path instead of a relative path",
        example_dir="z105-absolute-path",
        expected_pass=False,
    ),
    "z108": _Act(
        code="z108",
        title="Empty Link Text",
        description="Z108 EMPTY_LINK_TEXT — link label is empty or whitespace-only",
        example_dir="z108-empty-link-text",
        expected_pass=False,
    ),
    "z202": _Act(
        code="z202",
        title="Path Traversal",
        description="Z202 PATH_TRAVERSAL — link escapes the docs root boundary; non-suppressible, exit 1 (error)",
        example_dir="z202-path-traversal",
        expected_pass=False,
    ),
    "z204": _Act(
        code="z204",
        title="Policy Violation",
        description="Z204 FORBIDDEN_TERM — project-specific forbidden term; requires .zenzic.local.toml, exit 2",
        example_dir="z204-forbidden-term",
        expected_pass=False,
        expected_breach=True,
    ),
    "z301": _Act(
        code="z301",
        title="Dangling Reference",
        description="Z301 DANGLING_REF — reference-style link uses an undefined identifier",
        example_dir="z301-dangling-ref",
        expected_pass=False,
    ),
    "z302": _Act(
        code="z302",
        title="Dead Definition",
        description="Z302 DEAD_DEF — link definition declared but never referenced",
        example_dir="z302-dead-def",
        expected_pass=False,
    ),
    "z303": _Act(
        code="z303",
        title="Duplicate Definition",
        description="Z303 DUPLICATE_DEF — reference identifier defined more than once",
        example_dir="z303-duplicate-def",
        expected_pass=False,
    ),
    "z402": _Act(
        code="z402",
        title="Orphan Page",
        description="Z402 ORPHAN_PAGE — Markdown file not listed in site navigation (zensical engine)",
        example_dir="z402-orphan-page",
        expected_pass=False,
    ),
    "z403": _Act(
        code="z403",
        title="Missing Alt Text",
        description="Z403 MISSING_ALT — image element has no alt text",
        example_dir="z403-missing-alt",
        expected_pass=False,
    ),
    "z501": _Act(
        code="z501",
        title="Placeholder Content",
        description="Z501 PLACEHOLDER — page contains stub or TODO content patterns",
        example_dir="z501-placeholder",
        expected_pass=False,
    ),
    "z502": _Act(
        code="z502",
        title="Short Content",
        description="Z502 SHORT_CONTENT — page word count below minimum threshold (default 50 words)",
        example_dir="z502-short-content",
        expected_pass=False,
    ),
    "z503": _Act(
        code="z503",
        title="Snippet Error",
        description="Z503 SNIPPET_ERROR — fenced Python code block contains a syntax error",
        example_dir="z503-snippet-error",
        expected_pass=False,
    ),
    "z505": _Act(
        code="z505",
        title="Untagged Code Block",
        description="Z505 UNTAGGED_CODE_BLOCK — fenced code block has no language specifier",
        example_dir="z505-untagged-code-block",
        expected_pass=False,
    ),
    "z510": _Act(
        code="z510",
        title="Heading Hierarchy Violation",
        description="Z510 HEADING_HIERARCHY — heading level skipped (e.g., H3 follows H1)",
        example_dir="z510-heading-hierarchy",
        expected_pass=False,
    ),
    "z511": _Act(
        code="z511",
        title="Excessive Sentence Length",
        description="Z511 EXCESSIVE_SENTENCE_LENGTH — sentence word count exceeds maximum limit",
        example_dir="z511-excessive-sentence-length",
        expected_pass=False,
    ),
    "z512": _Act(
        code="z512",
        title="Empty Section",
        description="Z512 EMPTY_SECTION — heading section contains no body content before next heading or EOF",
        example_dir="z512-empty-section",
        expected_pass=False,
    ),
    "z104": _Act(
        code="z104",
        title="File Not Found",
        description="Z104 FILE_NOT_FOUND — link target file missing from the filesystem; penalty 8.0, exit 1",
        example_dir="z104-file-not-found",
        expected_pass=False,
    ),
    "z107": _Act(
        code="z107",
        title="Circular Anchor",
        description="Z107 CIRCULAR_ANCHOR — self-referential anchor whose text slugifies to its own fragment",
        example_dir="z107-circular-anchor",
        expected_pass=False,
    ),
    "z401": _Act(
        code="z401",
        title="Missing Directory Index",
        description="Z401 MISSING_DIRECTORY_INDEX — directory has docs but no index page; directory URL returns 404",
        example_dir="z401-missing-directory-index",
        expected_pass=True,
        show_info=True,
    ),
    "z404": _Act(
        code="z404",
        title="Config Asset Missing",
        description="Z404 CONFIG_ASSET_MISSING — asset declared in mkdocs.yml theme not found on disk",
        example_dir="z404-config-asset-missing",
        expected_pass=False,
    ),
    "z406": _Act(
        code="z406",
        title="Nav Contract",
        description="Z406 NAV_CONTRACT — extra.alternate link absent from Virtual Site Map; exit 1",
        example_dir="z406-nav-contract",
        expected_pass=False,
    ),
    "z120": _Act(
        code="z120",
        title="Unknown HTML Attribute",
        description="Z120 UNKNOWN_HTML_ATTRIBUTE — raw HTML contains unauthorized attributes",
        example_dir="z120-unknown-html-attr",
        expected_pass=False,
    ),
    "z121": _Act(
        code="z121",
        title="Missing or Empty Href",
        description="Z121 MISSING_OR_EMPTY_HREF — anchor tag without a valid href",
        example_dir="z121-missing-href",
        expected_pass=False,
    ),
    "z122": _Act(
        code="z122",
        title="Jump Link Detected",
        description="Z122 JUMP_LINK_DETECTED — javascript jump link detected",
        example_dir="z122-jump-link",
        expected_pass=False,
    ),
    "z123": _Act(
        code="z123",
        title="Non-HTTP Scheme",
        description="Z123 NON_HTTP_SCHEME — link uses non-standard protocol (e.g. mailto)",
        example_dir="z123-non-http-scheme",
        expected_pass=True,
        show_info=True,
    ),
    "z124": _Act(
        code="z124",
        title="Opaque HTML Context",
        description="Z124 OPAQUE_HTML_CONTEXT — unparseable HTML block",
        example_dir="z124-opaque-context",
        expected_pass=False,
    ),
    "z205": _Act(
        code="z205",
        title="Forbidden Scheme",
        description="Z205 FORBIDDEN_SCHEME — link uses forbidden protocol (e.g. javascript:)",
        example_dir="z205-forbidden-scheme",
        expected_pass=False,
        expected_breach=True,
    ),
    "z603": _Act(
        code="z603",
        title="Dead Suppression",
        description="Z603 DEAD_SUPPRESSION — inline zenzic:ignore matches no findings",
        example_dir="z603-dead-suppression",
        expected_pass=False,
    ),
    "z610": _Act(
        code="z610",
        title="Required Frontmatter",
        description="Z610 REQUIRED_FRONTMATTER_MISSING — required frontmatter key absent from document",
        example_dir="z610-required-frontmatter",
        expected_pass=False,
    ),
    "z611": _Act(
        code="z611",
        title="Forbidden External Domain",
        description="Z611 FORBIDDEN_DOMAIN_REFERENCE — link references forbidden external domain",
        example_dir="z611-forbidden-domain",
        expected_pass=False,
    ),
    "z612": _Act(
        code="z612",
        title="Forbidden Frontmatter Key",
        description="Z612 FORBIDDEN_FRONTMATTER_KEY — forbidden key present in YAML frontmatter block",
        example_dir="z612-forbidden-frontmatter-key",
        expected_pass=False,
    ),
    "z613": _Act(
        code="z613",
        title="Frontmatter Schema Mismatch",
        description="Z613 FRONTMATTER_SCHEMA_MISMATCH — frontmatter key value fails required RE2 pattern",
        example_dir="z613-frontmatter-schema-mismatch",
        expected_pass=False,
    ),
    "z410": _Act(
        code="z410",
        title="Unreachable Graph Node",
        description="Z410 UNREACHABLE_GRAPH_NODE — Document is isolated and unreachable from navigation entry points",
        example_dir="z410-unreachable-graph-node",
        expected_pass=False,
    ),
    "z411": _Act(
        code="z411",
        title="Dead End Node",
        description="Z411 DEAD_END_NODE — Document has no outgoing links and forms a structural dead end",
        example_dir="z411-dead-end-node",
        expected_pass=False,
    ),
}

_VALID_CODES: frozenset[str] = frozenset(_GALLERY)


# ── Input parser ─────────────────────────────────────────────────────────────


def parse_scenario_keys(raw: str) -> list[str]:
    """Parse a Z-code input into an ordered list of valid scenario keys.

    Accepted formats:

    - ``"z101"``   -> ``["z101"]``
    - ``"all"``    -> all codes in definition order

    Raises :exc:`ValueError` for unknown codes.
    """
    raw = raw.strip().lower()
    if raw == "all":
        return list(_GALLERY)
    if raw not in _VALID_CODES:
        valid = ", ".join(sorted(_VALID_CODES))
        raise ValueError(
            f"Unknown Z-code '{raw}'. Valid codes: {valid}. Use 'all' to run the full gallery."
        )
    return [raw]


# ── Scenario runner ──────────────────────────────────────────────────────────


@dataclass
class _ActResult:
    act: _Act
    errors: int
    warnings: int
    has_breach: bool
    elapsed: float
    engine: str
    docs_count: int = 0
    assets_count: int = 0

    @property
    def total_files(self) -> int:
        return self.docs_count + self.assets_count

    @property
    def throughput(self) -> float:
        """Files per second -- 0.0 when elapsed is zero."""
        return self.total_files / self.elapsed if self.elapsed > 0 else 0.0

    @property
    def met_expectation(self) -> bool:
        if self.act.expected_breach:
            return self.has_breach
        if self.act.expected_pass:
            return self.errors == 0
        return self.errors > 0 or self.warnings > 0


def _run_act(act: _Act, examples_root: Path) -> _ActResult:
    """Run all checks for *act* against its example directory."""
    example_dir = examples_root / act.example_dir
    from zenzic.core.exceptions import ConfigurationError

    t0 = time.monotonic()
    try:
        config, _ = ZenzicConfig.load(example_dir)
    except ConfigurationError as exc:
        elapsed = time.monotonic() - t0
        get_console().print(f"[bold red]Error:[/] Configuration validation failed.\n{exc}")
        return _ActResult(
            act=act,
            errors=1,
            warnings=0,
            has_breach=False,
            elapsed=elapsed,
            engine="standalone",
            docs_count=0,
            assets_count=0,
        )

    single_file: Path | None = None
    target_hint: str | None = None

    if act.single_file is not None:
        config, single_file, _, target_hint = _apply_target(example_dir, config, act.single_file)
    elif act.docs_root_override is not None:
        config, _, _, target_hint = _apply_target(example_dir, config, act.docs_root_override)

    docs_root = (example_dir / config.docs_dir).resolve()
    exclusion_mgr = LayeredExclusionManager(config, repo_root=example_dir, docs_root=docs_root)

    t0 = time.monotonic()
    results = _collect_all_results(
        example_dir, docs_root, config, exclusion_mgr, strict=(act.code == "z109")
    )
    elapsed = time.monotonic() - t0

    findings: list[Finding] = _to_findings(results, docs_root, repo_root=example_dir, config=config)

    from zenzic.cli._check import _append_z620_findings
    from zenzic.cli._governance import _apply_directory_policies

    findings = _apply_directory_policies(findings, config)
    _append_z620_findings(findings, config, example_dir, check_all=True, check_external_urls=True)

    if single_file is not None:
        sf_rel = str(single_file.relative_to(example_dir))
        findings = [f for f in findings if f.rel_path == sf_rel]

    docs_count, assets_count = _count_docs_assets(docs_root, example_dir, exclusion_mgr, config)
    if single_file is not None:
        docs_count, assets_count = 1, 0

    reporter = ZenzicReporter(get_console(), docs_root, docs_dir=str(config.docs_dir))
    errors, warnings = reporter.render(
        findings,
        version=__version__,
        elapsed=elapsed,
        docs_count=docs_count,
        assets_count=assets_count,
        engine=config.build_context.engine,
        target=target_hint,
        show_info=act.show_info,
    )

    has_breach = any(f.severity == "security_breach" for f in findings)
    return _ActResult(
        act=act,
        errors=errors,
        warnings=warnings,
        has_breach=has_breach,
        elapsed=elapsed,
        engine=config.build_context.engine,
        docs_count=docs_count,
        assets_count=assets_count,
    )


# ── Output helpers ────────────────────────────────────────────────────────────


def _status_cell(r: _ActResult) -> str:
    if r.act.expected_breach:
        if r.has_breach:
            return "[bold red]BREACH[/] [green]✓[/]"
        return "[yellow]BREACH expected -- not triggered[/] [red]✗[/]"
    if r.act.expected_pass:
        if r.errors == 0:
            return "[bold green]PASS[/] [green]✓[/]"
        return "[bold red]FAIL (unexpected)[/] [red]✗[/]"
    if r.errors > 0 or r.warnings > 0:
        return "[yellow]EXPECTED FAIL[/] [green]✓[/]"
    return "[yellow]EXPECTED FAIL -- nothing found[/] [red]✗[/]"


def _print_summary(results: list[_ActResult]) -> None:
    table = Table(
        title=f"\n[bold {ZenzicPalette.BRAND}]⬡  ZENZIC LAB — Full Run Summary[/]",
        box=box.ROUNDED,
        show_header=True,
        header_style=ZenzicPalette.STYLE_BRAND,
    )
    table.add_column("Code", justify="center", style=ZenzicPalette.STYLE_BRAND, width=6)
    table.add_column("Title", style="bold", min_width=22)
    table.add_column("Engine", style="cyan", min_width=10)
    table.add_column("Files", justify="right", style=ZenzicPalette.DIM, min_width=7)
    table.add_column("files/s", justify="right", style=ZenzicPalette.DIM, min_width=8)
    table.add_column("Result", min_width=26)
    table.add_column("Time", justify="right", style=ZenzicPalette.DIM, min_width=7)

    unexpected = sum(1 for r in results if not r.met_expectation)
    total_files = sum(r.total_files for r in results)
    total_elapsed = sum(r.elapsed for r in results)
    for r in results:
        table.add_row(
            r.act.code.upper(),
            r.act.title,
            r.engine,
            str(r.total_files),
            f"{r.throughput:.0f}",
            _status_cell(r),
            f"{r.elapsed:.2f}s",
        )

    con = get_console()
    con.print(table)

    avg_throughput = total_files / total_elapsed if total_elapsed > 0 else 0.0
    seal_items = [
        Text.from_markup(
            f"[{ZenzicPalette.DIM}]{total_files} files scanned across {len(results)} scenarios"
            f" {emoji('dot')} {total_elapsed:.2f}s total"
            f" {emoji('dot')} {avg_throughput:.0f} files/s[/]"
        ),
        Text(),
    ]
    if unexpected == 0:
        seal_items.append(
            Text.from_markup(
                f"[bold {ZenzicPalette.SUCCESS}]{emoji('check')} All {len(results)} scenario(s) met expectations."
                " Zenzic: the audit surface is clean.[/]"
            )
        )
    else:
        seal_items.append(
            Text.from_markup(
                f"[bold {ZenzicPalette.ERROR}]{emoji('cross')} {unexpected}/{len(results)} scenario(s)"
                " did not meet expectations.[/]"
            )
        )

    con.print()
    con.print(
        Group(
            Text.from_markup(f"[bold {ZenzicPalette.BRAND}]{emoji('check')} LAB COMPLETE[/]"),
            Text(),
            *seal_items,
        ),
    )


def _print_act_seal(r: _ActResult) -> None:
    """Render a results footer after a single-scenario run."""
    files_line = (
        f"{r.total_files} file{'s' if r.total_files != 1 else ''} scanned"
        f" {emoji('dot')} {r.elapsed:.2f}s"
        + (f" {emoji('dot')} {r.throughput:.0f} files/s" if r.total_files else "")
    )
    seal_items: list[Text] = [
        Text.from_markup(f"[{ZenzicPalette.DIM}]{files_line}[/]"),
        Text(),
    ]
    if r.met_expectation:
        verdict = f"{emoji('check')} {r.act.code.upper()} — {r.act.title} — expectation met."
        seal_items.append(Text.from_markup(f"[bold {ZenzicPalette.SUCCESS}]{verdict}[/]"))
    else:
        verdict = f"{emoji('cross')} {r.act.code.upper()} — {r.act.title} — expectation NOT met."
        seal_items.append(Text.from_markup(f"[bold {ZenzicPalette.ERROR}]{verdict}[/]"))

    con = get_console()
    con.print()
    con.print(
        Group(
            Text.from_markup(f"[bold {ZenzicPalette.BRAND}]{emoji('check')} LAB RESULT[/]"),
            Text(),
            *seal_items,
        ),
    )


def _print_gallery_index() -> None:
    con = get_console()
    con.print(
        Text.from_markup(
            f"[bold {ZenzicPalette.BRAND}]⧡  ZENZIC LAB[/]  [{ZenzicPalette.DIM}]v{__version__}[/]"
        )
    )
    table = Table(box=box.ROUNDED, show_header=True, header_style="bold cyan")
    table.add_column("Z-Code", justify="center", style="bold cyan", width=7)
    table.add_column("Title", style="bold", min_width=22)
    table.add_column("Description", style=ZenzicPalette.WARNING)
    table.add_column("Expects", justify="center", min_width=8)
    for act in sorted(_GALLERY.values(), key=lambda a: a.code):
        expects = "[red]BREACH[/]" if act.expected_breach else "[yellow]FAIL[/]"
        table.add_row(act.code.upper(), act.title, act.description, expects)
    con.print(table)
    con.print(
        f"\n  [{ZenzicPalette.DIM}]zenzic lab <code>   eg. [bold cyan]zenzic lab z101[/]"
        f"   {emoji('dot')}   [bold cyan]zenzic lab all[/] -- full gallery[/]\n"
    )


# ── CLI command ───────────────────────────────────────────────────────────────


def lab(
    code: str | None = typer.Argument(
        None,
        help="Z-code to run (e.g. z101, z201) or 'all'. Omit to display the gallery menu.",
        show_default=False,
    ),
    list_acts: bool = typer.Option(
        False,
        "--list",
        "-l",
        help="Print the gallery index without running checks.",
    ),
) -> None:
    """Zenzic Lab — interactive showcase of bundled documentation examples.

    Run without arguments to display the gallery menu.  Pass a Z-code or
    'all' to execute the corresponding scenario:

        [bold cyan]zenzic lab[/]        -- show gallery menu
        [bold cyan]zenzic lab z101[/]   -- run the Z101 LINK_BROKEN scenario
        [bold cyan]zenzic lab z201[/]   -- run the Z201 CREDENTIAL_SECRET scenario
        [bold cyan]zenzic lab all[/]    -- run all gallery scenarios
        [bold cyan]zenzic lab --list[/] -- print gallery index without running
    """
    con = get_console()
    con.print()
    get_ui().print_header(__version__)

    if list_acts:
        _print_gallery_index()
        return

    if code is None:
        _print_gallery_index()
        con.print(
            "\n[bold]Welcome to the Zenzic Lab.[/] Choose a Z-code scenario to see Zenzic in action.\n"
            "  Run [bold cyan]zenzic lab z101[/] to execute the link integrity scenario.\n"
            "  Run [bold cyan]zenzic lab all[/] for the full gallery tour.\n"
        )
        return

    try:
        keys = parse_scenario_keys(code)
    except ValueError as exc:
        get_ui().print_exception_alert(str(exc), title="Lab -- Invalid Z-Code")
        raise typer.Exit(1) from exc

    try:
        examples_root = _examples_root()
    except FileNotFoundError as exc:
        con.print(f"[bold red]ERROR:[/] {exc}")
        raise typer.Exit(1) from exc

    scenarios_to_run = [_GALLERY[k] for k in keys]

    if len(scenarios_to_run) > 1:
        con.print(
            Text.from_markup(
                f"\n  [bold {ZenzicPalette.BRAND}]LAB SEQUENCE:[/]"
                f"  Running {len(scenarios_to_run)} gallery scenarios ...\n"
            )
        )

    act_results: list[_ActResult] = []
    for act in scenarios_to_run:
        con.print()
        con.print(
            Group(
                Text.from_markup(
                    f"[bold {ZenzicPalette.BRAND}]{act.code.upper()} -- {act.title}[/]"
                ),
                Text(),
                Text.from_markup(f"[bold]{act.description}[/]"),
            )
        )
        result = _run_act(act, examples_root)
        act_results.append(result)

    if len(act_results) == 1:
        _print_act_seal(act_results[0])
    elif len(act_results) > 1:
        _print_summary(act_results)
