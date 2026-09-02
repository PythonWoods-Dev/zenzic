---
description: "Walk through the z611-forbidden-domain fixture: a link to a domain named in [policies].forbidden_external_domains, triggering Z611 FORBIDDEN_DOMAIN_REFERENCE."
---
<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Z611 — Forbidden Domain Reference

**Z-Code:** `Z611 FORBIDDEN_DOMAIN_REFERENCE` · **Engine:** `standalone` · **Exit:** `1` (under strict mode) / `0` (warnings only)

---

## The Fixture

A link to a domain the project has explicitly ruled out.

| File | Role |
| :--- | :--- |
| `.zenzic.toml` | Names the forbidden domains |
| `docs/index.md` | Links to one of them |

The policy is a denylist:

```toml
[policies]
forbidden_external_domains = ["baddomain.com"]
```

`Z611` and `Z614` are the two halves of external-domain governance, and they are
not interchangeable:

| | Policy | Posture |
| :--- | :--- | :--- |
| `Z614` | `allowed_external_domains` | Default-deny — anything unlisted is refused |
| `Z611` | `forbidden_external_domains` | Default-allow — only named domains are refused |

Use the allowlist when the set of acceptable destinations is known and small.
Use the denylist when it is not, but specific domains must be kept out — a
deprecated documentation host, a competitor, a site that was compromised.
Declaring both is legitimate; the denylist then acts as an override.

---

## Running the Example

```bash
# Clone the Zenzic repository — no install required
cd examples/z611-forbidden-domain
uvx zenzic check all
```

Expected output:

```text
standalone • 1 file (1 pages, 0 assets) • 0.1s • 20 files/s

docs/index.md:1  ⚠  [Z411]  Document has no outgoing links and forms a
structural dead end: '/'
docs/index.md:8  ⚠  [Z611]  Link to 'https://baddomain.com/api' references
forbidden domain 'baddomain.com'. Remove or replace the link. Declared in
[policies].forbidden_external_domains.
     6  │  This document contains a link to a forbidden external domain.
     7  │
     8  ❱  See the [Bad API](https://baddomain.com/api) for details.
```

Zenzic never requests the URL. The finding comes from parsing the link, so it
works offline and cannot be affected by whether the site is reachable.

---

## Interpreting the Output

- **Severity:** `Warning`
- **Impact:** Deducts **3.0 DQS points** (brand category).
- **Auto-Fixable:** No. A replacement destination is an editorial choice.
- **Opt-In:** Yes — silent until `forbidden_external_domains` is declared.

Note the asymmetry with `Z614`, which is an **error** worth 5.0 points. Linking
to something unvetted is treated more severely than linking to something
specifically named, because the allowlist posture is the stronger control.

---

## Resolve the Issue

Replace the link with an approved destination, or remove it. If the domain
should no longer be forbidden, amend the policy — as a reviewed decision, not to
clear one finding.

Re-run `zenzic check all`; the finding clears.

---

## See Also

- [Z614 — Unapproved Domain](z614-unapproved-domain) — the allowlist half of
  external-domain governance.
- [Z615 — Forbidden URL Scheme](z615-forbidden-url-scheme) — the same idea
  applied to the protocol rather than the host.
- [Checks Reference](../../../reference/checks) — full rule specification.
