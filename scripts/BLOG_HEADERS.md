<!--
SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
SPDX-License-Identifier: Apache-2.0
-->

# Foundations Header Images — Capture Manifest

Lives beside the generator it documents (`scripts/generate_blog_headers.sh`) rather
than under `docs/`: an asset-folder Markdown file is never reachable from site
navigation, and hosting it there would mean declaring nav exemptions purely to
accommodate build tooling.

Every header listed here is a real `freeze` capture of real Zenzic output against
a real fixture — never a mock, never hand-edited (Rule 27). This manifest exists
so a regeneration never has to be reverse-engineered from a `.webp`.

> **Status: dormant.** The blog is currently text-only — no post embeds an image,
> and `docs/assets/images/` holds none. This generator and manifest are retained
> as working infrastructure for whichever visual approach comes next. Running the
> script writes six `.webp` files into `docs/assets/images/blog/`; until a post
> actually embeds one, `Z405` (`ASSET_UNUSED`) will correctly flag every file it
> produces. Regenerate when there is an article to put them in, not before.

**Regenerate all six:**

```bash
bash scripts/generate_blog_headers.sh
```

Verify the result with `file`, **not** `ffprobe` — see the warning below.

```bash
file docs/assets/images/blog/*_demo.webp   # must say "Web/P image"
```

The script builds each fixture from scratch in a temporary directory, captures,
and writes here. It is the single source of truth for these images; this file
documents what it does and why.

## Canonical capture recipe

```bash
freeze -x "<runner>" --output <name>.webp \
  --background "#18181a" --border.radius 8 --padding 20 --font.size 32
```

The recipe is **derived, not invented**. Each value was measured from the
terminal captures that were published under `docs/assets/images/terminal/`
before the blog moved to a text-only presentation. Those sample files are gone;
the measurements they yielded are recorded here so the house style can be
reproduced without them:

| Property | Value | How it was established |
| :--- | :--- | :--- |
| Background | `#18181a` | Centre-pixel sample of the measured captures — `RGB(24,24,26)`; the recipe reproduces it exactly |
| Corner | `--border.radius 8` | Corner pixel of the measured captures is `RGB(0,0,0)` (outside the rounded rect); reproduced exactly |
| Window chrome | none | No traffic-light controls present in the measured captures |
| Font size | `32` | The measured captures were 1400–2040px wide. `font.size` scales output linearly (14→715px, 22→1100px, 28→1390px, 32→~1582px), so 32 lands in that band |
| Padding | `20` | Matches the measured captures' margin |

**Why `font.size 32` matters.** An earlier set of headers rendered at ~715px
wide — roughly 2.2× less pixel density than the measured captures. That is what
made them look soft at blog display width. Resolution was the defect; the
captures themselves were always real.

## The webp trap — read before changing the output format

`freeze` v0.2.2 renders **SVG and PNG only**. Given a `.webp` output path it
writes an **SVG with a `.webp` extension** and exits 0 — no error, no warning —
even though `freeze --help` lists `.webp` as supported. Six headers shipped that
way and no browser would display any of them.

The generator therefore captures **PNG** and converts to real WebP with `ffmpeg`.
It also asserts the result with `file` and fails loudly if the bytes are not
`Web/P`.

**Verify with `file`, never `ffprobe`.** `ffprobe` parses an SVG's `width`/
`height` attributes and cheerfully reports plausible pixel dimensions for a file
nothing can render — which is exactly how the broken output passed review the
first time.

## Two constraints that will bite anyone editing the script

1. **Call `.venv/bin/zenzic` directly, never `uv run zenzic`.** Nesting `uv run`
   inside `freeze`'s pseudo-terminal hangs indefinitely — a first attempt ran
   past ten minutes and produced nothing, while the direct binary completes a
   scan in ~0.4s. Each capture also carries a hard 90s timeout.
2. **`freeze` refuses to write when the captured command exits non-zero**
   (`could not execute: exit status 1`). Every fixture below deliberately
   produces findings — exit 1, or exit 2 for the security-breach capture — so
   the command runs through a small runner script that always ends `0`. The
   rendered output is unchanged. A runner *file* is used rather than inline
   quoting, which silently mangles the command inside `-x`.

## The six images

| Image | Article | Command captured | What the fixture contains |
| :--- | :--- | :--- | :--- |
| `baseline_tracking_demo.webp` | Snapshot Your Debt | `check all` (after `--update-baseline`) | Two broken links, frozen into a baseline so the gate passes |
| `progressive_gates_demo.webp` | Enforce What Matters First | `check all --only Z101` | A broken link plus a short page; only `Z101` is enforced |
| `custom_rules_demo.webp` | Bring Your Own Rules | `check all` | A `ZZ-NOINTERNAL` custom rule (TOML DSL) catching an internal hostname |
| `quality_pyramid_demo.webp` | The Quality Pyramid | `score docs` | A planted `Z201` credential collapsing the score to 0 |
| `privacy_gate_demo.webp` | Zero Network, By Default | `check all` | A `forbidden_patterns` term triggering the `Z204` Privacy Gate |
| `governance_exemption_demo.webp` | Archived on Purpose | `check all` | `directory_policies` exempting `Z402` on `archive/**` while other checks still fire |

`quality_pyramid_demo` deliberately captures plain `score docs`, **not**
`score docs --breakdown`: the compact table plus the security override is the
article's actual subject, and `--breakdown`'s long detail sections produced a
2328px-tall portrait image, unusable as a header.
