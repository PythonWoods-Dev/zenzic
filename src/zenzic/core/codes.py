# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""Zenzic Finding Code Registry.

Every finding Zenzic emits carries a stable machine-readable code of the form
``Zxxx``.  This module is the single source of truth for code assignments.

Schema
------
Z0xx — Configuration Guard
    Z001  CORE_CONFIG_STRUCTURE — invalid configuration structure; ZenzicConfigError before analysis

Z1xx — Link Integrity
    Z101  LINK_BROKEN          — target file not found in the Virtual Site Map
    Z102  ANCHOR_MISSING       — fragment target (#anchor) not defined on the page
    Z103  ORPHAN_LINK          — link target exists but is not in the nav (ORPHAN_BUT_EXISTING)
    Z104  FILE_NOT_FOUND       — link target file missing from the filesystem
    Z105  ABSOLUTE_PATH        — link uses an absolute path (not portable)
    Z106  CIRCULAR_LINK        — link is part of a circular reference cycle (info)
    Z107  CIRCULAR_ANCHOR      — anchor link whose text slugifies to its own fragment
    Z108  EMPTY_LINK_TEXT      — link label is empty or whitespace-only
    Z109  EXTERNAL_LINK_BROKEN — external URL returned an HTTP error or could not be reached
    Z110  CONFIG_SYNTAX_ERROR  — malformed TOML syntax in configuration file; ConfigurationError before analysis
    Z111  CONFIG_SCHEMA_ERROR  — invalid schema structure or type in configuration file; ZenzicConfigError before analysis
    Z112  STALE_ALLOWLIST_ENTRY — stale absolute path allowlist entry declared in .zenzic.toml
    Z120  UNKNOWN_HTML_ATTRIBUTE — HTML attribute not in Safe-Core list (Polyglot Extractor — v0.17.0)
    Z121  MISSING_OR_EMPTY_HREF  — <a>/<img> tag has no href/src, or it is empty
    Z122  JUMP_LINK_DETECTED     — href="#" detected (placeholder or opaque JS anchor)
    Z123  NON_HTTP_SCHEME        — non-HTTP scheme (mailto:, tel:, ftp:) — informational, not resolved
    Z124  OPAQUE_HTML_CONTEXT    — blacklisted attribute detected (event-handler or shadow-routing)

Z2xx — Security (Credential Scanner + Polyglot Security Gate)
    Z201  CREDENTIAL_SECRET    — credential / secret detected (Exit 2)
    Z202  PATH_TRAVERSAL       — path escapes the docs root boundary
    Z203  PATH_TRAVERSAL_FATAL — traversal targeting OS system directories (Exit 3)
    Z204  FORBIDDEN_TERM       — project-specific forbidden term in documentation content (Exit 2)
    Z205  FORBIDDEN_SCHEME     — forbidden href scheme (javascript:, data:) — XSS vector; Exit 2; non-suppressible

Z3xx — Reference Integrity
    Z301  DANGLING_REF         — reference link uses an undefined ID
    Z302  DEAD_DEF             — reference definition never used by any link
    Z303  DUPLICATE_DEF        — reference ID defined more than once

Z4xx — Navigation & Structure
    Z401  MISSING_DIRECTORY_INDEX — directory lacks an index page (Standalone Mode)
    Z402  ORPHAN_PAGE          — Markdown file not listed in the site navigation
    Z403  MISSING_ALT          — image element has no alt text
    Z404  CONFIG_ASSET_MISSING — infrastructure asset referenced in engine config not found on disk
    Z405  UNUSED_ASSET         — asset file not referenced by any documentation page
    Z406  NAV_CONTRACT         — navigation contract violation
    Z410  UNREACHABLE_GRAPH_NODE — document is isolated and unreachable from navigation entry points
    Z411  DEAD_END_NODE        — document has no outgoing links and forms a structural dead end
    Z412  TRACEABILITY_BROKEN  — target document has no inbound links from required source namespaces (opt-in)

Z5xx — Content Quality & Specification-Driven Development (SDD)
    Z501  PLACEHOLDER          — page contains stub / TODO content
    Z502  SHORT_CONTENT        — page word count below minimum threshold
    Z503  SNIPPET_ERROR        — fenced code block fails syntax validation
    Z504  QUALITY_REGRESSION   — quality scorer detected score drop vs saved baseline
    Z505  UNTAGGED_CODE_BLOCK  — fenced code block has no language specifier
    Z506  MALFORMED_FRONTMATTER — frontmatter opening delimiter is malformed (e.g., '--' instead of '---')
    Z510  HEADING_HIERARCHY    — heading hierarchy level skipped
    Z511  EXCESSIVE_SENTENCE_LENGTH — sentence length exceeds readability limit
    Z512  EMPTY_SECTION        — heading section contains no body content
    Z513  DUPLICATE_HEADING    — duplicate heading within the same document
    Z514  GENERIC_IMAGE_ALT_TEXT — generic alt text detected in image tag
    Z515  BARE_URL_USED        — bare URL in prose without link syntax
    Z516  MULTIPLE_H1_HEADINGS — multiple H1 headings in single document (error)
    Z517  HEADING_PUNCTUATION  — heading ends with invalid trailing punctuation
    Z518  PASSIVE_VOICE_DETECTED — passive voice construction detected (opt-in)
    Z519  WEASEL_WORDS          — weasel word detected in technical prose (opt-in)
    Z520  MALFORMED_LIST_DETECTED — fake list formatted with newlines and semicolons/commas without list markers
    Z521  REQUIRED_TABLE_COLUMN — Markdown table missing required column header (opt-in)
    Z522  TABLE_CELL_ENUM       — table cell value not in allowed enum list (opt-in)
    Z523  HEADING_ORDER_VIOLATION — headings appear out of configured sequential order (opt-in)

Z6xx — Governance (Policy-as-Code)
    Z601  BRAND_OBSOLESCENCE   — deprecated brand term found in documentation source
    Z603  DEAD_SUPPRESSION     — inline suppression exists on a line with no active finding
    Z610  REQUIRED_FRONTMATTER_MISSING — required frontmatter key absent from document (v0.28.0, opt-in)
    Z611  FORBIDDEN_DOMAIN_REFERENCE  — link references a domain forbidden by [policies] (v0.28.0, opt-in)
    Z612  FORBIDDEN_FRONTMATTER_KEY   — document contains forbidden frontmatter key (opt-in)
    Z613  FRONTMATTER_SCHEMA_MISMATCH — frontmatter value violates regex schema pattern (opt-in)
    Z614  UNAPPROVED_DOMAIN_REFERENCE — link references domain outside allowed whitelist (opt-in)
    Z615  FORBIDDEN_URL_SCHEME        — link uses forbidden URL scheme (opt-in)
    Z616  CROSS_NAMESPACE_LINK_FORBIDDEN — forbidden cross-namespace link detected (opt-in)
    Z617  FORBIDDEN_CONTENT_PATTERN   — content matches forbidden regex pattern (opt-in)
    Z618  REQUIRED_HEADING_PATTERN    — document lacks required heading pattern (opt-in)
    Z619  MAX_DOCUMENT_COMPLEXITY     — document complexity exceeds configured threshold (opt-in)
    Z620  STALE_GLOBAL_SUPPRESSION    — global configuration rule was never used during the scan

Z9xx — Engine / System
    Z901  RULE_ENGINE_ERROR    — plugin rule raised an unexpected exception
    Z902  RULE_TIMEOUT         — plugin rule exceeded the per-file time limit (ReDoS guard)
    Z906  NO_FILES_FOUND       — target directory contains no Markdown sources (audit skipped)
"""

from __future__ import annotations

from typing import Final, Literal, NamedTuple, cast


# ── Code Definition — Single Source of Truth ─────────────────────────────────


class CodeDefinition(NamedTuple):
    """Per-code scoring and CI gate metadata — Single Source of Truth (ADR-031).

    All three attributes are defined **once** here; ``scorer.py`` derives its
    penalty/category tables and ``_check.py`` derives finding severity from this
    structure.  No catch-all ``else 'error'`` logic is permitted elsewhere.

    Attributes:
        severity: SARIF ``defaultConfiguration.level`` — ``"error"``,
            ``"warning"``, or ``"note"``.
        penalty:  Points deducted from the category bucket per occurrence.
            ``0.0`` for codes that are informational or handled by a dedicated
            gate (Security Override, Governance Gate).
        category: DQS bucket — ``"structural"``, ``"navigation"``,
            ``"content"``, ``"brand"``, or ``None`` for codes outside the
            penalty table.
        status:   Lifecycle state — ``"active"`` (default) or ``"inactive"``
            for codes whose scanner logic has been deferred or removed.
            Inactive codes remain in the namespace for config compatibility
            but are never emitted by the engine.
    """

    severity: str
    penalty: float
    category: str | None
    status: str = "active"
    fixable: bool = False


# ── Exit Code Contract ────────────────────────────────────────────────────────


class ZenzicExitCode:
    """Centralised exit code constants for the Zenzic CLI.

    These values implement the Exit Code Contract:

    * ``SUCCESS`` (0) — all checks passed; documentation is clean.
    * ``QUALITY`` (1) — quality findings (broken links, orphans, …);
      suppressible by ``--exit-zero``.
    * ``CREDENTIAL_LEAK`` (2) — credential or forbidden-term/scheme detected
      (Z201, Z204, Z205); **never** suppressible.
    * ``PATH_TRAVERSAL_FATAL`` (3) — path traversal targeting an OS system
      directory (Z203 only); **never** suppressible. Z202 (ordinary
      docs-root-boundary traversal) is also non-suppressible but remains a
      plain ``QUALITY`` (1) finding — it is deliberately *not* escalated to
      Exit 3.

    Usage in CLI layer::

        from zenzic.core.codes import ZenzicExitCode
        raise typer.Exit(ZenzicExitCode.CREDENTIAL_LEAK)
    """

    SUCCESS: int = 0
    QUALITY: int = 1
    CREDENTIAL_LEAK: int = 2
    PATH_TRAVERSAL_FATAL: int = 3


# ── Stability Contract ────────────────────────────────────────────────────────

FROZEN_CODES: frozenset[str] = frozenset(
    {
        "Z110",  # CONFIG_SYNTAX_ERROR — malformed .zenzic.toml
        "Z111",  # CONFIG_SCHEMA_ERROR — invalid .zenzic.toml schema
        "Z201",
        "Z202",
        "Z203",
        "Z204",
        "Z205",  # FORBIDDEN_SCHEME — Polyglot Security Gate (v0.17.0)
        "Z405",
        "Z406",
        "Z601",
    }
)

NON_SUPPRESSIBLE_CODES: frozenset[str] = frozenset(
    {
        "Z110",  # CONFIG_SYNTAX_ERROR — malformed .zenzic.toml; non-suppressible
        "Z111",  # CONFIG_SCHEMA_ERROR — invalid .zenzic.toml schema; non-suppressible
        "Z201",
        "Z202",
        "Z203",
        "Z204",
        "Z205",  # FORBIDDEN_SCHEME — javascript:/data: XSS vector; non-suppressible (v0.17.0)
    }
)

# Graph-level and file-level findings that CANNOT be suppressed via inline comments
# (see ADR-093).  They must be governed in .zenzic.toml via directory_policies or per_file_ignores.
NON_INLINE_SUPPRESSIBLE_CODES: frozenset[str] = frozenset(
    {
        "Z401",  # MISSING_DIRECTORY_INDEX
        "Z402",  # ORPHAN_PAGE
        "Z404",  # CONFIG_ASSET_MISSING
        "Z405",  # UNUSED_ASSET
        "Z406",  # NAV_CONTRACT
        "Z410",  # UNREACHABLE_GRAPH_NODE
        "Z411",  # DEAD_END_NODE
        "Z412",  # TRACEABILITY_BROKEN
        "Z521",  # REQUIRED_TABLE_COLUMN -- anchors to the table header row; a same-line
        # inline comment corrupts GFM table-row parsing, silently hiding the
        # real violation (confirmed empirically, ADR-093 extension, v0.31.0)
        "Z522",  # TABLE_CELL_ENUM -- anchors to a data row, which empirically tolerates
        # a trailing inline comment (the finding still fires); included here for
        # consistency with its sibling table-policy codes (Z521/Z523), not because
        # it independently reproduces the same parsing-corruption failure
        "Z523",  # HEADING_ORDER_VIOLATION -- anchors to the heading line; a same-line
        # inline comment corrupts the heading-title regex match, silently hiding
        # the real violation (confirmed empirically, same failure class as Z521)
        "Z620",  # STALE_GLOBAL_SUPPRESSION
    }
)

PLUGIN_FORBIDDEN_EXITS: frozenset[int] = frozenset({2, 3})


# ── Code Definitions (SSoT) ───────────────────────────────────────────────────
# Every Zxxx code is defined ONCE here with its severity, DQS penalty, and
# scoring category.  scorer.py and _check.py derive their tables from this dict.
# Adding a new code requires a single entry here — nowhere else.

CODE_DEFINITIONS: dict[str, CodeDefinition] = {
    # ── Z0xx — Configuration Guard ──────────────────────────────────────────
    # Aborts config loading before any analysis; not in the DQS penalty table.
    "Z001": CodeDefinition("error", 0.0, None),  # CORE_CONFIG_STRUCTURE
    # ── Z1xx — Link Integrity & Configuration Validation ──────────────────────
    "Z101": CodeDefinition("error", 8.0, "structural"),  # LINK_BROKEN
    "Z102": CodeDefinition("error", 5.0, "structural"),  # ANCHOR_MISSING
    "Z103": CodeDefinition(
        "error", 2.0, "structural"
    ),  # ORPHAN_LINK      — ADR-031 paradox resolved
    "Z104": CodeDefinition("error", 8.0, "structural"),  # FILE_NOT_FOUND
    "Z105": CodeDefinition("error", 2.0, "structural"),  # ABSOLUTE_PATH
    "Z106": CodeDefinition("note", 0.0, None),  # CIRCULAR_LINK    — informational
    "Z107": CodeDefinition("error", 1.0, "structural"),  # CIRCULAR_ANCHOR
    "Z108": CodeDefinition("error", 1.0, "structural", fixable=True),  # EMPTY_LINK_TEXT
    "Z109": CodeDefinition("error", 3.0, "structural"),  # EXTERNAL_LINK_BROKEN
    "Z110": CodeDefinition("error", 0.0, None),  # CONFIG_SYNTAX_ERROR — malformed TOML
    "Z111": CodeDefinition("error", 0.0, None),  # CONFIG_SCHEMA_ERROR — invalid schema/type
    "Z112": CodeDefinition("warning", 1.0, "structural"),  # STALE_ALLOWLIST_ENTRY
    "Z620": CodeDefinition("warning", 1.0, "brand"),  # STALE_GLOBAL_SUPPRESSION
    # ── Z12x — HTML Integrity (Polyglot Extractor — v0.17.0) ──────────────────
    # Emitted by PolyglotExtractor for raw HTML <a>/<img> tags in Markdown.
    # Z120/Z122 are warnings; Z121/Z124 are errors (exit 1); Z123 is informational.
    # All Z12x codes are suppressible via data-zenzic-ignore (-1.0 pts DQS each).
    "Z120": CodeDefinition("warning", 1.0, "content"),  # UNKNOWN_HTML_ATTRIBUTE
    "Z121": CodeDefinition("error", 1.0, "structural"),  # MISSING_OR_EMPTY_HREF
    "Z122": CodeDefinition("warning", 1.0, "content"),  # JUMP_LINK_DETECTED
    "Z123": CodeDefinition("note", 0.0, None),  # NON_HTTP_SCHEME — informational
    "Z124": CodeDefinition("error", 1.0, "structural"),  # OPAQUE_HTML_CONTEXT
    # ── Z2xx — Security ───────────────────────────────────────────────────────
    # Score collapses to 0 via Security Override; never in DQS category bucket.
    # All five are non-suppressible (see NON_SUPPRESSIBLE_CODES). Exit codes are
    # NOT uniform across the range: Z201/Z204/Z205 -> Exit 2, Z203 -> Exit 3,
    # but Z202 deliberately stays at plain Exit 1 (see ZenzicExitCode's
    # docstring and tests/test_cli.py::test_z202_still_maps_to_plain_error).
    "Z201": CodeDefinition("error", 0.0, None),  # CREDENTIAL_SECRET
    "Z202": CodeDefinition("error", 0.0, None),  # PATH_TRAVERSAL
    "Z203": CodeDefinition("error", 0.0, None),  # PATH_TRAVERSAL_FATAL
    "Z204": CodeDefinition("error", 0.0, None),  # FORBIDDEN_TERM
    "Z205": CodeDefinition("error", 0.0, None),  # FORBIDDEN_SCHEME — javascript:/data: XSS gate
    # ── Z3xx — Reference Integrity ────────────────────────────────────────────
    "Z301": CodeDefinition("warning", 4.0, "navigation"),  # DANGLING_REF
    "Z302": CodeDefinition("warning", 1.0, "navigation"),  # DEAD_DEF
    "Z303": CodeDefinition("warning", 3.0, "navigation"),  # DUPLICATE_DEF
    # ── Z4xx — Structure ──────────────────────────────────────────────────────
    "Z401": CodeDefinition(
        "note", 0.0, "navigation"
    ),  # MISSING_DIRECTORY_INDEX — info only, no DQS penalty
    "Z402": CodeDefinition("warning", 4.0, "navigation"),  # ORPHAN_PAGE
    "Z403": CodeDefinition("warning", 1.0, "content"),  # MISSING_ALT
    "Z404": CodeDefinition("warning", 3.0, "brand"),  # CONFIG_ASSET_MISSING
    "Z405": CodeDefinition("warning", 3.0, "brand"),  # UNUSED_ASSET
    "Z406": CodeDefinition("warning", 2.0, "brand"),  # NAV_CONTRACT
    "Z410": CodeDefinition("warning", 5.0, "structural"),  # UNREACHABLE_GRAPH_NODE
    "Z411": CodeDefinition("warning", 5.0, "structural"),  # DEAD_END_NODE
    "Z412": CodeDefinition(
        "warning", 4.0, "navigation", fixable=False
    ),  # TRACEABILITY_BROKEN (v0.31.0) — graph topology, suppressed via directory_policies
    # ── Z5xx — Content Quality ────────────────────────────────────────────────
    "Z501": CodeDefinition("warning", 2.0, "content"),  # PLACEHOLDER
    "Z502": CodeDefinition("warning", 1.0, "content"),  # SHORT_CONTENT
    "Z503": CodeDefinition("warning", 10.0, "content"),  # SNIPPET_ERROR
    "Z504": CodeDefinition("warning", 0.0, None),  # QUALITY_REGRESSION — governance gate
    "Z505": CodeDefinition("warning", 1.0, "content", fixable=True),  # UNTAGGED_CODE_BLOCK
    "Z506": CodeDefinition("error", 5.0, "content"),  # MALFORMED_FRONTMATTER
    "Z510": CodeDefinition("warning", 1.0, "content"),  # HEADING_HIERARCHY
    "Z511": CodeDefinition("warning", 1.0, "content"),  # EXCESSIVE_SENTENCE_LENGTH
    "Z512": CodeDefinition("warning", 1.0, "content"),  # EMPTY_SECTION
    "Z513": CodeDefinition("warning", 2.0, "content"),  # DUPLICATE_HEADING
    "Z514": CodeDefinition("warning", 2.0, "content"),  # GENERIC_IMAGE_ALT_TEXT
    "Z515": CodeDefinition("warning", 1.0, "content", fixable=True),  # BARE_URL_USED
    "Z516": CodeDefinition("error", 5.0, "content"),  # MULTIPLE_H1_HEADINGS
    "Z517": CodeDefinition("warning", 1.0, "content", fixable=True),  # HEADING_PUNCTUATION
    "Z518": CodeDefinition("warning", 1.0, "content"),  # PASSIVE_VOICE_DETECTED (opt-in)
    "Z519": CodeDefinition("warning", 1.0, "content"),  # WEASEL_WORDS (opt-in)
    "Z520": CodeDefinition(
        "warning", 2.0, "content", fixable=True
    ),  # MALFORMED_LIST_DETECTED (v0.30.0)
    "Z521": CodeDefinition(
        "warning", 2.0, "content", fixable=False
    ),  # REQUIRED_TABLE_COLUMN (v0.31.0, opt-in) — non-fixable (requires semantic data)
    "Z522": CodeDefinition(
        "warning", 2.0, "content", fixable=False
    ),  # TABLE_CELL_ENUM (v0.31.0, opt-in) — non-fixable (requires human enum selection)
    "Z523": CodeDefinition(
        "warning", 2.0, "content", fixable=False
    ),  # HEADING_ORDER_VIOLATION (v0.31.0, opt-in) — non-fixable (requires section restructuring)
    # ── Z6xx — Governance ─────────────────────────────────────────────────────
    "Z601": CodeDefinition("warning", 2.0, "brand"),  # BRAND_OBSOLESCENCE (escalates exponentially)
    "Z603": CodeDefinition("warning", 1.0, "brand", fixable=True),  # DEAD_SUPPRESSION
    "Z610": CodeDefinition("warning", 3.0, "brand"),  # REQUIRED_FRONTMATTER_MISSING (v0.28.0)
    "Z611": CodeDefinition("warning", 3.0, "brand"),  # FORBIDDEN_DOMAIN_REFERENCE (v0.28.0)
    "Z612": CodeDefinition("warning", 3.0, "brand"),  # FORBIDDEN_FRONTMATTER_KEY (v0.29.0)
    "Z613": CodeDefinition("error", 5.0, "brand"),  # FRONTMATTER_SCHEMA_MISMATCH (v0.29.0)
    "Z614": CodeDefinition("error", 5.0, "brand"),  # UNAPPROVED_DOMAIN_REFERENCE (v0.29.0)
    "Z615": CodeDefinition("warning", 3.0, "brand"),  # FORBIDDEN_URL_SCHEME (v0.29.0)
    "Z616": CodeDefinition("error", 8.0, "brand"),  # CROSS_NAMESPACE_LINK_FORBIDDEN (v0.29.0)
    "Z617": CodeDefinition("warning", 2.0, "brand"),  # FORBIDDEN_CONTENT_PATTERN (v0.30.0)
    "Z618": CodeDefinition("warning", 3.0, "brand"),  # REQUIRED_HEADING_PATTERN (v0.30.0)
    "Z619": CodeDefinition("warning", 3.0, "brand"),  # MAX_DOCUMENT_COMPLEXITY (v0.30.0)
    # ── Z9xx — Engine / System ────────────────────────────────────────────────
    "Z901": CodeDefinition("error", 0.0, None),  # RULE_ENGINE_ERROR — HALT gate
    "Z902": CodeDefinition("warning", 0.0, None),  # RULE_TIMEOUT
    "Z906": CodeDefinition("note", 0.0, None),  # NO_FILES_FOUND
}


def code_severity(code: str) -> Literal["error", "warning", "info"]:
    """Return *code*'s ``CODE_DEFINITIONS`` severity, translated to the
    vocabulary Core finding objects accept: ``"error"``, ``"warning"``, or
    ``"info"`` (``CODE_DEFINITIONS`` itself stores the third state as
    ``"note"`` -- this is not a CLI-only display overlay, ``rules.py``'s own
    ``RuleFinding.severity`` is typed ``Literal["error", "warning", "info"]``
    and has never accepted ``"note"``).

    This is the Core-layer SSoT lookup for any subsystem that constructs a
    finding object and needs its severity (e.g. ``rules.py``'s
    ``RuleFinding``). The Z2xx security-breach/security-incident
    reclassification is a separate, CLI-layer-only concern -- see
    ``_check.py``'s ``_finding_severity()`` for that translation.

    Raises:
        KeyError: if *code* is not a registered code. Every call site here
            passes a hardcoded, known-valid code literal (e.g. ``"Z107"``),
            so an unknown code is a bug in the caller, not a runtime
            condition to silently default around.
    """
    severity = CODE_DEFINITIONS[code].severity
    if severity == "note":
        return "info"
    return cast(Literal["error", "warning"], severity)


#: Human-readable name for each code (for report headers).
CODE_NAMES: Final[dict[str, str]] = {
    "Z001": "CORE_CONFIG_STRUCTURE",
    "Z101": "LINK_BROKEN",
    "Z102": "ANCHOR_MISSING",
    "Z103": "ORPHAN_LINK",
    "Z104": "FILE_NOT_FOUND",
    "Z105": "ABSOLUTE_PATH",
    "Z106": "CIRCULAR_LINK",
    "Z107": "CIRCULAR_ANCHOR",
    "Z108": "EMPTY_LINK_TEXT",
    "Z109": "EXTERNAL_LINK_BROKEN",
    "Z110": "CONFIG_SYNTAX_ERROR",
    "Z111": "CONFIG_SCHEMA_ERROR",
    "Z112": "STALE_ALLOWLIST_ENTRY",
    "Z620": "STALE_GLOBAL_SUPPRESSION",
    "Z120": "UNKNOWN_HTML_ATTRIBUTE",
    "Z121": "MISSING_OR_EMPTY_HREF",
    "Z122": "JUMP_LINK_DETECTED",
    "Z123": "NON_HTTP_SCHEME",
    "Z124": "OPAQUE_HTML_CONTEXT",
    "Z201": "CREDENTIAL_SECRET",
    "Z202": "PATH_TRAVERSAL",
    "Z203": "PATH_TRAVERSAL_FATAL",
    "Z204": "FORBIDDEN_TERM",
    "Z205": "FORBIDDEN_SCHEME",
    "Z301": "DANGLING_REF",
    "Z302": "DEAD_DEF",
    "Z303": "DUPLICATE_DEF",
    "Z401": "MISSING_DIRECTORY_INDEX",
    "Z402": "ORPHAN_PAGE",
    "Z403": "MISSING_ALT",
    "Z404": "CONFIG_ASSET_MISSING",
    "Z405": "UNUSED_ASSET",
    "Z406": "NAV_CONTRACT",
    "Z410": "UNREACHABLE_GRAPH_NODE",
    "Z411": "DEAD_END_NODE",
    "Z412": "TRACEABILITY_BROKEN",
    "Z501": "PLACEHOLDER",
    "Z502": "SHORT_CONTENT",
    "Z503": "SNIPPET_ERROR",
    "Z504": "QUALITY_REGRESSION",
    "Z505": "UNTAGGED_CODE_BLOCK",
    "Z506": "MALFORMED_FRONTMATTER",
    "Z510": "HEADING_HIERARCHY",
    "Z511": "EXCESSIVE_SENTENCE_LENGTH",
    "Z512": "EMPTY_SECTION",
    "Z513": "DUPLICATE_HEADING",
    "Z514": "GENERIC_IMAGE_ALT_TEXT",
    "Z515": "BARE_URL_USED",
    "Z516": "MULTIPLE_H1_HEADINGS",
    "Z517": "HEADING_PUNCTUATION",
    "Z518": "PASSIVE_VOICE_DETECTED",
    "Z519": "WEASEL_WORDS",
    "Z520": "MALFORMED_LIST_DETECTED",
    "Z521": "REQUIRED_TABLE_COLUMN",
    "Z522": "TABLE_CELL_ENUM",
    "Z523": "HEADING_ORDER_VIOLATION",
    "Z601": "BRAND_OBSOLESCENCE",
    "Z603": "DEAD_SUPPRESSION",
    "Z610": "REQUIRED_FRONTMATTER_MISSING",
    "Z611": "FORBIDDEN_DOMAIN_REFERENCE",
    "Z612": "FORBIDDEN_FRONTMATTER_KEY",
    "Z613": "FRONTMATTER_SCHEMA_MISMATCH",
    "Z614": "UNAPPROVED_DOMAIN_REFERENCE",
    "Z615": "FORBIDDEN_URL_SCHEME",
    "Z616": "CROSS_NAMESPACE_LINK_FORBIDDEN",
    "Z617": "FORBIDDEN_CONTENT_PATTERN",
    "Z618": "REQUIRED_HEADING_PATTERN",
    "Z619": "MAX_DOCUMENT_COMPLEXITY",
    "Z901": "RULE_ENGINE_ERROR",
    "Z902": "RULE_TIMEOUT",
    "Z906": "NO_FILES_FOUND",
}

#: Short description of each code for SARIF ``shortDescription`` and human display.
#: Single source of truth — never duplicate these strings in other modules.
CODE_DESCRIPTIONS: dict[str, str] = {
    # Z0xx — Configuration Guard
    "Z001": "Invalid configuration structure — configuration guard raised before analysis begins",
    # Z1xx — Link Integrity
    "Z101": "Link target not found in the Virtual Site Map",
    "Z102": "Fragment anchor (#anchor) not defined on the target page",
    "Z103": "Link target exists but is not reachable via site navigation",
    "Z104": "Link target file missing from the filesystem",
    "Z105": "Absolute path detected — use a relative path for portability",
    "Z106": "Circular link chain detected between documentation pages",
    "Z107": "Self-referential anchor link — slug(text) resolves to the same fragment",
    "Z108": "Link label is empty or contains only whitespace",
    "Z109": "External URL returned an HTTP error or could not be reached",
    "Z110": "Malformed TOML syntax in configuration file (.zenzic.toml)",
    "Z111": "Invalid schema structure or type in configuration file (.zenzic.toml)",
    "Z112": "Stale absolute_path_allowlist entry declared in configuration but never matched by any scanned link",
    "Z620": "Global configuration rule was never used during the scan — remove the dead configuration",
    # Z12x — HTML Integrity (Polyglot Extractor — v0.17.0)
    "Z120": "HTML attribute not in Safe-Core list — declare intent or suppress with data-zenzic-ignore",
    "Z121": "Tag <a> or <img> has no href/src attribute, or it is empty",
    "Z122": 'href="#" detected — placeholder or opaque JS anchor; add destination or suppress with data-zenzic-ignore',
    "Z123": "Non-HTTP scheme (mailto:, tel:, ftp:) — informational; link not resolved by Zenzic",
    "Z124": "Opaque HTML context: blacklisted attribute detected (event-handler or shadow-routing attr)",
    # Z2xx — Security
    "Z201": "Potential credential or secret detected in documentation content",
    "Z202": "Link escapes the documentation root boundary (path traversal)",
    "Z203": "Path traversal targeting OS system directories — fatal security breach",
    "Z204": "Forbidden project term detected in documentation content",
    "Z205": "Forbidden href scheme detected (javascript: or data:) — potential XSS vector; non-suppressible security violation",
    # Z3xx — Reference Integrity
    "Z301": "Reference-style link uses an undefined identifier",
    "Z302": "Link definition declared but never referenced",
    "Z303": "Reference identifier defined more than once",
    # Z4xx — Structure
    "Z401": "Directory lacks a required index page",
    "Z402": "Markdown file not listed in the site navigation",
    "Z403": "Image element has no alt text",
    "Z404": "Asset referenced in engine config not found on disk",
    "Z405": "Asset file not referenced by any documentation page",
    "Z406": "Navigation contract violation detected",
    "Z410": "Document is isolated and unreachable from the navigation entry points",
    "Z411": "Document has no outgoing links and forms a structural dead end",
    "Z412": "Document lacks required inbound links from specified documentation namespaces (graph traceability broken)",
    # Z5xx — Content Quality
    "Z501": "Page contains placeholder or stub content",
    "Z502": "Page word count is below the minimum threshold",
    "Z503": "Fenced code block contains a syntax error",
    "Z504": "Documentation quality score regressed below the saved baseline",
    "Z505": "Fenced code block has no language specifier",
    "Z506": "Frontmatter boundary is malformed (e.g., opening delimiter is '--' instead of '---')",
    "Z510": "Heading hierarchy level skipped (e.g., H3 follows H1 without an intervening H2)",
    "Z511": "Sentence length exceeds the maximum readability limit",
    "Z512": "Heading section contains no body content before next heading or EOF (a heading that only groups deeper subheadings is exempt)",
    "Z513": "Duplicate heading found within the same document — ensure heading titles are unique",
    "Z514": "Generic image alt text detected (e.g., 'image', 'screenshot') — provide descriptive alt text for accessibility",
    "Z515": "Bare URL detected in prose — wrap in angle brackets '<url>' or Markdown link syntax '[text](url)'",
    "Z516": "Multiple H1 headings detected in document — ensure exactly one top-level title per page",
    "Z517": "Heading ends with invalid trailing punctuation (., :, ;) — remove trailing punctuation",
    "Z518": "Passive voice construction detected — consider using active voice for clearer technical writing",
    "Z519": "Weasel word detected in technical prose — use direct, assertive language instead",
    "Z520": "Malformed list detected in paragraph — convert to a standard Markdown list with '- ' for accessibility and semantic rendering",
    "Z521": "Table matching configured context lacks a required column header",
    "Z522": "Table cell contains a value outside the allowed enumeration whitelist for this column",
    "Z523": "Configured required headings appear out of expected sequential order in document flow",
    # Z6xx — Governance
    "Z601": "Deprecated brand term found in documentation source",
    "Z603": "Inline suppression directive does not suppress any active finding. Remove the dead comment.",
    "Z610": "Required frontmatter key is absent from this document",
    "Z611": "Link references an external domain forbidden by the [policies] configuration",
    "Z612": "Forbidden frontmatter key is present in YAML frontmatter block",
    "Z613": "Frontmatter key value does not match the required RE2 pattern declared in [policies].frontmatter_schema_match",
    "Z614": "Link references an external domain not listed in the Zero-Trust allowed_external_domains whitelist",
    "Z615": "Link uses a URL scheme not permitted by the required_url_schemes whitelist",
    "Z616": "Internal link crosses a forbidden topological namespace boundary",
    "Z617": "Prose content matches a forbidden RE2 regex pattern declared in [policies].forbidden_content_patterns",
    "Z618": "Document does not contain any heading matching the required RE2 pattern declared in [policies].required_heading_patterns",
    "Z619": "Document complexity score exceeds the maximum limit configured in [policies].max_document_complexity",
    # Z9xx — Engine / System
    "Z901": "Plugin rule raised an unexpected exception",
    "Z902": "Plugin rule exceeded the per-file time limit (ReDoS guard)",
    "Z906": "Target directory contains no Markdown sources — audit skipped",
}

#: Default SARIF ``defaultConfiguration.level`` for each code.
#: Derived from :data:`CODE_DEFINITIONS` — do not edit manually.
#: Individual Finding severity always takes precedence at result level.
CODE_SARIF_LEVELS: dict[str, str] = {code: defn.severity for code, defn in CODE_DEFINITIONS.items()}


def get_sarif_name(code: str) -> str:
    """Convert a Zxxx code to its SARIF-canonical CamelCase rule name.

    Derives the name deterministically from :data:`CODE_NAMES`:
    ``"LINK_BROKEN"`` → ``"LinkBroken"``.  Falls back to the raw code
    string for unknown codes so the SARIF remains valid even for
    dynamically emitted plugin codes.

    Args:
        code: A canonical Zxxx code string, e.g. ``"Z101"``.

    Returns:
        CamelCase rule name suitable for the SARIF ``rules[].name`` field.
    """
    name = CODE_NAMES.get(code, code)
    return "".join(word.capitalize() for word in name.split("_"))


# ── Core Scanner Registry ─────────────────────────────────────────────────────


class CoreScanner(NamedTuple):
    """Static descriptor for a built-in Zenzic scanner.

    These scanners are compiled into Zenzic itself — always active, not
    configurable or removable via the ``zenzic.rules`` entry-point group.
    """

    codes: str
    """Display code range, e.g. ``"Z201"`` or ``"Z202\u2013203"``."""

    name: str
    """Human-readable scanner name, e.g. ``"Credential Scanner"``."""

    capability: str
    """One-line capability summary shown in ``zenzic inspect capabilities``."""

    primary_exit: int
    """Primary exit code: 1 (quality), 2 (credential leak), or 3 (path traversal)."""

    non_suppressible: bool
    """``True`` when ``--exit-zero`` cannot override this scanner's exit."""


#: Built-in scanners — static, always active, single source of truth for
#: ``zenzic inspect capabilities`` and any future Arsenal introspection.
CORE_SCANNERS: list[CoreScanner] = [
    CoreScanner(
        codes="Z201",
        name="Credential Scanner",
        capability=(
            "Credential & secret detection \u2014 9 families "
            "(AWS, GitHub, GitLab PAT, Stripe, Slack, OpenAI, Google, PEM, hex)"
        ),
        primary_exit=2,
        non_suppressible=True,
    ),
    CoreScanner(
        codes="Z204",
        name="Privacy Gate",
        capability=(
            "Project-specific forbidden term detection \u2014 "
            "verbatim case-insensitive match against patterns in .zenzic.local.toml"
        ),
        primary_exit=2,
        non_suppressible=True,
    ),
    CoreScanner(
        codes="Z202",
        name="Path Traversal Guard",
        capability=(
            "Path-traversal boundary enforcement \u2014 rejects any link escaping the docs/ root"
        ),
        primary_exit=1,
        non_suppressible=True,
    ),
    CoreScanner(
        codes="Z203",
        name="Path Traversal Guard (fatal)",
        capability=(
            "Fatal path-traversal detection \u2014 traversal targeting an OS system "
            "directory (/etc/, /root/, ...)"
        ),
        primary_exit=3,
        non_suppressible=True,
    ),
    CoreScanner(
        codes="Z101–106, Z108–109",
        name="Link Validator",
        capability=(
            "Broken links, dead anchors, circular refs, "
            "absolute internal links, empty link text, external URL validation"
        ),
        primary_exit=1,
        non_suppressible=False,
    ),
    CoreScanner(
        codes="Z120–124, Z205",
        name="Polyglot Extractor",
        capability=(
            "HTML integrity analysis for <a> and <img> tags in Markdown source — "
            "Safe-Core classification, opaque-context detection (Z124), "
            "jump-link and missing-href checks, non-HTTP scheme info (Z123), "
            "forbidden-scheme XSS gate (Z205 — non-suppressible, Exit 2)"
        ),
        primary_exit=1,
        non_suppressible=False,
    ),
    CoreScanner(
        codes="Z301\u2013303",
        name="Reference Scanner",
        capability="Dangling reference IDs, dead link definitions, duplicate reference keys",
        primary_exit=1,
        non_suppressible=False,
    ),
    CoreScanner(
        codes="Z401\u2013404, Z410\u2013411",
        name="Structure Guard",
        capability=(
            "Directory-index integrity, orphan pages, missing alt text, config asset paths, topological orphans and dead ends"
        ),
        primary_exit=1,
        non_suppressible=False,
    ),
    CoreScanner(
        codes="Z501\u2013503, Z506",
        name="Content Guard",
        capability=(
            "Placeholder / stub text, overly short pages, syntax errors in code snippets, "
            "malformed frontmatter delimiters"
        ),
        primary_exit=1,
        non_suppressible=False,
    ),
    CoreScanner(
        codes="Z405",
        name="Asset Sentry",
        capability="Unused images and media files not referenced anywhere in the docs tree",
        primary_exit=1,
        non_suppressible=False,
    ),
    CoreScanner(
        codes="Z406",
        name="Nav Contract Enforcer",
        capability="Navigation contract violation — page presence against declared nav structure",
        primary_exit=1,
        non_suppressible=False,
    ),
    CoreScanner(
        codes="Z107",
        name="Circular Anchor Guard",
        capability=(
            "Self-referential anchor links \u2014 detects [text](#fragment) "
            "where slug(text) == fragment"
        ),
        primary_exit=1,
        non_suppressible=False,
    ),
    CoreScanner(
        codes="Z505",
        name="Code Block Scanner",
        capability="Fenced code blocks without a language specifier (``` or ~~~)",
        primary_exit=1,
        non_suppressible=False,
    ),
    CoreScanner(
        codes="Z601",
        name="Brand Integrity Guard",
        capability=(
            "Deprecated brand term detection \u2014 configurable via [governance], "
            "suppressed per-line with <!-- zenzic:ignore: Z601 --> (Markdown) or {/* zenzic:ignore: Z601 */} (MDX)"
        ),
        primary_exit=1,
        non_suppressible=False,
    ),
    CoreScanner(
        codes="Z603",
        name="Suppression Governance",
        capability="Detects dead inline suppressions that do not suppress any active finding",
        primary_exit=1,
        non_suppressible=False,
    ),
    CoreScanner(
        codes="Z610\u2013611",
        name="Policy Engine",
        capability=(
            "Declarative Policy-as-Code evaluation \u2014 required frontmatter keys (Z610) "
            "and forbidden external domains (Z611), both Markdown and HTML links. "
            "Activated via [policies] in .zenzic.toml. Opt-in, inactive by default."
        ),
        primary_exit=1,
        non_suppressible=False,
    ),
]


def label(code: str) -> str:
    """Return ``"Zxxx NAME"`` for display, e.g. ``"Z101 LINK_BROKEN"``.

    Falls back to just the code when no name is registered.
    """
    name = CODE_NAMES.get(code, "")
    return f"{code} {name}".strip()
