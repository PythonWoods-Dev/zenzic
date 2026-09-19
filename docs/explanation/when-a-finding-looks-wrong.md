---
description: "Three reasons a finding can look wrong, three different remedies, and how to tell which one you are holding."
---
<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# When a Finding Looks Wrong

Sooner or later Zenzic reports something you disagree with. There are **three different
reasons** that happens, they have **three different remedies**, and confusing them costs you
in opposite directions.

This page is about telling them apart. The mechanics of writing a suppression are in
[Suppression Policy](../reference/suppression-policy.md); what each code means is in
[Finding Codes](../reference/finding-codes.md).

---

## The three conditions

### 1. The engine is wrong

The finding should not exist, for anybody. Zenzic misread the construct.

**Remedy: a fix in the engine.** You write nothing and you pay nothing.

*What it looks like:* the finding describes something that is not there. A `Z520` malformed
list where the lines are an MDX `import` block. A `Z403` missing alt text where the image is
inside a fenced code example. A bare URL reported in prose where the URL is a JSX attribute.

*If you are holding one of these, report it.* Suppressing it is the worst outcome available:
you pay a debt point for our defect, and we never learn the construct exists, because your
silence is indistinguishable from correctness.

### 2. The rule is an opinion

The finding is accurate, and the rule expresses a preference your project does not share.

**Remedy: the rule is opt-in and off by default.** You still write nothing.

*What it looks like:* a threshold. `Z511` flags long sentences, and its limit was tuned on
Zenzic's own prose. On a foreign corpus it produced 23 findings — every one of them a
correct measurement of a sentence length that project was perfectly happy with. It became
opt-in, and five other codes went with it.

*The signal that separates this from the first case is a question:* **would the project's
maintainer accept a pull request fixing it?** If the answer is no, the rule is too opinionated
to run by default, and that is our problem to fix rather than yours to silence.

### 3. The rule is right and you are choosing to live with it

The finding is accurate, it is a real defect, and you have decided not to fix it — now, or
ever.

**Remedy: a declared suppression.** It costs one point of Technical Debt, the Suppression
Audit counts it, and that is the mechanism working rather than failing.

*What it looks like:* twelve `not_in_nav` pairs in this repository. Each one is a deliberate
exemption with a written reason, each one costs a point, and the total is visible in every
run.

---

## Why confusing them is expensive in both directions

**Suppressing an engine defect** makes you pay for our mistake, and hides the measurement
that would have told us the construct exists. Six such defects were closed in one day once a
corpus made them visible; a project that had quietly suppressed them would have kept them
forever.

**Waiting for a fix where the rule is right** leaves a real defect open in your
documentation, indefinitely, while nothing is coming.

The difference is worth thirty seconds of thought, and the maintainer question above usually
settles it.

---

## What to do with each

| Condition | You do | It costs you | Where it is recorded |
| :--- | :--- | :--- | :--- |
| The engine is wrong | [Report it](https://github.com/PythonWoods-Dev/zenzic/issues) | nothing | our tracker |
| The rule is an opinion | Leave it off, or [report the case](https://github.com/PythonWoods-Dev/zenzic/issues) | nothing | our tracker |
| You choose to live with it | [Declare a suppression](../reference/suppression-policy.md) | 1 debt point | your `.zenzic.toml` |

A finding you cannot place is worth reporting anyway. Telling the three apart is our job
before it is yours.
