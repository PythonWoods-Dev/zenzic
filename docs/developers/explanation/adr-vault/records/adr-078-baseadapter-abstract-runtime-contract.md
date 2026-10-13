---
description: "Architectural Decision Record for the v0.8.0 move from a duck-typed Protocol adapter surface to a concrete BaseAdapter Abstract Base Class, and its v0.25.0 ADR-078-STRICT amendment adding the watched_config_files contract property."
---
<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# ADR 078: BaseAdapter Abstract Runtime Contract

This document details the architectural specification and contract for ADR 078: BaseAdapter Abstract Runtime Contract within the Zenzic ecosystem.

---

## Context

In the v0.7 line, engine-adapter compliance relied on a `Protocol` surface plus runtime duck-typing checks. That model was flexible but late-failing: a missing capability on a third-party adapter could escape detection until a scan or validation path was already running mid-pipeline, rather than at adapter construction.

v0.8.0 replaced this with a concrete `BaseAdapter` Abstract Base Class carrying required abstract methods, enforced by factory-level subclass construction. This closed the late-failure gap, but left the contract's required-property surface fixed at whatever v0.8.0 shipped with.

v0.25.0's LSP stabilization work then needed adapters to declare which of an engine's own configuration files (`mkdocs.yml`, `docusaurus.config.js`, etc.) should trigger a live VSM rebuild when the Language Server's file watcher observes a change. No v0.8.0 adapter had any way to express this capability, since the Core engine does not and must not hardcode engine-specific filenames (Radical Unawareness, ADR 075).

---

## Decision

1. **Nominal ABC Contract (v0.8.0)**:
   Every engine adapter subclasses `BaseAdapter(ABC)` and implements its required abstract methods and properties. Invalid or incomplete adapter implementations fail at instantiation time, not mid-pipeline.

2. **Inversion of Control at the Scanner Boundary (v0.8.0)**:
   The Core scanner no longer discovers engine details internally. Adapter context (callbacks, discovered content roots) is resolved once by orchestration and injected explicitly, keeping the scanner itself engine-agnostic.

3. **Amendment — `watched_config_files` (v0.25.0, "ADR-078-STRICT")**:
   `BaseAdapter` gained a new mandatory abstract property, `watched_config_files`, returning the set of configuration filenames or glob patterns whose modification should trigger an LSP-side VSM rebuild. This is a **breaking change for third-party adapters**: any adapter subclassing `BaseAdapter` before this amendment must implement the new property to remain instantiable. First-party adapters (`MkDocsAdapter`, `ZensicalAdapter`) were updated natively in the same release.

This amendment is recorded as a section of this same ADR, not as a separate ADR number — it tightens the identical contract the 2026-05-24 decision established (adapter capabilities as required abstract surface, not optional duck-typed probing), rather than introducing an unrelated architectural choice. The "-STRICT" suffix in existing citations refers to this specific amendment, not a different governing document.

---

## Rationale

A `Protocol` plus duck-typing check tells you an adapter is *probably* compatible; it does not stop an incomplete adapter from being constructed and then failing partway through a scan or validation run, which is a worse failure mode for both first-party and third-party adapter authors — the error surfaces far from its cause. A nominal ABC with required abstract methods moves that failure to construction time, where it is unambiguous and immediate.

The `watched_config_files` amendment applies the same reasoning one level further: rather than the LSP file watcher special-casing which config filenames matter per engine (violating ADR 075's Radical Unawareness), each adapter declares its own watched set as a required, typed contract property. Making it mandatory rather than optional means a third-party adapter cannot silently omit hot-reload support and leave editor diagnostics stale without at least a construction-time signal.

---

## Invariants

- Every class instantiated as an engine adapter (first-party or third-party) must subclass `BaseAdapter` and implement all of its abstract methods and properties, including `watched_config_files`.
- The Core scanner and validator receive adapter context (callbacks, content roots) via explicit injection at orchestration time — they do not perform their own engine-specific discovery.
- `watched_config_files` is the sole mechanism by which an adapter declares which of its engine's own configuration files should trigger an LSP-driven VSM rebuild; the Core engine does not hardcode engine-specific config filenames anywhere else.

---

## Consequences

- A third-party adapter written against the pre-v0.25.0 `BaseAdapter` contract fails at instantiation after upgrading, with a clear abstract-method error, until `watched_config_files` is implemented — the documented migration path is a single property override.
- LSP-driven configuration hot-reloading (mkdocs.yml/zensical.toml edits triggering an immediate VSM rebuild without a server restart) is available uniformly across every adapter that implements this contract, first-party or third-party, with no engine-specific logic in the Core or the LSP server itself.
- Adapter authors get a single, current point of reference for the full required interface: this ADR, rather than the v0.8.0 decision and the v0.25.0 amendment being scattered across separate, unlinked documents.
