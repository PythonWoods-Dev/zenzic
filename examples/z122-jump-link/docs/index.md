<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Z122 JUMP_LINK_DETECTED

## Jump links (href="#")

<a href="#">Back to top</a>

<a href="#" class="btn btn-primary" id="cta-button">Click here</a>

## Suppressed jump link

<a href="#" data-zenzic-ignore>Intentional placeholder (suppressed)</a>

## Why this matters

A jump link that always points to `#` without an id target never actually
navigates anywhere, which misleads readers who expect it to jump to a
specific section instead of staying put.
