---
description: "Walk through the z615-forbidden-url-scheme fixture: an http:// link where [policies].required_url_schemes permits only https and mailto, triggering Z615 FORBIDDEN_URL_SCHEME."
---
<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Z615 — Forbidden URL Scheme

**Z-Code:** `Z615 FORBIDDEN_URL_SCHEME` · **Engine:** `standalone` · **Exit:** `1` (under strict mode) / `0` (warnings only)

---

## The Fixture

A link whose destination is fine and whose protocol is not.

| File | Role |
| :--- | :--- |
| `.zenzic.toml` | Names the permitted schemes |
| `docs/index.md` | Links over plain `http` |

The policy is an allowlist of protocols:

```toml
[policies]
required_url_schemes = ["https", "mailto"]
```

The page uses one that is not on it:

```markdown
Check out [insecure site](http://example.com/docs).
```

`example.com` is not the problem — the same host over `https` would pass. The
finding is about the scheme alone.

This catches a specific kind of rot. Links written years ago, before a site
offered TLS, keep working via redirect and quietly teach readers that plain
`http` is acceptable. Pinning the permitted schemes makes the exceptions
visible instead of letting them accumulate.

---

## Running the Example

```bash
# Clone the Zenzic repository — no install required
cd examples/z615-forbidden-url-scheme
uvx zenzic check all
```

Expected output:

```text
standalone • 1 file (1 pages, 0 assets) • 0.0s • 22 files/s

docs/index.md:1  ⚠  [Z411]  Document has no outgoing links and forms a
structural dead end: '/'
docs/index.md:3  ⚠  [Z615]  Link to 'http://example.com/docs' uses scheme 'http'
which is not permitted by [policies].required_url_schemes (['https', 'mailto']).
Change scheme to an allowed protocol.
    1  │  # Welcome
    2  │
    3  ❱  Check out [insecure site](http://example.com/docs).
```

The message lists the permitted set inline, so the fix does not require opening
the config.

---

## Interpreting the Output

- **Severity:** `Warning`
- **Impact:** Deducts **3.0 DQS points** (brand category).
- **Auto-Fixable:** No. Rewriting `http` to `https` looks mechanical, but Zenzic
  performs no network access and cannot confirm the target serves TLS — a
  rewrite could turn a working link into a broken one.
- **Opt-In:** Yes — silent until `required_url_schemes` is declared.

Include every scheme the documentation legitimately uses. Omitting `mailto`
turns every contact address into a finding.

---

## Resolve the Issue

Change the scheme, having confirmed the target supports it:

```markdown
Check out [secure site](https://example.com/docs).
```

Re-run `zenzic check all`; the finding clears.

---

## See Also

- [Z611 — Forbidden Domain Reference](z611-forbidden-domain) — the same posture
  applied to the host rather than the protocol.
- [Z123 — Non-HTTP Scheme](../z1xx-links/z123-non-http-scheme) — schemes outside
  the web entirely.
- [Checks Reference](../../../reference/checks) — full rule specification.
