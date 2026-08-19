---

description: "How to prepare and submit a pull request to Zenzic."
---

<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Pull requests

The process and requirements we describe below serve as important guardrails
that are essential to running an Open Source project and help us prevent wasted
effort and ensure the integrity of the codebase.

## Local development setup

Clone the repository and set up the full development environment in one step:

```bash
git clone https://github.com/PythonWoods/zenzic.git
cd zenzic
nox -s dev
```

`nox -s dev` runs `uv sync --group dev` (installing all dependency groups — test, lint, docs,
and release tooling) and then installs the pre-commit hooks. It is the canonical one-shot
setup command; run it once after cloning.

For a lower-level setup or if you do not have `nox` installed yet, install with `uv` directly:

=== "uv (recommended)"

    ```bash
    git clone https://github.com/PythonWoods/zenzic.git
    cd zenzic
    uv sync --group dev
    source .venv/bin/activate   # Windows: .venv\Scripts\activate
    ```

    [`uv`](https://docs.astral.sh/uv/) resolves dependencies significantly faster than pip and
    produces a reproducible environment via `uv.lock`. Preferred for all development work.

=== "pip"

    ```bash
    git clone https://github.com/PythonWoods/zenzic.git
    cd zenzic
    python -m venv .venv
    source .venv/bin/activate   # Windows: .venv\Scripts\activate
    pip install -e .
    pip install pytest pytest-cov ruff mypy pre-commit reuse mkdocs-material mkdocstrings[python] mkdocs-minify-plugin mkdocs-static-i18n
    ```

    Standard pip editable install. Manual installation of all test, lint, docs, and build dependencies.

### Dependency groups {#dependency-groups}

Zenzic uses [PEP 735](https://peps.python.org/pep-0735/) dependency groups to keep CI fast
by installing only what each job needs. The groups are:

| Group | Contents | When to use |
| :---- | :------- | :---------- |
| `test` | `pytest`, `pytest-cov`, `hypothesis`, `mutmut` | Running the test suite |
| `lint` | `ruff`, `mypy`, `pre-commit`, `reuse` | Linting and type checking |
| `docs` | MkDocs stack (`mkdocs-material`, etc.) | Building the documentation |
| `release` | `nox`, `bump-my-version`, `pip-audit` | Releases and audits |
| `dev` | All of the above (aggregator) | Local development |

Install a single group when you only need a subset:

```bash
uv sync --group test      # just pytest
uv sync --group lint      # just ruff + mypy
uv sync --group docs      # documentation build dependencies
uv sync --group dev       # everything (recommended for contributors)
```

With an editable install, the `zenzic` binary on your `PATH` always runs the
source you are working on. Validate the repository's own documentation at any
time:

```bash
zenzic check all            # all seven checks
zenzic check references     # includes custom [[custom_rules]] evaluation
pytest                      # full test suite (Hypothesis dev profile — 50 examples)
```

!!! note "Thorough property-based testing"

    To run the test suite with the **ci** Hypothesis profile (500 examples),
    use `just test-full` or set the environment variable directly:

    ```bash
    just test-full
    # or
    HYPOTHESIS_PROFILE=ci pytest
    ```

!!! note "End users vs contributors"

    **End users** run `uvx zenzic check all` — no clone, no install, zero
    friction. That is the entry point documented in the user-facing guides.

    **Contributors** clone the repo and install editably as shown above.
    The `zenzic` binary in your activated virtual environment is what you want
    — not `uvx`, which would download the published PyPI version.

## Issue-First Policy

To optimize resources and ensure contributions align with the architectural goals of the project, Zenzic enforces a strict **Issue-First Policy**. No Pull Request will be reviewed, merged, or discussed unless it is preceded by a corresponding Issue that has been formally discussed and approved by the maintainers. Always link the approved Issue in your PR description.

## CI/CD & Draft PRs

To optimize resources, Zenzic's GitHub Actions trigger ONLY on pushes to `main` and on Pull Requests. Pushes to isolated development branches do not trigger CI. If you want continuous feedback from CI during development, open a Draft PR immediately.

### Local Hooks

Zenzic uses `pre-commit` for automatic mutations (e.g., updating DQS badges). The use of hooks like `post-commit` is an anti-pattern and is not supported, as it would leave the working tree dirty after the commit.

## Styles and linting

It is important that your edits produce clean commits that can be reviewed
quickly and without distractions caused by spurious diffs. The project uses the
following styling and linting tools:

| Language | Tool   | Notes                       |
| :------- | :----- | :---------------------------|
| Python   | [ruff] | Linting and code formatting |
| Python   | [mypy] | Type checking               |

  [ruff]: https://docs.astral.sh/ruff/
  [mypy]: https://www.mypy-lang.org/

We also use an [.editorconfig] file that configures compatible editors to behave
consistently for tasks like removing trailing whitespace or applying indentation
styles.

  [.editorconfig]: https://editorconfig.org/

## Verified commits

To ensure the integrity of our project, we require [verified commits] that are
cryptographically signed. Follow the instructions on GitHub for using [gpg],
[ssh], or [s/mime] keypairs.

  [verified commits]: https://docs.github.com/en/authentication/managing-commit-signature-verification/about-commit-signature-verification
  [gpg]: https://docs.github.com/en/authentication/managing-commit-signature-verification/about-commit-signature-verification#gpg-commit-signature-verification
  [ssh]: https://docs.github.com/en/authentication/managing-commit-signature-verification/about-commit-signature-verification#ssh-commit-signature-verification
  [s/mime]: https://docs.github.com/en/authentication/managing-commit-signature-verification/about-commit-signature-verification#smime-commit-signature-verification

## Developer certificate of origin

To ensure the legal integrity of our project, we require all contributors to
*sign off* on their commits, thus accepting the Developer Certificate of Origin.
This certifies that you have the right to submit the code under the project's
license.

Add a `Signed-off-by` line to every commit using the `-s` flag:

```bash
git commit -s -m "<type>: <summary> (#<issue number>)"
```

## REUSE 3.3 — Copyright headers

This project enforces [REUSE 3.3](https://reuse.software/spec/) compliance via a
pre-commit hook. Every source file must carry an SPDX copyright header.

### Single-author file (default)

```text
# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
```

### Multi-author file — append, never overwrite

If you contribute to a file that already has a copyright header, **append** your
own `SPDX-FileCopyrightText` line on a new line immediately below the existing
one. Never replace or remove the original author's line:

```text
# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-FileCopyrightText: 2026 Your Name <your@email.example>
# SPDX-License-Identifier: Apache-2.0
```

The `SPDX-License-Identifier` line stays last and appears only once per file.

!!! note "credential scanner and copyright lines"

    Zenzic's normalizer skips `SPDX-FileCopyrightText` comment lines during
    word-count checks (Z502) — they are metadata, not prose.  The credential scanner (Z201)
    does not trigger on these lines either, because copyright email addresses
    are structurally distinct from credential patterns.

### HTML / Jinja2 files

Use HTML comment syntax:

```html
<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-FileCopyrightText: 2026 Your Name <your@email.example> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->
```

### Files that cannot carry inline headers

For binary files, generated assets, or formats with no comment syntax, add an
entry to `REUSE.toml` at the repository root instead of adding inline headers.
The pre-commit hook validates both inline headers and `REUSE.toml` entries.

## Use of Generative AI (No AI Slop)

We enforce a strict policy against unverified AI-generated code ("No AI Slop"). AI-assisted coding can be useful, but contributors must thoroughly understand, explain, and architecturally justify every single line of code proposed in a PR. Proposing code that you cannot explain will lead to immediate rejection of the contribution.

## Commit message standards

We follow the [Conventional Commits] specification. Each commit message must
follow this structure:

```text
<type>: <summary description> (#<issue number>)

Signed-off-by: ...
```

  [Conventional Commits]: https://www.conventionalcommits.org/

<figure markdown>

| Type          | Description                                    |
| :------------ | :--------------------------------------------- |
| `feat`        | Implements a new feature                       |
| `fix`         | Fixes a bug                                    |
| `perf`        | Improves performance                           |
| `refactor`    | Improves code without changing behavior        |
| `build`       | Makes changes to the build or CI system        |
| `docs`        | Adds or improves documentation                 |
| `style`       | Makes stylistic changes only (e.g. whitespace) |
| `test`        | Adds or improves tests                         |
| `chore`       | Updates build process, prepares releases, etc. |

  <figcaption>Accepted commit types</figcaption>
</figure>

## See Also

- [Zenzic Style Guide](../../reference/zenzic-style.md)
