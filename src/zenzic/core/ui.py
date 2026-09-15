# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""Zenzic Visual Identity — ZenzicPalette, terminal detection, and UI helpers.

``ZenzicPalette`` is the **sole source of truth** for every colour used in the
Zenzic terminal output.  Raw hex values live inside the class and **nowhere else**
in the codebase.  Every other module must import ``ZenzicPalette`` and address
its semantic attributes (e.g. ``ZenzicPalette.BRAND``) — never a raw hex string.
"""

from __future__ import annotations

import os
import sys
from typing import Any

from rich import box as _rich_box
from rich.console import RenderableType
from rich.panel import Panel


# ── Zenzic Visual Identity System ───────────────────────────────────────────


class ZenzicPalette:
    """Zenzic brand colour system — the only place where hex values are permitted.

    Internal (private) attributes store raw hex values.  External code must always
    address the **semantic** public attributes so that a future palette update only
    requires editing this class.

    Semantic colours::

        BRAND   — Zenzic primary / brand accent       (#4f46e5 Indigo)
        SUCCESS — OK · clean · pass                   (#10b981 Emerald)
        WARNING — caution · advisory                  (#f59e0b Amber)
        ERROR   — failure · broken links              (#f43f5e Rose)
        DIM     — muted · secondary text              (#64748b Slate)
        FATAL   — security breach · path traversal    (#8b0000 Critical)

    Pre-composed Rich style strings (``STYLE_*``) cover the most common
    combinations — prefer them over constructing ``f"bold {X}"`` inline.
    """

    # ── Raw hex values (edit only here) ──────────────────────────────────────
    _INDIGO = "#4f46e5"
    _EMERALD = "#10b981"
    _AMBER = "#f59e0b"
    _ROSE = "#f43f5e"
    _SLATE = "#64748b"
    _CRITICAL = "#8b0000"  # dark red — security breach / path traversal

    # ── Semantic colour aliases (the only public interface for the codebase) ─
    BRAND: str = _INDIGO  # Zenzic primary / brand accent
    SUCCESS: str = _EMERALD  # OK · clean · pass
    WARNING: str = _AMBER  # caution · advisory
    ERROR: str = _ROSE  # failure · broken links
    DIM: str = _SLATE  # muted · secondary text
    FATAL: str = _CRITICAL  # security breach · path traversal

    # ── Pre-composed Rich style strings ──────────────────────────────────────
    STYLE_BRAND: str = f"bold {_INDIGO}"
    STYLE_OK: str = f"bold {_EMERALD}"
    STYLE_WARN: str = f"bold {_AMBER}"
    STYLE_ERR: str = f"bold {_ROSE}"
    STYLE_DIM: str = _SLATE


# ── Terminal capability detection ─────────────────────────────────────────────


def _detect_capabilities() -> tuple[bool, bool]:
    """Detect whether the terminal supports colour and unicode emoji.

    Returns ``(supports_color, supports_emoji)``.

    Heuristics (conservative — false negatives are fine, false positives are not):

    * **NO_COLOR** env var (https://no-color.org/) → colour off.
    * **CI** env var → emoji off (many CI log viewers mangle multi-byte chars).
    * **TERM=dumb** → both off.
    * Not a TTY → colour off (piped output), emoji preserved.
    """
    no_color = bool(os.environ.get("NO_COLOR"))
    is_ci = bool(os.environ.get("CI"))
    term = os.environ.get("TERM", "")
    is_dumb = term == "dumb"
    is_tty = hasattr(sys.stderr, "isatty") and sys.stderr.isatty()

    supports_color = not no_color and not is_dumb and is_tty
    supports_emoji = not is_ci and not is_dumb

    return supports_color, supports_emoji


SUPPORTS_COLOR, SUPPORTS_EMOJI = _detect_capabilities()

# ── Emoji map with ASCII fallback ─────────────────────────────────────────────

_EMOJI: dict[str, tuple[str, str]] = {
    # key: (unicode, ascii_fallback)
    "check": ("\u2714", "*"),  # ✔
    "cross": ("\u2718", "x"),  # ✘
    "warn": ("\u26a0", "!"),  # ⚠
    "info": ("\U0001f4a1", "i"),  # 💡
    "lock": ("\U0001f512", "["),  # 🔒
    "brand": ("\U0001f6e1", "#"),  # 🛡
    "bolt": ("\u26a1", ">"),  # ⚡
    "dot": ("\u2022", "-"),  # •
    "arrow": ("\u279c", "->"),  # ➜
    "sparkles": ("\u2728", "*"),  # ✨
}


def emoji(name: str) -> str:
    """Return the emoji for *name*, or its ASCII fallback in degraded terminals."""
    pair = _EMOJI.get(name)
    if pair is None:
        return name
    return pair[0] if SUPPORTS_EMOJI else pair[1]


# ── Elapsed-time formatting ───────────────────────────────────────────────────


def format_elapsed_ms(elapsed_seconds: float) -> str:
    """Format a duration for a progress-line suffix, e.g. ``(331.2ms)``.

    Single source of truth for the per-phase timing suffix rendered on every
    Zenzic progress line. Previously each call site inlined its own
    ``f"({x:.1f}ms)"``, which is how two of them ended up measuring windows
    their labels did not describe without anything making the inconsistency
    visible.

    Deliberately always milliseconds with one decimal, and deliberately *not*
    threshold-switching to seconds for long runs: the progress lines are read
    against each other to compare phase costs, and a column that silently
    changes unit partway down the list is harder to scan, not easier. The final
    summary line is the one place a coarser seconds figure is appropriate, and
    it is produced separately by the reporter.

    Args:
        elapsed_seconds: Duration in **seconds** (as returned by
            ``time.perf_counter()``/``time.monotonic()`` deltas), not
            milliseconds — the conversion happens here so no call site repeats
            a ``* 1000`` it might get wrong.

    Returns:
        The formatted suffix including surrounding parentheses and Rich dim
        markup, ready to append to a task description.
    """
    return f"[dim]({elapsed_seconds * 1000:.1f}ms)[/dim]"


# ── Banner ────────────────────────────────────────────────────────────────────


def make_banner(version: str) -> str:
    """Return the Zenzic startup banner as a Rich-markup string.

    The banner is wrapped inside a :class:`rich.panel.Panel` by the caller —
    this function only builds the *content* string.
    """
    brand_icon = emoji("brand")
    lines = [
        f"[bold white]{brand_icon}  ZENZIC[/]  [{ZenzicPalette.DIM}]v{version}[/]",
        f"[{ZenzicPalette.DIM}]Engine-agnostic Markdown static analyzer & credential scanner[/]",
    ]
    return "\n".join(lines)


def make_report_header(
    version: str,
    *,
    engine: str = "auto",
    docs_count: int = 0,
    assets_count: int = 0,
    elapsed: float = 0.0,
    target: str | None = None,
) -> str:
    """Return the compact Zenzic Report header for ``check all`` output.

    Used by :class:`~zenzic.core.reporter.ZenzicReporter` as the top-of-report
    banner.  Separate from :func:`make_banner` (which is the CLI startup panel).

    Telemetry is unified: *docs_count* (Markdown + engine config files) and
    *assets_count* (images and static files) are shown as a breakdown inside
    the total file count.  This makes the banner's total directly comparable
    to the footer's "files with findings" count.

    When *target* is set (a custom file or directory was passed on the CLI),
    it is shown in the meta line so the user can confirm what is being scanned.
    """
    brand_icon = emoji("brand")
    dot = emoji("dot")
    total = docs_count + assets_count
    parts = [engine]
    if target is not None:
        parts.append(target)
    if total:
        breakdown = (
            f"([{ZenzicPalette.BRAND}]{docs_count}[/] docs, "
            f"[{ZenzicPalette.BRAND}]{assets_count}[/] assets)"
        )
        parts.append(
            f"[{ZenzicPalette.BRAND}]{total}[/] file{'s' if total != 1 else ''} {breakdown}"
        )
    if elapsed:
        parts.append(f"[{ZenzicPalette.BRAND}]{elapsed:.1f}[/]s")
    meta = f" {dot} ".join(parts)
    return (
        f"[{ZenzicPalette.STYLE_BRAND}]{brand_icon}  ZENZIC[/]  "
        f"[{ZenzicPalette.DIM}]v{version}[/]\n"
        f"[{ZenzicPalette.DIM}]{meta}[/]"
    )


# ── ZenzicUI: Centralized UI Bridge ─────────────────────────────────────────


class ZenzicUI:
    """Central UI bridge for all Zenzic CLI output.

    All header, seal, telemetry, and alert panels must go through this interface.
    This ensures consistent Zenzic Frame styling across all commands.
    """

    def __init__(self, console: Any):
        self.console = console

    @staticmethod
    def make_panel(
        content: RenderableType,
        *,
        title: str = "PythonWoods",
        subtitle: str = "Apache-2.0",
        border_style: str | None = None,
    ) -> Panel:
        """Create a canonical Zenzic Frame panel.

        The frame features a left-aligned title, bottom-right subtitle, and an
        Indigo rounded border. Every Zenzic output panel must be created
        through this factory to guarantee visual consistency.
        """
        title_markup = title if "[" in title else f"[{ZenzicPalette.STYLE_BRAND}]{title}[/]"
        return Panel(
            content,
            title=title_markup,
            title_align="left",
            subtitle=f"[{ZenzicPalette.DIM}]{subtitle}[/]",
            subtitle_align="right",
            border_style=border_style if border_style is not None else ZenzicPalette.BRAND,
            box=_rich_box.ROUNDED,
            padding=(1, 2),
        )

    def print_header(self, version: str) -> None:
        """Print the standardized Zenzic banner panel."""
        banner = make_banner(version)
        panel = self.make_panel(banner)
        self.console.print()
        self.console.print(panel)
        self.console.print()

    def print_exception_alert(
        self,
        message: str,
        *,
        context: dict[str, Any] | None = None,
        title: str = "Zenzic Error",
        border_style: str | None = None,
    ) -> None:
        """Render a styled error alert panel for an exception.

        Replaces ad-hoc ``Panel()`` calls in error handlers with a branded,
        consistent layout.  The *border_style* defaults to :data:`ZenzicPalette.ERROR`
        (error); pass ``ZenzicPalette.STYLE_BRAND`` for plugin-contract violations.
        """
        effective_style = border_style if border_style is not None else ZenzicPalette.ERROR
        lines = [message]
        if context:
            lines.append("")
            for k, v in context.items():
                lines.append(f"  [{ZenzicPalette.DIM}]{k}:[/] {v}")
        panel = Panel(
            "\n".join(lines),
            title=f"[{effective_style}]{title}[/]",
            border_style=effective_style,
            box=_rich_box.ROUNDED,
            padding=(0, 1),
        )
        self.console.print(panel)


__all__ = [
    "ZenzicPalette",
    "ZenzicUI",
    "make_banner",
    "make_report_header",
    "emoji",
    "SUPPORTS_COLOR",
    "SUPPORTS_EMOJI",
]
