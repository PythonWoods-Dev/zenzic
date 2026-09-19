<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Engine substitution

This project declares the MkDocs engine in its configuration and carries no
`mkdocs.yml` beside it. The run therefore uses the standalone adapter instead,
and says so in the `engine` object of the JSON payload rather than only on
standard error, where a continuous-integration consumer would never see it.

The page itself is ordinary and reports nothing; the fixture is about the
metadata a run carries, not about a finding.
