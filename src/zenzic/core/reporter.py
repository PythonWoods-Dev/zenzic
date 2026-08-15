# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""Zenzic Report Engine — Ruff-inspired CLI output for Zenzic."""

from __future__ import annotations

import shutil
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

from rich.console import Console, RenderableType
from rich.markup import escape as _esc
from rich.rule import Rule
from rich.text import Text

from zenzic.core.ui import ZenzicPalette, emoji


@dataclass(slots=True)
class Finding:
    """Normalized finding for display grouping."""

    rel_path: str
    line_no: int  # 0 = file-level finding
    code: str
    severity: str  # "error", "warning", "info"
    message: str
    source_line: str = ""
    col_start: int = 0
    match_text: str = ""
    is_baselined: bool = False


@dataclass(slots=True, frozen=True)
class FooterNotice:
    """Declarative footer contract appended after the rendered report body."""

    lines: tuple[str, ...] = ()


_SEVERITY_STYLE: dict[str, str] = {
    "error": ZenzicPalette.STYLE_ERR,
    "warning": ZenzicPalette.STYLE_WARN,
    "info": ZenzicPalette.STYLE_BRAND,
    "security_breach": f"bold white on {ZenzicPalette.ERROR}",
    "security_incident": f"bold white on {ZenzicPalette.FATAL}",
}


def _obfuscate_secret(raw: str) -> str:
    """Partially redact a secret for safe display in logs and CI output.

    Preserves the first four and last four characters so reviewers can
    identify the secret type and suffix without exposing the full credential.
    Strings of length ≤ 8 are fully redacted.

    This function is the only place where raw secret material is allowed
    to be formatted for human consumption.  It **must never** be bypassed.

    Args:
        raw: The raw matched secret string from the credential scanner.

    Returns:
        A partially-redacted string safe for log output.
    """
    if len(raw) <= 8:  # too short to redact partially — hide the whole thing
        return "*" * len(raw)
    return raw[:4] + "*" * (len(raw) - 8) + raw[-4:]


def _strip_prefix(rel_path: str, line_no: int, message: str) -> str:
    """Remove the redundant 'relpath:lineno: ' prefix already shown in the file header."""
    if line_no > 0:
        prefix = f"{rel_path}:{line_no}: "
        if message.startswith(prefix):
            return message[len(prefix) :]
    return message


# Context lines to show before/after the error line in snippets.
_CONTEXT_LINES = 2


def _read_snippet(path: Path, line_no: int) -> tuple[list[str], int] | None:
    """Read a few lines around *line_no* from *path*, or ``None`` on failure."""
    try:
        all_lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return None
    if not all_lines or line_no < 1:
        return None
    start = max(0, line_no - 1 - _CONTEXT_LINES)
    end = min(len(all_lines), line_no + _CONTEXT_LINES)
    return all_lines[start:end], start + 1


def _render_snippet(
    abs_path: Path, line_no: int, *, col_start: int = 0, match_text: str = ""
) -> list[Text]:
    """Render code snippet with custom ``│ ❱`` gutter and targeted ``^^^^`` carets.

    Carets are rendered **only** when the caller provides a non-empty
    *match_text* with a valid *col_start* — i.e. when the checker natively
    knows the exact token position.  No guessing, no regex heuristics.
    """
    snippet = _read_snippet(abs_path, line_no)
    if snippet is None:
        return []

    lines, start_line = snippet
    end_line_no = start_line + len(lines) - 1
    gutter_w = len(str(end_line_no))
    result: list[Text] = []

    for i, src in enumerate(lines):
        cur = start_line + i
        is_err = cur == line_no
        num = str(cur).rjust(gutter_w)

        # Prefix overhead: "    {num}  ❱  " or "    {num}  │  "
        # = 4 + gutter_w + 2 + 3 = 9 + gutter_w visual chars.
        # Keep source display within 2/3 of the terminal width so long lines
        # don't wrap and misalign the caret row below.
        term_cols = shutil.get_terminal_size(fallback=(120, 24)).columns
        max_src = max(20, term_cols - 9 - gutter_w)

        t = Text()
        t.append(f"    {num}  ", style=ZenzicPalette.DIM)
        if is_err:
            t.append("❱  ", style=ZenzicPalette.STYLE_ERR)
            if len(src) > max_src:
                t.append(src[: max_src - 1] + "…")
            else:
                t.append(src)
        else:
            t.append("│  ", style=ZenzicPalette.DIM)
            if len(src) > max_src:
                t.append(src[: max_src - 1] + "…", style=ZenzicPalette.DIM)
            else:
                t.append(src, style=ZenzicPalette.DIM)
        result.append(t)

        # Surgical caret: render only when the checker provided native position data
        # AND the caret falls within the visible (non-truncated) portion of the line.
        if is_err and match_text and col_start >= 0:
            caret_len = len(match_text)
            if col_start + caret_len <= max_src:
                ct = Text()
                ct.append(f"    {' ' * gutter_w}  ", style=ZenzicPalette.DIM)
                ct.append("│  ", style=ZenzicPalette.DIM)
                ct.append(" " * col_start + "^" * caret_len, style=ZenzicPalette.STYLE_ERR)
                result.append(ct)

    return result


class ZenzicReporter:
    """Render check results as a Ruff-inspired grouped report."""

    def __init__(self, console: Console, docs_root: Path, *, docs_dir: str = "docs") -> None:
        self._con = console
        self._docs_root = docs_root
        self._docs_dir = docs_dir

    def _full_rel(self, rel_path: str) -> str:
        """Return project-relative path as is."""
        return rel_path

    def _rel(self, path: Path) -> str:
        try:
            return str(path.relative_to(self._docs_root))
        except ValueError:
            return str(path)

    # ── Full report ───────────────────────────────────────────────────────────

    def render(
        self,
        findings: list[Finding],
        *,
        version: str,
        elapsed: float,
        docs_count: int = 0,
        assets_count: int = 0,
        engine: str = "auto",
        target: str | None = None,
        strict: bool = False,
        ok_message: str | None = None,
        show_info: bool = False,
        footer_notice: FooterNotice | None = None,
    ) -> tuple[int, int]:
        """Print the full Zenzic Report.

        Breach findings (``severity=="security_breach"``) are rendered as
        dedicated red panels **before** the grouped findings section and are
        excluded from the grouped view to avoid noise.  All other findings flow
        through the normal grouped pipeline.

        Args:
            ok_message: Optional success message shown when no hard failures are
                found.  Defaults to ``"All checks passed. Your documentation is
                secure."`` (all-clear panel) or ``"All checks passed."`` (with
                warnings).  Individual commands should pass a specific message
                such as ``"No broken links found."``.

        Returns:
            ``(error_count, warning_count)`` — breaches are counted separately
            by the caller (``cli.py``) and cause Exit 2, not Exit 1.
        """
        errors = sum(1 for f in findings if f.severity == "error")
        warnings = sum(1 for f in findings if f.severity == "warning")
        info_total = sum(1 for f in findings if f.severity == "info")

        # ── Split: breach findings get dedicated panels; rest goes to the grouped view
        breach_findings = [f for f in findings if f.severity == "security_breach"]
        normal_findings = [f for f in findings if f.severity != "security_breach"]

        # ── Info filter: suppress advisory findings unless opt-in ─────────────
        if not show_info:
            _info = [f for f in normal_findings if f.severity == "info"]
            normal_findings = [f for f in normal_findings if f.severity != "info"]
            info_count = len(_info)
        else:
            info_count = 0

        # ── Telemetry line ────────────────────────────────────────────────────
        dot = emoji("dot")
        total = docs_count + assets_count
        parts = [engine]
        if target is not None:
            parts.append(target)
        if total:
            breakdown = f"([{ZenzicPalette.BRAND}]{docs_count}[/] docs, [{ZenzicPalette.BRAND}]{assets_count}[/] assets)"
            parts.append(
                f"[{ZenzicPalette.BRAND}]{total}[/] file{'s' if total != 1 else ''} {breakdown}"
            )
        if elapsed:
            parts.append(f"[{ZenzicPalette.BRAND}]{elapsed:.1f}[/]s")
            if total:
                throughput = total / elapsed
                parts.append(f"[{ZenzicPalette.BRAND}]{throughput:.0f}[/] files/s")
        telemetry = Text.from_markup(f"[{ZenzicPalette.DIM}]{f' {dot} '.join(parts)}[/]")

        # ── Security breach flat output (rendered BEFORE main findings) ──────
        if breach_findings:
            for bf in breach_findings:
                self._con.print()
                if bf.code == "Z204":
                    self._con.print(
                        Text("\u2718 POLICY VIOLATION DETECTED", style="bold white on #8b0000")
                    )
                else:
                    self._con.print(
                        Text("\u2718 SECURITY BREACH DETECTED", style="bold white on #8b0000")
                    )
                self._con.print(
                    Text.from_markup(f"  {emoji('cross')} [bold]Finding:[/]    {_esc(bf.message)}")
                )
                self._con.print(
                    Text.from_markup(
                        f"  {emoji('cross')} [bold]Location:[/]   "
                        f"[bold]{_esc(self._full_rel(bf.rel_path))}[/]:{bf.line_no}"
                    )
                )
                if bf.code == "Z204":
                    self._con.print(
                        Text.from_markup(
                            f"  {emoji('cross')} [bold]Term:[/]       "
                            f"[bold reverse] {_esc(bf.match_text or '[unknown]')} [/]"
                        )
                    )
                    self._con.print(Text())
                    self._con.print(
                        Text.from_markup(
                            "  [bold]Action:[/] Remove this term from the documentation "
                            "or update the [bold]forbidden_patterns[/] list in "
                            "[bold].zenzic.local.toml[/]."
                        )
                    )
                else:
                    obfuscated = _obfuscate_secret(bf.match_text) if bf.match_text else "[redacted]"
                    self._con.print(
                        Text.from_markup(
                            f"  {emoji('cross')} [bold]Credential:[/] "
                            f"[bold reverse] {_esc(obfuscated)} [/]"
                        )
                    )
                    self._con.print(Text())
                    self._con.print(
                        Text.from_markup(
                            "  [bold]Action:[/] Rotate this credential immediately "
                            "and purge it from the repository history."
                        )
                    )

        if not normal_findings and not breach_findings:
            # ── All-clear panel ───────────────────────────────────────────────
            _ok = ok_message or (
                f"[bold {ZenzicPalette.SUCCESS}]Analysis complete:[/bold {ZenzicPalette.SUCCESS}]"
                f" [{ZenzicPalette.SUCCESS}]Links, credentials, semantic structure,"
                f" and policies verified.[/{ZenzicPalette.SUCCESS}]"
            )
            _ok_items: list[RenderableType] = [
                telemetry,
                Text(),
                Rule(style=ZenzicPalette.DIM),
                Text(),
                Text.from_markup(f"{emoji('sparkles')} {_ok}")
                if not ok_message
                else Text.from_markup(f"[{ZenzicPalette.SUCCESS}]{emoji('check')} {_ok}[/]"),
            ]
            if info_count:
                _ok_items.append(Text())
                _ok_items.append(
                    Text.from_markup(
                        f"[{ZenzicPalette.DIM}]{emoji('info')} {info_count} info finding"
                        f"{'s' if info_count != 1 else ''} suppressed"
                        f" — use --show-info for details.[/]"
                    )
                )
            self._con.print()
            for _item in _ok_items:
                self._con.print(_item)
            if footer_notice is not None:
                for line in footer_notice.lines:
                    self._con.print(Text.from_markup(line))
            return 0, 0

        # ── Grouped findings (non-breach only) ───────────────────────────────
        grouped: dict[str, list[Finding]] = defaultdict(list)
        for f in normal_findings:
            grouped[f.rel_path].append(f)

        renderables: list[RenderableType] = []
        for rel_path in sorted(grouped):
            abs_path = self._docs_root / rel_path
            for idx, f in enumerate(sorted(grouped[rel_path], key=lambda x: (x.line_no, x.code))):
                if idx > 0:
                    renderables.append(Text())  # breathing between findings within a file

                sev_icon = (
                    emoji("cross")
                    if f.severity in {"error", "security_incident"}
                    else emoji("warn")
                    if f.severity == "warning"
                    else emoji("info")
                )
                style = _SEVERITY_STYLE.get(f.severity, ZenzicPalette.DIM)
                msg = _strip_prefix(f.rel_path, f.line_no, f.message)
                # Bold-cyan clickable location prefix (ruff-style, CEO-169)
                loc = self._full_rel(f.rel_path)
                if f.line_no > 0:
                    loc += f":{f.line_no}"
                    if f.col_start > 0:
                        loc += f":{f.col_start}"
                baselined_tag = f"  [{ZenzicPalette.DIM}][BASELINED][/]" if f.is_baselined else ""
                renderables.append(
                    Text.from_markup(
                        f"[bold cyan]{_esc(loc)}[/]  [{style}]{sev_icon}[/]  [{style}][{f.code}][/]{baselined_tag}  {_esc(msg)}"
                    )
                )
                # Snippet with native position data — no guessing
                if f.line_no and f.source_line:
                    renderables.append(Text())  # breathing before snippet
                    snippet_lines = _render_snippet(
                        abs_path,
                        f.line_no,
                        col_start=f.col_start,
                        match_text=f.match_text,
                    )
                    if snippet_lines:
                        renderables.extend(snippet_lines)
                    else:
                        # Fallback: file unreadable, use source_line directly
                        gutter_w = len(str(f.line_no))
                        t = Text()
                        t.append(f"    {str(f.line_no).rjust(gutter_w)}  ", style=ZenzicPalette.DIM)
                        t.append("❱  ", style=ZenzicPalette.STYLE_ERR)
                        t.append(f.source_line)
                        renderables.append(t)

            renderables.append(Text())  # spacing after file group

        # ── Summary (inside the panel) ────────────────────────────────────────
        renderables.append(Rule(style=ZenzicPalette.DIM))
        renderables.append(Text())  # breathing after Rule
        incidents_count = sum(1 for f in normal_findings if f.severity == "security_incident")
        policy_findings = [f for f in breach_findings if f.code == "Z204"]
        credential_findings = [f for f in breach_findings if f.code != "Z204"]
        policy_count = len(policy_findings)
        breaches_count = len(credential_findings)
        breach_files_count = len({f.rel_path for f in breach_findings})
        summary_parts: list[str] = [f"[{ZenzicPalette.DIM}]Summary:[/]"]
        if breaches_count:
            summary_parts.append(
                f"[bold white on {ZenzicPalette.FATAL}]{emoji('cross')} {breaches_count}"
                f" security breach{'es' if breaches_count != 1 else ''}[/]"
            )
        if policy_count:
            summary_parts.append(
                f"[bold white on {ZenzicPalette.FATAL}]{emoji('cross')} {policy_count}"
                f" policy violation{'s' if policy_count != 1 else ''}[/]"
            )
        if breach_files_count:
            summary_parts.append(
                f"[{ZenzicPalette.DIM}]{emoji('dot')} {breach_files_count} file"
                f"{'s' if breach_files_count != 1 else ''} impacted[/]"
            )
        if incidents_count:
            summary_parts.append(
                f"[bold white on {ZenzicPalette.FATAL}]{emoji('cross')} {incidents_count}"
                f" security incident{'s' if incidents_count != 1 else ''}[/]"
            )
        summary_parts.append(
            f"[{ZenzicPalette.ERROR}]{emoji('cross')} {errors} error{'s' if errors != 1 else ''}[/]"
        )
        summary_parts.append(
            f"[{ZenzicPalette.WARNING}]{emoji('warn')} {warnings} warning{'s' if warnings != 1 else ''}[/]"
        )
        summary_parts.append(f"[{ZenzicPalette.BRAND}]{emoji('info')} {info_total} info[/]")
        n_files = len(grouped)
        summary_parts.append(
            f"[{ZenzicPalette.DIM}]{emoji('dot')} {n_files} file{'s' if n_files != 1 else ''} with findings[/]"
        )
        renderables.append(Text.from_markup("  ".join(summary_parts)))

        # ── Status line (verdict) ─────────────────────────────────────────────
        renderables.append(Text())  # breathing before verdict
        has_hard_failures = (
            (breaches_count > 0) or (policy_count > 0) or (incidents_count > 0) or (errors > 0)
        )
        has_strict_failures = strict and warnings > 0
        has_failures = has_hard_failures or has_strict_failures
        if has_failures:
            if has_hard_failures:
                if breaches_count and policy_count:
                    renderables.append(
                        Text.from_markup(
                            f"[bold {ZenzicPalette.ERROR}]FAILED:[/]"
                            " Security breaches and policy violations detected. Exit code 2 is mandatory."
                        )
                    )
                elif breaches_count:
                    renderables.append(
                        Text.from_markup(
                            f"[bold {ZenzicPalette.ERROR}]FAILED:[/]"
                            " Security breaches detected. Exit code 2 is mandatory."
                        )
                    )
                elif policy_count:
                    renderables.append(
                        Text.from_markup(
                            f"[bold {ZenzicPalette.ERROR}]FAILED:[/]"
                            " Policy violations detected. Exit code 2 is mandatory."
                        )
                    )
                else:
                    renderables.append(
                        Text.from_markup(
                            f"[bold {ZenzicPalette.ERROR}]FAILED:[/]"
                            " Hard errors detected. Exit code 1 is mandatory."
                        )
                    )
                if has_strict_failures:
                    renderables.append(
                        Text.from_markup(
                            f"[bold {ZenzicPalette.WARNING}]STRICT MODE:[/]"
                            " Warnings have been promoted to errors."
                        )
                    )
            else:
                renderables.append(
                    Text.from_markup(
                        f"[bold {ZenzicPalette.WARNING}]FAILED:[/]"
                        " Warnings promoted to errors via --strict flag."
                    )
                )
        else:
            _ok = ok_message or (
                f"[bold {ZenzicPalette.SUCCESS}]Analysis complete:[/bold {ZenzicPalette.SUCCESS}]"
                f" [{ZenzicPalette.SUCCESS}]Links, credentials, semantic structure,"
                f" and policies verified.[/{ZenzicPalette.SUCCESS}]"
            )
            renderables.append(
                Text.from_markup(f"{emoji('sparkles')} {_ok}")
                if not ok_message
                else Text.from_markup(f"[{ZenzicPalette.SUCCESS}]{emoji('check')} {_ok}[/]")
            )

        if info_count:
            renderables.append(Text())
            renderables.append(
                Text.from_markup(
                    f"[{ZenzicPalette.DIM}]{emoji('info')} {info_count} info finding"
                    f"{'s' if info_count != 1 else ''} hidden — use --show-info to display.[/]"
                )
            )

        # ── Flat output (ruff-style, CEO-169) ──────────────────────────────────────
        self._con.print()
        self._con.print(telemetry)
        self._con.print()
        for _r in renderables:
            self._con.print(_r)
        if footer_notice is not None:
            for line in footer_notice.lines:
                self._con.print(Text.from_markup(line))
        return errors, warnings

    # ── Quiet mode (pre-commit) ──────────────────────────────────────────────

    def render_quiet(self, findings: list[Finding]) -> tuple[int, int]:
        """Minimal output for pre-commit hooks.

        Breach findings always produce a one-liner even in quiet mode — silent
        failure on a credential leak is more dangerous than noisy CI output.
        """
        breaches = [f for f in findings if f.severity == "security_breach"]
        errors = sum(1 for f in findings if f.severity == "error")
        warnings = sum(1 for f in findings if f.severity == "warning")
        if breaches:
            self._con.print(
                f"[bold red]SECURITY CRITICAL:[/] {len(breaches)} secret(s) detected — "
                f"rotate immediately. Exit 2."
            )
        if errors or warnings:
            self._con.print(f"zenzic: {errors} error(s), {warnings} warning(s)")
        return errors, warnings
