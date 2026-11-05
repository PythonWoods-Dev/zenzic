<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Guide

## Overview

This is the Overview section. The anchor `#overview` is valid.

There is no `#nonexistent-section` heading on this page — that is the
intentional defect that triggers Z102 ANCHOR_MISSING when `index.md` links
to `guide.md#nonexistent-section`.

Anchor validation matters because Markdown renderers silently ignore
unresolved fragments, leaving readers stranded at the top of a page instead
of the section they expected. See the [gallery index](index.md) for the
full walkthrough of this finding.
