---
title: Security & Gatekeeper Scenarios (Z2xx)
---

<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Security & Gatekeeper Scenarios (Z2xx)

Interactive lab scenarios and test fixtures for security gatekeeper rules (`Z2xx`). These fixtures demonstrate hardcoded credential detection (`Z201`), path traversal guards (`Z202`/`Z203`), privacy gate forbidden terms (`Z204`), and forbidden URL schemes (`Z205`).

Run `zenzic lab z201` to test these scenarios interactively, or return to the [Lab Gallery Overview](../index.md).

The scenario carries its own fixture, so nothing has to be set up first:

![Terminal session. zenzic lab z201 runs the credential scenario. The report reads SECURITY BREACH DETECTED, names the finding as an aws-access-key secret at docs/setup.md line 15, and shows the credential masked to AKIA followed by asterisks and MPLE. It advises rotating the key. The LAB RESULT line reports the expectation met.](../../../assets/demo/lab-z201-detection.gif)

The scenario is designed to fail: the breach block is the expected `Z201`
detection, not a problem with the install. `zenzic lab` itself exits `0` when a
scenario meets its expectation — the `Exit code 2 is mandatory` line inside the
report is the contract the *scenario* demonstrates, not the exit code of `lab`.
The key is masked in the report because that output lands in CI logs.
