<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Z611 FORBIDDEN_DOMAIN_REFERENCE — Gallery Example

**Category:** Z6xx Governance
**Expected exit:** 1 (errors)

## What this demonstrates

`.zenzic.toml` declares `[policies]` with `forbidden_external_domains = ["baddomain.com"]`.
`docs/index.md` contains a link to `https://baddomain.com/api`.
Zenzic flags the link as **Z611 FORBIDDEN_DOMAIN_REFERENCE**.

## Run it

```bash
zenzic lab z611
```

## Expected output

```text
docs/index.md:8  [Z611]  Link to 'https://baddomain.com/api' references forbidden domain 'baddomain.com'
```

## Real-world fix

Replace or remove the link to the forbidden domain:

```markdown
See the [Approved Documentation](https://approved.example.com/api).
```
