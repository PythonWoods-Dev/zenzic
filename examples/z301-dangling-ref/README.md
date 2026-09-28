<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Z301 DANGLING_REF — Gallery Example

**Category:** Z3xx Reference Integrity
**Expected exit:** 0 (warnings only; 1 under `--strict`)

## What this demonstrates

`docs/index.md` uses the reference-style link `[Click here][missing-ref]`.
The identifier `missing-ref` is never defined anywhere in the file
(there is no `[missing-ref]: https://...` definition).

Zenzic's reference scanner detects the undefined ID in Pass 1 (Harvest) and
reports it as Z301 DANGLING_REF in the Integrity Report.

## Run it

```bash
zenzic lab z301
# or directly:
zenzic check references
```

## Expected output

```text
docs/index.md:9:  Z301  DANGLING_REF  reference ID 'missing-ref' is used but never defined
```

Exit code **0** (warning-level finding, non-blocking by default); **1** under `--strict`.

## Fix

Add the missing definition: `[missing-ref]: https://example.com/docs`
Or convert to an inline link: `[Click here](https://example.com/docs)`.
