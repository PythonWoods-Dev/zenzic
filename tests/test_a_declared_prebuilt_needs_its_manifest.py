# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""A declared `prebuilt` with no manifest fails at configuration, everywhere.

**The declaration had no effect.** Measured on Astro's own documentation —
2,604 pages, one commit, three configurations — `prebuilt` without a manifest
and `standalone` declared outright produced the *same total, the same
distribution and the same exit code*. 98% of those 15,254 findings came from
three codes, all derived from routing that was never resolved: the engine the
user asked for did not run, and the only signal was a notice on stderr, which no
CI consumer reads.

That is the shape `Z111` closed for a missing `docs_dir` and `Z906` was
corrected on in the same week: a run that did not do what it was asked,
reporting as though it had.

The separation holds. A manifest that **exists** and is empty is a generator
that published nothing — a different statement, which produces `Z115` per
source rather than this error.

Every surface, because an action that fails differently from the CLI for the
same condition is two products.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import jsonschema
import pytest


_SCHEMA = Path(__file__).resolve().parent / "fixtures" / "sarif-2.1.0-schema.json"


@pytest.fixture
def astro_without_manifest(tmp_path: Path) -> Path:
    docs = tmp_path / "src" / "content" / "docs"
    docs.mkdir(parents=True)
    (docs / "index.md").write_text("# Home\n\n" + " ".join(["word"] * 60) + "\n", encoding="utf-8")
    (tmp_path / "astro.config.mjs").write_text("export default {};\n", encoding="utf-8")
    (tmp_path / ".zenzic.toml").write_text(
        'docs_dir = "src/content/docs"\n\n[build_context]\nengine = "prebuilt"\n', encoding="utf-8"
    )
    subprocess.run(["git", "init", "-q", "."], cwd=tmp_path, check=True)  # noqa: S607
    return tmp_path


def _run(project: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603
        [sys.executable, "-m", "zenzic.main", *args],
        cwd=project,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        env={**os.environ, "NO_COLOR": "1"},
    )


@pytest.mark.parametrize(
    "command", [["check", "all"], ["audit"], ["guard", "scan"]], ids=["check", "audit", "guard"]
)
def test_every_command_refuses(astro_without_manifest: Path, command: list[str]) -> None:
    out = _run(astro_without_manifest, *command)

    assert out.returncode == 1, f"exit {out.returncode}\n{out.stdout}\n{out.stderr}"
    assert "Z111" in (out.stdout + out.stderr)


def test_the_message_names_the_generator_and_how_to_generate_it(
    astro_without_manifest: Path,
) -> None:
    """`Z111`'s message is the model: name what was detected and what it expects,
    rather than offering a menu."""
    out = _run(astro_without_manifest, "check", "all")
    combined = out.stdout + out.stderr

    assert "astro.config.mjs" in combined
    assert "Astro" in combined
    assert "positional" in combined, "the message does not say how the manifest is derived"
    assert "configure-adapter" in combined, "the message does not point at the page"
    assert 'engine = "standalone"' in combined, "the message does not name the way out"


def test_it_fails_before_a_single_page_is_read(astro_without_manifest: Path) -> None:
    """The user never sees the findings of an engine they did not ask for.

    The substitution notice is what a run prints *while* analysing with the
    replacement. Its absence is how we know nothing was analysed.
    """
    out = _run(astro_without_manifest, "check", "all")

    assert "found no route manifest" not in out.stderr, (
        "the run announced the substitution it then refused to make"
    )
    assert "files/s" not in out.stdout, "a telemetry line means pages were scanned"


def test_the_machine_formats_explain_rather_than_going_quiet(
    astro_without_manifest: Path,
) -> None:
    """A consumer receiving an empty payload with no explanation is the silence
    this closes.

    The SARIF carries the failure twice on purpose: as a tool notification,
    which is the correct idiom, and as a `result`, because GitHub code scanning
    surfaces only `result`/`location`/`reportingDescriptor` and a handful of
    others — `toolExecutionNotifications` is not among them, verified against
    GitHub's own SARIF support page.
    """
    payload = json.loads(_run(astro_without_manifest, "check", "all", "--format", "json").stdout)
    assert payload["code"] == "Z111", (
        f"the payload reports {payload['code']!r} beside a message reading [Z111] — "
        "a contract contradicting itself, and the payload is what the wrapper reads"
    )
    assert "Z111" in payload["message"]

    sarif_run = _run(astro_without_manifest, "check", "all", "--format", "sarif")
    sarif = json.loads(sarif_run.stdout)
    jsonschema.validate(instance=sarif, schema=json.loads(_SCHEMA.read_text(encoding="utf-8")))

    run = sarif["runs"][0]
    assert run["invocations"][0]["executionSuccessful"] is False
    assert [r["ruleId"] for r in run["results"]] == ["Z111"], (
        "GitHub renders a run with no results as an empty analysis, whatever the notifications say"
    )
    assert "Z111" in {rule["id"] for rule in run["tool"]["driver"]["rules"]}

    # And the step log, which is stderr, carries the same sentence — otherwise
    # the action fails silently while the CLI explains itself.
    assert "Z111" in sarif_run.stderr
    json.loads(sarif_run.stdout)  # the payload itself stays pure


def test_a_manifest_that_exists_is_not_this_error(tmp_path: Path) -> None:
    """The other half of the separation. An empty manifest is a generator that
    published nothing, which is `Z115` per source, not a configuration error."""
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "index.md").write_text("# Home\n\n" + " ".join(["word"] * 60) + "\n", encoding="utf-8")
    (tmp_path / ".zenzic-vsm.json").write_text("{}", encoding="utf-8")
    (tmp_path / ".zenzic.toml").write_text(
        'docs_dir = "docs"\n\n[build_context]\nengine = "prebuilt"\n', encoding="utf-8"
    )
    subprocess.run(["git", "init", "-q", "."], cwd=tmp_path, check=True)  # noqa: S607

    out = _run(tmp_path, "check", "all")

    assert "Z111" not in out.stdout + out.stderr
    assert "Z115" in out.stdout


def test_the_editor_says_it_and_keeps_working(astro_without_manifest: Path) -> None:
    """The language server has no channel to fail through.

    Driven through `LanguageServer`, not `IncrementalAnalysisEngine`.

    It built the engine directly until 2026-09-21, and that is why it could not
    see the defect it is written to cover. The server resolves the container
    vocabulary *before* the engine exists, and that resolution builds an
    adapter too: a declared `zensical` with no `zensical.toml` raised there and
    the session published nothing at all, while this test went green against an
    engine handed a working adapter. An editor test that never starts the
    editor asserts the half that was never in doubt.

    It reads what was published rather than the site map, because the
    configuration diagnostic is attached to `.zenzic.toml`, which is not a
    route.
    """
    import io
    import json

    from zenzic.lsp.server import LanguageServer

    project = astro_without_manifest
    server = LanguageServer()
    server.stdout = io.BytesIO()
    server.repo_root = project
    server._sync_workspace_and_publish()

    raw = server.stdout.getvalue().decode("utf-8")
    codes: set[str] = set()
    while True:
        head = raw.find("\r\n\r\n")
        if head == -1:
            break
        length = 0
        for line in raw[:head].split("\r\n"):
            if line.lower().startswith("content-length:"):
                length = int(line.split(":", 1)[1])
        message = json.loads(raw[head + 4 : head + 4 + length])
        raw = raw[head + 4 + length :]
        if message.get("method") == "textDocument/publishDiagnostics":
            codes.update(d["code"] for d in message["params"]["diagnostics"])

    assert "Z111" in codes, f"the editor stayed silent; codes were {sorted(codes)}"
