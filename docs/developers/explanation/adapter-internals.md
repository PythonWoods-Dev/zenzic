---

description: "A pedagogical comparison of adapter internals."
---

<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Adapter Internals — Pedagogical Design

The adapter pattern is the core architectural mechanism that allows Zenzic to validate documentation sites without depending on the runtime of specific build frameworks (e.g., Python for MkDocs).

By abstracting site layouts and navigation contracts into a unified protocol (`BaseAdapter`), Zenzic decouples the validation engine from engine-specific behaviors.

---

## Architectural Trade-offs: Engine-Aware vs. Sovereign Modes

Zenzic adapters fall into two major paradigms: **Engine-Aware** (e.g., `MkDocsAdapter`) and **Zero-Assumption / Sovereign** (e.g., `StandaloneAdapter`).

### Engine-Aware Adapters

Engine-Aware adapters read build-engine configuration files, sidebars, and frontmatter to reconstruct the engine's internal routing table.

- **Capabilities:** Enable advanced validation features such as strict orphan detection (Z402), locale shadow detection, and custom URI scheme validation (e.g., custom link bypasses).
- **Complexity:** High. The adapter must parse complex configurations (YAML/TOML/JS/TS) and replicate route-generation logic exactly as the engine would execute it.

### Zero-Assumption Adapters

Zero-Assumption adapters treat the documentation tree as a raw set of Markdown files and directories with no navigation contract.

- **Capabilities:** Fall back to a flat filesystem model where every file is considered reachable. Under this model, certain scans (like orphan detection) are automatically deactivated to prevent false positives.
- **Complexity:** Extremely low. The adapter assumes no metadata or special route generation.

---

> For concrete code comparisons showing how these strategies are implemented in Python, see [Writing an Adapter — Concrete Examples](../how-to/implement-adapter.md#concrete-implementation-examples-zensical-vs-standalone).
>
> For the abstract class definition and protocol signatures, see [API Reference — `BaseAdapter`](../reference/adapter-api.md#baseadapter-interface).
