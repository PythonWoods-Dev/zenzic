---

description: "Immediate advanced assurance baseline for zenzic family repositories, with enforceable controls and audit commands."
---

<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Supply-Chain Assurance Profile

This profile defines the immediate advanced assurance baseline for the zenzic
family repositories (`zenzic`, `zenzic-doc`, `zenzic-action`).

It is designed to be enforceable with repository-local gates, reproducible in
CI, and auditable from logs.

---

## 1) Target Level

- Operational target: advanced assurance baseline now.
- Scope: source integrity, deterministic verification, fail-closed policy paths,
  and cross-repository parity controls.
- Rule: no silent downgrade from hard gates to advisory warnings.

---

## 2) Mandatory Controls (Current Baseline)

| Control | Required behavior | Enforcement locus |
|---|---|---|
| Single verification entrypoint | Local and CI must converge on `just verify` | `justfile` + CI workflows |
| Sovereign core resolution | `ZENZIC_CORE_PATH -> ./_zenzic_core -> ../zenzic`, fail-closed | `justfile`, `noxfile.py`, CI |
| Governed branch override | `ZENZIC_CORE_REF` requires ticket/reason/approver/expiry | `zenzic-action` self-check workflow |
| Lexical boundary guard | Forbidden terms blocked in governed paths | `scripts/enforce-radical-unawareness.sh` + pre-commit |
| Public contract drift guard | Required guard markers must exist; release recipes must not auto-create tags | `release-contracts` recipes |
| License provenance hygiene | SPDX/REUSE verification required | pre-commit `reuse` + CI |

---

## 3) Audit Commands (Operator Runbook)

Run from repository root unless noted otherwise.

```bash
just release-contracts
just verify
```

Tagging policy: tags are created and pushed manually after merge; release recipes must not create tags.

Lexical guard (policy-as-code):

```bash
bash scripts/enforce-radical-unawareness.sh
```

Docs parity contract (in `zenzic-doc`):

```bash
uvx nox -s verify-codes-parity
```

License provenance check:

```bash
uvx reuse lint
```

---

## 4) Evidence Requirements

A release candidate is considered assurance-compliant only if:

1. `just verify` exits 0 in local gate and CI gate.
2. Branch override (if used) emits governed metadata in CI summary.
3. Lexical guard emits a pass state with zero forbidden references.
4. No policy guard is bypassed through fallback behavior.

---

## 5) Next Hardening Layer

This baseline is the minimum industrial profile now in force.

Planned next layer:

- workflow dependency attestation expansion,
- stronger workflow pinning policy enforcement,
- periodic evidence export for quarterly governance review.

## See Also

- [Contributing Pull Requests](../how-to/contribute/pull-requests.md)
