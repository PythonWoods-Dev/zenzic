<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Check Repository Health

`zenzic check` analyses the content of your documentation — links, anchors, credentials,
prose. `zenzic doctor` asks a different question: are the repository's own conventions
still intact?

Run it from the repository root:

```bash title="Terminal"
zenzic doctor
```

```text
✨ Repository conventions verified: no findings.
```

It exits `0` when every check passes and `1` when any reports a finding, so it drops into a
pipeline beside your other gates.

---

## What It Checks {#checks}

| Check | Question it answers |
| :--- | :--- |
| `config-schema` | Does `.zenzic.toml` actually load? Surfaces `Z110` syntax and `Z111` schema errors. |
| `adr-citations` | Does every architectural decision cited in code or prose have a record you can read? |
| `redirects` | Is the redirects file structurally valid, and has anything reshaped it unexpectedly? |

The ADR check is the one most projects notice first. A citation naming a decision record
that does not exist is the same class of defect as a broken link, one level up: prose or a
code comment claims a decision was recorded, and there is nothing there to read.

```text
src/app/parser.py: ADR-013 is cited but has no record in 'docs/decisions'.
```

---

## Point It at Your Own Layout {#configure}

The defaults describe Zenzic's own repository. Override them under `[doctor]` if yours
differs — see the [configuration reference](../reference/configuration-reference.md#doctor-settings)
for every setting.

```toml title=".zenzic.toml"
[doctor]
adr_vault_path = "architecture/decisions"
adr_citation_pattern = "RFC-\\d{4}"
```

That one pair of settings is usually the whole change: the same pattern identifies both a
citation in text and the record file that satisfies it.

If your project keeps no redirects file, nothing needs configuring — an absent file is not
a finding.

!!! info "Public repository content only"
    `doctor` reads the published tree, exactly like every other Zenzic check. Paths pointing
    into a gitignored directory are rejected when the config loads, so a check cannot be
    written that passes locally for one person and cannot run in CI at all.

---

## In CI {#ci}

```yaml title=".github/workflows/docs.yml"
- name: Repository health
  run: zenzic doctor --format json
```

`--format json` returns `healthy` plus every finding grouped by check, for a dashboard or a
pull-request comment.

---

## Related Documents

* [`zenzic doctor` CLI reference](../reference/cli.md) — All flags and checks.
* [`[doctor]` configuration](../reference/configuration-reference.md#doctor-settings) — Every setting and its default.
