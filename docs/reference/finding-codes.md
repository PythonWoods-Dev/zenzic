---
description: "Zenzic finding-code quick reference. Severity, penalty, exit code, and remediation for every Zxxx diagnostic identifier."
---

<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Finding Codes Reference

Every issue detected by Zenzic is tagged with a **canonical finding code** (`Zxxx`). This page is the quick-reference cheat sheet — severity, penalty, exit code, and the essential remediation path for every diagnostic signal.

---

## Tier Model

Zenzic organises diagnostics into four operational tiers:

| Tier | Ownership | Format | Scope |
|---|---|---|---|
| Core | Zenzic | `Zxxx` | Built-in scanners and system findings |
| Governance | Zenzic | `Z6xx` | Opt-in policy checks (`[governance]`) |
| Plugin | Third-party | `<plugin-id>:<code>` | External entry-point rules |
| Custom | Project local | `ZZxxx` | `[[custom_rules]]` declared in TOML |

---

## Stability Contract

The code registry is governed by immutable contract surfaces:

- `FROZEN_CODES`: codes that cannot be renumbered or semantically changed without architecture-level approval.
- `NON_SUPPRESSIBLE_CODES`: security codes that cannot be silenced inline.
- `PLUGIN_FORBIDDEN_EXITS`: plugins are forbidden from emitting Exit 2/3 (reserved for core security semantics).

!!! tip "Deep-linking"
    Each code has a permanent anchor. You can link directly to a specific code using `./finding-codes.md#z101`.

---

## Category Overview

| **Category** | **Range** | **Purpose** | **Default Severity** | **Suppressible?** |
|---|---|---|---|:---:|
| **Z0xx** | Migration & Compatibility | Engine deprecation; migration guidance | :material-alert-circle:{ style="color: #e11d48;" } `error` | ❌ No (fatal abort) |
| **Z1xx** | Link Integrity | Broken, empty, circular links; orphaned pages; path issues | :material-alert-circle:{ style="color: #e11d48;" } `error` / :material-alert:{ style="color: #f59e0b;" } `warning` | ✅ Yes (except Z110/Z111, never) |
| **Z2xx** | Security Surface | Secret detection; path traversal; security breaches | :material-shield-alert:{ style="color: #ef4444;" } `fatal` (Exit 2, or Exit 3 for Z203 only — Z202 stays Exit 1) | 🔒 **Never** |
| **Z3xx** | Reference Integrity | Dangling/duplicate reference definitions | :material-alert:{ style="color: #f59e0b;" } `warning` | ✅ Yes |
| **Z4xx** | Topology & Structure | Directory indexes, orphan pages, config assets | :material-information:{ style="color: #0284c7;" } `info` / :material-alert:{ style="color: #f59e0b;" } `warning` | ✅ Yes |
| **Z5xx** | Content Quality | Placeholders, short content, snippet validation | :material-alert:{ style="color: #f59e0b;" } `warning` / :material-alert-circle:{ style="color: #e11d48;" } `error` | ✅ Yes |
| **Z6xx** | Governance | Brand obsolescence, dead suppressions, domain policies | :material-alert:{ style="color: #f59e0b;" } `warning` | ✅ Yes |
| **Z9xx** | Engine & System | Rule execution errors, timeouts, system faults | :material-alert-circle:{ style="color: #e11d48;" } `error` | ✅ Yes |

!!! info "Per-line suppression syntax"
    **Markdown (.md):** `<!-- zenzic:ignore: Zxxx -->`\
    **HTML Tags:** `<a href="..." data-zenzic-ignore="Zxxx">`\
    See [Suppression Policy](./suppression-policy.md) for the full reference.

### Exit Code Contract

| Exit Code | Meaning | Suppressible? | Execution Impact |
| :---: | :--- | :---: | :--- |
| **0** | All checks passed (or suppressed via `--exit-zero`) | — | Clean Pass / Normal Completion |
| **1** | Errors and warnings detected; use `--strict` to promote warnings | ✅ Yes | Standard Gate Failure |
| **2** | Security breaches (Z201, Z204, Z205). **Never** suppressed | ❌ Never | **Fatal Security Override** |
| **3** | Security incidents (Z203 PATH_TRAVERSAL_FATAL). **Never** suppressed | ❌ Never | **Fatal Boundary Breach** |

---

## Severity Levels and Pipeline Impact {#severity-pipeline-impact}

Every finding code carries a **severity** that determines its DQS math contribution and its pipeline gate behaviour. The `inspect codes` table makes these values explicit via the **Severity** and **Penalty** columns.

### Standard Severity Levels

| Severity | DQS Math | CI Gate Behaviour | Suppressible? |
|---|---|---|---|
| `error` | Subtracts the code's penalty from the category bucket | Triggers Exit 1. Promotes to Exit 2/3 for Z2xx codes. | ✅ Yes (except Z2xx) |
| `warning` | Subtracts the code's penalty from the category bucket | Triggers Exit 1 only under `--strict` mode | ✅ Yes |
| `note` (0.0) | **Zero** — no points deducted | **Never** fails the CI gate. Always exits 0. | ✅ Yes |

**`error`** findings subtract their penalty points and unconditionally trigger Exit 1 (or higher for security codes). If the resulting DQS score drops below `fail_under`, the gate fails even without a specific error-level finding.

**`warning`** findings subtract their penalty points. They are invisible to the CI gate in default mode. With `--strict`, warnings are promoted to errors and become gate-blocking.

**`note` / 0.0** findings are purely informational telemetry. They never subtract points, never fail the gate, and are hidden by default (`--show-info` is required to display them). Z106 (CIRCULAR_LINK) is an example.

### Override Penalties: FATAL and HALT

Two additional pipeline states are shown in `inspect codes` that override the standard math model:

#### FATAL

```text
Penalty: FATAL
```

Displayed for **Z0xx** (configuration abort) and **Z2xx** (Security Codes). These codes do not subtract points incrementally — they trigger a **Security Override** that collapses the entire DQS to **0/100** unconditionally.

- **Z0xx** (e.g. Z000 `UNSUPPORTED_ENGINE`): Fatal configuration error. Execution halts before any scan begins. Exit 1.
- **Z2xx** (Z201–Z205): Security Breach or Security Incident. The score collapses to 0 regardless of all other findings. Exit 2 (breach) or Exit 3 (incident, Z203 only). **Cannot be suppressed.**

> The FATAL label replaces `0.0` in the Penalty column to prevent the dangerous misreading that security codes are "harmless" because they carry no incremental point deduction.

#### HALT

```text
Penalty: HALT
```

Displayed for **`warning`-severity codes with a 0.0 penalty** — codes that do not subtract math points but act as **hard pipeline blockers** through the CI gate logic rather than through the scoring formula.

Examples:

| Code | Name | Why HALT, not a number |
|---|---|---|
| Z504 | QUALITY_REGRESSION | Triggers when the current DQS regresses below the saved baseline. Not scored itself (that would be circular). Blocks `zenzic diff` gate. |
| Z901 | RULE_ENGINE_ERROR | Scanner crash. Partial results may be unreliable; pipeline cannot pass. |
| Z902 | RULE_TIMEOUT | Scanner timed out (ReDoS risk). Partial results are untrustworthy. |

> HALT codes are the most semantically dangerous codes in the table: they look like `warning` entries with no visible cost, but they unconditionally block CI when triggered. The HALT label makes this explicit.

### Summary Table

| `inspect codes` Penalty display | Meaning | DQS impact | CI impact |
|---|---|---|---|
| `-8.0`, `-2.0`, etc. | Standard penalty deducted from DQS bucket | Reduces score by that amount per occurrence | Fails gate if score drops below `fail_under` |
| `0.0` (dim) | Informational note — no cost | None | None — exits 0 |
| **FATAL** | Security Override (Z0xx, Z2xx) | Collapses DQS to 0/100 | Mandatory Exit 1/2/3 |
| **HALT** | Pipeline block gate (warning + 0.0) | None | Mandatory Exit 1 when triggered |

---

## Z0xx — Migration & Compatibility

Migration and legacy engine compatibility diagnostic findings.

---

### Z000: UNSUPPORTED_ENGINE {#z000}

**Severity:** `error` (fatal abort) · **Penalty:** none · **Exit:** 1 · **Suppressible:** No · [↗ Rule Specification](../rules/Z000.md)

Fatal configuration error: the adapter factory encountered a deprecated or removed engine alias in `.zenzic.toml`. Execution stops before any scan begins — Z000 does not appear in `--format json` output.

**Fix:**

1. Open `.zenzic.toml` and set `engine = "standalone"` (or `"mkdocs"`, `"zensical"`).
2. Remove any legacy engine alias.

---

## Z1xx — Link Integrity

Diagnostic findings related to link targets, anchors, and Virtual Site Map resolution.

---

### Z001: CORE_CONFIG_STRUCTURE {#z001}

**Severity:** `error` · **Penalty:** none · **Exit:** 1 · **Suppressible:** No · [↗ Rule Specification](../rules/Z001.md)

This rule exists to detect when an invalid configuration structure is detected (ZenzicConfigError before analysis).

---

### Z101: LINK_BROKEN {#z101}

**Severity:** `error` · **Penalty:** −8.0 pts (Structural) · **Exit:** 1 · **Suppressible:** Yes · [↗ Gallery](../tutorials/examples/z1xx-links/z101-broken-links.md) · [↗ Rule Specification](../rules/Z101.md)

A relative link points to a resource not found in the Virtual Site Map. The file may be outside `docs_dir` scope or matched by an exclusion rule.

**Fix:**

1. Verify the physical file exists.
2. Correct the relative path (e.g. `../folder/target.md`).
3. Confirm the file is not matched by `ignored_patterns` in config.

---

### Z102: ANCHOR_MISSING {#z102}

**Severity:** `error` · **Penalty:** −5.0 pts (Structural) · **Exit:** 1 · **Suppressible:** Yes · [↗ Gallery](../tutorials/examples/z1xx-links/z102-anchor-missing.md) · [↗ Rule Specification](../rules/Z102.md)

The link target file exists (Z101 passes), but the specific HTML anchor (e.g. `#setup`) is absent from the target file's header registry. Zenzic parses all headings and explicit `<a id="...">` tags during Pass 1.

**Fix:**

1. Check the target file's heading text and verify the anchor slug.
2. Ensure Kebab-case slugification matches the Markdown engine.
3. Use `{#id}` or `<a id="id"></a>` for custom IDs.

---

### Z103: ORPHAN_LINK {#z103}

**Severity:** `error` · **Penalty:** −2.0 pts (Structural) · **Exit:** 1 · **Suppressible:** Yes · [↗ Gallery](../tutorials/examples/z1xx-links/z103-orphan-link.md) · [↗ Rule Specification](../rules/Z103.md)

The link target exists in the VSM but is not reachable through any navigation structure (sidebar/nav). Users can reach it only by direct URL.

**Fix:**

1. Add the file to `nav` (MkDocs).
2. If the hidden page is intentional, suppress with `<!-- zenzic:ignore: Z103 -->`.

---

### Z104: FILE_NOT_FOUND {#z104}

**Severity:** `error` · **Penalty:** −8.0 pts (Structural) · **Exit:** 1 · **Suppressible:** Yes · [↗ Rule Specification](../rules/Z104.md)

Low-level filesystem error: the engine could not open a file referenced by a link.
In a full `zenzic check` scan, this condition is consolidated and emitted under
**`Z101` LINK_BROKEN** rather than `Z104` — see the [LINK_BROKEN entry](#z101). The Language
Server's incremental analysis engine (used for live editor diagnostics) is a separate code path
and **does** emit a genuine, distinct `Z104` for a missing local asset file.

```text
blog/post.md:12: '/blog/zenzic-v070' not found in the site map
💡 Did you mean: '/blog/zenzic-v070-release/'?
```

**Fix:**

1. Verify no concurrent process is modifying `docs/` during the scan.
2. Check `docs_dir` is correct and the file path is absolute relative to the repo root.
3. *(Slug-mismatch)* Run `zenzic inspect routes --kind physical` to list all canonical slugs in the VSM. Update the link to match the exact frontmatter `slug:`.

---

### Z105: ABSOLUTE_PATH {#z105}

**Severity:** `error` · **Penalty:** −2.0 pts (Structural) · **Exit:** 1 · **Suppressible:** Yes · [↗ Gallery](../tutorials/examples/z1xx-links/z105-absolute-path.md) · [↗ Rule Specification](../rules/Z105.md)

An absolute filesystem path (e.g. `C:\Docs\page.md` or `/home/user/docs/page.md`) breaks documentation portability. Project-owned URL prefixes (`/blog/`, `/docs/`) are exempt from Z105 but still checked via VSM lookup (a missing slug raises **Z104** instead).

**Fix:**

1. Convert to a relative path from the current file's directory.
2. Use `@site/` or engine-specific aliases where supported.
3. If you received Z104 on an absolute `/blog/` link, see Z104 remediation above.

---

### Z106: CIRCULAR_LINK {#z106}

**Severity:** `info` · **Penalty:** 0.0 pts · **Exit:** 0 · **Suppressible:** Yes (informational only, `--show-info`) · [↗ Rule Specification](../rules/Z106.md)

A set of links forms a directed cycle (A → B → A). This is a structural telemetry signal — it does not block the Quality Gate or reduce the DQS.

**Fix:** Review the content flow; consider replacing one link with a "See Also" section. No action required if the cycle is intentional.

---

### Z107: CIRCULAR_ANCHOR {#z107}

**Severity:** `error` · **Penalty:** −1.0 pt (Structural) · **Exit:** 1 · **Suppressible:** Yes · [↗ Rule Specification](../rules/Z107.md)

A link of the form `[text](#anchor)` resolves to a heading on the **same** page — a self-loop that navigates the reader to exactly where they already are. Distinct from a ToC entry (which links forward to a lower anchor on a long page).

**Fix:**

1. Replace `[text](#anchor)` with plain prose if no navigation is intended.
2. Or link to the concept on a different page.

---

### Z108: EMPTY_LINK_TEXT {#z108}

**Severity:** `error` · **Penalty:** −1.0 pt (Structural) · **Exit:** 1 · **Suppressible:** Yes · **Fixable:** Yes · [↗ Gallery](../tutorials/examples/z1xx-links/z108-empty-link-text.md) · [↗ Rule Specification](../rules/Z108.md)

Inline Markdown link or collapsed reference link has empty or whitespace-only visible text — e.g. `[](./page.md)`, `[ ](./page.md)`, `[][ref]`. Breaks screen reader accessibility and semantic indexing simultaneously.

**Fix:**

1. Add descriptive link text: `[Documentation](./page.md)`.
2. Remove the link entirely if the destination is not yet known.

---

### Z109: EXTERNAL_LINK_BROKEN {#z109}

**Severity:** `error` · **Penalty:** −3.0 pt (Structural) · **Exit:** 1 · **Suppressible:** Yes · [↗ Gallery](../tutorials/examples/z1xx-links/z109-external-link-broken.md) · [↗ Rule Specification](../rules/Z109.md)

An external URL returned an HTTP error status code (e.g. 404, 500) or was completely unreachable due to a connection timeout or DNS resolution failure during scan.
Cataloged separately, but the current engine consolidates and emits this
condition under **`Z101` LINK_BROKEN** rather than `Z109` — see the [LINK_BROKEN entry](#z101).

**Fix:**

1. Check the target URL in a web browser.
2. Correct the URL if misspelled, or remove the link if the destination has ceased to exist.

---

### Z110: CONFIG_SYNTAX_ERROR {#z110}

**Severity:** `error` · **Penalty:** none · **Exit:** 1 · **Suppressible:** No · [↗ Rule Specification](../rules/Z110.md)

The `.zenzic.toml` (or `pyproject.toml`) workspace configuration file contains a malformed TOML syntax error. Zenzic halts document analysis before any Markdown file is read to prevent cascading false positives or running with corrupted governance policies.

**Fix:**

1. Fix the TOML syntax error in `.zenzic.toml` indicated in the diagnostic message (such as missing quotes, unclosed brackets, or unescaped characters).

---

### Z111: CONFIG_SCHEMA_ERROR {#z111}

**Severity:** `error` · **Penalty:** none · **Exit:** 1 · **Suppressible:** No · [↗ Rule Specification](../rules/Z111.md)

The `.zenzic.toml` (or `pyproject.toml`) configuration file contains an invalid schema structure, unknown key, or data type mismatch (e.g. providing a string instead of an integer). Zenzic halts document analysis before any Markdown file is read to protect workspace integrity.

**Fix:**

1. Correct the configuration key name or value type in `.zenzic.toml` as indicated by the field error in the diagnostic message.

---

### Z112: STALE_ALLOWLIST_ENTRY {#z112}

**Severity:** `warning` · **Penalty:** −1.0 pt (Structural) · **Exit:** 1 · **Suppressible:** Yes · [↗ Rule Specification](../rules/Z112.md)

An entry in the `absolute_path_allowlist` configuration was never matched by any scanned absolute path link. This indicates that the entry is stale and no longer needed.

**Fix:**

1. Open `.zenzic.toml` (or `pyproject.toml`) and locate `absolute_path_allowlist`.
2. Remove the unused entry from the list.

---

### Z120: UNKNOWN_HTML_ATTR {#z120}

**Severity:** `warning` · **Penalty:** −1.0 pt (Structural) · **Exit:** 1 · **Suppressible:** Yes · [↗ Gallery](../tutorials/examples/z1xx-links/z120-unknown-html-attr.md)

An HTML `<a>` tag contains unknown or malformed attributes.

**Fix:** Correct the HTML tag attributes or use `data-zenzic-ignore="Z120"` to suppress.

---

### Z121: MISSING_HREF {#z121}

**Severity:** `error` · **Penalty:** −1.0 pt (Structural) · **Exit:** 1 · **Suppressible:** Yes · [↗ Gallery](../tutorials/examples/z1xx-links/z121-missing-href.md)

An HTML `<a>` tag is missing the required `href` attribute.

**Fix:** Add a valid `href="..."` attribute to the anchor tag.

---

### Z122: JUMP_LINK {#z122}

**Severity:** `warning` · **Penalty:** −1.0 pt (Navigation) · **Exit:** 1 · **Suppressible:** Yes · [↗ Gallery](../tutorials/examples/z1xx-links/z122-jump-link.md)

An HTML tag uses `href="javascript:void(0)"` or `href="#"`, which is an anti-pattern for documentation.

**Fix:** Replace with an actual URL or remove the anchor tag.

---

### Z123: NON_HTTP_SCHEME {#z123}

**Severity:** `info` · **Penalty:** 0.0 pts · **Exit:** 0 · **Suppressible:** Yes · [↗ Gallery](../tutorials/examples/z1xx-links/z123-non-http-scheme.md)

An HTML tag uses an unusual scheme (e.g., `ftp://`, `ssh://`) instead of `http/https`.

**Fix:** Verify the scheme is intentional, or suppress if necessary.

---

### Z124: OPAQUE_CONTEXT {#z124}

**Severity:** `error` · **Penalty:** −1.0 pt (Structural) · **Exit:** 1 · **Suppressible:** Yes · [↗ Gallery](../tutorials/examples/z1xx-links/z124-opaque-context.md)

An HTML link has an opaque context or relies on inline scripts for navigation.

**Fix:** Refactor the link to be statically identifiable.

---

## Z2xx — Security (credential scanner)

!!! danger "🔒 NON-SUPPRESSIBLE SECURITY GOVERNANCE"
    All `Z2xx` Security findings are strictly **Non-Suppressible** across the Zenzic engine and Language Server Protocol (LSP). `<!-- zenzic:ignore: Z2xx -->` directives are silently rejected, and the editor will **never** offer inline suppression Code Actions for security findings. Security breaches must be resolved at the source.

---

### Z201: CREDENTIAL_SECRET {#z201}

!!! danger "🔒 INVIOLABLE — Cannot be suppressed | Exit 2 | DQS collapses to 0/100"
    `zenzic:ignore: Z201` is **silently rejected**. The credential scanner fires unconditionally on every line. [↗ Gallery](../tutorials/examples/z2xx-security/z201-credentials.md)

**Severity:** `security_breach` · **Penalty:** DQS collapses to 0/100 · **Exit:** 2 · [↗ Rule Specification](../rules/Z201.md)

The credential scanner uses deterministic pattern matching (e.g., RE2) to detect known structural secrets (like AWS keys or GitHub tokens) without exponential backtracking, rather than relying on high-noise entropy checks. Speculative Base64 decoding is also applied — encoded tokens that decode to credential patterns are flagged.

**Fix:**

1. **IMMEDIATE:** Rotate the leaked credential — it is compromised.
2. Remove the secret from the file.
3. Purge the git history using `git-filter-repo`.
4. Use placeholders such as `YOUR_API_KEY` in documentation examples.

---

### Z202: PATH_TRAVERSAL {#z202}

!!! danger "🔒 INVIOLABLE — Cannot be suppressed | Exit 1 | DQS collapses to 0/100"
    `zenzic:ignore: Z202` is **silently rejected**. [↗ Gallery](../tutorials/examples/z2xx-security/z202-path-traversal.md)

**Severity:** `error` · **Penalty:** DQS collapses to 0/100 · **Exit:** 1 · [↗ Rule Specification](../rules/Z202.md)

The Path Traversal Guard intercepts any relative links attempting to escape the documentation root (e.g. `../.env`). A relative path uses `..` segments to escape the `docs/` boundary, potentially exposing private repository files.

**Fix:**

1. Move the target asset into the `docs/` or `static/` hierarchy.
2. If you must reference an external file, use a symbolic link (if permitted) or a literal absolute URL.

---

### Z203: PATH_TRAVERSAL_FATAL {#z203}

!!! danger "🔒 INVIOLABLE — Cannot be suppressed | Exit 3 (highest) | DQS collapses to 0/100"
    `zenzic:ignore: Z203` is **silently rejected**. Distinct from Z202: targets OS directories (`/etc/`, `/root/`) signalling supply-chain compromise.

**Severity:** `security_incident` · **Penalty:** DQS collapses to 0/100 · **Exit:** 3 · [↗ Rule Specification](../rules/Z203.md)

Path traversal detected targeting restricted OS directories (e.g. `/etc/`, `/root/`). Cannot result from a legitimate documentation workflow — presence indicates template injection, a compromised toolchain, or a malicious commit.

**Fix:**

1. Investigate the source file for malicious intent or supply-chain compromise.
2. Remove all absolute paths referencing host-system locations.
3. Audit your CI pipeline for injection vectors.

---

### Z204: FORBIDDEN_TERM {#z204}

!!! danger "🔒 INVIOLABLE — Cannot be suppressed | Exit 2 | DQS collapses to 0/100"
    `zenzic:ignore: Z204` is **silently rejected**. Source: `forbidden_patterns` in `.zenzic.local.toml` (git-ignored). [↗ Gallery](../tutorials/examples/z2xx-security/z204-forbidden-term.md)

**Severity:** `security_breach` · **Penalty:** DQS collapses to 0/100 · **Exit:** 2 · [↗ Rule Specification](../rules/Z204.md)

The Privacy Gate detected a confidential project term (internal code-name, staging hostname, team alias) configured in `.zenzic.local.toml`. Matching is case-insensitive verbatim substring — no regex. Run `zenzic init` to scaffold `.zenzic.local.toml` (auto-added to `.gitignore`).

!!! info "Brand integrity — two layers"
    | Layer | Source | Scope | Severity |
    |---|---|---|---|
    | **Z204 Privacy Gate** | `forbidden_patterns` in `.zenzic.local.toml` *(git-ignored)* | Private terms — code-names, staging hosts | **Exit 2 (Critical)** |
    | **Z601 Brand Guard** | `[governance].brand_obsolescence` in `.zenzic.toml` | Deprecated brand terms | Exit 1 (Quality) |

**Fix:**

1. Remove or generalise the forbidden term.
2. If the term is legitimately public, remove it from `forbidden_patterns`.
3. Verify `.zenzic.local.toml` is in `.gitignore`.

---

### Z205: FORBIDDEN_SCHEME {#z205}

!!! danger "🔒 INVIOLABLE — Cannot be suppressed | Exit 2 | DQS collapses to 0/100"
    `zenzic:ignore: Z205` and `data-zenzic-ignore="Z205"` are **silently rejected**. [↗ Gallery](../tutorials/examples/z2xx-security/z205-forbidden-scheme.md)

**Severity:** `security_breach` · **Penalty:** DQS collapses to 0/100 · **Exit:** 2

The Polyglot Extractor detected a highly dangerous scheme (such as `javascript:` or `data:text/html`) in an HTML `href` attribute. This is an XSS injection vector and is strictly forbidden.

**Fix:**

1. **IMMEDIATE:** Remove the injected `javascript:` payload.
2. Investigate how the malicious HTML reached the documentation source.

---

## Z3xx — Reference Integrity

Diagnostic findings related to reference-style links and definition definitions.

---

### Z301: DANGLING_REF {#z301}

**Severity:** `warning` · **Penalty:** −4.0 pts (Navigation) · **Exit:** 1 · **Suppressible:** Yes · [↗ Gallery](../tutorials/examples/z3xx-references/z301-dangling-ref.md) · [↗ Rule Specification](../rules/Z301.md)

A reference-style link (`[my link][ref]`) exists but its definition (`[ref]: http://...`) is missing. Most renderers silently degrade the link to plain text. Ensure your Markdown formatter (like Prettier or Markdownlint) does not inadvertently remove unused reference definitions during an automated pass, which can cause downstream references to dangle.

**Fix:**

1. Add the missing definition at the bottom of the Markdown file.
2. Check for typos in the reference ID.

---

### Z302: DEAD_DEF {#z302}

**Severity:** `warning` · **Penalty:** −1.0 pt (Navigation) · **Exit:** 1 · **Suppressible:** Yes · [↗ Gallery](../tutorials/examples/z3xx-references/z302-dead-def.md) · [↗ Rule Specification](../rules/Z302.md)

A reference definition exists but no link in the file uses it. Harmless for readers but creates maintenance debt.

**Fix:** Remove the unused definition, or update a link to use this reference.

---

### Z303: DUPLICATE_DEF {#z303}

**Severity:** `warning` · **Penalty:** −3.0 pts (Navigation) · **Exit:** 1 · **Suppressible:** Yes · [↗ Gallery](../tutorials/examples/z3xx-references/z303-duplicate-def.md) · [↗ Rule Specification](../rules/Z303.md)

Multiple definitions exist for the same reference ID. CommonMark specifies that the first definition wins, but this ambiguity should be resolved for deterministic cross-engine rendering.

**Fix:** Ensure each reference ID has exactly one definition; consolidate duplicates into a single canonical reference.

---

## Z4xx — Structure

Diagnostic findings related to Virtual Site Map topology and navigation structure.

---

### Z401: MISSING_DIRECTORY_INDEX {#z401}

**Severity:** `info` · **Penalty:** none (structural hint) · **Exit:** 0 · **Suppressible:** Yes · [↗ Rule Specification](../rules/Z401.md)

A documentation directory has no `index.md` or `README.md`. The directory URL may return 404 or a raw listing depending on the build engine.

**Fix:** Create `index.md` in the flagged directory with a brief section overview.

---

### Z402: ORPHAN_PAGE {#z402}

**Severity:** `warning` · **Penalty:** −4.0 pts (Navigation) · **Exit:** 1 · **Suppressible:** Yes · [↗ Gallery](../tutorials/examples/z4xx-topology/z402-orphan-page.md) · [↗ Rule Specification](../rules/Z402.md)

A file exists in `docs/` but is not reachable from any navigation menu. The documentation equivalent of dead code.

**Fix:**

1. Add the file to `nav` (MkDocs).
2. Delete the file if it is a leftover artifact.

---

### Z403: MISSING_ALT {#z403}

**Severity:** `warning` · **Penalty:** −1.0 pt (Content) · **Exit:** 1 · **Suppressible:** Yes · [↗ Gallery](../tutorials/examples/z4xx-topology/z403-missing-alt.md) · [↗ Rule Specification](../rules/Z403.md)

An image has no alt text, degrading screen reader accessibility and SEO.

**Fix:** Add descriptive text: `![A description of the image](url)`. Avoid generic labels like "image" or "screenshot".

---

### Z404: CONFIG_ASSET_MISSING {#z404}

**Severity:** `warning` · **Penalty:** −3.0 pts (Governance) · **Exit:** 1 · **Suppressible:** Yes · [↗ Rule Specification](../rules/Z404.md)

The build engine's main configuration (e.g. `zensical.toml`) references a logo or favicon that does not exist at the specified path. The failure is global: every page in every locale ships without the branding asset.

**Fix:**

1. Check `favicon:` or `logo.src:` paths in your config file.
2. Ensure the asset is physically present in the target folders.

---

### Z405: UNUSED_ASSET {#z405}

**Severity:** `warning` · **Penalty:** −3.0 pts (Governance) · **Exit:** 1 · **Suppressible:** Yes · [↗ Rule Specification](../rules/Z405.md)

An image or asset file in the repository is never referenced by any Markdown file. "Dark Assets" bloat the repository and build artifacts silently.

!!! info "Infrastructure Exemptions"
    Standard infrastructure files (`robots.txt`, `_redirects`, `CNAME`, `sitemap.xml`) are natively exempt from this check by the core engine. They will never trigger a Z405 finding.

**Fix:**

1. Delete the unused file.
2. Or reference it in a documentation page where appropriate.

---

### Z406: NAV_CONTRACT {#z406}

**Severity:** `warning` · **Penalty:** −2.0 pts (Governance) · **Exit:** 1 · **Suppressible:** Yes · [↗ Rule Specification](../rules/Z406.md)

A conflict between the physical file structure and the engine's navigation config. For MkDocs: a `nav` entry pointing to a path that no physical file activates.

**Fix:**

1. Align the nav path in your config with the physical file path.
2. Run `zenzic check all` to verify the fix across the VSM.

---

### Z410: UNREACHABLE_GRAPH_NODE {#z410}

**Severity:** `warning` · **Penalty:** −5.0 pt (Structural) · **Exit:** 1 · **Suppressible:** Yes · [↗ Rule Specification](../rules/Z410.md)

This rule exists to detect when an internal document is physically present but unreachable from any node in the Virtual Site Map.

---

### Z411: DEAD_END_NODE {#z411}

**Severity:** `warning` · **Penalty:** −5.0 pt (Structural) · **Exit:** 1 · **Suppressible:** Yes · [↗ Rule Specification](../rules/Z411.md)

This rule exists to detect when an active document has no outgoing navigational edges to the rest of the site structure.

---

### Z412: TRACEABILITY_BROKEN {#z412}

**Severity:** `warning` · **Penalty:** −4.0 pt (Navigation) · **Exit:** 1 · **Suppressible:** Yes · **Opt-In** · [↗ Rule Specification](../rules/Z412.md)

This rule exists to verify that target specification documents have at least one incoming reference from configured source namespaces (`[policies].traceability_targets`), ensuring complete cross-architecture traceability.

---

## Z5xx — Content Quality

Diagnostic findings related to prose quality, sentence length, and structural formatting.

---

### Z501: PLACEHOLDER {#z501}

**Severity:** `warning` · **Penalty:** −2.0 pts (Content) · **Exit:** 1 · **Suppressible:** Yes · [↗ Gallery](../tutorials/examples/z5xx-content/z501-placeholder.md) · [↗ Rule Specification](../rules/Z501.md)

Placeholder strings committed to production documentation signal incomplete work. Examples include:

```text
TODO
FIXME
[INSERT IMAGE HERE]
```

**Fix:** Replace the placeholder with actual content, or remove it until the content is ready.

---

### Z502: SHORT_CONTENT {#z502}

**Severity:** `warning` · **Penalty:** −1.0 pt (Content) · **Exit:** 1 · **Suppressible:** Yes · [↗ Gallery](../tutorials/examples/z5xx-content/z502-short-content.md) · [↗ Rule Specification](../rules/Z502.md)

A page contains fewer than 50 words of rendered prose (frontmatter, Markdown comments, and HTML comments excluded). A page below this threshold cannot contain the semantic components necessary to answer a reader's question.

**Fix:** Expand the page, or combine it with a related page.

---

### Z503: SNIPPET_ERROR {#z503}

**Severity:** `warning` · **Penalty:** −10.0 pts (Content — highest single-occurrence penalty) · **Exit:** 1 · **Suppressible:** Yes · [↗ Gallery](../tutorials/examples/z5xx-content/z503-snippet-error.md) · [↗ Rule Specification](../rules/Z503.md)

The Snippet Guard identified a syntax error in a fenced code block marked with a language tag. The reported line number is **absolute** — relative to the source file, not to the start of the snippet.

**Fix:**

1. Correct the syntax within the code block.
2. For intentionally broken examples, use `` ```text `` to bypass validation.

!!! tip "Documenting type signatures and incomplete snippets"
    If you are documenting a **function signature**, a **type stub**, or any fragment
    that is not syntactically complete (e.g., a parameter list without a surrounding
    `def` statement), use `` ```text `` instead of the actual language tag.

    **Z503 (error — do not do this):**

    ````markdown
    ```text
    my_function(
        param: str,
        other: int = 0,
    )
    ```
    ````

    **Correct (use `text`):**

    ````markdown
    ```text
    my_function(
        param: str,
        other: int = 0,
    )
    ```
    ````

    The `text` identifier preserves monospace formatting and disables syntax validation.
    Use it whenever the snippet is display-only and not intended to be copy-pasted
    as runnable code.

---

### Z505: UNTAGGED_CODE_BLOCK {#z505}

**Severity:** `warning` · **Penalty:** −1.0 pt (Content) · **Exit:** 1 · **Suppressible:** Yes · **Fixable:** Yes · [↗ Gallery](../tutorials/examples/z5xx-content/z505-untagged-code-block.md) · [↗ Rule Specification](../rules/Z505.md)

A fenced code block has no language specifier. Syntax highlighters, the Snippet Guard (Z503), and screen readers cannot process it. Some engine-specific metadata (e.g. `` ```python title="file.py" showLineNumbers ``) is fully supported and never flagged.

**Fix:** Add a language tag: `` ```python ``, `` ```bash ``, `` ```toml ``. For display-only blocks, use `` ```text `` or `` ```plaintext ``.

---

### Z506: MALFORMED_FRONTMATTER {#z506}

**Severity:** `error` · **Penalty:** −5.0 pts (Content) · **Exit:** 1 · **Suppressible:** Yes · [↗ Gallery](../tutorials/examples/z5xx-content/z506-malformed-frontmatter.md) · [↗ Rule Specification](../rules/Z506.md)

The opening frontmatter delimiter on line 1 of the file is not exactly `---`. Any line that starts with two or more dashes but is not exactly `---` — such as `--`, `----`, or `--- trailing chars` — is silently discarded by most static-site engines. The `template:`, `title:`, and all metadata keys will be rendered as raw prose content instead of being parsed.

**Common triggers:**

- Typo: `--` (two dashes) instead of `---`
- Copy-paste artefact: `----` (four or more dashes)
- Trailing text: `--- @generated` or `--- BEGIN YAML`

**Fix:** Ensure the very first line of the file is exactly `---` with no leading or trailing characters.

---

### Z510: HEADING_HIERARCHY {#z510}

**Severity:** `warning` · **Penalty:** −1.0 pt (Content) · **Exit:** 1 · **Suppressible:** Yes · [↗ Rule Specification](../rules/Z510.md)

This rule exists to detect when a heading level skips one or more levels in the document hierarchy.

---

### Z511: EXCESSIVE_SENTENCE_LENGTH {#z511}

**Severity:** `warning` · **Penalty:** −1.0 pt (Content) · **Exit:** 1 · **Suppressible:** Yes · [↗ Rule Specification](../rules/Z511.md)

This rule exists to detect when a sentence in the markdown body exceeds the maximum configured word limit.

---

### Z512: EMPTY_SECTION {#z512}

**Severity:** `warning` · **Penalty:** −1.0 pt (Content) · **Exit:** 1 · **Suppressible:** Yes · [↗ Rule Specification](../rules/Z512.md)

This rule exists to detect when a heading section contains no body content before the next section or EOF.

---

### Z513: DUPLICATE_HEADING {#z513}

**Severity:** `warning` · **Penalty:** −2.0 pt (Content) · **Exit:** 1 · **Suppressible:** Yes · [↗ Rule Specification](../rules/Z513.md)

This rule exists to detect when two or more headings within the same document resolve to identical text, preventing ambiguous anchor collisions.

---

### Z514: GENERIC_IMAGE_ALT_TEXT {#z514}

**Severity:** `warning` · **Penalty:** −2.0 pt (Content) · **Exit:** 1 · **Suppressible:** Yes · [↗ Rule Specification](../rules/Z514.md)

This rule exists to detect when an image uses generic filler words (such as "image" or "screenshot") as its alternative text instead of providing descriptive accessibility content.

---

### Z515: BARE_URL_USED {#z515}

**Severity:** `warning` · **Penalty:** −1.0 pt (Content) · **Exit:** 1 · **Suppressible:** Yes · **Auto-fixable:** Yes · [↗ Rule Specification](../rules/Z515.md)

This rule exists to detect raw URLs in prose that are not properly enclosed in angle brackets (`<url>`) or formatted as Markdown links (`[text](url)`).

---

### Z516: MULTIPLE_H1_HEADINGS {#z516}

**Severity:** `error` · **Penalty:** −5.0 pt (Content) · **Exit:** 1 · **Suppressible:** Yes · [↗ Rule Specification](../rules/Z516.md)

This rule exists to enforce that every document has at most one top-level H1 heading for structural hierarchy and document outline integrity.

---

### Z517: HEADING_PUNCTUATION {#z517}

**Severity:** `warning` · **Penalty:** −1.0 pt (Content) · **Exit:** 1 · **Suppressible:** Yes · **Auto-fixable:** Yes · [↗ Rule Specification](../rules/Z517.md)

This rule exists to detect headings that end with invalid trailing punctuation (such as periods, colons, or semicolons).

---

### Z518: PASSIVE_VOICE_DETECTED {#z518}

**Severity:** `warning` · **Penalty:** −1.0 pt (Content) · **Exit:** 1 · **Suppressible:** Yes · **Opt-In** · [↗ Rule Specification](../rules/Z518.md)

This rule exists to detect passive voice constructions in prose via deterministic RE2 heuristic matching, promoting direct and active technical prose.

---

### Z519: WEASEL_WORDS {#z519}

**Severity:** `warning` · **Penalty:** −1.0 pt (Content) · **Exit:** 1 · **Suppressible:** Yes · **Opt-In** · [↗ Rule Specification](../rules/Z519.md)

This rule exists to detect weasel words (e.g., "clearly", "simply", "obviously") that weaken technical prose.

---

### Z520: MALFORMED_LIST_DETECTED {#z520}

**Severity:** `warning` · **Penalty:** −2.0 pt (Content) · **Exit:** 1 · **Suppressible:** Yes · **Auto-fixable:** Yes · [↗ Rule Specification](../rules/Z520.md)

This rule exists to detect pseudo-lists in paragraphs that use newlines and semicolons/commas but lack Markdown list markers (`-`, `*`, `1.`), preventing accessibility and HTML list rendering degradation.

---

### Z521: REQUIRED_TABLE_COLUMN {#z521}

**Severity:** `warning` · **Penalty:** −2.0 pt (Content) · **Exit:** 1 · **Suppressible:** Yes · **Opt-In** · [↗ Rule Specification](../rules/Z521.md)

This rule exists to detect Markdown tables that omit required column headers specified in `[policies].required_table_columns`.

---

### Z522: TABLE_CELL_ENUM {#z522}

**Severity:** `warning` · **Penalty:** −2.0 pt (Content) · **Exit:** 1 · **Suppressible:** Yes · **Opt-In** · [↗ Rule Specification](../rules/Z522.md)

This rule exists to validate that table cells in designated columns only contain approved enumeration values declared in `[policies].table_cell_enums`.

---

### Z523: HEADING_ORDER_VIOLATION {#z523}

**Severity:** `warning` · **Penalty:** −2.0 pt (Content) · **Exit:** 1 · **Suppressible:** Yes · **Opt-In** · [↗ Rule Specification](../rules/Z523.md)

This rule exists to enforce that document headings appear in the strictly ascending sequential order defined in `[policies].required_heading_order`.

---

## Z6xx — Governance

Diagnostic findings related to brand governance, deprecation, suppression audit state, and Policy-as-Code violations (v0.28.0).

---

### Z601: BRAND_OBSOLESCENCE {#z601}

**Severity:** `warning` · **Penalty:** −2.0 pts (Governance) + Escalation · **Exit:** 1 · **Suppressible:** Yes · [↗ Gallery](../tutorials/examples/z6xx-brand/z601-brand-obsolescence.md) · [↗ Rule Specification](../rules/Z601.md)

A deprecated release name or brand identifier appears in a scanned file. Configured via `[governance].brand_obsolescence` in `.zenzic.toml`. CHANGELOG files are exempt by default (`obsolete_names_exclude_patterns`).

**Governance Escalation:** Beyond 10 total Z6xx occurrences, an exponential multiplier applies: `deduction × 2^(excess / 5)`, capped at the 25-pt tier ceiling.

**Fix:**

1. Update the text to the active release name.
2. For intentional historical references in `.md`: append `<!-- zenzic:ignore: Z601 -->`.
3. For `.md` files: append `<!-- zenzic:ignore: Z601 -->`.
4. To exempt a file pattern entirely, add it to `obsolete_names_exclude_patterns` in `.zenzic.toml`.

---

### Z603: DEAD_SUPPRESSION {#z603}

**Severity:** `warning` · **Penalty:** −1.0 pt (Governance) · **Exit:** 1 · **Suppressible:** Yes · **Fixable:** Yes · [↗ Gallery](../tutorials/examples/z6xx-brand/z603-dead-suppression.md) · [↗ Rule Specification](../rules/Z603.md)

An inline suppression directive (`<!-- zenzic:ignore: Zxxx -->`) does not correspond to any active finding on that line. The directive silences nothing — it is **Phantom Debt** that consumes part of the 30-point governance budget without justification.

```text
docs/guide.md:12:  [Z603]  Inline suppression directive does not suppress
any active finding. Remove the dead comment.

    10  │  See [Installation](./install.md) for setup instructions.
    11  │
    12  ❱  ## Getting Started <!-- zenzic:ignore: Z101 - precaution -->
       │                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
    13  │
```

**Common causes:**

- A broken link was fixed but the `zenzic:ignore` comment was left behind.
- A suppression was added speculatively ("just in case") for a link that was never actually broken.
- A developer attempted to suppress a **security code** (Z201–Z205) — the Inviolability Law rejects these silently, making the directive permanently dead.
- A developer attempted to suppress a **topological code** (e.g. Z401, Z402, Z404, Z405, Z406, Z410–Z412, Z620) via an inline comment — these are governed only through `.zenzic.toml`'s `directory_policies`/`per_file_ignores` (ADR-093) and inline directives never consume them either.

**Fix:**

1. Remove the dead `<!-- zenzic:ignore: Zxxx -->` comment from the flagged line.
2. If the suppression was legitimate (the finding was recently fixed), cleaning the comment is the correct action — it eliminates Technical Debt.
3. If you suppressed Z201/Z202/Z203/Z204/Z205: those codes are **non-suppressible**. Remove the comment and address the underlying security finding.

!!! warning "Inviolability Law & Z603"
    Attempting `<!-- zenzic:ignore: Z201 -->` above a real credential **does not suppress Z201**. The credential scanner fires unconditionally. The suppression directive is therefore never consumed, and **Z603 fires on top of Z201** — two findings for one bad line.

---

### Z610: REQUIRED_FRONTMATTER_MISSING {#z610}

**Severity:** `warning` · **Penalty:** −3.0 pts (Governance) · **Exit:** 1 · **Suppressible:** Yes · **Opt-in:** Yes · [↗ Rule Specification](../rules/Z610.md)

A required YAML frontmatter key declared in `[policies].required_frontmatter_keys` is absent from this document. Z610 is opt-in and inactive by default — activate it by declaring `required_frontmatter_keys` in `.zenzic.toml`.

**Fix:** Add the missing key to the `---` frontmatter block at the top of the file.

```toml
[policies]
required_frontmatter_keys = ["title", "description", "author"]
```

---

### Z611: FORBIDDEN_DOMAIN_REFERENCE {#z611}

**Severity:** `warning` · **Penalty:** −3.0 pts (Governance) · **Exit:** 1 · **Suppressible:** Yes · **Opt-in:** Yes · [↗ Rule Specification](../rules/Z611.md)

A link (native Markdown or raw HTML `<a href>`) references an external domain listed in `[policies].forbidden_external_domains`. Domain matching is case-insensitive and covers exact matches and all subdomains. Z611 is opt-in and inactive by default.

**Fix:** Replace the link with an approved alternative, or remove it.

```toml
[policies]
forbidden_external_domains = ["legacy.corp", "competitor.example.com"]
```

---

### Z612: FORBIDDEN_FRONTMATTER_KEY {#z612}

**Severity:** `warning` · **Penalty:** −3.0 pts (Governance) · **Exit:** 1 · **Suppressible:** Yes · **Opt-in:** Yes · [↗ Rule Specification](../rules/Z612.md)

A YAML frontmatter key declared in `[policies].forbidden_frontmatter_keys` is present in this document.

**Fix:** Remove the forbidden key from the YAML frontmatter block.

```toml
[policies]
forbidden_frontmatter_keys = ["draft", "internal_notes"]
```

---

### Z613: FRONTMATTER_SCHEMA_MISMATCH {#z613}

**Severity:** `error` · **Penalty:** −5.0 pts (Governance) · **Exit:** 1 · **Suppressible:** Yes · **Opt-in:** Yes · [↗ Rule Specification](../rules/Z613.md)

A YAML frontmatter key value fails to match the required RE2 regular expression pattern declared in `[policies].frontmatter_schema_match`.

**Fix:** Update the frontmatter value to conform to the required pattern.

```toml
[policies.frontmatter_schema_match]
version = "^v\\d+\\.\\d+\\.\\d+$"
```

---

### Z614: UNAPPROVED_DOMAIN_REFERENCE {#z614}

**Severity:** `error` · **Penalty:** −5.0 pts (Governance) · **Exit:** 1 · **Suppressible:** Yes · **Opt-in:** Yes · [↗ Rule Specification](../rules/Z614.md)

An external link references a domain name that is not included in the Zero-Trust allowed external domains whitelist (`[policies].allowed_external_domains`).

**Fix:** Update the link to point to an approved domain, or add the domain to `allowed_external_domains` in `.zenzic.toml`.

```toml
[policies]
allowed_external_domains = ["zenzic.dev", "github.com"]
```

---

### Z615: FORBIDDEN_URL_SCHEME {#z615}

**Severity:** `warning` · **Penalty:** −3.0 pts (Governance) · **Exit:** 1 · **Suppressible:** Yes · **Opt-in:** Yes · [↗ Rule Specification](../rules/Z615.md)

A link uses a URL scheme protocol that is not permitted by the explicit whitelist declared in `[policies].required_url_schemes`.

**Fix:** Update the link scheme to an allowed protocol.

```toml
[policies]
required_url_schemes = ["https", "mailto"]
```

---

### Z616: CROSS_NAMESPACE_LINK_FORBIDDEN {#z616}

**Severity:** `error` · **Penalty:** −8.0 pts (Governance) · **Exit:** 1 · **Suppressible:** Yes · **Opt-in:** Yes · [↗ Rule Specification](../rules/Z616.md)

An internal link originates from a restricted source namespace and resolves to a forbidden target namespace in the Virtual Site Map (VSM).

**Fix:** Remove the link targeting the restricted namespace, or adjust directory boundaries in `[policies].cross_namespace_restrictions`.

```toml
[policies.cross_namespace_restrictions]
"docs/public" = ["docs/internal"]
```

---

### Z617: FORBIDDEN_CONTENT_PATTERN {#z617}

**Severity:** `warning` · **Penalty:** −2.0 pt (Governance) · **Exit:** 1 · **Suppressible:** Yes · **Opt-In** · [↗ Rule Specification](../rules/Z617.md)

This rule exists to detect prose content that matches any forbidden regular expression pattern declared in `[policies].forbidden_content_patterns`.

---

### Z618: REQUIRED_HEADING_PATTERN {#z618}

**Severity:** `warning` · **Penalty:** −3.0 pt (Governance) · **Exit:** 1 · **Suppressible:** Yes · **Opt-In** · [↗ Rule Specification](../rules/Z618.md)

This rule exists to enforce that documents include required section headings matching patterns declared in `[policies].required_heading_patterns`.

---

### Z619: MAX_DOCUMENT_COMPLEXITY {#z619}

**Severity:** `warning` · **Penalty:** −3.0 pts (Governance) · **Exit:** 1 · **Suppressible:** Yes · **Opt-In** · [↗ Rule Specification](../rules/Z619.md)

This rule exists to detect overly complex documents whose structural score exceeds the threshold set in `[policies].max_document_complexity`.

---

### Z620: STALE_GLOBAL_SUPPRESSION {#z620}

**Severity:** `warning` · **Penalty:** −1.0 pt (Governance) · **Exit:** 1 · **Suppressible:** Yes · **Opt-in:** No · [↗ Gallery](../tutorials/examples/z6xx-brand/z620-stale-global-suppression.md) · [↗ Rule Specification](../rules/Z620.md)

An entry in `directory_policies`, `excluded_file_patterns`, or `excluded_external_urls` inside `.zenzic.toml` was never utilised to suppress an active finding. This indicates configuration debt.

**Fix:** Remove the dead configuration line from `.zenzic.toml`.

---

## Z9xx — Engine & System

System-level diagnostic findings and worker watchdog execution alerts.

---

### Z901: RULE_ENGINE_ERROR {#z901}

**Severity:** `error` · **Penalty:** none (system-level) · **Exit:** 1 · **Suppressible:** Yes

An unhandled exception in a core rule or plugin. Zenzic's fail-visible principle converts silent crashes into explicit Z901 findings so the partial result is auditable.

**Fix:** Check the CLI output for a Python traceback. Report the issue at `https://github.com/PythonWoods/zenzic/issues`.

---

### Z902: RULE_TIMEOUT {#z902}

**Severity:** `warning` · **Penalty:** none (system-level) · **Exit:** 1 · **Suppressible:** Yes

A rule exceeded the execution time limit (default > 30s). Almost always caused by catastrophic backtracking in a custom regex — a ReDoS risk that can also silently disable a security gate.

**Fix:**

1. Review custom regex patterns in `.zenzic.toml`.
2. Simplify patterns: avoid nested quantifiers like `(a+)+`.
3. Use non-backtracking alternatives where possible.

---

### Z906: NO_FILES_FOUND {#z906}

**Severity:** `info` · **Penalty:** none · **Exit:** 0 · **Suppressible:** Yes (informational)

No `.md` / `.md` files found in the resolved `docs_root` after all exclusion layers. Suppressed in machine-output formats (`json`, `sarif`).

**Fix:**

1. Verify `docs_dir` in `.zenzic.toml` (or `--docs-dir`) points to the correct directory.
2. If the directory is intentionally empty, Z906 can be safely ignored — it exits 0.

---

## Reserved Codes (Inactive) {#reserved-codes}

!!! note "Runtime-inactive by contract"
    The codes in this section are defined in the Zenzic registry and reserved for engine implementations. They are **not emitted at runtime** and have **no impact on the Deterministic Quality Score**.

---

### Z504: QUALITY_REGRESSION {#z504}

**Severity:** `warning` *(reserved)* · [↗ Rule Specification](../rules/Z504.md)

Emitted by `zenzic diff` when the current DQS is lower than the saved baseline (`.zenzic-score.json`). Not itself weighted into the score (that would be circular); it identifies which commit introduced a regression.

**Fix:** Run `zenzic score` to see the breakdown by category, fix the underlying findings that caused the drop, then run `zenzic score --save` on `main` to update the baseline.

---

## Breaking Changes: Legacy Code Migration {#historical-code-remap}

> **\[FATAL\]** As of `v0.14.0`, automatic legacy code translation (`LEGACY_TO_CODE`) has been eradicated. Using the dead codes below in your `.zenzic.toml` will trigger a **FATAL Configuration Crash** (`Unknown Z-Code`). You must manually update your configuration to the active codes.

<!-- zenzic:migration-matrix:start -->
| Dead Code | Active Code | Status / Action Required |
|---|---|---|
| `Z903` | `Z405` | **DEAD.** Triggers FATAL crash. Manually replace with `Z405`. |
| `Z904` | `Z406` | **DEAD.** Triggers FATAL crash. Manually replace with `Z406`. |
| `Z905` | `Z601` | **DEAD.** Triggers FATAL crash. Manually replace with `Z601`. |
<!-- zenzic:migration-matrix:end -->

---

## Suppressing Diagnostics

> See [Suppression Policy](./suppression-policy.md) for inline suppression syntax (`zenzic:ignore`), the Suppression Debt model, and the `--audit` override.
