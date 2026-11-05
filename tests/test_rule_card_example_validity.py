# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""Regression guard for V031_FINAL_SEVERITY_SWEEP_AND_CONTENT_REMEDIATION's
corpus-wide "How to Fix" example-validity sweep (scripts/sweep_rule_card_examples.py).

Found and fixed 3 pages with a fabricated/invalid example: Z901.md
(non-existent [rules] TOML table), Z902.md (non-existent [plugins]
timeout_seconds key), Z906.md (invalid `zenzic check docs/` command,
missing its required subcommand). Runs the sweep script's own detection
logic as a subprocess-free import to keep this a fast, deterministic test.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SWEEP_SCRIPT = REPO_ROOT / "scripts" / "sweep_rule_card_examples.py"


def _load_sweep_module():
    spec = importlib.util.spec_from_file_location("sweep_rule_card_examples", SWEEP_SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_no_rule_card_has_a_fabricated_or_invalid_example() -> None:
    sweep = _load_sweep_module()
    findings: dict[str, list[str]] = {}

    for path in sorted(sweep.RULES_DIR.glob("Z*.md")):
        if path.stem == "index":
            continue
        text = path.read_text(encoding="utf-8")
        page_problems: list[str] = []
        for m in sweep.CODE_FENCE_RE.finditer(text):
            lang, body = m.group("lang"), m.group("body")
            if "toml" in lang and "zensical.toml" not in lang:
                page_problems.extend(sweep._check_toml_fence(lang, body))
            if "bash" in lang or "zenzic " in body:
                page_problems.extend(sweep._check_bash_fence(lang, body))
        if page_problems:
            findings[path.stem] = page_problems

    assert not findings, (
        "Rule card(s) with a fabricated/invalid config key or CLI command "
        "in a 'How to Fix' example -- verify against the real config schema "
        "(src/zenzic/models/config.py) or CLI command tree "
        "(src/zenzic/main.py):\n"
        + "\n".join(f"  {code}: {p}" for code, ps in sorted(findings.items()) for p in ps)
    )
