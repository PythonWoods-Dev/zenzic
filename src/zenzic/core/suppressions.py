# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0

import contextlib
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

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
_SUPPRESS_RE = re.compile(
    r"(?:<!--|\{/\*)\s*zenzic:ignore:\s*(?P<code>Z\d{3})(?:[^\n]*?)?(?:-->|\*/\})",
)

#: ADR-084 — Strip backtick inline code spans before counting suppressions.
_INLINE_CODE_STRIP_RE = re.compile(r"``[^`\n]+``|`[^`\n]+`")

#: Topological findings are governed as a paired policy family.
_TOPOLOGY_POLICY_CODES: frozenset[str] = frozenset({"Z410", "Z411"})


@dataclass
class SuppressionDirective:
    code: str
    line_no: int
    consumed: bool = False


class SuppressionTracker:
    """Tracks inline suppressions within a single file to identify Z603 Dead Suppressions."""

    def __init__(
        self,
        file_path: Path,
        text: str,
        globally_suppressed_codes: dict[str, list[str]] | None = None,
        global_tracker: "GlobalUsageTracker | None" = None,
    ):
        self.file_path = file_path
        self.directives: list[SuppressionDirective] = []
        self.globally_suppressed_codes = globally_suppressed_codes or {}
        self.consumed_global_patterns: set[tuple[str, str]] = set()
        self.global_tracker = global_tracker
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
                                code="DATA-ZENZIC-IGNORE",
                                line_no=node.line_no,
                                consumed=False,
                            )
                        )

    def is_suppressed(self, line_no: int, code: str) -> bool:
        """Return True if the given code is suppressed at the specified line number.

        Marks the suppression directive as consumed if a match is found.
        """
        if get_sovereign_context().force_audit:
            return False

        if code in NON_SUPPRESSIBLE_CODES:
            return False

        # ADR-093: graph-level and file-level findings cannot be suppressed
        # via inline comments -- only .zenzic.toml governance applies. Same
        # mechanism as NON_SUPPRESSIBLE_CODES above: leave the directive
        # unconsumed so get_dead_suppressions() reports it as Z603, with a
        # message distinguishing this cause from an ordinary dead comment.
        if code in NON_INLINE_SUPPRESSIBLE_CODES:
            return False

        code = code.upper()

        # If the finding is already globally suppressed, do NOT consume the inline directive.
        # This leaves the inline directive unconsumed, so get_dead_suppressions() emits Z603.
        if code in self.globally_suppressed_codes:
            for pattern in self.globally_suppressed_codes[code]:
                self.consumed_global_patterns.add((pattern, code))
                if self.global_tracker:
                    self.global_tracker.mark_directory_policy_used(pattern, code)
            return True

        for d in self.directives:
            if d.line_no == line_no and not d.consumed:
                if d.code == code or (d.code == "DATA-ZENZIC-IGNORE" and code.startswith("Z12")):
                    d.consumed = True
                    return True
        return False

    def get_dead_suppressions(self) -> list["RuleFinding"]:
        """Yield Z603 findings for all directives that were never consumed."""
        from zenzic.core.rules import RuleFinding

        findings = []
        for d in self.directives:
            if not d.consumed:
                if d.code == "DATA-ZENZIC-IGNORE":
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
    """Tracks global policy usage (Z620) for directory_policies, excluded_file_patterns, and excluded_external_urls."""

    def __init__(self, config: "ZenzicConfig"):
        self.config = config
        self.unused_dir_policies: set[tuple[str, str]] = set()
        self.unused_file_patterns: set[str] = set()
        self.unused_ext_urls: set[str] = set()

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

        return findings
