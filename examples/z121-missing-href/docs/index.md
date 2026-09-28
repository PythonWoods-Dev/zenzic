<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Z121 MISSING_OR_EMPTY_HREF

## <a> without href

<a class="nav-link" id="section-1">Anchor without destination</a>

## <a> with empty href

<a href="" class="button">Empty href</a>

## img tag without src attribute

<img alt="Placeholder for missing src attribute demonstration" width="200" height="100">

## Why this matters

Anchors and images without a destination attribute are dead weight in
rendered HTML — they look interactive but lead nowhere, which frustrates
readers and assistive technology alike. See the
[WCAG 2.2 link purpose guideline](https://www.w3.org/WAI/WCAG22/Understanding/link-purpose-in-context.html)
for the full accessibility rationale.
