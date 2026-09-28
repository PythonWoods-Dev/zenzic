# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""Single-file incremental parsing latency benchmark.

Proves that the Table AST parser and full Markdown tokenizer operate well
within the sub-50ms latency budget required for real-time Language Server
typing and diagnostics.
"""

from __future__ import annotations

import time

from zenzic.core.ast import TableNode
from zenzic.core.parser import parse, serialize


def test_incremental_table_parse_sub_50ms() -> None:
    """Benchmark parse() execution time on a realistic technical document with tables."""
    sample_doc = """# Specification & Architecture Document

This document contains structural specifications, data dictionaries, and architectural contracts.

## System Topology & Endpoints

| Endpoint Route | HTTP Method | Auth Scope | Rate Limit | Cache TTL | Data Classification |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `/api/v1/auth/login` | `POST` | `public` | `10 req/min` | `0s` | `CONFIDENTIAL` |
| `/api/v1/users/me` | `GET` | `user:read` | `100 req/min` | `30s` | `RESTRICTED` |
| `/api/v1/admin/audit` | `POST` | `admin:write`| `20 req/min` | `0s` | `CRITICAL` |
| `/api/v1/telemetry/push`| `PUT` | `service:mesh`| `1000 req/min`| `60s` | `INTERNAL` |
| `/api/v1/reports/dqs` | `GET` | `audit:read` | `60 req/min` | `300s`| `PUBLIC` |

## Security & Compliance Matrix

| Regulation Code | Control Objective | Verification Method | Enforcement Layer | Status |
| :--- | :--- | :--- | :--- | :--- |
| `SOC2-CC6.1` | Logical Access Controls | Automated CI Scanner | Gateway / WAF | `ENFORCED` |
| `ISO-27001-A.9` | User Access Management | RBAC Policy Evaluator| IAM Controller | `ENFORCED` |
| `HIPAA-164.312` | Cryptographic Safeguards | TLS 1.3 + AES-256 | Transport Core | `ACTIVE` |
| `GDPR-Art.32` | Data Protection by Design| AST Static Analyzer | Pre-Commit CI | `ENFORCED` |

```python
def authenticate(token: str) -> bool:
    return bool(token and token.startswith("Bearer "))
```

## Additional Notes

- All endpoints strictly enforce JSON payloads.
- Refer to [Security Policy](../security/overview.md) for remediation runbooks.
"""

    # Warmup pass
    ast = parse(sample_doc)
    assert any(isinstance(node, TableNode) for node in ast.children)

    # Measured benchmark iterations
    iterations = 100
    start = time.perf_counter()
    for _ in range(iterations):
        tree = parse(sample_doc)
        _ = serialize(tree)
    elapsed = time.perf_counter() - start

    avg_ms = (elapsed / iterations) * 1000.0
    print(
        f"\n[PERF EVIDENCE] Incremental single-file parse + serialize: {avg_ms:.3f} ms / file (Budget: 50.0 ms)"
    )

    # Assert sub-50ms latency (typically < 1.0ms in native Python RE2)
    assert avg_ms < 50.0, f"Incremental parse exceeded 50ms budget: {avg_ms:.2f}ms"
