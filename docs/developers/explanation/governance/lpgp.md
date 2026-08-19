---
description: Structural Improvement Plan for the Zenzic Landing Page.
---

<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Landing Page Governance Plan (LPGP)

**Subject:** Structural Improvement Plan for the Landing Page
**Objective:** Optimize information density, spatial precision, and the visual communication of Zenzic's rigor.

---

## 1. Content Hierarchy (Topology)

The reading order of the Landing Page will be restructured to optimize the technical attention funnel:

1. **Hero Section:** Immediate value proposition (Engine-agnostic Markdown static analyzer & credential scanner).
2. **Value Prop (Invariants):** The three fundamental rules of Zenzic, displayed with high information density.
3. **Live Demo / Gallery:** Terminal output and diagnostic simulation (e.g., `diagnostic_output.html` component).
4. **CI Integration (Ecosystem):** Usage examples (Zenzic Core, Zenzic-Action) and CI/CD integration (GitHub Actions, uvx, pre-commit).

---

## 2. "Hostile Precision" Integration

The current extended textual descriptions, which produce unnecessary cognitive load for a technical audience, will be deprecated in favor of highly structured formats:

* **Replace Prose with Tables:** Conversational texts ("Every public entry point validates...") will be converted into specification tables and metrics matrices (Input, Validation, Expected Exit Code).
* **Rigorous Grid Systems:** Use of strictly aligned `flex` and `grid` components (fixed 0.5rem gap, compressed padding), adhering to the `gap-y-2` rules and the `.diagnostic-item` class.

---

## 3. Proof of Integrity (Standardized CI Badges)

Zenzic will prove its own integrity via "dogfooding". Instead of custom UI components, the Landing Page will embed the official CI-generated Shields.io badges (DQS Score, Audit Status). This guarantees absolute real-time state synchronization without custom build hooks, proving the effectiveness of the tool using its own standard outputs.

---

## See Also

* [Contributing Pull Requests](../../how-to/contribute/pull-requests.md)
