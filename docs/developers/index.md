---

description: "Extend Zenzic with custom adapters, plugin rules, and integrations."
---

<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Developer Guide

Welcome to the Zenzic engineering community. We build tools that bridge the gap
between human documentation and executable truth. Our codebase follows rigorous
standards for performance, type safety (`mypy --strict`), and accessibility.

This section covers everything you need to extend, adapt, or contribute to Zenzic.

Operational governance and release troubleshooting start here:

- [Governance Playbook: Troubleshooting and Invariants](how-to/release-governance-protocol.md)
- [Shared Sovereign Verification Model](explanation/sovereign-verification-model.md)

---

## Core Engineering Guides

<div class="grid cards" markdown>

- :material-puzzle-edit-outline:{ .lg .middle style="color: #6366f1;" } **[Writing Plugin Rules](how-to/write-plugin.md)**

    ---

    Implement `BaseRule` subclasses, satisfy the pickle purity contract, and register entry-points.

    [:material-arrow-right: Read Guide](how-to/write-plugin.md)

- :material-transit-connection-variant:{ .lg .middle style="color: #0284c7;" } **[Writing an Adapter](how-to/implement-adapter.md)**

    ---

    Implement the `BaseAdapter` protocol to teach Zenzic about a new documentation engine topology.

    [:material-arrow-right: Read Guide](how-to/implement-adapter.md)

- :material-folder-play-outline:{ .lg .middle style="color: #10b981;" } **[Z-Code Gallery](../tutorials/examples/index.md)**

    ---

    Reproducible, runnable fixtures for every diagnostic code Zenzic emits — run any scenario locally via `zenzic lab`.

    [:material-arrow-right: Explore the Gallery](../tutorials/examples/index.md)

- :material-shield-lock-open-outline:{ .lg .middle style="color: #f59e0b;" } **[Governance Playbook](how-to/release-governance-protocol.md)**

    ---

    Release CAP policies, suppression rules, and failure troubleshooting playbooks.

    [:material-arrow-right: Read Playbook](how-to/release-governance-protocol.md)

- :material-server-security:{ .lg .middle style="color: #e11d48;" } **[Sovereign Verification Model](explanation/sovereign-verification-model.md)**

    ---

    Fail-closed core resolution, zero-network quality gate, and complete local-to-CI parity.

    [:material-arrow-right: Read Model](explanation/sovereign-verification-model.md)

</div>

---

## Interactive Workflow with Just

Zenzic uses [`just`](https://github.com/casey/just) as its interactive command runner.
`just` is the fast day-to-day layer; `nox` is the reproducible CI layer underneath.

| Command | Description |
|:--------|:------------|
| `just sync` | Install / update all dependency groups (`uv sync --all-groups`) |
| `just check` | **Self-lint — run Zenzic on its own documentation (strict)** |
| `just test` | Run the test suite directly via `pytest -n auto` (parallel, no coverage), Hypothesis **dev** profile |
| `just test-full` | Run the test suite via `nox -s tests` with Hypothesis **ci** profile (500 examples) |
| `just verify` | **Pre-push gate: pre-commit hooks + pip-audit + pytest (coverage enforced) + `zenzic check all --strict` + `zenzic score --stamp`** |
| `just docs-build` | Build the documentation site (`mkdocs build --strict` — always strict, no fast/non-strict variant) |
| `just docs-serve [args]` | Start the live-reload documentation server |
| `just check-badges` | Verify badge freshness (`zenzic score --check-stamp`) without mutating anything — the CI-safe counterpart to `just verify`'s stamp step |
| `just clean` | Remove generated artefacts (`dist/`, `.pytest_cache/`, `.hypothesis/`, `.zenzic-score.json`, `coverage.json` — **not** `site/`) |

The Zenzic self-linting duty — `just check` — is the first command to run after
any documentation change. Run `just verify` before every push to `main`.

<details>
<summary>Hypothesis profiles</summary>

Property-based tests use [Hypothesis](https://hypothesis.readthedocs.io/) with
three profiles, controlled by the `HYPOTHESIS_PROFILE` environment variable:

| Profile | Examples per test | When to use |
|:--------|------------------:|:------------|
| **dev** (default) | 50 | Day-to-day development (`just test`) |
| **ci** | 500 | CI pipelines and `just test-full` |
| **purity** | 1 000 | Pre-release exhaustive validation |

```bash
just test                          # dev profile (fast)
just test-full                     # ci profile (thorough)
HYPOTHESIS_PROFILE=purity just test  # pre-release
```

</details>

<details>
<summary>Mutation testing</summary>

Use `just mutation` to run [mutmut](https://mutmut.readthedocs.io/) against
`src/zenzic/core/credentials.py` (`[tool.mutmut]` in `pyproject.toml`) and check the
score against a recorded floor. **CI runs this on every build.**

```bash
just mutation
```

The score is a ratchet, not the target: the credential scanner measures **56.5%**
against a stated target of **≥ 90%**, and the gate prints that gap on every run. See
[Credential Scanner Obligations](reference/credential-scanner-obligations) for what it
does and does not promise.

`nox -s mutation` also exists and runs mutmut, but computes no floor and fails on
nothing.

</details>

---

## Contributing

Full contribution guidelines, code conventions, Core Laws, and the pre-PR checklist
are in [`CONTRIBUTING.md`](https://github.com/PythonWoods/zenzic/blob/main/CONTRIBUTING.md)
on GitHub.

When you open a pull request, GitHub automatically loads the
[PR checklist](https://github.com/PythonWoods/zenzic/blob/main/.github/PULL_REQUEST_TEMPLATE.md)
— verify all items before requesting a review.
