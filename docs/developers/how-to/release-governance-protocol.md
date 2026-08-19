---

description: "Operational developer runbook for the 4-gate release flow, brand governance, and namespace contracts."
---

<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Developer Release and Governance Protocol

Use this guide as the default operational contract for every contribution in
Zenzic repositories.

This is the execution protocol. ADRs remain the historical rationale layer.

Release A policy applies hard enforcement: no suppression debt beyond
the CAP scan scope.

---

## 1) Four-Gate Hierarchy

A change is Ready for release only when all four gates pass.

1. IDE Gate

Fix lint and type issues while authoring.

1. Pre-commit Gate

Commit is blocked on style, parsing, and local consistency failures.

1. Pre-push Gate

Push is blocked by full project verification, including structural audit and
path/link security checks.

1. CI/CD Gate

The same verification runs in shared infrastructure and must match local outcome.

Operational rule: do not bypass a failing gate by downgrading checks. Fix root
cause or apply a narrowly-scoped and auditable exception.

---

## 2) Brand and Obsolescence Policy

- Strong enforcement baseline is active.
- Legacy patterns are deprecated and must be detected by governance checks.
- Transitional terminology is tolerated during the current migration window.

Practical effect:

- New material should target stable enforcement terminology.
- Legacy terminology may remain only where required by historical context.
- Do not deprecate legacy terminology until a dedicated cleanup phase is
  completed, otherwise Z601 noise will flood the pipeline.

---

## 3) Namespace Contracts (Z4 and Z6)

- Z4 namespace: structural and infrastructure invariants.
- Z6 namespace: governance and lifecycle policy invariants.

Mandatory rules:

- Frozen code identities are immutable.
- Reuse or semantic reassignment of frozen IDs is forbidden.
- New governance behavior belongs in Z6.
- Structural checks and platform invariants belong in Z4.

---

## 4) Contribution Checklist

Before commit:

- Run the repository standard local checks.
- Confirm no unsanctioned config bypass was introduced.

Before push:

- Run full verify entrypoint.
- Confirm hook-driven execution paths and direct command paths produce the same
  result.

Before merge:

- Ensure CI reproduces local pass state.
- Remove temporary exclusions that are no longer justified.
- No Core PR that alters documented behavior can be merged into the release branch without a corresponding merged PR in zenzic-doc. The author is the final guarantor of the Mirror Law.

### Adding a Dependency

When adding a new third-party dependency to a Zenzic project:

1. Verify license compatibility (must be Apache-2.0-compatible: MIT, BSD, Apache-2.0, LGPL-3.0, ISC). GPL and proprietary licenses are forbidden.
2. Add the dependency details to the `NOTICE` file (name, URL, copyright holder, license identifier).
3. Run `uv run reuse lint` to verify compliance.

---

## 5) Suppression Policy (Release A)

- CAP sovereign default is 30 active suppressions.
- CAP is configurable per repository in `[governance].suppression_cap`.
- Scope is global: inline comments plus per-file config suppressions.
- Enforcement is fail-hard: if count is 31 or more, `check all` exits 1.
- Every run prints the suppression counter in the report footer.

When configured CAP is higher than the sovereign default (`> 30`), the footer
shows `[EXTENDED DEBT]` to make tolerance regimes explicit and auditable.

Expected footer format:

```text
Suppression Audit: X/30
```

Canonical inline syntax:

- Markdown: `<!-- zenzic:ignore: Z601 - historical reference -->`
- Markdown: `<!-- * zenzic:ignore: Z601 - historical reference * -->`

---

## 6) Common Zenzic Blocks

> This section has moved — see [Developer Troubleshooting](./troubleshooting.md#common-zenzic-blocks).

---

## 7) Shared Sovereign Verification Model (Family Repositories)

The zenzic family repositories share one deterministic gate model for `nox`,
`just`, and CI workflows:

1. Explicit override: environment variable `ZENZIC_CORE_PATH`.
2. CI canonical topology: `./_zenzic_core`.
3. Developer sibling topology: `../zenzic`.
4. Each candidate must contain `src/zenzic`.
5. Fail-closed policy: PyPI fallback is prohibited in repository quality gates.

Operational consequences:

- Local and CI are required to run the same verification entrypoint (`just verify`).
- CI must checkout the core repository into `_zenzic_core` before verification.
- Temporary config workarounds must not replace structural gate alignment.
- Explicit branch override (`ZENZIC_CORE_REF`) is allowed only as a governed
  exception with mandatory metadata (ticket, reason, approver, expiry) and
  fail-closed enforcement.
- Isolation checks must remain silent in tracked sources: contributor dogfooding
  uses local `.zenzic.local.toml`, while CI receives isolation parameters only
  through runtime environment injection.

Canonical reference:

- [Shared Sovereign Verification Model](../explanation/sovereign-verification-model.md)
- [Supply-Chain Assurance Profile](../reference/supply-chain-assurance-profile.md)

### Contributor Runbook (Local Setup) {#contributor-runbook-local-setup}

Two supported local setups for running verification:

1. **Sibling layout (recommended):**
   Place the core repository as a sibling of your target repository:

   ```text
   workspace/
     zenzic/
     zenzic-doc/
     zenzic-action/
   ```

   Then run:

   ```bash
   just verify
   ```

2. **Explicit override layout (custom path):**
   If your core repository is in a different location, export `ZENZIC_CORE_PATH` when running verify:

   ```bash
   ZENZIC_CORE_PATH=/absolute/path/to/zenzic just verify
   ```

If verification reports a missing core path, treat it as a setup misconfiguration, not as a quality warning to suppress.

---

## 8) Adding a New ADR

When a significant architectural decision is made — one that constrains future contributors or resolves a structural tension — it must be recorded:

1. Create `docs/developers/explanation/adr-<slug>.md` with the next available ADR number.
2. Add the file to the index table in [ADR Vault](../explanation/adr-vault/index.md).
3. Record the decision in the `[ADR]` section of the relevant repository governance log.

Per governance policy, ADR entries are append-only records. To amend a decision, add a new ADR that references the original and documents the amendment — never rewrite history.

---

## 9) Release Checklist Automation

The `RELEASE.md` file acts as the primary governance checklist for release verification. In accordance with the Mirror Law (ADR-020), this file is now fully integrated into the version bumping automation (`bump-my-version`).

**Mandatory Rule:** Do not manually edit the version strings or dates within `RELEASE.md` or `CITATION.cff`. The `just release <part>` command will automatically and deterministically synchronize the metadata table and checklist items to reflect the target release version.

---
