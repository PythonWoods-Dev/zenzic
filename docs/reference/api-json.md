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
| `suppression_count` | integer | Active suppressions (`inline + per-file`) |
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
  "links": [],
  "orphans": [],
  "snippets": [],
  "unused_assets": [],
  "references": [],
  "nav_contract": [],
  "security_breaches": 0,
  "security_incidents": 0,
  "suppression_count": 0,
  "suppression_cap": 30,
  "suppression_debt_pts": 0,
  "debt_status": "CLEAN"
}
```

`security_breaches` counts `Z201`/`Z204`/`Z205`-severity findings; `security_incidents` counts
`Z203`-severity findings. `Z202` (ordinary path traversal, plain Exit 1) is excluded from both.
These fields let a JSON consumer detect a security breach or fatal path-traversal incident
without parsing issue message text or relying solely on the process exit code.

In this shape, `suppression_debt_pts` is a **flat count** — every active suppression costs 1 point
regardless of `suppression_cap` (ADR-061: the cap is a hard-fail threshold, not a free allowance).
This differs from the CAP Fail-Hard shape below.

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

---

## Validation Guidance

For strict machine consumers, validate payloads against `zenzic-output.schema.json` for JSON output or `tests/fixtures/sarif-2.1.0-schema.json` for SARIF output during CI.
This prevents silent contract drift across minor releases.

---

## See Also

- [CLI Reference](./cli.md)
- [Finding Codes Index](./finding-codes.md)
