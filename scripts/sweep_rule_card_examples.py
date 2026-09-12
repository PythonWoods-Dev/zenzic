# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""Corpus-wide sweep: does every TOML config key or `zenzic` CLI command cited
in a docs/rules/*.md "How to Fix"/"Configuration" code fence correspond to a
real, current key/command?

Report-only (no writes) -- these defects need a human/semantic rewrite, not
a mechanical one, unlike the badge sweep. Two independent checks:

1. TOML fences: every `[section]` header must be a known valid section name
   (root config sections, or a Track-2 `tool.zenzic...` equivalent, or a
   nested `policies.<field>`/`governance.<field>` table); every top-level
   `key = value` assignment's key must be a real field on some config model
   (checked as a flat set across all models -- this will not catch a key
   used in the wrong section, only a key that does not exist anywhere).

2. Bash fences containing a `zenzic ...` invocation: the command/subcommand
   chain must exist in the real Typer command tree.

Run from the repo root::

    uv run python scripts/sweep_rule_card_examples.py
"""

from __future__ import annotations

from pathlib import Path

from zenzic.core import regex as re
from zenzic.models.config import (
    BuildContext,
    GovernanceConfig,
    NetworkConfig,
    PoliciesConfig,
    ProjectMetadata,
    ZenzicConfig,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
RULES_DIR = REPO_ROOT / "docs" / "rules"

_ALL_MODELS = (
    ZenzicConfig,
    PoliciesConfig,
    GovernanceConfig,
    BuildContext,
    NetworkConfig,
    ProjectMetadata,
)
VALID_KEYS: frozenset[str] = frozenset(key for model in _ALL_MODELS for key in model.model_fields)

VALID_SECTIONS: frozenset[str] = frozenset(
    {
        "policies",
        "governance",
        "build_context",
        "network",
        "custom_rules",
        "project_metadata",
        "secrets",
        "debug",
        "env",
        "core",
        "i18n",
        "tool.zenzic",
        "tool.zenzic.policies",
        "tool.zenzic.governance",
        "tool.zenzic.build_context",
        "tool.zenzic.network",
        "tool.zenzic.project_metadata",
    }
    | {f"policies.{k}" for k in PoliciesConfig.model_fields}
    | {f"governance.{k}" for k in GovernanceConfig.model_fields}
    | {f"tool.zenzic.policies.{k}" for k in PoliciesConfig.model_fields}
    | {f"tool.zenzic.governance.{k}" for k in GovernanceConfig.model_fields}
)

CODE_FENCE_RE = re.compile(r"```(?P<lang>[\w.\"= -]*)\n(?P<body>.*?)```", flags=re.DOTALL)
SECTION_RE = re.compile(r'^\[([\w."-]+)\]\s*$', flags=re.MULTILINE)
KEY_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)\s*=", flags=re.MULTILINE)

# The real Typer command tree (zenzic.main.app), enumerated manually since
# introspecting Click's Group objects generically is noisier than listing
# the known, stable top-level surface.
VALID_COMMANDS: frozenset[tuple[str, ...]] = frozenset(
    {
        ("lab",),
        ("lsp",),
        ("score",),
        ("audit",),
        ("fix",),
        ("diff",),
        ("explain",),
        ("init",),
        ("env",),
        ("clean",),
        ("clean", "assets"),
        ("guard",),
        ("guard", "scan"),
        ("guard", "init"),
        ("inspect",),
        ("inspect", "capabilities"),
        ("inspect", "codes"),
        ("inspect", "routes"),
        ("config",),
        ("config", "explain"),
        ("check",),
        ("check", "links"),
        ("check", "orphans"),
        ("check", "snippets"),
        ("check", "references"),
        ("check", "assets"),
        ("check", "placeholders"),
        ("check", "all"),
    }
)

ZENZIC_CMD_RE = re.compile(r"^\s*(?:uvx\s+)?zenzic\s+(?P<rest>.+)$", flags=re.MULTILINE)

# Group commands (Typer sub-apps with no_args_is_help=True) require a real
# subcommand as their second token -- a bare path/flag there is invalid.
# Non-group top-level commands accept positional arguments freely.
GROUP_COMMANDS: frozenset[str] = frozenset({"check", "guard", "inspect", "clean", "config"})


def _check_toml_fence(code: str, body: str) -> list[str]:
    problems: list[str] = []
    for section in SECTION_RE.findall(body):
        if section not in VALID_SECTIONS:
            problems.append(f"unknown section [{section}]")

    # Only check root-level keys (not indented under a [section]) against
    # the flat VALID_KEYS set -- section-scoped keys are checked structurally
    # above via VALID_SECTIONS's policies.<field>/governance.<field> members.
    in_section = False
    for line in body.splitlines():
        if SECTION_RE.match(line + "\n"):
            in_section = True
            continue
        if in_section:
            continue
        m = KEY_RE.match(line)
        if m and m.group(1) not in VALID_KEYS:
            problems.append(f"unknown root-level key '{m.group(1)}'")
    return problems


def _check_bash_fence(code: str, body: str) -> list[str]:
    problems: list[str] = []
    for m in ZENZIC_CMD_RE.finditer(body):
        rest = m.group("rest").strip()
        tokens = [t for t in rest.split() if not t.startswith("-")]
        if not tokens:
            continue

        top = tokens[0]
        if (top,) not in VALID_COMMANDS:
            problems.append(f"unknown command 'zenzic {rest}'")
            continue

        if top in GROUP_COMMANDS:
            if len(tokens) < 2 or (top, tokens[1]) not in VALID_COMMANDS:
                problems.append(
                    f"'zenzic {rest}': '{top}' requires a real subcommand, "
                    f"not a bare argument (Typer no_args_is_help=True group)"
                )
    return problems


def main() -> int:
    findings: dict[str, list[str]] = {}

    for path in sorted(RULES_DIR.glob("Z*.md")):
        if path.stem == "index":
            continue
        text = path.read_text(encoding="utf-8")
        page_problems: list[str] = []
        for m in CODE_FENCE_RE.finditer(text):
            lang, body = m.group("lang"), m.group("body")
            if "toml" in lang and "zensical.toml" not in lang:
                page_problems.extend(_check_toml_fence(lang, body))
            if "bash" in lang or "zenzic " in body:
                page_problems.extend(_check_bash_fence(lang, body))
        if page_problems:
            findings[path.stem] = page_problems

    print(f"Scanned {len(list(RULES_DIR.glob('Z*.md')))} rule cards.")
    print(f"Pages with a suspicious example: {len(findings)}")
    for code, problems in sorted(findings.items()):
        for p in problems:
            print(f"  {code}: {p}")

    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
