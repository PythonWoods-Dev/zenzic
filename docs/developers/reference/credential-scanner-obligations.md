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
See `docs/internal/security/shattered_mirror_report.md` for the full post-mortem.

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

## Obligation 2 — The Regex-Canary Protocol

Every `[[custom_rules]]` entry that specifies a `pattern` is subject to the
**Regex-Canary**, a POSIX `SIGALRM`-based stress test that runs at `AdaptiveRuleEngine`
construction time.

```python
# _assert_regex_canary() in rules.py — runs automatically for every CustomRule
_CANARY_STRINGS = (
    "a" * 30 + "b",  # classic (a+)+  trigger
    "A" * 25 + "!",  # uppercase variant
    "1" * 20 + "x",  # numeric variant
)
_CANARY_TIMEOUT_S = 0.1  # 100 ms
```

Test your pattern before committing:

```python
from pathlib import Path
from zenzic.core.rules import CustomRule, _assert_regex_canary
from zenzic.core.exceptions import PluginContractError

rule = CustomRule(
    id="MY-001",
    pattern=r"your-pattern-here",
    message="Found.",
    severity="warning",
)

try:
    _assert_regex_canary(rule)
    print("✅ Canary passed — pattern is safe for production")
except PluginContractError as e:
    print(f"❌ Canary failed — ReDoS risk detected:\n{e}")
```

**Patterns to avoid** (catastrophic backtracking triggers):

| Pattern | Why dangerous |
|---------|---------------|
| `(a+)+` | Nested quantifiers — exponential paths |
| `(a\|aa)+` | Alternation with overlap |
| `(a*)*` | Nested star — infinite empty matches |
| `.+foo.+bar` | Greedy multi-wildcard with suffix |

**Patterns that are always safe:**

| Pattern | Notes |
|---------|-------|
| `EXAMPLE` | Literal match, O(n) |
| `^(START\|END):` | Anchored alternation, O(1) at each position |
| `[A-Z]{3}-\d+` | Bounded character classes |
| `\bfoo\b` | Word-boundary anchored |

> **Platform note:** `_assert_regex_canary()` uses `signal.SIGALRM`, which is only available
> on POSIX systems (Linux, macOS). On Windows, the canary is a no-op. The worker timeout
> (Obligation 1) is the universal backstop.

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

## Obligation 4 — Mutation Score ≥ 90% for Core Changes

Any PR that modifies `src/zenzic/core/` must maintain or improve the mutation score on
the affected module. Target for rc1: **≥ 90%**.

Run the mutation suite to see the current baseline for `rules.py` — do not rely on a
number written in this document, since a hardcoded figure goes stale on the next release
and nothing forces it to be updated:

```bash
nox -s mutation
```

The session targets `rules.py`, `credentials.py`, and `reporter.py`. Any PR touching the
`_map_credentials_to_finding()` conversion function, the `SECURITY_BREACH` severity path
in `ZenzicReporter`, or the exit-code routing in `cli.py` **must kill all three mandatory
mutants**:

| Mutant name | What is changed | Test that must kill it |
|-------------|----------------|------------------------|
| **The Invisible** | `severity="security_breach"` → `severity="warning"` in `_map_credentials_to_finding()` | `test_map_always_emits_security_breach_severity` |
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
