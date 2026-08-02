---
title: "Tutorial: Get Started with Zenzic"
date: 2026-04-29
authors:
  - pythonwoods
description: "Tutorial: Get Started with Zenzic"
---
<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

Your docs have broken links. You just haven't found them yet.

**Zenzic finds them before your readers do** — before you build, before you deploy,
before it's too late.

<!-- more -->

---

## Step 1 — Launch

No install. No virtual environment. One command:

```bash title="Terminal"
uvx zenzic check all ./docs
```

No browser, no build engine, no heavy framework — a single Python tool cached on
first run and ready in seconds from then on.

---

## Step 2 — Read the Report

You'll see one of two results:

**All clear:**

```text
✨ Sentinel Seal: All checks passed. Your documentation is clean.
```

**Issues found:**

<ZenzicTerminal title="zenzic check all">
<div className="flex gap-2 items-baseline mb-1"><span className="text-rose-500">✘</span><span className="bg-rose-500/10 text-rose-400 px-1 rounded-sm text-[11px]">[Z101]</span><span className="text-zinc-300">docs/guide.md:42 — Broken link → ./missing-page.md. </span></div>
<div className="flex gap-2 items-baseline mb-1"><span className="text-amber-500">⚠</span><span className="bg-amber-500/10 text-amber-400 px-1 rounded-sm text-[11px]">[Z402]</span><span className="text-zinc-300">docs/old-api.md — Orphan page, not in navigation. </span></div>
<div className="flex gap-2 items-baseline"><span className="text-rose-500">✘</span><span className="bg-rose-500/10 text-rose-400 px-1 rounded-sm text-[11px]">[Z201]</span><span className="text-zinc-300">docs/config.md:7 — Credential pattern detected. </span></div>
<div className="mt-2 text-rose-500 font-semibold text-[11px] tracking-wide">FAILED — exit 1</div>
</ZenzicTerminal>

Each finding carries a `Zxxx` code, a file path, a line number, and a clear description.
Fix what's flagged, re-run, and ship with confidence.

---

## Step 3 — Protect Your CI

One line in your GitHub Actions workflow:

```yaml title=".github/workflows/zenzic.yml"

- name: Audit documentation

  run: uvx zenzic check all ./docs
```

Every pull request is now guarded. Broken links, orphan pages, and leaked credentials
are caught before they reach `main`.

---

## Why Zenzic

- **Fast** — Zenzic is fast because it's lightweight. No build step, no Node.js,

  no browser launch. Analysis happens directly on your Markdown source files.

- **Safe** — Zenzic is secure because it doesn't touch your system files.

  Zenzic is read-only by default. Auto-fixing is an explicit, opt-in operation protected by atomic file writes.

- **Universal** — Works with MkDocs, Zensical, or any plain Markdown folder.

  Point it at your `docs/` directory and it figures out the rest.

---

## Go Further

| Command | What it does |
|---------|-------------|
| `uvx zenzic check all` | Full audit: links, orphans, credentials, snippets |
| `uvx zenzic check links` | Link integrity only |
| `uvx zenzic score` | Quality score with trend tracking |
| `uvx zenzic check all --format sarif` | SARIF output for GitHub Code Scanning |

Pin a specific version for reproducible CI:

```bash title="Terminal"
uvx "zenzic==0.7.0" check all ./docs
```
