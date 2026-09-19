---
description: "Canonical machine-readable JSON contract for check all, score, and suppression CAP fail-hard outputs."
---

<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# API JSON Contract

This page defines the stable JSON contract consumed by CI/CD tooling and downstream automations.

Covered outputs:

- `zenzic check all --format json`
- `zenzic score --format json`
- `zenzic check all --format json` when suppression CAP fail-hard triggers

The canonical schema is `zenzic-output.schema.json` in the root of the `zenzic` repository.

---

## Mandatory Suppression Fields

All contract outputs above include these fields, always:

| Field | Type | Meaning |
| :--- | :--- | :--- |
| `suppression_count` | integer | Suppressions in use (`inline + per-file + directory policy`) |
| `suppression_cap` | integer | Configured governance CAP |
| `suppression_debt_pts` | integer | Debt points — formula differs by shape (see below) |
| `debt_status` | enum | Governance debt posture |

`debt_status` values:

- `CLEAN`: `suppression_count == 0`
- `MANAGED`: `0 < suppression_count <= suppression_cap` and `suppression_cap <= 30`
- `EXTENDED`: `0 < suppression_count <= suppression_cap` and `suppression_cap > 30`
- `CRITICAL`: `suppression_count > suppression_cap`

---

## Shape: check all JSON

```json
{
  "findings": [
    {
      "rel_path": "docs/index.md",
      "line_no": 11,
      "code": "Z101",
      "severity": "error",
      "message": "'missing.md' resolves to '/missing/' which is not in the Virtual Site Map",
      "col_start": 0,
      "fixable": false
    }
  ],
  "security_breaches": 0,
  "security_incidents": 0,
  "suppression_count": 0,
  "suppression_cap": 30,
  "suppression_debt_pts": 0,
  "debt_status": "CLEAN"
}
```

### `engine` — which adapter actually produced these findings

*Added in v0.31.0. A new key; nothing was repurposed to make room for it.*

| Field | Type | Meaning |
| :--- | :--- | :--- |
| `declared` | string | The engine named in `.zenzic.toml`, or `auto` |
| `resolved` | string | The engine whose adapter produced the findings below |
| `substituted` | boolean | `true` when the two differ |
| `reason` | string | Present only when `substituted` is `true`: what was looked for and not found |

The two can differ, and that is why this field exists. **A declared engine that finds none
of its own configuration is replaced rather than defaulted**: the run continues with the
standalone adapter and reports what *that* adapter reports. On a site whose pages are
addressed by route rather than by file path, that is an order of magnitude more findings —
and until v0.31.0 the only signal was a notice on standard error, which no CI consumer
reads.

**Gate on `substituted`** if your pipeline depends on the engine it configured:

```bash
zenzic check all --format json | jq -e '.engine.substituted | not'
```

`substituted` is `false` on an ordinary run, including when `declared` is `auto` — auto
resolution is discovery, not substitution. A declared `prebuilt` with no route manifest
does not reach this field at all: since v0.31.0 that is a configuration error and the run
stops before reading a page.

The same object is carried by SARIF as a run-level property, described below.

**`findings[]` is the array to read**, and since v0.31.0 it is the only one. It carries every
finding the run produced, in one shape, with the code and the location as separate fields.

Six grouped arrays — `links[]`, `orphans[]`, `snippets[]`, `unused_assets[]`,
`references[]` and `nav_contract[]` — were **removed in v0.31.0**. They carried the same
findings a second time, in shapes a consumer could not use: `links[]` and `nav_contract[]`
held pre-formatted prose with no code in it at all, and `orphans[]` and `unused_assets[]`
held bare paths, so a finding could not be resolved to a file and a code from them.
Everything they carried is in `findings[]`, verified by execution per array across the whole
example gallery immediately before removal: **216 items, 216 covered, 0 missing**.

`col_start` is 0-based, and `0` means *no column was determined* rather than column zero.
SARIF's `startColumn` is this value plus one, since SARIF columns are 1-based.

`security_breaches` counts `Z201`/`Z204`/`Z205`-severity findings; `security_incidents` counts
`Z203`-severity findings. `Z202` (ordinary path traversal, plain Exit 1) is excluded from both.
These fields let a JSON consumer detect a security breach or fatal path-traversal incident
without parsing issue message text or relying solely on the process exit code.

In this shape, `suppression_debt_pts` is a **flat count** — every active suppression costs 1 point
regardless of `suppression_cap` (ADR-061: the cap is a hard-fail threshold, not a free allowance).
This differs from the CAP Fail-Hard shape below.

---

## Shape: check &lt;subcommand&gt; JSON

`zenzic check links`, `orphans`, `snippets`, `references`, `assets` and `placeholders` all
emit one shape with `--format json`, and it is not the `check all` shape above — it carries
no grouped arrays, because these commands were built after `findings[]` existed.

```json
{
  "findings": [
    {
      "rel_path": "docs/index.md",
      "line_no": 11,
      "code": "Z101",
      "severity": "error",
      "message": "'missing.md' resolves to '/missing/' which is not in the Virtual Site Map",
      "col_start": 0,
      "fixable": false
    }
  ],
  "summary": {
    "errors": 1,
    "warnings": 0,
    "info": 0,
    "security_incidents": 0,
    "security_breaches": 0,
    "elapsed_seconds": 0.026
  }
}
```

A finding here is byte-identical in shape to one in `check all`'s `findings[]` — both are
built by the same helper, so the two commands cannot disagree about the same finding.

`elapsed_seconds` is informational: it varies per run and per machine, so nothing should
gate on it.

Under Silent-on-Success a subcommand with nothing to report prints nothing at all, so a
consumer must treat empty output as "no findings" rather than as a parse failure.

---

## Shape: score JSON

```json
{
  "project": "zenzic",
  "score": 100,
  "threshold": 0,
  "status": "success",
  "timestamp": "2026-05-17T10:00:00+00:00",
  "categories": [
    {
      "name": "structural",
      "weight": 0.3,
      "issues": 0,
      "category_score": 1.0,
      "contribution": 0.3,
      "raw_penalty": 0.0,
      "is_capped": false
    }
  ],
  "suppression_count": 0,
  "suppression_cap": 30,
  "suppression_debt_pts": 0,
  "debt_status": "CLEAN"
}
```

Optional score fields (`security_override`, `security_findings`) appear when the Security Override fires.

Like the `check all` shape above, `suppression_debt_pts` here is a flat count of active suppressions, not
`suppression_count - suppression_cap`.

---

## Shape: CAP Fail-Hard JSON

```json
{
  "error": "SUPPRESSION_CAP_EXCEEDED",
  "severity": "error",
  "message": "Suppression cap exceeded: 31/30. Architectural debt limit reached.",
  "suppression_count": 31,
  "suppression_cap": 30,
  "suppression_debt_pts": 1,
  "debt_status": "CRITICAL",
  "statistics": {
    "active_suppressions": 31,
    "configured_global_cap": 30,
    "excess_debt": 1,
    "inline_ignores": 31,
    "per_file_ignores": 0
  },
  "hotspots": [
    {
      "path": "docs/index.md",
      "count": 31
    }
  ],
  "remediation": [
    "Review hotspots and remove suppressions where possible.",
    "If debt is intentional, update governance.suppression_cap in .zenzic.toml.",
    "Follow the playbook: https://zenzic.dev/developers/how-to/release-governance-protocol"
  ],
  "playbook": "https://zenzic.dev/developers/how-to/release-governance-protocol"
}
```

This is the one shape where `suppression_debt_pts` equals `max(0, suppression_count - suppression_cap)`
(the `excess_debt` statistic) — the flat-count formula used by the two shapes above does not apply here.

---

## Enterprise SARIF v2.1.0 Contract

`zenzic check all --format sarif` emits OASIS SARIF v2.1.0 compliant JSON designed for GitHub Code Scanning and enterprise security dashboards.

### Enriched `rules` Array

Each rule descriptor under `runs[0].tool.driver.rules` includes rich taxonomy and DQS penalty metadata:

```json
{
  "id": "Z101",
  "name": "LinkBroken",
  "shortDescription": {
    "text": "Link target not found in the Virtual Site Map"
  },
  "fullDescription": {
    "text": "Link target not found in the Virtual Site Map"
  },
  "defaultConfiguration": {
    "level": "error"
  },
  "helpUri": "https://zenzic.dev/reference/finding-codes/#z101",
  "properties": {
    "category": "structural",
    "penalty": 8.0
  }
}
```

- **`helpUri`**: Direct URL to Zenzic finding code documentation or Custom Rule SDK v3 `docs_url`.
- **`properties.category`**: DQS taxonomy category (`structural`, `navigation`, `content`, `brand`, `governance`, `custom`, or `uncategorized` — the fallback for any registered code with no explicit category assigned).
- **`properties.penalty`**: DQS penalty deduction cost per occurrence.
- **`defaultConfiguration.level`**: OASIS SARIF level (`error`, `warning`, `note`).

### Run-level properties

*Added in v0.31.0.* `runs[0].properties` carries facts about the run rather than about a
finding. GitHub ignores properties it does not recognise, so these cost a consumer nothing
and give one that reads them something the terminal could not deliver.

```json
{
  "engine": {
    "declared": "mkdocs",
    "resolved": "standalone",
    "substituted": true,
    "reason": "no mkdocs.yml (or mkdocs.yaml) found"
  },
  "githubTruncation": {
    "resultCount": 15254,
    "githubIncludedLimit": 5000,
    "githubRejectedAbove": 25000,
    "githubWillDiscard": 10254,
    "githubWillReject": false
  }
}
```

- **`engine`** is the same object the JSON payload carries, described above.
- **`githubTruncation`** is present **only when the file carries more results than GitHub
  Code Scanning will include**, and is absent otherwise.

#### What GitHub does with a large SARIF file

GitHub rejects an upload carrying more than **25,000** results, and of the results it
accepts it **includes only the first 5,000**, ordered by severity. The rest are discarded
with no message to the user — a clean tail and a truncated one look identical in the
interface.

Zenzic knows the count before it writes the file, so it says so: the property above, and a
notice on standard error.

```text
NOTICE: this SARIF carries 15,254 results. GitHub Code Scanning includes only
the first 5,000, so 10,254 would not appear there.
```

Standard error rather than standard output, because standard output is the SARIF.

**The file is not truncated.** Zenzic emits every result it found; what to do about the
limit is your decision, not the tool's. The usual answers are to narrow the scan with
`--only` or `[governance] directory_policies`, to fix the largest class first, or to
consume the file with something other than Code Scanning.

---

## GitLab Code Quality Contract

`zenzic check all --format gitlab-codequality` emits GitLab's Code Quality report schema — a
single JSON array whose objects carry `description`, `check_name`, `fingerprint`, `severity`
and `location.path` + `location.lines.begin`.

Unlike the JSON and SARIF contracts above, this one is **not ours to version**: the shape is
GitLab's, and Zenzic conforms to it. The severity mapping, fingerprint stability rules and
suppression-cap behaviour are specified in
[CLI Reference → GitLab Code Quality output](./cli.md#gitlab-codequality-output).

Available on `check all` only.

## Validation Guidance

For strict machine consumers, validate payloads against `zenzic-output.schema.json` for JSON output or `tests/fixtures/sarif-2.1.0-schema.json` for SARIF output during CI.
This prevents silent contract drift across minor releases.

---

## See Also

- [CLI Reference](./cli.md)
- [Finding Codes Index](./finding-codes.md)
