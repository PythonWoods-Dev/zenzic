<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Z115 STALE_ROUTE_MANIFEST — Gallery Example

**Category:** Z1xx Link Integrity
**Expected exit:** 1 (the stale manifest also produces a Z101 on a correct link)

## What this demonstrates

The `prebuilt` engine does not compute URLs — it reads them from
`.zenzic-vsm.json`, a routing table written by your site generator. That file
is a second copy of a fact, and it goes stale the moment a page is added
without re-running the generator.

Here `docs/guide.md` exists and the manifest does not list it. A source the
manifest does not declare routes as `IGNORED`, so the correct link
`[guide](guide.md)` in `docs/index.md` is reported **Z101** as unreachable.

**Z115 is the finding that names the cause.** Without it the run points at the
link, and the fix it implies — edit the link — is the wrong one.

## Run it

```bash
zenzic check all
```

## Expected output

```text
docs/index.md:10  ✘  [Z101]  'guide.md' resolves to '/guide/' which has VSM status 'IGNORED' …
docs/guide.md:1   ⚠  [Z115]  'guide.md' is not declared in the route manifest (.zenzic-vsm.json), …
```

## Real-world fix

Re-run the generator that writes `.zenzic-vsm.json`, then commit the updated
manifest. If the manifest is generated in CI rather than committed, generate it
before `zenzic check` runs — a manifest built after the check has no effect on
it.

If you are not using a generator that writes one, `prebuilt` is the wrong
engine: `standalone` derives every URL from the path it reads and cannot go
stale.
