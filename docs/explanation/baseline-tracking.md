---
title: Baseline & Regression Tracking
description: Snapshot existing technical debt into .zenzic-baseline.json to prevent quality regressions in CI/CD pipelines.
---

<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

Zenzic provides an anti-regression engine that captures existing technical debt into a deterministic snapshot file (`.zenzic-baseline.json`). This allows engineering teams to adopt strict Quality Gates without being blocked by legacy documentation debt.

## Core Concepts

The baseline engine is designed around stable signatures and explicit visibility of debt.

### 1. Deterministic Cryptographic Signatures

Findings are matched across runs using a deterministic SHA-256 signature (`SHA-256(RuleCode + PosixPath + ContextTarget)`).

- **Line-Number Invariant**: Line numbers are intentionally excluded from the signature. Adding, deleting, or moving lines above a finding will **not** invalidate its baseline match.
- **Context Specificity**: Differentiates distinct defects in the same file (such as two broken links pointing to different targets).

### 2. Radical Unawareness (ADR-075)

The Core Engine does not drop baselined findings; it flags them with `is_baselined: true`. This allows editor integrations (LSP) and reports to display existing debt transparently while allowing the CLI to enforce anti-regression exit rules.

---

## Command Line Usage

The following commands cover baseline creation, baseline consumption, and CI decision rules.

### Creating or Updating a Baseline

To capture current findings and Document Quality Score (DQS) into `.zenzic-baseline.json`:

```bash
zenzic check all --update-baseline
```

This creates a human-readable JSON snapshot:

```json
{
  "$schema": "https://zenzic.dev/schemas/zenzic-baseline.schema.json",
  "version": "1.0",
  "created_at": "2026-08-01T17:40:00Z",
  "score": 85.0,
  "findings_count": 3,
  "signatures": [
    "7a2b9f1c3d4e5f6a",
    "8b3c0d2e4f5a6b7c",
    "9c4d1e3f5a6b7c8d"
  ],
  "metadata": {
    "zenzic_version": "0.27.0"
  }
}
```

### Consuming a Baseline in CI/CD

When `.zenzic-baseline.json` exists in your workspace root, `zenzic check` automatically loads it:

```bash
zenzic check all
```

You can also pass a custom baseline file:

```bash
zenzic check all --baseline ci-baseline.json
```

### CI Exit Code Logic

When a baseline is active:

- **Exit 0**: All active defects are present in the baseline snapshot and current DQS score $\ge$ baseline score.
- **Exit 1**: A new defect is introduced OR current DQS score drops below the baseline score.
- **Resolution Hint**: If baselined issues are fixed, Zenzic displays a hint suggesting to refresh the baseline:
  `💡 2 baselined issues resolved! Run 'zenzic check --update-baseline' to refresh baseline.`

## See Also

- [CLI Commands](../reference/cli.md)
- [Scoring System](./scoring-system.md)
- [Core Mechanics](./core-mechanics.md)
