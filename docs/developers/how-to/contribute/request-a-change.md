---

tags:

  - Community

description: "How to propose new features or changes to Zenzic."
---

<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Change requests

Zenzic is a deterministic document integrity engine for Markdown/MDX graphs. We aim to support a wide range
of use cases, and change requests are an essential mechanism for ensuring that
our software meets the needs of our community.

!!! warning "How we manage change requests"

    We highly value every idea or contribution from our community, and we
    kindly ask you to take the time to read the following guidelines before
    submitting your change request in our public [issue tracker](https://github.com/PythonWoods/zenzic/issues). Before
    submitting a new idea, please take a moment to read
    the section on how we manage change requests below.

---

## Before creating an issue

Before you invest your time filling out a change request, please answer the
following preliminary questions to determine if your idea is a good fit for
Zenzic.

### It's not a bug, it's a feature

Change requests are intended to suggest minor adjustments, propose ideas for
new features, or provide input to the project's direction. They are **not**
intended for reporting bugs — please refer to our [bug reporting guide](report-a-bug.md) instead.

### Look for sources of inspiration

If you have seen your idea implemented in another tool, gather enough
information about its implementation before submitting, as this will help us
evaluate potential fit more quickly.

**Keep track of all <u>search terms</u> and <u>relevant links</u>, you'll need
them in the change request.**

---

## Issue template

Opening a new issue and selecting **Feature Request** loads
[`feature_request.yml`](https://github.com/PythonWoods/zenzic/blob/main/.github/ISSUE_TEMPLATE/feature_request.yml),
which asks for the following fields:

- Feature category <small>required</small>
- Problem to solve <small>required</small>
- Proposed solution <small>required</small>
- Alternatives considered <small>optional</small>
- Zenzic design pillars <small>self-check</small>
- Pre-submission checklist <small>required</small>

### Feature category

A dropdown naming the kind of change: a new check, a new engine adapter, a
new Shield credential family, a CLI command or flag, a `.zenzic.toml`
configuration option, a custom-rules DSL extension, a performance
improvement, developer/API surface, or "Other." Picking the right category
routes the request to the right reviewer.

### Problem to solve

What gap does this fill? What currently breaks or is missing? Focus on the
problem, not the solution yet.

- **Explain the <u>what</u>, not the <u>why</u>** — describe the gap

  precisely; broader motivation belongs in this same field but stays brief.

- **One idea at a time** — open separate requests for unrelated ideas.

### Proposed solution

Describe the feature in concrete terms. For a new adapter proposal, describe
the entry-point registration, which `BaseAdapter` methods it implements, and
how engine-specific config will be read.

### Alternatives considered

What other approaches did you consider, and why did you rule them out? This
field is optional but speeds up review — it tells us you've already thought
through the design space.

### Zenzic design pillars

A self-check confirming your proposal respects the Core's three
non-negotiable constraints: **source-first** (operates on raw source files,
no documentation engine required to run or be installed), **no
subprocesses** (pure Python/stdlib only, no `subprocess.run` in the linting
path), and **pure functions** (deterministic, side-effect-free, testable
without I/O).

### Pre-submission checklist

Confirms you searched existing issues for a duplicate proposal, and whether
documentation needs updating alongside the feature.

**We'll take it from here.**

---

## How we manage change requests

Change requests are submitted as issues on our public [issue tracker](https://github.com/PythonWoods/zenzic/issues). Here's
how we handle them:

1. We read and review the request to understand the idea.
2. We may leave comments to clarify intent or suggest alternatives.
3. If the idea is out of scope, we will close the request and explain why.
4. If the idea aligns with the project's vision, we'll move it to our backlog.
5. Otherwise, we close the request to keep the issue tracker focused on bugs.

---

## Rejected requests

The following principles (in no particular order) form the basis for our
decisions:

- [ ] Alignment with the vision and goals of the project
- [ ] Compatibility with existing features
- [ ] Effort of implementation and maintenance
- [ ] Usefulness to the majority of users
- [ ] Simplicity and ease of use

If you're unsure why your change request was rejected, please don't hesitate
to ask for clarification.
