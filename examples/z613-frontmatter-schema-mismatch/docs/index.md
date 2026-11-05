---
title: "Schema Mismatch Demonstration"
version: 1.0
---

# Schema Mismatch Demonstration

This page contains a version string `1.0` that does not match `^v\d+\.\d+\.\d+$`. Validating frontmatter values against a strict RE2 pattern catches typos and format drift before a build pipeline propagates the bad metadata into a generated site or a downstream search index used by readers every day.
