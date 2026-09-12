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

---

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

Opening a new issue and selecting __Bug Report__ loads
[`bug_report.yml`](https://github.com/PythonWoods/zenzic/blob/main/.github/ISSUE_TEMPLATE/bug_report.yml),
which asks for the following fields:

- Zenzic version <small>required</small>
- Python version <small>required</small>
- Operating system <small>required</small>
- Documentation engine <small>required</small>
- Command run <small>required</small>
- Expected behaviour <small>required</small>
- Actual behaviour <small>required</small>
- `zenzic.toml` (if any) <small>optional</small>
- Zenzic alert output (exit codes 2–3), if applicable <small>optional</small>
- Pre-submission checklist <small>required</small>

### Zenzic version, Python version, operating system

Output of `zenzic --version` and `python --version`, and the OS you're running
on. These narrow down whether a bug is version-specific or platform-specific.

### Documentation engine

Which adapter was active when the bug occurred — MkDocs, Zensical, Standalone,
or "not applicable / unsure." Several bugs are engine-specific (`mkdocs.yml`
nav parsing vs. Zensical's own config format), so this narrows the search
space immediately.

### Command run

The exact `zenzic` command that triggered the bug (e.g. `zenzic check all
--strict`). We reproduce from this, so paste the real command rather than a
paraphrase.

### Expected behaviour / Actual behaviour

Two short, focused fields: what you expected, and what actually happened.
Paste the __full terminal output__ into "Actual behaviour" when possible —
Zenzic's own output (finding codes, exit code, DQS score) is usually enough
context to reproduce without a separate attachment.

- __Explain the <u>what</u>, not the <u>how</u>__ – focus on the problem
  and its impact.
- __One bug at a time__ – open separate issues for unrelated bugs.

### `zenzic.toml` and alert output

Paste your `.zenzic.toml` (remove any secrets first) if it's relevant to the
bug. If the bug involves a security exit code (2 for a credential alert, 3
for path traversal), paste that output too — redact any real secrets or paths
before posting.

### Pre-submission checklist

Confirms you searched existing issues for a duplicate and reproduced the bug
against the latest published release before filing.

__We'll take it from here.__

---

## See Also

- [Contributing Pull Requests](./pull-requests.md)
