---

description: "Implement BaseRule subclasses and register them as Zenzic plugin rules."
---

<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Writing Plugin Rules (API v1)

> **Looking for a simpler alternative?**
> If your rule is project-local and you don't need to distribute it as a Python package,
> use the [Custom AST Rules API v2](./write-ast-rule.md) — drop a `.py` file in
> `.zenzic/rules/` with zero configuration.

Zenzic supports external lint rules written in Python.  A plugin rule is a
subclass of `BaseRule` distributed as a normal Python package and discovered at
runtime via the `zenzic.rules` [entry-point group][ep].

---

## The Rule Contract

Every plugin rule must satisfy four non-negotiable requirements. The first
three are enforced at engine construction time — a rule that violates any of
them is rejected with a `PluginContractError` before the first file is
scanned. The fourth (code namespace) is a required rule with no mechanical
enforcement yet — see its own section below for what that means in practice.

### 1. Defined at module level

The class must be importable by name from a module.  Classes defined inside
functions or closures cannot be pickled and **will be rejected**.

```python
# ✓ correct — importable as my_rules.NoDraftRule
class NoDraftRule(BaseRule): ...


# ✗ wrong — not pickleable; will raise PluginContractError at load time
def make_rule():
    class NoDraftRule(BaseRule): ...

    return NoDraftRule()
```

### 2. Pickle-serialisable

The `AdaptiveRuleEngine` serialises rules via `pickle` before dispatching them
to worker processes.  Every attribute stored on `self` must be pickleable.

Safe attributes: strings, numbers, `re.compile()` patterns, frozen dataclasses,
`Path` objects, tuples of safe types.

Unsafe attributes: open file handles, database connections, lambda functions,
`threading.Lock`, generator objects, or any object that defines `__reduce__`
incorrectly.

```python
# ✓ compiled regex is pickleable
class NoDraftRule(BaseRule):
    _pattern = re.compile(r"(?i)\bDRAFT\b")  # class-level attribute


# ✓ also fine as an instance attribute set in __init__
class NoDraftRule(BaseRule):
    def __init__(self) -> None:
        self._pattern = re.compile(r"(?i)\bDRAFT\b")
```

### 3. Pure and deterministic

`check()` and `check_vsm()` must:

- **Never** open files, make network requests, or call subprocesses.
- **Always** return the same output for the same input — no randomness, no

  dependency on mutable global state.

- **Not** mutate their arguments (`file_path`, `text`, `vsm`, `anchors_cache`).

!!! warning "Avoid global mutable state"
    A rule that writes to a global counter will appear to work in sequential
    mode but will produce **non-deterministic, silently wrong** results in
    parallel mode.  Worker processes each receive an independent pickle copy
    of the engine — mutations are local to the worker and discarded on
    completion.  All state must be returned as `RuleFinding` objects.

### 4. Code namespace does not collide with a core Zenzic code

A plugin rule's `rule_id` must never equal a real Zenzic-owned finding code
(`Z101`, `Z201`, and so on — the full set is `codes.py`'s `CODE_DEFINITIONS`
registry). A collision is meaningless at best: two unrelated findings sharing
one code in every report, baseline, and suppression file. It is dangerous at
worst. Several internal code paths key exclusively on `rule_id` to decide
whether a finding belongs to Zenzic's own non-suppressible security tier. A
plugin claiming one of those codes can cause its own findings to be silently
discarded by logic that assumes only Zenzic's built-in scanners can produce
them.

!!! warning "This requirement is not yet mechanically enforced"
    Unlike the three requirements above, nothing currently rejects a plugin
    rule whose `rule_id` collides with a real Zenzic code — the intended
    check (`_validate_plugin_code` in `core/rules.py`) inspects an attribute
    named `code`, which `BaseRule` does not define; every plugin's `rule_id`
    is the attribute actually used downstream, and it is never validated.
    Confirmed live: a plugin declaring `rule_id = "Z201"` loads without error
    today. This is a known, tracked gap (`.claude/state/03-priority-table.md`,
    `V031_SECURITY_FIX_FULL_CLOSURE` Phase 5 finding), not yet fixed. Until it
    is, honor this requirement voluntarily — do not choose a `rule_id` that
    could plausibly become a real Zenzic code (a `<your-plugin-id>:` prefix,
    as used in the Plugin tier's documented format, is the safe choice).

---

## Minimal example

```python title="my_org_rules/rules.py"
# my_org_rules/rules.py
import re
from pathlib import Path
from zenzic.rules import BaseRule, RuleFinding


class NoInternalHostnameRule(BaseRule):
    """Flag occurrences of the internal hostname in public documentation."""

    _pattern = re.compile(r"internal\.corp\.example\.com", re.IGNORECASE)

    @property
    def rule_id(self) -> str:
        return "MYORG-001"

    def check(self, file_path: Path, text: str) -> list[RuleFinding]:
        findings = []
        for lineno, line in enumerate(text.splitlines(), start=1):
            if self._pattern.search(line):
                findings.append(
                    RuleFinding(
                        file_path=file_path,
                        line_no=lineno,
                        rule_id=self.rule_id,
                        message="Internal hostname must not appear in public docs.",
                        severity="error",
                        matched_line=line,
                    )
                )
        return findings
```

---

## Packaging and registration

Expose the rule through the `zenzic.rules` entry-point group in your package's
`pyproject.toml`:

```toml title="pyproject.toml"
[project.entry-points."zenzic.rules"]
no-internal-hostname = "my_org_rules.rules:NoInternalHostnameRule"
```

The entry-point name (`no-internal-hostname`) is the **plugin ID** that users
reference in `.zenzic.toml` (see [Enabling plugins](#config-enabling-plugins) below).

Install your package alongside Zenzic:

```bash
uv add my-org-rules            # or: pip install my-org-rules
```

After installing, run `zenzic inspect capabilities` to confirm the rule is discovered:

```bash
zenzic inspect capabilities
# Core Scanners  (built-in)
# …
# Extensible Rules  (plugin system)
#   broken-links          Z101       (core)          zenzic.core.rules.VSMBrokenLinkRule
#   no-internal-hostname  MYORG-001  (my-org-rules)  my_org_rules.rules.NoInternalHostnameRule
```

---

## Fast-Track: from zero to plugin in 30 seconds

Use the scaffold command to generate a ready-to-edit plugin package:

```bash
zenzic init --plugin plugin-scaffold-demo
```

Generated structure:

```text
plugin-scaffold-demo/
    pyproject.toml
    README.md
    .zenzic.toml
    docs/
        index.md
    src/
        plugin_scaffold_demo/
            __init__.py
            rules.py
```

The scaffold includes:

- a pre-configured `zenzic.rules` entry-point in `pyproject.toml`
- a module-level `BaseRule` class template in `rules.py`
- a minimal docs fixture so `zenzic check all` passes immediately

Quick verification:

```bash
cd plugin-scaffold-demo
uv pip install -e .
zenzic inspect capabilities
zenzic check all
```

---

## Enabling plugins {#config-enabling-plugins}

Core rules (registered under `zenzic.rules` by Zenzic itself) are always
active.  External plugin rules must be explicitly enabled in `.zenzic.toml`
under the `plugins` key:

```toml title=".zenzic.toml"
# .zenzic.toml
[build_context]
engine = "mkdocs"

plugins = ["no-internal-hostname"]
```

Only plugins listed here will be loaded.  Installing a package that registers
rules under `zenzic.rules` without listing it in `plugins` has no effect —
this is intentional **Privacy Gate** behaviour: you always know exactly which
rules are active in your project.

---

## VSM-aware rules

Rules that need to validate links against the routing table should override
`check_vsm` instead of (or in addition to) `check`.  The engine calls
`check_vsm` when a VSM and `anchors_cache` are available:

```python
from collections.abc import Mapping
from zenzic.core.rules import BaseRule, ResolutionContext, RuleFinding
from zenzic.models.vsm import Route


class NoOrphanLinkRule(BaseRule):
    @property
    def rule_id(self) -> str:
        return "MYORG-002"

    def check(self, file_path, text):
        return []  # no standalone check; requires VSM context

    def check_vsm(
        self,
        file_path,
        text,
        vsm: Mapping[str, Route],
        anchors_cache,
        context: ResolutionContext | None = None,
    ):
        # vsm maps canonical URL → Route; consult vsm[url].status
        ...
        return []  # return list[Violation]
```

See [`BaseRule`][api-baserule] in the API reference for the complete interface.

---

## Testing your rules

Use the `run_rule` test helper to validate a rule in a single call — no engine
setup required:

```python
from zenzic.rules import run_rule
from my_org_rules.rules import NoInternalHostnameRule


def test_internal_hostname_detected():
    findings = run_rule(
        NoInternalHostnameRule(),
        "Visit internal.corp.example.com for details.",
    )
    assert len(findings) == 1
    assert findings[0].rule_id == "MYORG-001"
    assert findings[0].severity == "error"


def test_clean_content_passes():
    findings = run_rule(NoInternalHostnameRule(), "All public content here.")
    assert findings == []
```

`run_rule` creates an `AdaptiveRuleEngine` internally, runs the rule, and
returns the findings list.  It accepts an optional `file_path` keyword argument
for labelling (defaults to `test.md`).

---

## Error isolation

If a plugin rule raises an unexpected exception inside `check()` or
`check_vsm()`, the engine catches it, emits a single `"error"` finding with
`rule_id="RULE-ENGINE-ERROR"`, and continues scanning.  One faulty plugin
cannot abort the scan of the entire docs tree.

If a plugin rule fails the **eager pickle validation** at load time (i.e. it
is not serialisable), Zenzic raises `PluginContractError` immediately and
refuses to start.  Fix the rule before running Zenzic.

---

## Checklist before publishing

- [ ] Class defined at module level (not inside a function or lambda).
- [ ] All `self.*` attributes are pickleable.
- [ ] `check()` is pure: no I/O, no side effects, same output for same input.
- [ ] `rule_id` is a stable, unique string (include an org prefix, e.g. `"MYORG-001"`).
- [ ] Entry-point registered under `zenzic.rules` in `pyproject.toml`.
- [ ] Plugin ID listed in the project's `.zenzic.toml` under `plugins`.

!!! info "Next Steps"
     Bridge your rule from implementation to production Zenzic flow:

     1. Register and enable the plugin ID in `.zenzic.toml` under `plugins`

         (see [Enabling plugins](#config-enabling-plugins)).

     2. Validate the rule under strict pipeline semantics:

         `zenzic check all --strict`.
         For run-time policy controls, see
         [CLI Commands: Global flags](../../reference/cli.md#global-flags).

     3. If your rule is nav-aware, map expected Ghost Route behavior against the VSM model:

         [Core Mechanics — VSM](../../explanation/core-mechanics.md#vsm).

[ep]: https://packaging.python.org/en/latest/guides/creating-and-discovering-plugins/#using-package-metadata
[api-baserule]: ../reference/adapter-api.md
