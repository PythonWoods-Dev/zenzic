---

tags:

  - Community

description: "How to propose a new Z-Code rule to catch a documentation flaw."
---

<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Custom rule proposals

If you've spotted a documentation flaw Zenzic doesn't catch yet, you can propose a new
Z-Code rule to detect it. This is a narrower, more specific path than a general
[change request](request-a-change.md) — use it when your idea is specifically "Zenzic
should flag this pattern," not a broader feature or CLI change.

---

## Issue template

Opening a new issue and selecting __Custom Rule Proposal__ loads
[`custom_rule_proposal.yml`](https://github.com/PythonWoods/zenzic/blob/main/.github/ISSUE_TEMPLATE/custom_rule_proposal.yml),
which asks for the following fields:

- What documentation flaw do you want to catch? <small>required</small>
- Example of failing Markdown <small>required</small>
- Example of passing Markdown <small>required</small>
- Proposed Z-Code name <small>required</small>

### What documentation flaw do you want to catch?

Describe the issue in detail — what pattern is wrong, and why it matters for
documentation quality.

### Example of failing Markdown

A concrete Markdown snippet that should trigger the new rule. Real examples are far more
useful than abstract descriptions — this becomes the rule's first test fixture.

### Example of passing Markdown

The corrected version of the same content — what the rule should consider clean. Together
with the failing example, this pins down the exact boundary the rule needs to detect.

### Proposed Z-Code name

A placeholder code in the right category range (e.g. `Z7xx` for a new category, or a
specific number if you know which range fits — see [Finding Codes](../../../reference/finding-codes.md)
for the current ranges). The maintainers may assign a different final code.

__We'll take it from here.__

---

## See Also

- [Request a Change](request-a-change.md)
- [Writing Custom Rules (SDK v3)](../write-ast-rule.md)
