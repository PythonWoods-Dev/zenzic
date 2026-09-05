---

description: "The four security obligations that apply to every PR touching src/zenzic/core/. All four must be satisfied or the PR is rejected."
---

<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Credential Scanner Obligations

This page documents the **four security obligations** that apply to every PR touching
`src/zenzic/core/`. A PR that resolves a bug without satisfying all four will be rejected
by the Architecture Lead.

These rules exist because a security review demonstrated that four individually reasonable
design choices — each correct in isolation — composed into four distinct attack vectors.

---

## Obligation 1 — The Security Tax (Worker Timeout)

Any PR that modifies `ProcessPoolExecutor` usage in `scanner.py` must preserve the
`future.result(timeout=_WORKER_TIMEOUT_S)` call. The current timeout is **30 seconds**.

```python
# ✅ Required form — always use submit() + wait(FIRST_COMPLETED) + result(timeout=...)
futures_map = {executor.submit(_worker, item): item[0] for item in work_items}
raw: list[IntegrityReport] = []
_pending: set[concurrent.futures.Future[IntegrityReport]] = set(futures_map)
while _pending:
    done, _pending = concurrent.futures.wait(
        _pending,
        timeout=_WORKER_TIMEOUT_S,
        return_when=concurrent.futures.FIRST_COMPLETED,
    )
    if not done:
        # ZRT-002 deadlock guard: no worker completed within the timeout window
        for fut in _pending:
            raw.append(_make_timeout_report(futures_map[fut]))  # Z902 finding
            fut.cancel()
        break
    for fut in done:
        raw.append(fut.result())

# ❌ Forbidden — blocks indefinitely on ReDoS or deadlocked workers
raw = list(executor.map(_worker, work_items))
```

The **Z902 finding** (`WORKER_TIMEOUT`) is not a crash — it surfaces in the standard report
UI. A worker that times out does not kill the scan; the coordinator continues with the
remaining workers.

If your change requires a longer timeout, increase `_WORKER_TIMEOUT_S` with a comment
explaining the cost and a benchmark proving the worst-case input.

---

## Obligation 2 — The RE2 DFA Purity Contract

Every `[[custom_rules]]` entry that specifies a `pattern` is compiled with
**Google RE2** (`zenzic.core.regex`), not Python's backtracking `re` module.
RE2 is a DFA-based engine with a hard linear-time execution guarantee: it
structurally cannot backtrack, so no pattern it accepts can cause
catastrophic backtracking — there is no runtime stress test, because the
protection is a compile-time structural rejection instead
(`CustomRule.__post_init__`, ZRT-007). A pattern RE2 cannot represent as a
DFA — a backreference or a lookaround — fails at load time, before any scan
runs, so CI catches a bad pattern immediately rather than at scan time.

```python
# CustomRule.__post_init__() in rules.py — runs automatically for every CustomRule
def __post_init__(self) -> None:
    try:
        self._compiled = re.compile(self.pattern)  # zenzic.core.regex, RE2-backed
    except re.error as exc:
        raise PluginContractError(...) from exc  # ZRT-007 — DFA Purity Contract
```

Test your pattern before committing:

```python
from pathlib import Path
from zenzic.core.rules import CustomRule
from zenzic.core.exceptions import PluginContractError

try:
    rule = CustomRule(
        id="MY-001",
        pattern=r"your-pattern-here",
        message="Found.",
        severity="warning",
    )
    print("✅ Accepted — RE2 compiled the pattern as a DFA")
except PluginContractError as e:
    print(f"❌ Rejected — not representable as a DFA:\n{e}")
```

**Patterns RE2 rejects** (non-regular constructs, no DFA representation exists):

| Pattern | Why rejected |
|---------|---------------|
| `(\w+)\1` | Backreference |
| `(?=foo)bar` | Lookahead |
| `(?<=foo)bar` | Lookbehind |

**Patterns RE2 accepts and runs in linear time, even against a pathological input**
(these would cause catastrophic backtracking under a backtracking engine like Python's
`re` — under RE2 they are ordinary, safe patterns; live-verified against the actual
installed engine, sub-millisecond against a 40-character adversarial string):

| Pattern | Notes |
|---------|-------|
| `(a+)+` | Nested quantifiers — classic ReDoS trigger elsewhere, harmless under RE2 |
| `(a\|aa)+` | Alternation with overlap |
| `(a*)*` | Nested star |
| `.+foo.+bar` | Greedy multi-wildcard with suffix |
| `EXAMPLE` | Literal match, O(n) |
| `^(START\|END):` | Anchored alternation |
| `[A-Z]{3}-\d+` | Bounded character classes |
| `\bfoo\b` | Word-boundary anchored |

> **Portability note:** unlike a signal-based timeout, RE2's DFA guarantee has no
> platform dependency — the rejection is structural (a compile-time error), not a
> runtime race against a wall-clock timer, so there is no POSIX/Windows distinction
> to document here. The worker timeout (Obligation 1) remains the backstop for a
> genuinely slow *Python* plugin rule, which is an unrelated risk.

---

## Obligation 3 — The Dual-Stream Invariant

The credential scanner stream and the Content stream in `ReferenceScanner.harvest()` must
**never share a generator**. This is the architectural lesson from ZRT-001.

```python
# ✅ CORRECT — independent generators, independent filtering contracts
with file_path.open(encoding="utf-8") as fh:
    for lineno, line in enumerate(fh, start=1):  # Credential scanner: ALL lines
        list(scan_line_for_secrets(line, file_path, lineno))

for lineno, line in _iter_content_lines(file_path):  # Content: filtered
    ...

# ❌ FORBIDDEN — sharing a generator silently drops frontmatter from credential scanner
with file_path.open(encoding="utf-8") as fh:
    shared = _skip_frontmatter(fh)
    for lineno, line in shared:
        list(scan_line_for_secrets(...))  # ← blind to frontmatter
    for lineno, line in shared:  # ← already exhausted
        ...
```

**Performance baseline:** The dual-scan (raw + normalised line) runs at approximately
**235,000 lines/second** (12.74 ms median for 3,000 lines over 20 iterations). If a PR
refactors `harvest()` and CI throughput drops below **100,000 lines/second**, investigate
before merging.

---

## Obligation 4 — Mutation Score: target ≥ 90%, currently 68.2%

Any PR that modifies `src/zenzic/core/` must maintain or improve the mutation score on the
affected module. The target is **≥ 90%**. The measured score is **not there yet**, and this
page states both rather than only the target.

!!! warning "Current state, measured"

    The credential scanner scores **68.2%**: 285 mutants killed, 133 survived, 0 with no
    covering test (2026-09-05, after the test-selection the gate runs against was corrected
    to include two existing suites it had omitted — no code change). Closing the remaining
    gap is tracked as its own work item. Until it closes, treat this obligation as a
    direction, not as a property the codebase already has.

CI runs the gate on every build, as a **ratchet**: `just mutation` fails when the score
drops below a recorded floor, and prints the distance to the 90% target on every run. It
does not gate at 90% — doing so would fail every build today, and gating at the measured
value while calling the obligation satisfied would change what is shown rather than what
is true.

```bash
just mutation
```

The gate targets `src/zenzic/core/credentials.py` against the nine suites that exercise it.
`nox -s mutation` also exists and runs mutmut, but computes **no** floor and fails on
nothing — prefer `just mutation`, which is what CI runs. Any PR touching the
`_map_credentials_to_finding()` conversion function, the `SECURITY_BREACH` severity path
in `ZenzicReporter`, or the exit-code routing in `cli.py` **must kill all three mandatory
mutants**:

| Mutant name | What is changed | Test that must kill it |
|-------------|----------------|------------------------|
| **The Invisible** | `exit_contract_severity()`'s `Z201`/`Z204` branch (`codes.py`) returns `"warning"` instead of `"security_breach"` — the mutation site moved here from a bare literal in `_map_credential_to_finding()` when `V031_SECURITY_FIX_FULL_CLOSURE` eliminated the literal in favour of direct derivation | `test_map_always_emits_security_breach_severity`, `test_finding_severity_agrees_with_the_tier_for_every_security_code` |
| **The Amnesiac** | `_obfuscate_secret()` returns `raw` instead of the redacted form | `test_obfuscate_never_leaks_raw_secret` |
| **The Silencer** | `_map_credentials_to_finding()` returns `None` instead of a `Finding` | `test_pipeline_appends_breach_finding_to_list` |

**ResolutionContext pickle validation:** Any PR that adds a field to `ResolutionContext` must
include:

```python
def test_resolution_context_is_pickleable():
    import pickle

    ctx = ResolutionContext(docs_root=Path("/docs"), source_file=Path("/docs/a.md"))
    assert pickle.loads(pickle.dumps(ctx)) == ctx
```

> **Reporting integrity:** A secret that is detected but not correctly reported is a CRITICAL
> bug — indistinguishable from a secret that was never detected at all.

---

## See Also

- [Finding Codes Index](../../reference/finding-codes.md)
