# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0

import contextlib
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from zenzic.core import regex as re
from zenzic.core.codes import (
    NON_INLINE_SUPPRESSIBLE_CODES,
    NON_SUPPRESSIBLE_CODES,
    code_severity,
)
from zenzic.core.sovereign_context import get_sovereign_context


if TYPE_CHECKING:
    from zenzic.core.rules import RuleFinding
    from zenzic.models.config import ZenzicConfig


#: Fenced code block line: captures the fence chars and the full info string.
_FENCE_OPEN_RE = re.compile(r"^(?P<fence>[`~]{3,})(?P<info>.*)$")

#: Strict suppression protocol: only exact ``zenzic:ignore:`` directives are valid.
#: **This is the single definition** — ``rules.py`` imports it rather than keeping
#: its own copy, because the parser and the audit counter are the same pattern and
#: a second copy desynchronises them the day one spelling is added.
#:
#:   Markdown (.md):  ``<!-- zenzic:ignore: Z905 - reason -->``
#:   MDX (.mdx):      ``{/* zenzic:ignore: Z905 - reason */}``
#:
#: The MDX braces accept surrounding whitespace (``{ /* … */ }``). They are an
#: expression container and the whitespace is legal, and Prettier emits exactly
#: that form -- so requiring them adjacent meant a formatted file's directive was
#: not a directive: the finding stayed, nothing was suppressed, and because an
#: *unparsed* directive is not an *unconsumed* one there was no ``Z603`` either.
#: No effect and no explanation. The same adjacency assumption was fixed in four
#: comment-*masking* sites earlier in this release; this is the fifth, in the
#: place that decides what a directive is at all.
_SUPPRESS_RE = re.compile(
    r"(?:<!--|\{\s*/\*)\s*zenzic:ignore:\s*(?P<code>Z\d{3})(?:[^\n]*?)?(?:-->|\*/\s*\})",
)

#: Strip backtick inline code spans before counting suppressions, so a
#: didactic example like `<!-- zenzic:ignore: Z601 -->` in prose is not
#: miscounted as an active suppression directive.
_INLINE_CODE_STRIP_RE = re.compile(r"``[^`\n]+``|`[^`\n]+`")

#: Topological findings are governed as a paired policy family.
_TOPOLOGY_POLICY_CODES: frozenset[str] = frozenset({"Z410", "Z411"})

#: Sentinel code for a ``data-zenzic-ignore`` attribute, which names no code of
#: its own -- it covers whatever its tag can produce.
DATA_ATTR_DIRECTIVE = "DATA-ZENZIC-IGNORE"

#: What ``data-zenzic-ignore`` is documented to suppress, stated once so the
#: lookup and the rule cards cannot drift apart.
#:
#: The HTML hygiene tier (``Z120``-``Z124``) is the half every rule card names.
#: The three link codes are the half that was only ever documented in prose --
#: ``docs/how-to/troubleshooting.md`` tells readers to silence a ``Z104`` on a
#: generated feed with this attribute, and v0.20.0's release notes record the
#: URP leak that made it necessary -- and they belong here because the pipeline
#: used to honour them by skipping the check outright, which no ledger can see.
#: The security tier is absent on purpose: ``Z202``/``Z203``/``Z205`` are
#: non-suppressible, and a page must not silence its own by editing its own tag.
DATA_ATTR_SUPPRESSIBLE_CODES: frozenset[str] = frozenset(
    {
        "Z120",  # UNKNOWN_HTML_ATTRIBUTE
        "Z121",  # MISSING_OR_EMPTY_HREF
        "Z122",  # JUMP_LINK_DETECTED
        "Z123",  # NON_HTTP_SCHEME
        "Z124",  # OPAQUE_HTML_CONTEXT
        "Z102",  # BROKEN_RELATIVE_LINK
        "Z104",  # MISSING_ASSET
        "Z105",  # ABSOLUTE_PATH_USED
    }
)


@dataclass
class SuppressionDirective:
    code: str
    line_no: int
    consumed: bool = False


SuppressionSource = Literal[
    "inline",
    "directory-policy",
    "non-suppressible",
    "non-inline-suppressible",
    "force-audit",
    "none",
]


@dataclass(frozen=True)
class SuppressionVerdict:
    """Why a finding is, or is not, suppressed at a given line.

    ``source`` names the mechanism that decided, which is the part a bare
    boolean throws away:

    ``inline``
        An ``<!-- zenzic:ignore: CODE -->`` directive on that exact line.
    ``directory-policy``
        A ``[governance.directory_policies]`` glob in ``.zenzic.toml`` covers
        this code for this file. ``pattern`` holds the matching glob.
    ``non-suppressible``
        A Tier-0 security code. Cannot be silenced by any mechanism.
    ``non-inline-suppressible``
        ADR-093: a graph- or file-level code, governable only through
        ``.zenzic.toml``, never by an inline comment.
    ``force-audit``
        ``--audit`` is active, so every suppression is ignored for this run.
    ``none``
        Nothing suppresses it; the finding is reported.

    Truthy exactly when ``suppressed`` is, so it reads naturally in a condition.
    """

    suppressed: bool
    source: SuppressionSource
    pattern: str | None = None

    def __bool__(self) -> bool:
        return self.suppressed


class SuppressionTracker:
    """Tracks inline suppressions within a single file to identify Z603 Dead Suppressions."""

    def __init__(
        self,
        file_path: Path,
        text: str,
        globally_suppressed_codes: dict[str, list[str]] | None = None,
        global_tracker: "GlobalUsageTracker | None" = None,
        per_file_ignore_patterns: frozenset[str] = frozenset(),
        directory_policy_patterns: frozenset[str] = frozenset(),
    ):
        self.file_path = file_path
        self.directives: list[SuppressionDirective] = []
        self.globally_suppressed_codes = globally_suppressed_codes or {}
        self.consumed_global_patterns: set[tuple[str, str]] = set()
        self.global_tracker = global_tracker
        # Which table each glob in globally_suppressed_codes came from. The two
        # are merged into one lookup because suppression does not care, but
        # Z620 does: usage was recorded against the directory-policy ledger for
        # both kinds, so the per-file ledger was never cleared and every
        # per_file_ignores entry was reported "never used" -- including the ones
        # actively suppressing findings. Callers that build a tracker without
        # provenance (a unit test, a caller with only directory policies) leave
        # both empty and keep the old single-ledger behaviour.
        self.per_file_ignore_patterns = per_file_ignore_patterns
        self.directory_policy_patterns = directory_policy_patterns
        self._parse(text)

    def _parse(self, text: str) -> None:
        inside_fence = False
        open_char = ""
        open_count = 0
        for i, line in enumerate(text.splitlines(), start=1):
            fm = _FENCE_OPEN_RE.match(line)
            if not inside_fence:
                if fm:
                    fence = fm.group("fence")
                    inside_fence = True
                    open_char = fence[0]
                    open_count = len(fence)
                else:
                    stripped = _INLINE_CODE_STRIP_RE.sub("", line)
                    for m in _SUPPRESS_RE.finditer(stripped):
                        self.directives.append(
                            SuppressionDirective(
                                code=m.group("code").upper(),
                                line_no=i,
                                consumed=False,
                            )
                        )
            else:
                if fm:
                    fence = fm.group("fence")
                    info = fm.group("info").strip()
                    if fence[0] == open_char and len(fence) >= open_count and not info:
                        inside_fence = False
                        open_char = ""
                        open_count = 0

        # Parse html data-zenzic-ignore tags
        if "data-zenzic-ignore" in text:
            from zenzic.core.validator import PolyglotExtractor

            with contextlib.suppress(Exception):
                extractor = PolyglotExtractor()
                html_nodes = extractor.extract(text)
                for node in html_nodes:
                    if node.suppressed:
                        self.directives.append(
                            SuppressionDirective(
                                code=DATA_ATTR_DIRECTIVE,
                                line_no=node.line_no,
                                consumed=False,
                            )
                        )

    def _matching_directive(self, line_no: int, code: str) -> SuppressionDirective | None:
        """The inline directive that would suppress *code* at *line_no*, if any.

        Pure lookup — never consumes. *code* must already be upper-cased.
        """
        for d in self.directives:
            if d.line_no == line_no and not d.consumed:
                if d.code == code or (
                    d.code == DATA_ATTR_DIRECTIVE and code in DATA_ATTR_SUPPRESSIBLE_CODES
                ):
                    return d
        return None

    def explain_suppression(self, line_no: int, code: str) -> SuppressionVerdict:
        """Why *code* is (or is not) suppressed at *line_no*, without changing anything.

        The read-only half of the suppression decision. ``is_suppressed`` is this
        function plus the state changes its verdict implies, so the two cannot
        disagree about *whether* something is suppressed — there is one decision
        tree, evaluated here.

        Separating them is required, not stylistic. ``is_suppressed`` consumes
        directives and marks policies used, which feeds ``Z603`` dead-suppression
        detection; anything that merely wants to *describe* the state — an editor
        hover, a report — must not perturb it (Command-Query Segregation).
        """
        if get_sovereign_context().force_audit:
            return SuppressionVerdict(False, "force-audit")

        # Normalized once, up front: both non-suppressible guards below and
        # every suppression-lookup branch after them must agree on the same
        # code, or a lowercase caller could pass the guards (checked against
        # the upper-case-only registries) and still reach a lookup branch
        # that normalizes -- desynchronizing the two decisions.
        upper = code.upper()

        if upper in NON_SUPPRESSIBLE_CODES:
            return SuppressionVerdict(False, "non-suppressible")

        # ADR-093: graph-level and file-level findings cannot be suppressed
        # via inline comments -- only .zenzic.toml governance applies. Same
        # mechanism as NON_SUPPRESSIBLE_CODES above: leave the directive
        # unconsumed so get_dead_suppressions() reports it as Z603, with a
        # message distinguishing this cause from an ordinary dead comment.
        if upper in NON_INLINE_SUPPRESSIBLE_CODES:
            return SuppressionVerdict(False, "non-inline-suppressible")

        # A governance policy already covers this code, so the inline directive
        # (if any) is deliberately NOT consumed -- get_dead_suppressions() then
        # reports it as Z603, since the comment is redundant with the policy.
        if upper in self.globally_suppressed_codes:
            patterns = self.globally_suppressed_codes[upper]
            return SuppressionVerdict(True, "directory-policy", patterns[0] if patterns else None)

        if self._matching_directive(line_no, upper) is not None:
            return SuppressionVerdict(True, "inline")

        return SuppressionVerdict(False, "none")

    def is_suppressed(self, line_no: int, code: str) -> bool:
        """Return True if the given code is suppressed at the specified line number.

        Marks the suppression directive as consumed if a match is found.

        Deliberately still returns a plain ``bool``: this runs once per finding on
        the scanning hot path, and several call sites assert on the ``True``/
        ``False`` singletons. Callers wanting the reason ask
        :meth:`explain_suppression`, which is free of side effects.
        """
        verdict = self.explain_suppression(line_no, code)

        if verdict.source == "directory-policy":
            upper = code.upper()
            for pattern in self.globally_suppressed_codes[upper]:
                self.consumed_global_patterns.add((pattern, upper))
                if self.global_tracker:
                    self._mark_global_pattern_used(pattern, upper)
        elif verdict.source == "inline":
            directive = self._matching_directive(line_no, code.upper())
            if directive is not None:
                directive.consumed = True

        return verdict.suppressed

    def _mark_global_pattern_used(self, pattern: str, code: str) -> None:
        """Record usage of *pattern* against the table it was declared in.

        With no provenance (both sets empty) this falls back to the
        directory-policy ledger, which is what every caller did before the two
        were told apart.
        """
        tracker = self.global_tracker
        if tracker is None:
            return
        if not self.per_file_ignore_patterns and not self.directory_policy_patterns:
            tracker.mark_directory_policy_used(pattern, code)
            return
        if pattern in self.per_file_ignore_patterns:
            tracker.mark_per_file_ignore_used(pattern, code)
        if pattern in self.directory_policy_patterns:
            tracker.mark_directory_policy_used(pattern, code)

    def get_dead_suppressions(self) -> list["RuleFinding"]:
        """Yield Z603 findings for all directives that were never consumed."""
        from zenzic.core.rules import RuleFinding

        findings = []
        for d in self.directives:
            if not d.consumed:
                if d.code == DATA_ATTR_DIRECTIVE:
                    msg = "data-zenzic-ignore attribute does not suppress any active html hygiene finding. Remove the dead attribute."
                elif d.code in NON_INLINE_SUPPRESSIBLE_CODES:
                    msg = (
                        f"{d.code} cannot be suppressed via inline comments (ADR-093) -- "
                        "it is governed only through .zenzic.toml's directory_policies or "
                        "per_file_ignores. Remove this comment and use TOML governance instead."
                    )
                else:
                    msg = "Inline suppression directive does not suppress any active finding. Remove the dead comment."
                findings.append(
                    RuleFinding(
                        file_path=self.file_path,
                        line_no=d.line_no,
                        rule_id="Z603",
                        message=msg,
                        severity=code_severity("Z603"),
                    )
                )
        return findings


def count_inline_suppressions(text: str) -> int:
    """Count suppression directives declared in Markdown/MDX source text."""
    tracker = SuppressionTracker(Path("dummy"), text)
    return len(tracker.directives)


def _resolve_toml_line(
    origin_path: Path, search_target: str, lines_cache: list[str] | None = None
) -> int:
    """Find the 1-based line number in origin_path containing search_target.

    Falls back to line 1 if the file cannot be read or search_target is not found.
    """
    lines = lines_cache
    if lines is None:
        try:
            lines = origin_path.read_text(encoding="utf-8").splitlines()
        except OSError:
            return 1

    quoted_d = f'"{search_target}"'
    quoted_s = f"'{search_target}'"
    for idx, line in enumerate(lines, start=1):
        if quoted_d in line or quoted_s in line or search_target in line:
            return idx
    return 1


class GlobalUsageTracker:
    """Tracks global policy usage (Z620) for directory_policies, excluded_file_patterns, excluded_external_urls, and per_file_ignores."""

    def __init__(self, config: "ZenzicConfig"):
        self.config = config
        self.unused_dir_policies: set[tuple[str, str]] = set()
        self.unused_file_patterns: set[str] = set()
        self.unused_ext_urls: set[str] = set()
        self.unused_per_file_ignores: set[tuple[str, str]] = set()

        if getattr(config, "governance", None) and config.governance.directory_policies:
            for pattern, codes in config.governance.directory_policies.items():
                for code in codes:
                    self.unused_dir_policies.add((pattern, str(code).strip().upper()))

        if getattr(config, "excluded_file_patterns", None):
            for pattern in config.excluded_file_patterns:
                self.unused_file_patterns.add(pattern)

        if getattr(config, "excluded_external_urls", None):
            for url in config.excluded_external_urls:
                self.unused_ext_urls.add(url)

        if getattr(config, "governance", None) and config.governance.per_file_ignores:
            for pattern, codes in config.governance.per_file_ignores.items():
                for code in codes:
                    self.unused_per_file_ignores.add((pattern, str(code).strip().upper()))

    def mark_directory_policy_used(self, pattern: str, code: str) -> None:
        normalized = code.upper()
        self.unused_dir_policies.discard((pattern, normalized))
        if normalized in _TOPOLOGY_POLICY_CODES:
            for sibling in _TOPOLOGY_POLICY_CODES:
                self.unused_dir_policies.discard((pattern, sibling))

    def mark_excluded_file_pattern_used(self, pattern: str) -> None:
        self.unused_file_patterns.discard(pattern)

    def mark_excluded_external_url_used(self, url: str) -> None:
        self.unused_ext_urls.discard(url)

    def mark_per_file_ignore_used(self, pattern: str, code: str) -> None:
        normalized = code.upper()
        self.unused_per_file_ignores.discard((pattern, normalized))
        if normalized in _TOPOLOGY_POLICY_CODES:
            for sibling in _TOPOLOGY_POLICY_CODES:
                self.unused_per_file_ignores.discard((pattern, sibling))

    def get_stale_findings(
        self,
        check_all: bool = True,
        check_external_urls: bool = True,
    ) -> list["RuleFinding"]:
        from zenzic.core.rules import RuleFinding

        origin = self.config.origin_file or Path(".zenzic.toml")
        findings = []

        try:
            toml_lines = origin.read_text(encoding="utf-8").splitlines()
        except OSError:
            toml_lines = []

        if check_all:
            for pattern, code in sorted(self.unused_dir_policies):
                # Do not complain about Z502 for the root files or Z601 for adr vault (these are implicit/system)
                if pattern in ("docs/index.md", "docs/blog/index.md") and code == "Z502":
                    continue
                line_no = _resolve_toml_line(origin, pattern, toml_lines)
                findings.append(
                    RuleFinding(
                        file_path=origin,
                        line_no=line_no,
                        rule_id="Z620",
                        message=f"Global policy '{pattern}' = ['{code}'] was never used to suppress a finding. Remove the dead configuration.",
                        severity=code_severity("Z620"),
                    )
                )

        for pattern in sorted(self.unused_file_patterns):
            line_no = _resolve_toml_line(origin, pattern, toml_lines)
            findings.append(
                RuleFinding(
                    file_path=origin,
                    line_no=line_no,
                    rule_id="Z620",
                    message=f"Excluded file pattern '{pattern}' did not match any files during traversal.",
                    severity=code_severity("Z620"),
                )
            )

        if check_external_urls:
            for url in sorted(self.unused_ext_urls):
                line_no = _resolve_toml_line(origin, url, toml_lines)
                findings.append(
                    RuleFinding(
                        file_path=origin,
                        line_no=line_no,
                        rule_id="Z620",
                        message=f"Excluded external URL '{url}' was never skipped (the URL was not found in checked files).",
                        severity=code_severity("Z620"),
                    )
                )

        if check_all:
            for pattern, code in sorted(self.unused_per_file_ignores):
                line_no = _resolve_toml_line(origin, pattern, toml_lines)
                findings.append(
                    RuleFinding(
                        file_path=origin,
                        line_no=line_no,
                        rule_id="Z620",
                        message=f"Per-file ignore '{pattern}' = ['{code}'] was never used to suppress a finding. Remove the dead configuration.",
                        severity=code_severity("Z620"),
                    )
                )

        return findings
