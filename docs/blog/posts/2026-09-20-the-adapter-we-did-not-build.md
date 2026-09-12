---
title: "The Adapter We Didn't Build, and What Changed Our Minds About Building Any"
slug: the-adapter-we-did-not-build
date: 2026-09-20 10:00:00
draft: true
authors:
  - pythonwoods
description: >
  A follow-up to the Docusaurus decision. The original reasoning still holds,
  but the thing that actually settled it was not the cost of the adapter — it
  was discovering that a route manifest a generator already produces answers
  the same question without an adapter at all.
categories:
  - Engineering
---

<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# The Adapter We Didn't Build

An earlier post explained why Zenzic dropped its Docusaurus adapter. Everything
in it remains true, which is why that post has not been edited. This one exists
because the reasoning has since acquired a second half, and a second half is a
new post rather than a rewrite.

<!-- more -->

## What the original argument was

An adapter's job is to answer one question: *given a source file, what URL does
this site publish it at?* Get that wrong and every link check downstream is
wrong with it — a link that resolves is reported broken, or worse, one that does
not resolve is reported fine.

Docusaurus answers that question with configuration, plugins, a routing layer,
and per-file front matter that can override all three. Reimplementing that
faithfully means reimplementing a moving target, and being *approximately* right
is not a weaker version of being right here. It is a different product: one that
reports findings a user cannot trust, which is worse than reporting none.

That argument was sound and it is unchanged.

## What it was missing

It framed the choice as *build the adapter or support the generator badly*. There
is a third option, and it was available the whole time: **ask the generator.**

Most static site generators can emit a route manifest — a mapping from source
file to published URL, produced by the same code that does the publishing. It is
not an approximation of the routing logic. It is the routing logic's own output.

Zenzic now consumes that manifest directly. The question an adapter existed to
answer is answered by the generator that actually knows, and the analyser does
not need to model anyone's routing at all.

## Why this is not a reversal

It is tempting to read this as "we were wrong to drop the adapter." We were not.
An adapter that reimplements Docusaurus routing would still be a moving target
today, and the manifest path does not resurrect it — it removes the need for it.

The correction is narrower and more useful: the original post argued from the
*cost* of being faithful, and cost arguments tend to end in a trade-off. The
better argument was about *who holds the answer*. Once that is asked out loud,
the trade-off disappears, because the party that holds the answer is willing to
hand it over.

## The transferable part

When a tool needs to know something another tool already computes, there are
three moves, and they are not equal:

1. **Recompute it.** Fastest to start, and you now own a model of someone else's
   behaviour that drifts every time they release.
2. **Approximate it.** Cheaper, and it produces findings whose wrongness is
   invisible until someone trusts one.
3. **Ask for it.** Often needs a build step you did not want, and it is the only
   one of the three whose answer is right by construction.

The third is frequently dismissed on ergonomics — it requires running a build —
and that dismissal is worth re-examining, because ergonomics is a cost you pay
once at setup and correctness is a cost you pay on every run.

Which generators expose a usable manifest, and what to do when one does not, is
covered in the adapter configuration guide.

---

## Resources

- **Source Code**: <https://github.com/PythonWoods/zenzic>
- **Documentation**: <https://zenzic.dev>
- **VS Code Extension**: <https://marketplace.visualstudio.com/items?itemName=PythonWoods.zenzic-vscode>
- **GitHub Action**: <https://github.com/PythonWoods/zenzic-action>
- **Finding Codes Index**: <https://zenzic.dev/reference/finding-codes/>
- **License**: Apache-2.0

## Trademark & Legal Disclaimer

*All product names, logos, and brands referenced in this publication are property of their respective owners. All company, product, and service names used on this site are for identification purposes only. Use of these names, logos, and brands does not imply endorsement or affiliation. Zenzic is an independent, open-source project created and maintained by PythonWoods.*
