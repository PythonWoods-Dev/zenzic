---
description: "Walk through the z614-unapproved-domain fixture: a link to an external domain absent from the [policies].allowed_external_domains whitelist, triggering Z614 UNAPPROVED_DOMAIN_REFERENCE."
---
<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Z614 — Unapproved Domain Reference

**Z-Code:** `Z614 UNAPPROVED_DOMAIN_REFERENCE` · **Engine:** `standalone` · **Exit:** `1`

---

## The Fixture

One page, one external link, and a whitelist that does not contain its domain.

| File | Role |
| :--- | :--- |
| `.zenzic.toml` | Declares `allowed_external_domains` |
| `docs/index.md` | Links to a domain outside the whitelist |

The policy names every domain the documentation is permitted to link to:

```toml
[policies]
allowed_external_domains = ["pythonwoods.dev"]
```

This is a default-deny list, not a blocklist. Any domain not named is refused,
which is what makes it a Zero-Trust control: adding a link to a new third-party
site is a decision someone has to make explicitly, rather than something that
happens quietly in a pull request.

`docs/index.md` links somewhere else on line 3:

```markdown
Check out [unvetted domain](https://unapproved.example.org/spec).
```

The link is well-formed and the syntax is valid. Zenzic does not fetch it — the
finding is about policy, not reachability.

---

## Running the Example

```bash
# Clone the Zenzic repository — no install required
cd examples/z614-unapproved-domain
uvx zenzic check all
```

Expected output:

```text
standalone • 1 file (1 pages, 0 assets) • 0.0s • 20 files/s

docs/index.md:1  ⚠  [Z411]  Document has no outgoing links and forms a
structural dead end: '/'
docs/index.md:3  ✘  [Z614]  Link to 'https://unapproved.example.org/spec'
references external domain 'unapproved.example.org' which is not in
[policies].allowed_external_domains whitelist. Replace or add to whitelist.
    1  │  # Welcome
    2  │
    3  ❱  Check out [unvetted domain](https://unapproved.example.org/spec).

Summary:  ✘ 1 error  ⚠ 1 warning  💡 0 info  • 1 file with findings
FAILED: Hard errors detected. Exit code 1 is mandatory.
DQS Final Score: 90/100 (Gate Failed)
```

The `Z411` warning above the `Z614` error is incidental: this one-page fixture
has no outgoing internal links, so it is also a structural dead end. It is not
part of what `Z614` demonstrates.

---

## Interpreting the Output

- **Severity:** `Error`
- **Impact:** Deducts **5.0 DQS points** (brand category).
- **Auto-Fixable:** No. Whether the correct action is removing the link or
  approving the domain is a judgement Zenzic cannot make.

The message states the offending URL, the extracted domain, and the policy key
that rejected it — enough to act on without opening the config.

---

## Resolve the Issue

Either remove the link, or approve the domain deliberately:

```toml
[policies]
allowed_external_domains = ["pythonwoods.dev", "unapproved.example.org"]
```

Approving is the right call when the domain is genuinely trusted. The point of
the check is not to forbid external links — it is to make each new external
dependency a visible, reviewable line in a config file rather than an
unremarkable link in a paragraph.

Re-run `zenzic check all`; the finding clears.

---

## See Also

- [Z616 — Cross-Namespace Link Forbidden](z616-cross-namespace-link) — the same
  Zero-Trust posture applied to internal namespace boundaries.
- [Checks Reference](../../../reference/checks) — full rule specification.
