# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0

import os

import nox


nox.options.reuse_existing_virtualenvs = True
nox.options.default_venv_backend = "uv"

# Nox = isolated environments for multi-version compatibility (3.10 – 3.14).
# Daily quality gate is `just verify` (single entry-point — see justfile).
# NOTE: posargs are forwarded with `--`, e.g.: nox -s lint -- --fix
nox.options.sessions = ["lint", "format", "typecheck"]

# Boundary Testing: mirrors the CI Pillar Matrix (Floor 3.10 / Peak 3.14).
# Intermediate versions are covered by the full nox-all run in release cycles.
PYTHONS = ["3.10", "3.14"]

# Per-group sync tuples — each session installs only what it needs.
_SYNC_TEST = ("uv", "sync", "--active", "--group", "test")
_SYNC_LINT = ("uv", "sync", "--active", "--group", "lint")


@nox.session(python=PYTHONS)
def tests(session: nox.Session) -> None:
    """Run the test suite with branch coverage across all supported Python versions."""
    session.run(*_SYNC_TEST, external=True)
    session.run(
        "pytest",
        "--cov=src/zenzic",
        "--cov-report=term-missing",
        "--cov-report=json:coverage.json",
        *session.posargs,
        env={"HYPOTHESIS_PROFILE": os.environ.get("HYPOTHESIS_PROFILE", "ci")},
    )


@nox.session(python="3.14")
def lint(session: nox.Session) -> None:
    """Run ruff linting checks.

    Read-only by default (used in CI). To auto-fix: nox -s lint -- --fix
    """
    session.run(*_SYNC_LINT, external=True)
    session.run("ruff", "check", *session.posargs, "src/", "tests/")


@nox.session(python="3.14")
def format(session: nox.Session) -> None:  # noqa: A001
    """Check code formatting with ruff (read-only, used in CI)."""
    session.run(*_SYNC_LINT, external=True)
    session.run("ruff", "format", "--check", "src/", "tests/")


@nox.session(python="3.14")
def fmt(session: nox.Session) -> None:
    """Auto-format code with ruff in place (use during development)."""
    session.run(*_SYNC_LINT, external=True)
    session.run("ruff", "format", "src/", "tests/")


@nox.session(python="3.14")
def typecheck(session: nox.Session) -> None:
    """Run static type checking with mypy."""
    session.run(*_SYNC_LINT, external=True)
    session.run("mypy", "src/")


@nox.session(python="3.14")
def reuse(session: nox.Session) -> None:
    """Verify REUSE/SPDX license compliance."""
    session.run(*_SYNC_LINT, external=True)
    session.run("reuse", "lint")


@nox.session(python="3.14")
def security(session: nox.Session) -> None:
    """Audit third-party dependencies for known CVEs with pip-audit."""
    session.install("pip-audit")
    req = os.path.join(session.create_tmp(), "requirements.txt")
    session.run(
        "uv",
        "export",
        "--no-emit-project",
        "--frozen",
        "--no-hashes",
        "-o",
        req,
        external=True,
    )
    session.run(
        "pip-audit",
        "--strict",
        "-r",
        req,
        # CVE-2026-3219: pip mishandles polyglot (tar+ZIP) archives, treating
        # them as ZIP regardless of filename.  Attack requires a malicious
        # archive already present on disk or fetched from a compromised index.
        # Zenzic uses uv for all package management; pip is a transitive
        # dev-only dependency of pip-audit itself and never installs packages
        # programmatically.  All packages are pinned via uv.lock.
        # No patched pip release exists on PyPI yet.
        # Remove this exemption once pip ships a fix.
        "--ignore-vuln",
        "CVE-2026-3219",
        # CVE-2026-4539: ReDoS in Pygments AdlLexer (archetype.py).
        # Attack vector is LOCAL-only (crafted .adl file); Zenzic does not
        # process ADL input and uses Pygments only for documentation syntax
        # highlighting.  No patched release exists on PyPI yet.
        # Remove this exemption once pygments>=2.19.3 (or equivalent) ships.
        "--ignore-vuln",
        "CVE-2026-4539",
    )


@nox.session(python="3.14")
def mutation(session: nox.Session) -> None:
    """Run mutation testing with mutmut on the credential scanner.

    Target (configured as ``source_paths`` in ``[tool.mutmut]``, ``pyproject.toml``):
    - ``src/zenzic/core/credentials.py``   — secret detection (ZRT-001/ZRT-003)

    A surviving mutant means a test gap.  Target: mutation score >= 90%; measured 68.2%
    as of 2026-09-05 (285 killed / 133 survived / 0 uncovered on the credential scanner).

    This session computes no floor and fails on nothing.  CI runs ``just mutation``
    instead, which reads mutmut's own stats export and fails below a recorded floor.

    Implementation note — non-editable install:
        ``uv sync`` installs zenzic as an editable package whose ``.pth`` file
        points Python directly to the original ``src/`` tree.  This bypasses
        mutmut's mutation injection, which modifies a *copy* of the source
        files inside ``mutants/``.  The ``uv pip install --no-editable`` step
        below switches to a static install so that the mutations are visible to
        pytest during each test run.  The sync step is still needed first to
        resolve and install all transitive test dependencies.
    """
    session.run(*_SYNC_TEST, external=True)
    # Reinstall as non-editable so that mutmut's source injection is visible
    # to pytest (editable .pth files would bypass the mutated copy in mutants/).
    # Note: 'uv pip install .' (without --editable) installs the built wheel,
    # which is non-editable by default.
    session.run("uv", "pip", "install", ".", external=True)
    session.run(
        "mutmut",
        "run",
        *session.posargs,
    )
    session.run("mutmut", "results")


@nox.session(python=False, venv_backend="none")
def dev(session: nox.Session) -> None:
    """One-time developer setup: install pre-commit AND pre-push hooks.

    Run once after cloning:
        nox -s dev

    Installs both stages so that the 4-Gates `just verify` Final Guard runs
    automatically on `git push` (EPOCH 4 / v0.7.0).
    """
    session.run("uv", "sync", "--group", "dev", external=True)
    session.run("uv", "run", "pre-commit", "install", external=True)
    session.run("uv", "run", "pre-commit", "install", "-t", "pre-push", external=True)
