---
description: "Add CI status and DQS Score badges to your README using Dual-Badge Telemetry."
---

<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Add Badges to Your README

Zenzic provides two orthogonal signals for your README: an **Audit Badge** (pass/fail governance) and a **DQS Score badge** (0–100 quality score). Both are written in-place by `zenzic score --stamp` without external dependencies.

---

## Badge 1 — Audit Status (`zenzic score --stamp`)

`zenzic score --stamp` also writes a deterministic governance badge (`passing` or `failing`).
The audit badge is based on the same score run and resolves pass/fail from policy conditions:

- no security override
- `score >= fail_under`
- `suppressions <= suppression_cap`

---

## Badge 2 — DQS Score (`zenzic score --stamp`)

`zenzic score --stamp` writes the current Documentation Quality Score directly into your README as a Shields.io badge — no Gist, no PAT tokens, no external dependencies.

### Setup

**Step 1.** Add both marker lines to your README. Each marker must be immediately followed by a Shields.io badge placeholder:

```markdown title="README.md"
<!-- zenzic:audit-badge -->
[![Zenzic Audit](https://img.shields.io/badge/%F0%9F%9B%A1%EF%B8%8F_zenzic--audit-passing-22c55e?style=flat-square)](../reference/scoring-algorithm.md)
<!-- zenzic:score-badge -->
[![Zenzic Score](https://img.shields.io/badge/%F0%9F%9B%A1%EF%B8%8F_zenzic--score-100_%2F_100-4f46e5?style=flat-square)](../reference/scoring-algorithm.md)
```

**Step 2.** Run `zenzic score --stamp`. Both badge URLs are replaced in place.

```bash
zenzic score --stamp
# Badge stamped → README.md
```

The `--stamp` option always updates badges **before** applying exit-code checks (fail_under, suppression_cap). This ensures telemetry reflects the actual run even when the build fails.

### Badge Colors

| Color | Hex | Condition |
|-------|-----|-----------|
| Indigo | `4f46e5` | Score = 100 |
| Amber | `f59e0b` | Score ≥ `fail_under` (passing) |
| Red | `ef4444` | Score < `fail_under` or security override |

### The Red Badge as a Local Signal

When `zenzic score --stamp` runs locally and the score is below `fail_under`, the badge in your README turns red. This gives immediate feedback before you push — the CI gate blocks Exit Code 1, so only indigo or amber badges reach main.

### Time-Traveling Badges

Because the URL is written inline into the commit, every historical commit shows the score computed at that point in time. This is the core advantage over Gist-based dynamic endpoints: no central state, no stale URLs.

### Multi-file stamping (`badge_stamp_files`)

By default, `--stamp` updates only `README.md`. To update additional files (e.g. `README.it.md` for multilingual projects), add `badge_stamp_files` to `[project_metadata]` in `.zenzic.toml`:

```toml title=".zenzic.toml"
[project_metadata]
badge_stamp_files = ["README.md", "README.it.md"]
```

Place both markers (`<!-- zenzic:audit-badge -->` and `<!-- zenzic:score-badge -->`) in each listed file.

---

## CI/CD Integration

Use `zenzic score --check-stamp` to **fail the pipeline** if the badge is stale — without git, without bash, without hardcoded file names.

```yaml title=".github/workflows/ci.yml"
- name: Verify badge freshness
  run: uvx zenzic score --check-stamp
```

`--check-stamp` reads `badge_stamp_files` from your `.zenzic.toml`, computes the expected Shields.io URLs for both badges, and exits 1 if any configured file contains stale telemetry. The error message names the stale file and badge type:

```text
[FAILED] Badge (score) in README.md is stale. Run 'zenzic score --stamp' locally and commit the result.
```

> **zenzic-action runs this automatically.** When you use `pythonwoods/zenzic-action`, the badge freshness check runs by default after `check all`. You can opt out with `check-stamp: 'false'`.

```yaml title=".github/workflows/zenzic.yml (opt-out example)"
- uses: pythonwoods/zenzic-action@v1
  with:
    check-stamp: 'false'
```

---

## Automating the Score Badge in CI/CD

Running `zenzic score --stamp` locally before every push works well for solo developers. Teams using GitHub Actions can automate it so the badge is always in sync — without relying on each contributor to remember the step.

### Why this requires `contents: write`

`--stamp` modifies a file on disk (`README.md`). To persist that change to the repository from a GitHub Actions runner, the workflow must commit and push the file back. This requires the `contents: write` permission.

### Full workflow snippet

The pattern below runs the Zenzic action first (the audit gate), then stamps the badge regardless of the audit result (`if: always()`), and commits only if the badge URL actually changed:

```yaml title=".github/workflows/zenzic.yml"
jobs:
  audit:
    runs-on: ubuntu-latest
    permissions:
      contents: write  # Required to commit the updated badge
    steps:
      - uses: actions/checkout@v4

      - name: Run Zenzic Action
        uses: pythonwoods/zenzic-action@v1

      - name: Update Score Badge
        if: always()  # Run even if the audit fails
        run: |
          uvx zenzic score --stamp

          # Commit only if the badge changed
          if [[ -n $(git status -s README.md) ]]; then
            git config --global user.name "github-actions[bot]"
            git config --global user.email "github-actions[bot]@users.noreply.github.com"
            git add README.md
            git commit -m "chore(docs): update Zenzic score badge"
            git push
          fi
```

### Workflow notes

- **`if: always()`** ensures the badge is stamped even when the audit fails — so contributors see the red badge on the PR branch immediately.
- **`git status -s README.md`** skips the commit when the score has not changed — avoids noisy "chore" commits on every push.
- **`contents: write` scoped to the job** limits blast radius: only this job can write to the repository.

### Multi-file stamping

If `badge_stamp_files` includes more than `README.md`, expand the `git add` and `git status` check accordingly:

```yaml
- name: Update Score Badge
  if: always()
  run: |
    uvx zenzic score --stamp
    if [[ -n $(git status -s README.md README.it.md) ]]; then
      git config --global user.name "github-actions[bot]"
      git config --global user.email "github-actions[bot]@users.noreply.github.com"
      git add README.md README.it.md
      git commit -m "chore(docs): update Zenzic score badge"
      git push
    fi
```

---

## See Also

- [CLI Reference](../reference/cli.md)
