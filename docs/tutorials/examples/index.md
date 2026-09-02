---
description: "Gallery of reproducible fixture examples for Zenzic finding codes — each one runnable in seconds with uvx, with real captured output."
---
<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Z-Code Gallery

A reproducible example for 66 of Zenzic's finding codes — each one a real fixture you
can run in seconds, with the output on its page captured from an actual run.

---

## Try It

No install, no clone. Run the whole gallery, or one scenario:

```bash
uvx zenzic lab           # gallery menu
uvx zenzic lab z101      # run one scenario
uvx zenzic lab all       # run all 65 scenarios
```

Or run any fixture directly from a clone of the repository, which is what each
page below walks through:

```bash
cd examples/z101-broken-links
uvx zenzic check all
```

---

## Feature-to-Example Matrix

| Z-Code | What it detects | Example |
| :--- | :--- | :--- |
| Z001 | Invalid configuration structure — configuration guard raise… | [z001-config-error](z0xx-core/z001-config-error) |
| Z101 | Link target not found in the Virtual Site Map | [z101-broken-links](z1xx-links/z101-broken-links) |
| Z102 | Fragment anchor (#anchor) not defined on the target page | [z102-anchor-missing](z1xx-links/z102-anchor-missing) |
| Z103 | Link target exists but is not reachable via site navigation | [z103-orphan-link](z1xx-links/z103-orphan-link) |
| Z104 | Link target file missing from the filesystem | [z104-file-not-found](z1xx-links/z104-file-not-found) |
| Z105 | Absolute path detected — use a relative path for portability | [z105-absolute-path](z1xx-links/z105-absolute-path) |
| Z107 | Self-referential anchor link — slug(text) resolves to the s… | [z107-circular-anchor](z1xx-links/z107-circular-anchor) |
| Z108 | Link label is empty or contains only whitespace | [z108-empty-link-text](z1xx-links/z108-empty-link-text) |
| Z109 | External URL returned an HTTP error or could not be reached | [z109-external-link-broken](z1xx-links/z109-external-link-broken) |
| Z110 | Malformed TOML syntax in configuration file (.zenzic.toml) | [z110-config-syntax-error](z0xx-core/z110-config-syntax-error) |
| Z111 | Invalid schema structure or type in configuration file (.ze… | [z111-config-schema-error](z0xx-core/z111-config-schema-error) |
| Z112 | Stale absolute_path_allowlist entry declared in configurati… | [z112-stale-allowlist](z1xx-links/z112-stale-allowlist) |
| Z120 | HTML attribute not in Safe-Core list — declare intent or su… | [z120-unknown-html-attr](z1xx-links/z120-unknown-html-attr) |
| Z121 | Tag `<a>` or `<img>` has no href/src attribute, or it is empty | [z121-missing-href](z1xx-links/z121-missing-href) |
| Z122 | href="#" detected — placeholder or opaque JS anchor; add de… | [z122-jump-link](z1xx-links/z122-jump-link) |
| Z123 | Non-HTTP scheme (mailto:, tel:, ftp:) — informational; link… | [z123-non-http-scheme](z1xx-links/z123-non-http-scheme) |
| Z124 | Opaque HTML context: blacklisted attribute detected (event-… | [z124-opaque-context](z1xx-links/z124-opaque-context) |
| Z201 | Potential credential or secret detected in documentation co… | [z201-credentials](z2xx-security/z201-credentials) |
| Z202 | Link escapes the documentation root boundary (path traversal) | [z202-path-traversal](z2xx-security/z202-path-traversal) |
| Z203 | Path traversal targeting OS system directories — fatal secu… | [z203-fatal-path-traversal](z2xx-security/z203-fatal-path-traversal) |
| Z204 | Forbidden project term detected in documentation content | [z204-forbidden-term](z2xx-security/z204-forbidden-term) |
| Z205 | Forbidden href scheme detected (javascript: or data:) — pot… | [z205-forbidden-scheme](z2xx-security/z205-forbidden-scheme) |
| Z301 | Reference-style link uses an undefined identifier | [z301-dangling-ref](z3xx-references/z301-dangling-ref) |
| Z302 | Link definition declared but never referenced | [z302-dead-def](z3xx-references/z302-dead-def) |
| Z303 | Reference identifier defined more than once | [z303-duplicate-def](z3xx-references/z303-duplicate-def) |
| Z401 | Directory lacks a required index page | [z401-missing-directory-index](z4xx-topology/z401-missing-directory-index) |
| Z402 | Markdown file not listed in the site navigation | [z402-orphan-page](z4xx-topology/z402-orphan-page) |
| Z403 | Image element has no alt text | [z403-missing-alt](z4xx-topology/z403-missing-alt) |
| Z404 | Asset referenced in engine config not found on disk | [z404-config-asset-missing](z4xx-topology/z404-config-asset-missing) |
| Z405 | Asset file not referenced by any documentation page | [z405-unused-assets](z4xx-topology/z405-unused-assets) |
| Z406 | Navigation contract violation detected | [z406-nav-contract](z4xx-topology/z406-nav-contract) |
| Z410 | Document is isolated and unreachable from the navigation en… | [z410-unreachable-graph-node](z4xx-topology/z410-unreachable-graph-node) |
| Z411 | Document has no outgoing links and forms a structural dead end | [z411-dead-end-node](z4xx-topology/z411-dead-end-node) |
| Z412 | Document lacks required inbound links from specified docume… | [z412-traceability-broken](z4xx-topology/z412-traceability-broken) |
| Z501 | Page contains placeholder or stub content | [z501-placeholder](z5xx-content/z501-placeholder) |
| Z502 | Page word count is below the minimum threshold | [z502-short-content](z5xx-content/z502-short-content) |
| Z503 | Fenced code block contains a syntax error | [z503-snippet-error](z5xx-content/z503-snippet-error) |
| Z505 | Fenced code block has no language specifier | [z505-untagged-code-block](z5xx-content/z505-untagged-code-block) |
| Z506 | Frontmatter boundary is malformed (e.g., opening delimiter… | [z506-malformed-frontmatter](z5xx-content/z506-malformed-frontmatter) |
| Z510 | Heading hierarchy level skipped (e.g., H3 follows H1 withou… | [z510-heading-hierarchy](z5xx-content/z510-heading-hierarchy) |
| Z511 | Sentence length exceeds the maximum readability limit | [z511-excessive-sentence-length](z5xx-content/z511-excessive-sentence-length) |
| Z512 | Heading section contains no body content before next headin… | [z512-empty-section](z5xx-content/z512-empty-section) |
| Z513 | Duplicate heading found within the same document — ensure h… | [z513-duplicate-heading](z5xx-content/z513-duplicate-heading) |
| Z514 | Generic image alt text detected (e.g., 'image', 'screenshot… | [z514-generic-image-alt](z5xx-content/z514-generic-image-alt) |
| Z515 | Bare URL detected in prose — wrap in angle brackets '<url>'… | [z515-bare-url](z5xx-content/z515-bare-url) |
| Z516 | Multiple H1 headings detected in document — ensure exactly… | [z516-multiple-h1](z5xx-content/z516-multiple-h1) |
| Z517 | Heading ends with invalid trailing punctuation (., :, ;) —… | [z517-heading-punctuation](z5xx-content/z517-heading-punctuation) |
| Z518 | Passive voice construction detected — consider using active… | [z518-passive-voice](z5xx-content/z518-passive-voice) |
| Z519 | Weasel word detected in technical prose — use direct, asser… | [z519-weasel-words](z5xx-content/z519-weasel-words) |
| Z520 | Malformed list detected in paragraph — convert to a standar… | [z520-malformed-list](z5xx-content/z520-malformed-list) |
| Z521 | Table matching configured context lacks a required column h… | [z521-required-table-column](z5xx-content/z521-required-table-column) |
| Z522 | Table cell contains a value outside the allowed enumeration… | [z522-table-cell-enum](z5xx-content/z522-table-cell-enum) |
| Z523 | Configured required headings appear out of expected sequent… | [z523-heading-order](z5xx-content/z523-heading-order) |
| Z601 | Deprecated brand term found in documentation source | [z601-brand-obsolescence](z6xx-brand/z601-brand-obsolescence) |
| Z603 | Inline suppression directive does not suppress any active f… | [z603-dead-suppression](z6xx-brand/z603-dead-suppression) |
| Z610 | Required frontmatter key is absent from this document | [z610-required-frontmatter](z6xx-brand/z610-required-frontmatter) |
| Z611 | Link references an external domain forbidden by the [polici… | [z611-forbidden-domain](z6xx-brand/z611-forbidden-domain) |
| Z612 | Forbidden frontmatter key is present in YAML frontmatter block | [z612-forbidden-frontmatter-key](z6xx-brand/z612-forbidden-frontmatter-key) |
| Z613 | Frontmatter key value does not match the required RE2 patte… | [z613-frontmatter-schema-mismatch](z6xx-brand/z613-frontmatter-schema-mismatch) |
| Z614 | Link references an external domain not listed in the Zero-T… | [z614-unapproved-domain](z6xx-brand/z614-unapproved-domain) |
| Z615 | Link uses a URL scheme not permitted by the required_url_sc… | [z615-forbidden-url-scheme](z6xx-brand/z615-forbidden-url-scheme) |
| Z616 | Internal link crosses a forbidden topological namespace bou… | [z616-cross-namespace-link](z6xx-brand/z616-cross-namespace-link) |
| Z617 | Prose content matches a forbidden RE2 regex pattern declare… | [z617-forbidden-content](z6xx-brand/z617-forbidden-content) |
| Z618 | Document does not contain any heading matching the required… | [z618-required-heading](z6xx-brand/z618-required-heading) |
| Z619 | Document complexity score exceeds the maximum limit configu… | [z619-max-complexity](z6xx-brand/z619-max-complexity) |
| Z620 | Global configuration rule was never used during the scan —… | [z620-stale-global-suppression](z6xx-brand/z620-stale-global-suppression) |

---

## See Also {#see-also}

- [Architecture](../../explanation/architecture) — Adapter vs Integration model.
- [Discovery & Exclusion](../../explanation/discovery) — How the Layered Exclusion hierarchy works.
- [Checks Reference](../../reference/checks) — All available `zenzic check` commands and their findings.
- [CLI Reference — lab](../../reference/cli#lab) — Full documentation for `zenzic lab`.
