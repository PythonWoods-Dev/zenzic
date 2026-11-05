<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Z205 FORBIDDEN_SCHEME

This page demonstrates the **non-suppressible** Z205 security gate.

## javascript: URIs — XSS vectors

<a href="javascript:void(0)">Void link (XSS vector)</a>

<a href="javascript:alert(document.cookie)">Cookie theft attempt</a>

## data: URIs — content injection

<a href="data:text/html,<script>alert(1)</script>">Data URI injection</a>

## Attempted suppression — Z205 ignores data-zenzic-ignore

<a href="javascript:void(0)" data-zenzic-ignore>Suppression attempt (FAILS)</a>

## For reference: img tag with data: src

<img src="data:image/svg+xml,<svg/onload=alert(1)>" alt="SVG injection via data: URI — Z205 trigger">

## Markdown-syntax links — the same vector, different transport

[Inline Markdown link](javascript:alert(document.cookie))

## Reference-style definitions

[Reference link][evil]

[evil]: javascript:void(0)
