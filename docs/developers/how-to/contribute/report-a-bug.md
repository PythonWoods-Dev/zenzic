---

tags:

  - Community

description: "How to report bugs effectively with reproduction steps."
---

<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Bug reports

Zenzic is an actively maintained project that we constantly strive to improve.
With a project of this size and complexity, bugs may occur. If you think you
have discovered a bug, you can help us by submitting an issue in our public
[issue tracker](https://github.com/PythonWoods/zenzic/issues), following this guide.

## Before creating an issue

We aim to keep the number of open issues low by addressing bugs promptly.
Before submitting a new issue, please complete the following steps.

### Upgrade to the latest version

Chances are that the bug you discovered was already fixed in a subsequent
version. Before reporting an issue, ensure that you're running the
[latest version](https://github.com/PythonWoods/zenzic/releases) of Zenzic.

!!! warning "Bug fixes are not backported"

    Only bugs that occur in the latest version of Zenzic will be addressed.

### Search for solutions

Before creating a bug report, do some research:

1. [Search our documentation](?q=) and look for sections

   related to your problem.

2. [Search our issue tracker](https://github.com/PythonWoods/zenzic/issues), as another user might already

   have reported the same problem.

__Keep track of all <u>search terms</u> and <u>relevant links</u>; you'll need
them in the bug report.__

---

## Issue template

Our issue template consists of the following parts:

- Title
- Context <small>optional</small>
- Bug description
- Related links
- Reproduction
- Steps to reproduce
- Checklist

### Title

A good title is short and descriptive — a one-sentence executive summary of
the issue.

| <!-- * * --> | Example |
| -------- | ------- |
| :material-check: __Clear__ | `validate_same_page_anchors` raises false positive on auto-generated headings |
| :material-close: __Unclear__ | Anchor validation doesn't work |
| :material-close: __Useless__ | Help |

### Context <small>optional</small> {#context}

Provide additional context to help us understand what you were trying to
achieve. Don't write about the bug here.

### Bug description

Provide a clear, focused, and concise summary of the bug. Adhere to the
following principles:

- __Explain the <u>what</u>, not the <u>how</u>__ – focus on the problem

    and its impact, not how to reproduce it.

- __Keep it short and concise__ – one or two sentences is ideal.

- __One bug at a time__ – create separate issues for unrelated bugs.

### Related links

Share links to all documentation sections relevant to the bug, as well as any
related issues you found while searching.

### Reproduction

A minimal reproduction is at the heart of every well-written bug report. It
allows us to instantly recreate the conditions needed to find the root cause.

After creating the reproduction, attach the `.zip` file directly to the issue.

!!! warning "Don't share links to repositories."

    Please attach a `.zip` reproduction rather than linking to a repository.

### Steps to reproduce

List the specific steps we should follow when running your reproduction to
observe the bug. Keep the steps concise and complete.

### Checklist

Thanks for following the guide and creating a high-quality bug report. The
checklist ensures that you have read this guide and provided us with everything
we need to help you.

__We'll take it from here.__

## See Also

- [Contributing Pull Requests](./pull-requests.md)
