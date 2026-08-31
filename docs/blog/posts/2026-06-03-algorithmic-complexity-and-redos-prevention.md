---
title: "Why we banned Python's regex module: The algorithm behind Zenzic"
date: 2026-06-03
authors:
  - pythonwoods
description: "Why we banned Python's regex module: The algorithm behind Zenzic"
---
<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

!!! abstract "Architectural Update"
    *Historical Note:* This post refers to Zenzic as a "linter". As the system evolved, its capabilities expanded far beyond surface-level linting. Zenzic is now officially classified as a **Deterministic Document Integrity Engine for Markdown/MDX graphs**. Read the [latest documentation](https://zenzic.dev/) for current architectural capabilities.

In modern CI/CD pipelines, security and performance should be structurally bounded, not just empirically observed. Traditional documentation linters and credential scanners often fail when operating at scale or under adversarial conditions. The primary failure mode is **ReDoS (Regular Expression Denial of Service)**.

<!-- more -->

---

## The ReDoS Problem in CI/CD

Many Python-based linters rely on the standard `re` module, which uses a backtracking NFA-style regex engine. When evaluating complex regex patterns against large or crafted payloads, backtracking can lead to exponential worst-case time complexity: $O(2^N)$.

In a CI/CD environment, an attacker or a simple misconfiguration can introduce a payload that triggers this exponential evaluation. This can stall a pipeline for impractically long periods of time, consuming runner minutes and effectively causing a denial of service on the build infrastructure. Traditional tools attempt to mitigate this using timeouts (`SIGALRM` or runtime canaries), but these are operational bandages, not architectural solutions.

---

## The Zenzic Solution: DFA and Algorithmic Separation

Zenzic solves this by completely decoupling the algorithmic approaches based on the problem domain, applying domain-appropriate algorithmic bounds to each layer.

By banning Python's `re` module and adopting `google-re2`, Zenzic avoids catastrophic backtracking. RE2 processes input without exponential fallback strategies, ensuring a linear time complexity of $O(N)$, where $N$ is the length of the text.

### Architectural Summary

The architectural decisions are summarized below:

| Layer | Complexity | Reason | Optimization |
| :--- | :--- | :--- | :--- |
| **Graph/Topology** | $\Theta(V+E)$ | DFS on adjacency list graph | Average $O(1)$ hash sets for subsequent lookups |
| **Credential Scanner** | $O(N)$ | RE2 engine | No catastrophic backtracking |
| **Custom Rules** | $O(N)$ | RE2 engine | Prevents exponential ReDoS from user-supplied rules |
| **I/O File Discovery** | $O(N)$ | Sequential scanning | Parallel process pool execution for large volumes |

### Structural Validation vs. Semantic Scanning

1. **Topology (Knowledge Graph)**: Zenzic treats documentation as a directed adjacency graph. Link validation uses an iterative Depth-First Search (DFS). Using an adjacency list representation, the traversal complexity is $\Theta(V+E)$. The resulting cycle registries are stored as hash sets, allowing average $O(1)$ lookups during the secondary validation pass.

2. **Semantic Scanning**: Credential scanning and custom rules use the aforementioned approach via `google-re2`. This ensures linear $O(N)$ semantic scanning, eliminating ReDoS vulnerabilities based on exponential backtracking.

3. **I/O Discovery**: The ingestion phase operates in $O(N)$ complexity relative to the total volume of processed data. To reduce wall-time without altering the fundamental computational complexity, Zenzic can distribute processing via parallel process pools.

This algorithmic separation ensures that Zenzic remains a structurally sound, security-hardened tool capable of operating safely within enterprise CI/CD gates.
