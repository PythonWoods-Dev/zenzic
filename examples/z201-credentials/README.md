<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Z201 CREDENTIAL_SECRET — Gallery Example

**Category:** Z2xx Security
**Expected exit:** 2 (SECURITY BREACH)

## What this demonstrates

`docs/setup.md` contains a fake AWS access key in a YAML code block.
Zenzic's credential scanner detects it using pattern matching and raises
a **security_breach** severity finding — collapsing the quality score to 0/100
regardless of all other checks.

## Run it

```bash
zenzic lab z201
# or directly:
zenzic check references
```bash

## Expected output

```bash
docs/setup.md  Z201  CREDENTIAL_SECRET  aws-access-key detected  [security_breach]
Exit 2 — SECURITY BREACH
```bash

## Real-world fix

Move credentials to environment variables:

```bash
export AWS_ACCESS_KEY_ID="your-real-key"
export AWS_SECRET_ACCESS_KEY="your-real-secret"
```bash
