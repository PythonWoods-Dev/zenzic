# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""HTML tag matching is case-insensitive, and traversal must *land* somewhere.

Two defects with one shape — a check reading raw text and drawing the wrong
conclusion from it.

``_RE_POLY_TAG`` had no ``(?i)``, so ``<A HREF="...">`` matched nothing at all
and the whole polyglot pipeline skipped the tag. HTML tag names are
case-insensitive and Markdown passes raw HTML through, so uppercase markup is
ordinary content — and it bypassed both ``Z203`` (exit 3) and ``Z205`` (exit 2)
completely. The ``.lower()`` on the captured tag name was dead code that
documented the intent the regex never implemented.

``_classify_traversal_intent`` substring-searched the raw href for ``/etc/``,
``/usr/`` and friends, which is true of a genuine attack *and* of
``../../guide/usr/manual.md``. The false positive is the worse half: it raises
a **non-suppressible exit 3** on legitimate documentation, and the security
tier has no escape hatch by design. Traversal is now classified by where the
path *lands* after normalisation, not by what its text contains.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from zenzic.core.validator import _classify_traversal_intent
from zenzic.main import app


_PROSE = "Prose long enough to clear the minimum word-count check comfortably here."


def _run(tmp_path: Path, body: str, extra: list[str] | None = None) -> int:
    (tmp_path / "mkdocs.yml").write_text("site_name: Demo\n", encoding="utf-8")
    (tmp_path / ".zenzic.toml").write_text('docs_dir = "docs"\n', encoding="utf-8")
    docs = tmp_path / "docs"
    docs.mkdir(exist_ok=True)
    for rel in extra or []:
        target = docs / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(f"# T\n\n{_PROSE}\n", encoding="utf-8")
    (docs / "index.md").write_text(f"# P\n\n{_PROSE}\n\n{body}\n", encoding="utf-8")
    return (
        CliRunner()
        .invoke(app, ["check", "all", str(docs), "--no-header", "--quiet"], catch_exceptions=False)
        .exit_code
    )


class TestUppercaseHtmlIsStillHtml:
    @pytest.mark.parametrize("tag", ["a", "A"])
    def test_traversal_is_caught_in_either_case(self, tmp_path: Path, tag: str) -> None:
        attr = "href" if tag == "a" else "HREF"
        body = f'<{tag} {attr}="../../../../etc/passwd">x</{tag}>'
        assert _run(tmp_path, body) == 3, f"<{tag}> traversal escaped the Z203 gate"

    @pytest.mark.parametrize("tag", ["a", "A"])
    def test_forbidden_scheme_is_caught_in_either_case(self, tmp_path: Path, tag: str) -> None:
        attr = "href" if tag == "a" else "HREF"
        body = f'<{tag} {attr}="javascript:alert(1)">x</{tag}>'
        assert _run(tmp_path, body) == 2, f"<{tag}> javascript: escaped the Z205 gate"


class TestTraversalIsClassifiedByWhereItLands:
    """A path containing ``usr`` is not the same as a path *reaching* ``/usr``."""

    @pytest.mark.parametrize(
        "href",
        [
            "../../../../etc/passwd",
            "/etc/passwd",
            "../../../../ETC/PASSWD",  # case: same file on a case-insensitive FS
            "..\\..\\..\\windows\\system32\\config\\sam",  # separator: Windows form
        ],
    )
    def test_real_traversal_is_suspicious(self, href: str) -> None:
        assert _classify_traversal_intent(href) == "suspicious", (
            f"{href!r} lands in a system directory and must be treated as an incident"
        )

    @pytest.mark.parametrize(
        "href",
        [
            "../../guide/usr/manual.md",
            "../../team/var/notes.md",
            "../sibling/etc/config-guide.md",
        ],
    )
    def test_incidental_segment_is_only_a_boundary_crossing(self, href: str) -> None:
        assert _classify_traversal_intent(href) == "boundary", (
            f"{href!r} merely contains a system-directory *name* deeper in the path "
            "and must not raise a non-suppressible exit 3 — the security tier has no "
            "escape hatch by design"
        )

    def test_landing_directly_on_a_system_name_stays_suspicious(self) -> None:
        """The deliberate conservative edge, documented rather than accidental.

        ``../../proc/onboarding/README.md`` *lands* on a directory named ``proc``.
        Without the source file's depth the classifier cannot tell that from an
        escape reaching the real ``/proc``, and it takes only the href by design
        (Zero I/O in the validator hot-path). Flagging is the safe direction
        here, and it is narrow: the segment must be where the path arrives, not
        merely present somewhere in it — which is exactly the distinction that
        stopped ``../../guide/usr/manual.md`` from failing a correct build.
        """
        assert _classify_traversal_intent("../../proc/onboarding/README.md") == "suspicious"

    def test_legitimate_docs_path_does_not_fail_ci(self, tmp_path: Path) -> None:
        """End-to-end: the false positive was the operationally urgent half."""
        code = _run(tmp_path, "[l](./guide/usr/manual.md)", extra=["guide/usr/manual.md"])
        assert code == 0, (
            f"a legitimate docs path containing '/usr/' raised exit {code}; this is "
            "non-suppressible, so it breaks a correct build with no workaround"
        )
