<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Z107 — Circular Anchor Gallery Example

This page links to `guide.md`, which contains a self-referential anchor link,
demonstrating **Z107 CIRCULAR_ANCHOR** detection.

## See the Guide

- [Guide](guide.md) — see the "Setup" section for the circular anchor example.

A circular anchor is a link whose visible text slugifies to the exact same
fragment identifier as the heading that already contains it, so clicking the
link leaves the reader exactly where they started instead of navigating
anywhere useful.

Run `zenzic check all` to reproduce the finding.
