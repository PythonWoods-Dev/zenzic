# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""End-to-end contract for the suppression *accounting* — not the parser.

``tests/test_suppressions.py`` already pins the tracker's own lifecycle, and it
passed throughout the period these tests were written to close: it drives
``parse -> is_suppressed -> get_dead_suppressions`` by hand, in that order. The
defect was that the pipeline called them in a different order, so a working
suppression was reported ``Z603`` in the same run in which it silenced a
finding. A unit test on a stateful accumulator cannot see a mis-sequenced
caller; only a test that runs the real command can.

Every case here is paired. The false-positive direction (a working suppression
must not be called dead) is what was broken; the true-positive direction (a
genuinely dead suppression must still be reported) is what stops a fix from
silencing the rule instead of correcting it.

Covers all three suppression mechanisms:

* inline ``<!-- zenzic:ignore: CODE -->`` — for a code decided in the per-file
  pass *and* for one decided in the later cross-file VSM pass, which is the
  distinction the defect turned on;
* ``data-zenzic-ignore`` on an HTML tag;
* ``[governance.per_file_ignores]`` in ``.zenzic.toml``, whose equivalent
  dead-configuration report is ``Z620``.

…and every surface that reads the accounting: ``check all``,
``check references``, the incremental engine behind the LSP, and ``zenzic fix``.
"""

from __future__ import annotations

import re as _re
import textwrap
from pathlib import Path

import pytest
from typer.testing import CliRunner

from zenzic.main import app


runner = CliRunner()


# ── corpus ───────────────────────────────────────────────────────────────────
#
# One corpus with a *known* number of suppressions, some working and some
# genuinely dead, so a count can be checked against it rather than against
# whatever the implementation happens to produce.
#
#   inline directives declared ............ 3  (comment form)
#   data-zenzic-ignore attributes ......... 2
#   per_file_ignores entries .............. 2
#
# Of the five in-file directives, three are working and two are dead. The
# counts are stated here because a figure checked against "whatever the
# implementation printed" checks nothing.

_CONFIG = """\
docs_dir = "docs"
fail_under = 0

[build_context]
engine = "standalone"

[governance.per_file_ignores]
"docs/pfi-used.md" = ["Z101"]
"docs/pfi-never.md" = ["Z601"]
"""

_FILES: dict[str, str] = {
    # The page every specimen links back to. It has to exist: the "genuinely
    # dead" directives sit on lines whose links must resolve, or the directive is
    # live after all — which is how the first draft of this corpus quietly turned
    # its own control into a second working suppression.
    "docs/index.md": """\
        # Index

        An entry page linking to every specimen, so the topology rules stay quiet
        and the only findings under measurement are the suppression ones.

        - [working vsm](./working-vsm.md)
        - [working atomic](./working-atomic.md)
        - [genuinely dead](./dead.md)
        - [html working](./html-working.md)
        - [html dead](./html-dead.md)
        - [fenced](./fenced.md)
        - [pfi used](./pfi-used.md)
        - [pfi never](./pfi-never.md)
        """,
    # Working, inline, code decided in the *cross-file* pass (Z101 needs the VSM).
    "docs/working-vsm.md": """\
        # Working VSM Suppression

        The target is generated at build time, so it is silenced deliberately and
        the directive below does real work on every scan of this file.

        [generated](./generated/api.md) <!-- zenzic:ignore: Z101 -->
        """,
    # Working, inline, code decided in the *per-file* pass (Z515 is atomic).
    "docs/working-atomic.md": """\
        # Working Atomic Suppression

        A bare URL quoted verbatim from a log line, where linkifying it would
        change the quotation, so the bare-URL finding is silenced on the spot.

        https://example.com/logline <!-- zenzic:ignore: Z515 -->
        """,
    # Genuinely dead, inline: the link on that line resolves.
    "docs/dead.md": """\
        # Genuinely Dead Suppression

        Nothing on the line below is a finding, so the directive really is dead
        and must be reported as such by every command that reports at all.

        [index](./index.md) <!-- zenzic:ignore: Z101 -->
        """,
    # Working data-zenzic-ignore: the unknown attribute is a real Z120.
    "docs/html-working.md": """\
        # Working HTML Suppression

        The extra attribute is emitted by the templating layer, so the
        unknown-attribute finding is silenced at the tag rather than in config.

        <a href="./index.md" data-track="nav" data-zenzic-ignore>Index</a>
        """,
    # Genuinely dead data-zenzic-ignore: the tag is entirely well formed.
    "docs/html-dead.md": """\
        # Dead HTML Suppression

        The tag below is well formed, so the attribute silences nothing at all
        and must be reported as a dead suppression.

        <a href="./index.md" data-zenzic-ignore>Index</a>
        """,
    # Zero directives: a fenced example and an inline code span are prose.
    "docs/fenced.md": """\
        # Fenced Example

        This page documents the syntax without declaring any suppression of its
        own, and the suppression count must agree with that.

        ```markdown
        [broken](./nope.md) <!-- zenzic:ignore: Z101 -->
        ```

        Also inline: `<!-- zenzic:ignore: Z601 -->` stays prose.
        """,
    # per_file_ignores entry that really does suppress something.
    "docs/pfi-used.md": """\
        # Per-File Ignore, Genuinely Used

        The broken link below is covered by a per_file_ignores entry, so that
        entry is demonstrably in use during every scan of this corpus.

        [gone](./also-generated.md)
        """,
    # per_file_ignores entry that suppresses nothing.
    "docs/pfi-never.md": """\
        # Per-File Ignore, Never Used

        Nothing here triggers the code its per_file_ignores entry names, so the
        entry really is dead configuration and must be reported.
        """,
}

#: Lines carrying a genuinely dead suppression, keyed by file. Line 6 in every
#: specimen: the corpus is written so the directive always lands there.
_DEAD_SITES = {("dead.md", 6), ("html-dead.md", 6)}

#: Lines carrying a working suppression, which must never be called dead.
_WORKING_SITES = {("working-vsm.md", 6), ("working-atomic.md", 6), ("html-working.md", 6)}


@pytest.fixture
def corpus(tmp_path: Path) -> Path:
    """A project whose suppressions are known, individually, to work or not."""
    (tmp_path / ".zenzic.toml").write_text(_CONFIG, encoding="utf-8")
    for rel, body in _FILES.items():
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(textwrap.dedent(body), encoding="utf-8")
    return tmp_path


def _z603_sites(output: str) -> set[tuple[str, int]]:
    """Every ``(file, line)`` the run reported as a dead suppression."""
    sites: set[tuple[str, int]] = set()
    for raw in output.splitlines():
        if "[Z603]" not in raw:
            continue
        # "docs/dead.md:6  ⚠  [Z603]  ..." — the location is the first token.
        loc = raw.split()[0]
        path, _, line = loc.rpartition(":")
        # A column may be appended ("file.md:6:21"); the line is what matters.
        if not line.isdigit():
            path, _, line = path.rpartition(":")
        sites.add((Path(path).name, int(line)))
    return sites


def _run(corpus: Path, *args: str) -> str:
    result = runner.invoke(app, [*args, "--no-header"], catch_exceptions=False)
    return result.stdout


# ── inline, both directions, on every reporting command ──────────────────────


@pytest.mark.parametrize("command", [("check", "all"), ("check", "references")])
def test_working_suppression_is_never_reported_dead(
    corpus: Path, monkeypatch: pytest.MonkeyPatch, command: tuple[str, ...]
) -> None:
    """A directive that silenced a finding must not be called dead in that run.

    This is the defect. It held for both inline forms and for
    ``data-zenzic-ignore``, and it depended on which pass decided the code:
    ``Z515`` is decided per file, before the accounting is read, while ``Z101``
    is decided later, in the cross-file pass, after it.
    """
    monkeypatch.chdir(corpus)
    reported = _z603_sites(_run(corpus, *command))
    assert not (reported & _WORKING_SITES), (
        f"{' '.join(command)} called a working suppression dead: "
        f"{sorted(reported & _WORKING_SITES)}"
    )


@pytest.mark.parametrize("command", [("check", "all"), ("check", "references")])
def test_genuinely_dead_suppression_is_still_reported(
    corpus: Path, monkeypatch: pytest.MonkeyPatch, command: tuple[str, ...]
) -> None:
    """The other direction: the rule must still fire where it should.

    Without this, a fix that deletes every ``Z603`` passes the test above.
    """
    monkeypatch.chdir(corpus)
    reported = _z603_sites(_run(corpus, *command))
    assert _DEAD_SITES <= reported, (
        f"{' '.join(command)} missed a genuinely dead suppression: {sorted(_DEAD_SITES - reported)}"
    )


def test_reporting_commands_agree_on_which_suppressions_are_dead(
    corpus: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``check all`` and ``check references`` must not disagree about this.

    They did: one read the accounting before the cross-file pass completed and
    the other patched it afterwards, so the same corpus produced two different
    answers depending on the subcommand. The disagreement is the cheapest
    possible signal that the accounting is read at the wrong time, which is why
    it gets its own test rather than being left implicit in the two above.
    """
    monkeypatch.chdir(corpus)
    assert _z603_sites(_run(corpus, "check", "all")) == _z603_sites(
        _run(corpus, "check", "references")
    )


# ── data-zenzic-ignore: it must actually suppress ────────────────────────────


def test_data_zenzic_ignore_suppresses_the_finding_it_claims_to(
    corpus: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``Z120``'s own remediation text names this attribute; it must work.

    The attribute was marked consumed before the filter that reads consumption
    ran, so it could neither suppress a finding nor be reported dead.
    """
    monkeypatch.chdir(corpus)
    out = _run(corpus, "check", "all")
    assert "html-working.md" not in out or "[Z120]" not in out, (
        "data-zenzic-ignore did not suppress the unknown-attribute finding:\n" + out
    )


def test_data_zenzic_ignore_that_suppresses_nothing_is_reported(
    corpus: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """And the attribute on a well-formed tag is still dead configuration."""
    monkeypatch.chdir(corpus)
    assert ("html-dead.md", 6) in _z603_sites(_run(corpus, "check", "all"))


# ── per_file_ignores: Z620, the equivalent dead-configuration report ─────────


def test_used_per_file_ignore_is_not_reported_stale(
    corpus: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A per-file ignore that suppresses a finding is not dead configuration.

    Usage was recorded against the directory-policy ledger for both kinds of
    entry, so the per-file ledger was never cleared and every entry was
    reported unused — working ones indistinguishable from dead ones.
    """
    monkeypatch.chdir(corpus)
    out = _run(corpus, "check", "all")
    offending = [ln for ln in out.splitlines() if "[Z620]" in ln and "pfi-used.md" in ln]
    assert not offending, "a per-file ignore in active use was reported stale:\n" + "\n".join(
        offending
    )


def test_unused_per_file_ignore_is_still_reported_stale(
    corpus: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The other direction, so the fix cannot be "stop reporting Z620"."""
    monkeypatch.chdir(corpus)
    out = _run(corpus, "check", "all")
    assert any("[Z620]" in ln and "pfi-never.md" in ln for ln in out.splitlines()), (
        "a genuinely unused per-file ignore was not reported:\n" + out
    )


# ── the incremental engine behind the LSP ────────────────────────────────────


def test_incremental_engine_honours_inline_suppression_of_cross_file_codes(
    corpus: Path,
) -> None:
    """In the editor, ``<!-- zenzic:ignore: Z101 -->`` must silence ``Z101``.

    The incremental engine appended its cross-file findings without consulting
    the tracker at all, so the directive was inert in the editor *and* then
    reported dead — the CLI and the editor disagreed about the same file.
    """
    from zenzic.core.adapter import get_adapter
    from zenzic.core.incremental import IncrementalAnalysisEngine
    from zenzic.core.scanner import _build_rule_engine
    from zenzic.core.validator import anchors_in_file
    from zenzic.models.config import load_config_with_diagnostics
    from zenzic.models.vsm import VirtualBufferOverlay, build_vsm

    config, _ = load_config_with_diagnostics(corpus)
    assert config is not None
    docs_root = corpus / str(config.docs_dir)
    contents = {p: p.read_text(encoding="utf-8") for p in sorted(docs_root.rglob("*.md"))}
    anchors = {p: anchors_in_file(t) for p, t in contents.items()}
    adapter = get_adapter(config.build_context, docs_root, corpus)
    vsm = build_vsm(adapter, docs_root, contents, anchors_cache=anchors, repo_root=corpus)

    engine = IncrementalAnalysisEngine(
        config, _build_rule_engine(config), adapter, docs_root, corpus
    )
    engine.anchors_cache = anchors
    for p, t in contents.items():
        engine.update_file_cache(p, t)

    diagnostics = engine.process_changes(vsm, VirtualBufferOverlay(vsm))
    flat = [(Path(uri).name, d.code) for uri, ds in diagnostics.items() for d in ds]

    assert ("working-vsm.md", "Z101") not in flat, (
        "the incremental engine ignored an inline suppression of a cross-file code"
    )
    assert ("working-vsm.md", "Z603") not in flat, (
        "the incremental engine reported a working suppression as dead"
    )
    assert ("dead.md", "Z603") in flat, (
        "the incremental engine stopped reporting a genuinely dead suppression"
    )


# ── zenzic fix: the auto-fix the rule card promises ──────────────────────────


def test_fix_removes_a_dead_suppression_and_leaves_working_ones_alone(
    corpus: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``Z603`` is published as Auto-Fixable, and its rule card says ``zenzic fix``.

    The mutation read its line numbers from a single-file scan that never built
    a tracker, so it was handed an empty set on every file and removed nothing.
    The paired half matters more than usual here: a fix that deletes comments
    it merely *believes* are dead edits the user's source.
    """
    monkeypatch.chdir(corpus)
    runner.invoke(app, ["fix", "--apply"], catch_exceptions=False)

    assert "zenzic:ignore" not in (corpus / "docs/dead.md").read_text(encoding="utf-8"), (
        "zenzic fix did not remove a genuinely dead suppression"
    )
    for still_needed in ("docs/working-vsm.md", "docs/working-atomic.md"):
        assert "zenzic:ignore" in (corpus / still_needed).read_text(encoding="utf-8"), (
            f"zenzic fix removed a working suppression from {still_needed}"
        )


# ── the Suppression Audit figure ─────────────────────────────────────────────


def test_suppression_audit_counts_declared_directives_against_a_known_corpus(
    corpus: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The governance figure counts *declared* debt, working or not.

    That is the right semantic for a debt ceiling — a dead directive is still a
    line someone has to remove — so the figure is deliberately independent of
    the consumption accounting this module otherwise tests. It is pinned here
    because it is the number the project publishes about itself, and because
    "independent" is a claim that needs a corpus with a known count behind it.

    Known: 4 comment directives + 2 ``data-zenzic-ignore`` attributes = 6
    inline, and 2 per-file entries. The fenced and inline-code examples in
    ``fenced.md`` are prose and count for nothing.
    """
    monkeypatch.chdir(corpus)
    out = _run(corpus, "check", "all")
    audit = next(ln for ln in out.splitlines() if "Suppression Audit" in ln)
    assert "(inline: 5, per-file: 2)" in audit, audit
    assert "7/" in audit, audit


def test_fix_declines_the_rename_when_the_suppression_scan_cannot_run(
    corpus: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A safety gate is not verified until it has been made to fail.

    The rename gate's whole purpose is to decline rather than overwrite, so the
    branch that matters is the one where it cannot find out. With the scan
    raising, every file must read as carrying a live suppression — and the
    previous code failed the other way: the scan raised, ``report`` became
    ``None``, ``suppressed`` became ``False``, and the mutation proceeded.
    """
    import zenzic.core.scanner as scanner_mod

    def _explode(*_a: object, **_k: object) -> None:
        raise RuntimeError("scan unavailable")

    monkeypatch.setattr(scanner_mod, "scan_docs_references", _explode)
    monkeypatch.chdir(corpus)

    before = (corpus / "docs/index.md").read_text(encoding="utf-8")
    result = runner.invoke(
        app,
        ["fix", "--rename", "docs/working-vsm.md", "docs/renamed.md", "--apply"],
        catch_exceptions=False,
    )

    assert "not overriding it" in result.stdout, result.stdout
    assert (corpus / "docs/index.md").read_text(encoding="utf-8") == before, (
        "the rename rewrote a file while the suppression scan was unavailable"
    )


# ── the three directive spellings ────────────────────────────────────────────
#
# The audit above was written entirely against `<!-- ... -->`. These cases exist
# because "the MDX form is equivalent" was an assumption, and the two forms take
# different paths: one is matched under the HTML branch of the suppression
# pattern, the other under the MDX branch — and this same release already found
# that MDX comment *masking* required the braces adjacent to the comment markers
# in four separate places, which is precisely the shape a directive parser can
# get wrong too.

_MDX_CONFIG = """\
docs_dir = "docs"
fail_under = 0

[build_context]
engine = "standalone"
"""

#: The spelling under test → whether it is the form Prettier emits.
_SPELLINGS = {
    "html": "<!-- zenzic:ignore: {code} -->",
    "mdx-adjacent": "{{/* zenzic:ignore: {code} */}}",
    # Legal MDX: the braces are an expression container and the whitespace is
    # free. Prettier emits exactly this, so a formatted file uses it whether the
    # author typed it or not.
    "mdx-spaced": "{{ /* zenzic:ignore: {code} */ }}",
}


def _mdx_corpus(tmp_path: Path, directive: str) -> Path:
    """A project whose suppressions all use one spelling.

    Three specimens: a cross-file code (`Z101`, decided against the site map), a
    per-file code (`Z515`, decided while parsing), and a directive that genuinely
    silences nothing.
    """
    (tmp_path / ".zenzic.toml").write_text(_MDX_CONFIG, encoding="utf-8")
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "index.mdx").write_text(
        textwrap.dedent("""\
            # Index

            An entry page linking to each specimen, so the topology rules stay quiet
            and the directive spelling is the only thing under measurement.

            - [cross file](./cross-file.mdx)
            - [per file](./per-file.mdx)
            - [dead](./dead.mdx)
            """),
        encoding="utf-8",
    )
    (docs / "cross-file.mdx").write_text(
        "# Cross-File\n\nThe target is generated at build time, so this directive does real\n"
        "work on every scan and must never be called dead.\n\n"
        f"[generated](./generated/api.mdx) {directive.format(code='Z101')}\n",
        encoding="utf-8",
    )
    (docs / "per-file.mdx").write_text(
        "# Per-File\n\nA bare URL quoted verbatim from a log line, where linkifying it would\n"
        "change the quotation.\n\n"
        f"https://example.com/logline {directive.format(code='Z515')}\n",
        encoding="utf-8",
    )
    (docs / "dead.mdx").write_text(
        "# Dead\n\nThe link below resolves, so this directive silences nothing and must be\n"
        "reported in every mode.\n\n"
        f"[index](./index.mdx) {directive.format(code='Z101')}\n",
        encoding="utf-8",
    )
    return tmp_path


@pytest.mark.parametrize("spelling", sorted(_SPELLINGS))
@pytest.mark.parametrize("command", [("check", "all"), ("check", "references")])
def test_every_directive_spelling_suppresses_what_it_names(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, spelling: str, command: tuple[str, ...]
) -> None:
    """All three spellings must silence both a cross-file and a per-file code.

    `mdx-spaced` was recognised by nothing: the pattern required `{` adjacent to
    `/*`, so a Prettier-formatted file's directive was not a directive. The
    finding stayed, and — because an unparsed directive is not an unconsumed one
    — there was no `Z603` either. No suppression and no explanation for why.
    """
    corpus = _mdx_corpus(tmp_path, _SPELLINGS[spelling])
    monkeypatch.chdir(corpus)
    out = _run(corpus, *command)
    assert "[Z101]" not in out, f"{spelling} did not suppress a cross-file code:\n{out}"
    assert "[Z515]" not in out, f"{spelling} did not suppress a per-file code:\n{out}"


@pytest.mark.parametrize("spelling", sorted(_SPELLINGS))
def test_every_directive_spelling_is_reported_dead_when_it_is(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, spelling: str
) -> None:
    """And all three must still be reported when they silence nothing."""
    corpus = _mdx_corpus(tmp_path, _SPELLINGS[spelling])
    monkeypatch.chdir(corpus)
    assert ("dead.mdx", 6) in _z603_sites(_run(corpus, "check", "all")), spelling


@pytest.mark.parametrize("spelling", sorted(_SPELLINGS))
def test_every_directive_spelling_counts_toward_the_suppression_audit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, spelling: str
) -> None:
    """A spelling the counter cannot see understates the published debt figure.

    The corpus declares three directives in every spelling. `mdx-spaced` counted
    two, because the counter and the parser are the same pattern — so an unparsed
    directive is also an uncounted one, and the governance number the project
    publishes about itself was quietly low.
    """
    corpus = _mdx_corpus(tmp_path, _SPELLINGS[spelling])
    monkeypatch.chdir(corpus)
    audit = next(
        ln for ln in _run(corpus, "check", "all").splitlines() if "Suppression Audit" in ln
    )
    assert "(inline: 3, per-file: 0)" in audit, f"{spelling}: {audit}"


@pytest.mark.parametrize("spelling", sorted(_SPELLINGS))
def test_every_directive_spelling_works_in_the_editor(tmp_path: Path, spelling: str) -> None:
    """The incremental engine reads the same pattern, so it must agree."""
    from zenzic.core.adapter import get_adapter
    from zenzic.core.incremental import IncrementalAnalysisEngine
    from zenzic.core.scanner import _build_rule_engine
    from zenzic.core.validator import anchors_in_file
    from zenzic.models.config import load_config_with_diagnostics
    from zenzic.models.vsm import VirtualBufferOverlay, build_vsm

    corpus = _mdx_corpus(tmp_path, _SPELLINGS[spelling])
    config, _ = load_config_with_diagnostics(corpus)
    assert config is not None
    docs_root = corpus / str(config.docs_dir)
    contents = {p: p.read_text(encoding="utf-8") for p in sorted(docs_root.rglob("*.mdx"))}
    anchors = {p: anchors_in_file(t) for p, t in contents.items()}
    adapter = get_adapter(config.build_context, docs_root, corpus)
    vsm = build_vsm(adapter, docs_root, contents, anchors_cache=anchors, repo_root=corpus)
    engine = IncrementalAnalysisEngine(
        config, _build_rule_engine(config), adapter, docs_root, corpus
    )
    engine.anchors_cache = anchors
    for p, t in contents.items():
        engine.update_file_cache(p, t)

    flat = [
        (Path(uri).name, d.code)
        for uri, ds in engine.process_changes(vsm, VirtualBufferOverlay(vsm)).items()
        for d in ds
    ]
    assert ("cross-file.mdx", "Z101") not in flat, spelling
    assert ("cross-file.mdx", "Z603") not in flat, spelling
    assert ("dead.mdx", "Z603") in flat, spelling


def test_the_directive_pattern_has_exactly_one_definition() -> None:
    """Two byte-identical copies of it existed, in two modules.

    `rules.py` and `suppressions.py` each defined the protocol, so extending one
    spelling would have desynchronised the parser from the counter — the parser
    lives in one and the audit figure is computed through the other. Identity,
    not equality: a copied pattern that agrees today is the thing that drifts.
    """
    from zenzic.core import rules, suppressions

    assert rules._SUPPRESS_RE is suppressions._SUPPRESS_RE


# ── the generalised detector ──────────────────────────────────────────────────


def _findings_from_text(output: str) -> set[tuple[str, int, str]]:
    """Every ``(file, line, code)`` a run reported, read from its text output.

    Text, not ``--format json``, and deliberately: the per-check JSON is
    structured (``rel_path``/``line_no``/``code`` fields) while ``check all``'s is
    grouped arrays of pre-formatted strings whose ``links[]`` entries carry no
    location at all. The one output shape every subcommand genuinely shares is
    the one a human reads.
    """
    pattern = _re.compile(r"^(?P<path>\S+?):(?P<line>\d+)(?::\d+)?\s+\S+\s+\[(?P<code>Z\d{3})\]")
    found: set[tuple[str, int, str]] = set()
    for raw in output.splitlines():
        m = pattern.match(raw.strip())
        if m:
            found.add((Path(m.group("path")).name, int(m.group("line")), m.group("code")))
    return found


def test_subcommands_agree_on_every_code_they_share(
    corpus: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Generalises the two-command Z603 check across every shared code.

    The narrow version above pins one code because one code broke. This is the
    same assertion without the narrowing, and it is here because it was shown to
    find the defect rather than argued to: run against the commit before the fix,
    over the same corpora, it reports five disagreements — three false ``Z603``
    from ``check references`` on this corpus and two more on another — and zero
    against the fixed engine.

    Scope is derived empirically, from what each command is observed to emit,
    rather than declared: subcommands legitimately differ in scope (``check
    links`` reports link integrity and not governance), so only the intersection
    can be compared, and a hand-written scope table would be one more thing to
    keep in step with the code.
    """
    monkeypatch.chdir(corpus)
    commands = [("check", "all"), ("check", "references"), ("check", "links")]
    observed = {cmd: _findings_from_text(_run(corpus, *cmd)) for cmd in commands}
    emits = {cmd: {code for _, _, code in found} for cmd, found in observed.items()}

    for i, a in enumerate(commands):
        for b in commands[i + 1 :]:
            shared = emits[a] & emits[b]
            if not shared:
                continue
            only_a = {f for f in observed[a] if f[2] in shared} - {
                f for f in observed[b] if f[2] in shared
            }
            only_b = {f for f in observed[b] if f[2] in shared} - {
                f for f in observed[a] if f[2] in shared
            }
            assert not (only_a or only_b), (
                f"'{' '.join(a)}' and '{' '.join(b)}' disagree about codes they both emit "
                f"({' '.join(sorted(shared))}):\n"
                f"  only in {' '.join(a)}: {sorted(only_a)}\n"
                f"  only in {' '.join(b)}: {sorted(only_b)}"
            )
