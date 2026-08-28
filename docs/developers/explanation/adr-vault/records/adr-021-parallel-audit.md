---

description: "ADR 020: Why Zenzic uses wait(FIRST_COMPLETED) for parallel result collection and how the fail-fast coordinator works without violating Pillar 3."
---

<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# ADR 020: Parallel Audit Completeness vs. Fail-Fast

**Date:** 2026-05-10
**Decider:** Architecture Lead
**Date:** 2026-05-02

---

## Context

Zenzic uses a `ProcessPoolExecutor` to scan documentation files in parallel
when a repository contains 50 or more Markdown files (`ADAPTIVE_PARALLEL_THRESHOLD`
in `core/scanner.py`). Each worker executes `_scan_single_file()` independently
and returns an `IntegrityReport` containing any findings, including `SecurityFinding`
objects emitted by the credential scanner (Z201/Z202/Z203).

In the earlier implementation, the coordinator collected results by
iterating over `futures_map.items()` **in submission order**, calling
`fut.result(timeout=30)` on each future in turn. This design had two consequences:

1. **No early termination.** If file 1 of 500 contained a credential (Z201,
   Exit Code 2), all 499 remaining workers continued to completion before the
   CLI could report the breach. On large repositories, this wasted significant
   CI compute time.

2. **Sequential result collection.** A slow worker at position 2 would block
   collection of all subsequent results until it completed or timed out, even
   if workers 3–500 had already finished.

Two abort mechanisms were evaluated before the adopted solution:

**`multiprocessing.Manager().Event()`** — a shared boolean flag visible to both
coordinator and workers. **Rejected.** Passing a manager event to `_worker()`
makes it stateful: its output would depend on external shared state rather than
solely on its inputs (`md_file`, `config`, `rule_engine`). This violates
**Pillar 3: Pure Functions First** — a founding invariant of the Zenzic
architecture. `_worker()` must remain a pure function.

**`concurrent.futures.as_completed()`** — an iterator that yields futures in
completion order. **Evaluated and replaced.** `as_completed()` provides no
per-batch timeout guarantee. A deadlocked final worker would block the generator
indefinitely. The ZRT-002 protection (Z902 for deadlocked workers) cannot be
preserved without introducing a separate per-future timeout mechanism that
negates the simplicity advantage of `as_completed()`.

---

## Decision

> **Zenzic, the parallel coordinator uses `concurrent.futures.wait()` with
> `return_when=FIRST_COMPLETED` and a `_abort` local flag. On the first
> `SecurityFinding` in a completed worker result, all still-queued (`PENDING`)
> futures are cancelled immediately. The ZRT-002 deadlock guard is preserved.**

The implementation replaces the `for fut, md_file in futures_map.items()` loop
with a `while _pending` loop. Each iteration calls:

```python
done, _pending = concurrent.futures.wait(
    _pending,
    timeout=_WORKER_TIMEOUT_S,
    return_when=concurrent.futures.FIRST_COMPLETED,
)
```

When a completed report contains `security_findings`, the coordinator sets
`_abort = True` and calls `pending_fut.cancel()` on every future still in
`_pending`. Subsequent iterations discard results silently.

**Behavioural changes after the coordinator redesign:**

| Scenario | Earlier implementation | Redesigned coordinator |
|---|---|---|
| No security breach | All files scanned | All files scanned (unchanged) |
| Security breach in file 1/500 | All 500 files scanned | Breach detected; pending tasks cancelled |
| Deadlocked worker | Z902 after 30 s per-worker | Z902 if no worker completes in 30 s |
| Result order | Submission order → sorted | Completion order → sorted |

**Cancellation semantics:** `future.cancel()` operates only on tasks that have
not yet been dispatched to a worker process (`PENDING` state). Tasks already
`RUNNING` cannot be interrupted — they complete and their results are silently
discarded (not added to the report). The fail-fast is therefore a
**best-effort CI optimisation**, not a hard execution guarantee.

**ZRT-002 preservation:** If `concurrent.futures.wait()` returns an empty `done`
set (no worker completed within `_WORKER_TIMEOUT_S` seconds), all remaining
pending futures are cancelled and a Z902 finding is emitted for each stalled
file. This protects against ReDoS patterns in `[[custom_rules]]` that somehow
bypass the startup canary (`_assert_regex_canary()`).

---

## Rationale

The technical rationale and architectural context driving this design decision are outlined below.

### 1. Pillar 3 Preserved

The fail-fast is implemented entirely in the coordinator, which is orchestration
logic — not analysis logic. The coordinator is the only scope where multiple
futures are visible simultaneously. No analysis function is aware of the abort
state.

`_worker()` and `_scan_single_file()` are **unchanged** in this design. Given the

same inputs, they produce the same output. They have no dependency on shared
state. This functional purity is what makes them deterministic in isolation and
trivially testable.

### 2. Audit-Complete Semantics for Running Workers

Workers already executing when a breach is detected are allowed to complete
naturally. Their results are discarded by the coordinator. This prevents the
scenario where a partially-written `IntegrityReport` (from a worker interrupted
mid-execution) corrupts the findings list or leaves file handles open.

### 3. Deterministic Output

The final `reports` list is always sorted by `file_path` after collection.
CLI output is reproducible regardless of worker completion order, pool size,
or how many files were scanned before the abort.

### 4. `wait(FIRST_COMPLETED)` vs `as_completed()`

`as_completed()` was the initially-proposed mechanism. It was replaced by
`wait(return_when=FIRST_COMPLETED)` for one specific reason: the ZRT-002
deadlock guard. With `as_completed()`, a deadlocked last worker causes the
generator to block indefinitely with no way to enforce a timeout per pending
batch. With `wait(timeout=_WORKER_TIMEOUT_S)`, an empty `done` set after 30
seconds unconditionally triggers the Z902 guard — no additional mechanism needed.

---

## Invariants

- `_worker()` must remain a pure, stateless function. No shared state, queue,
  or event may be passed to it.
- The `_abort` flag is a local variable in the coordinator loop. It is not
  exported, not shared with workers, and not visible outside the `with executor`
  block.
- Results are always sorted by `file_path` before being returned. The
  completion order from `wait()` is never the final output order.
- ZRT-002 deadlock guard: if no future completes within `_WORKER_TIMEOUT_S`
  seconds, all remaining futures are cancelled and a Z902 finding is emitted
  for each stalled file.

---

## Consequences

- On repositories with a security breach in the first few files, CI runtime
  is reduced proportionally to the number of cancelled workers.
- On repositories with no breach, performance is identical to the previous
  implementation (all workers complete, all results collected).
- The `ADAPTIVE_PARALLEL_THRESHOLD` constant retains its role: below 50 files,
  sequential mode is used and this ADR does not apply. The sequential path
  is unchanged.
- The fail-fast applies to parallel mode only. A scan that produces zero
  security findings is unaffected by this change.

!!! note "Historical snapshot"
    This ADR is dated 2026-05-10, when `ADAPTIVE_PARALLEL_THRESHOLD` was genuinely
    `50` files. The constant was raised to `1000` files in v0.30.0 (2026-08-18) — the
    decision and mechanism this ADR documents (fail-fast via `wait(FIRST_COMPLETED)`)
    are unaffected, but every "50 files" activation-threshold figure on this page
    (Context above, Consequences above) no longer matches the current value.
