---
title: "10 Documentation Bugs Caught by Zenzic"
# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
date: 2026-06-29
authors:
  - pythonwoods
categories:
  - Engineering
  - Documentation
  - Quality Assurance
---
Documentation isn't just text — it's a critical interface. When users rely on your docs to deploy infrastructure, configure security policies, or integrate APIs, a "simple typo" can lead to hours of lost productivity.

In a docs-as-code workflow, documentation is code. And just like code, it has bugs. That's why we built Zenzic: a Deterministic Document Integrity Engine for Markdown/MDX graphs.

Here are 10 subtle, frustrating, and downright dangerous documentation bugs that Zenzic catches automatically in your CI/CD pipelines.

<!-- more -->

!!! abstract "Architectural Update"
    *Historical Note:* This post refers to Zenzic as a "linter". As the system evolved, its capabilities expanded far beyond surface-level linting. Zenzic is now officially classified as a **Deterministic Document Integrity Engine for Markdown/MDX graphs**. Read the [latest documentation](https://zenzic.dev/) for current architectural capabilities.

---

## 1. The "Ghost Anchor" (Z102)

You update a heading from `## Setup Environment` to `## Environment Setup`. Congratulations, the content is better! But somewhere in another file, a link points to `[Setup](#setup-environment)`.
Zenzic doesn't just check if the target file exists; it performs deep anchor validation, ensuring the specific heading anchor exists in the compiled HTML representation.

---

## 2. The Raw HTML Blind Spot (Z112)

Markdown allows raw HTML, which is often used for custom styling or legacy components. But standard Markdown linters usually ignore `href` attributes inside `<a>` tags. Zenzic's recent updates introduced strict HTML link detection, ensuring that `<a href="/legacy-path">Click here</a>` is audited with the same rigor as standard Markdown links.

---

## 3. The Absolute Path Trap (Z105)

Linking to `/docs/guide/install.md` might work perfectly on your local machine or staging server. But when the site is deployed to a sub-path (like `example.com/project-v2/`), absolute links shatter. Zenzic flags absolute internal paths, enforcing robust, relative linking (`../guide/install.md`) that survives environment migrations.

---

## 4. The Topographical Orphan (Z402)

A developer creates a brilliant, 2000-word guide on advanced configuration. They merge the PR. Six months later, you realize nobody has read it. Why? Because it was never added to the MkDocs `nav` configuration. Zenzic detects structural orphans—files that exist on the filesystem but are unreachable via the site navigation.

---

## 5. The Phantom Asset (Z404)

You specify a brand logo or a custom CSS file in your `mkdocs.yml`: `logo: assets/brand/svg/zenzic-icon.svg`. Later, the asset directory is restructured, and the SVG is moved. The build might still pass, but the site deploys with a broken header. Zenzic audits your core configuration files to ensure every referenced asset actually exists on disk.

---

## 6. The Dangling Reference (Z301)

Markdown allows reference-style links: `[Read more][setup-guide]`. This is great for readability, but what happens when you delete the definition `[setup-guide]: ./setup.md` at the bottom of the file? The link renders as dead text. Zenzic identifies dangling references and unused definitions to keep your Markdown source clean and functional.

---

## 7. The Secrets Leak (Z201)

Copy-pasting curl commands from your local terminal to a documentation file is dangerous. If an API key or an AWS secret slips into the Markdown block, it becomes public the moment it's merged. Zenzic incorporates baseline security auditing to flag exposed credentials and forbidden terms before they leave the CI pipeline.

---

## 8. The Stale Suppression (Z620)

Sometimes, you *have* to link to a known broken external URL (e.g., as an example of what not to do). You add a suppression rule. A year later, the suppression is still there, but the link was removed from the documentation. Zenzic flags stale suppressions, preventing your ignore lists from becoming bloated technical debt.

---

## 9. The Missing Alt Text (Z403)

Accessibility isn't optional. Images without `alt` text break screen readers and degrade SEO. While many linters check for empty alt text, Zenzic actively monitors your asset topology to ensure every meaningful image reference is properly annotated.

---

## 10. The Placeholder Left Behind (Z501)

When drafting long technical guides, it's common to use placeholder text.

```text
TODO: Add architecture diagram here
```

Zenzic scans the content layer for forgotten placeholders, ensuring that your users never see unfinished, draft-state content in production.

---

### Why It Matters

Documentation integrity is an engineering problem. Relying on manual reviews to catch missing anchors, dead links, and orphan pages simply doesn't scale.

By integrating Zenzic into your docs-as-code workflow, you shift documentation testing left. Every commit is strictly audited, giving you a quantified **Documentation Quality Score (DQS)** that ensures your docs are as reliable as your code.

Want to stop these bugs in your own repositories? [Get started with Zenzic today.](https://zenzic.dev/how-to/install/)
