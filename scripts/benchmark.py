#!/usr/bin/env python
# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""Zenzic Performance Benchmark — Single-thread vs Multi-process.

Generates a synthetic docs tree of N Markdown files with reference links,
then measures the wall-clock time for sequential and parallel scans.

Usage::

    python scripts/benchmark.py                  # default: 200 files, 4 workers
    python scripts/benchmark.py --files 1000 --workers 8
    python scripts/benchmark.py --files 5000 --no-parallel
    python scripts/benchmark.py --repo .          # real adapter test (this repo)

Output is a Rich-formatted table with ms/file figures for each strategy.
"""

from __future__ import annotations

import argparse
import statistics
import tempfile
import time
from pathlib import Path

from rich.console import Console
from rich.table import Table

from zenzic.core.exclusion import LayeredExclusionManager
from zenzic.core.scanner import scan_docs_references
from zenzic.models.config import ZenzicConfig


console = Console()

_MD_TEMPLATE = """\
# Page {i}

This is the content of page {i}.  It contains [a reference link][ref-{i}] and
some prose text to ensure the parser has real work to do.

## Section A

More content for page {i}.  Lorem ipsum dolor sit amet, consectetur
adipiscing elit.  Sed do eiusmod tempor incididunt ut labore.

[ref-{i}]: https://example.com/page-{i}
[ref-shared]: https://docs.example.com/api
"""


def _create_synthetic_repo(n_files: int) -> Path:
    """Create a temporary repo with *n_files* Markdown files and return its path."""
    base = Path(tempfile.mkdtemp(prefix="zenzic-bench-"))
    docs = base / "docs"
    docs.mkdir()
    for i in range(n_files):
        (docs / f"page_{i:05d}.md").write_text(_MD_TEMPLATE.format(i=i))
    return base


def _make_exclusion_manager(config: ZenzicConfig, repo: Path) -> LayeredExclusionManager:
    """Build a LayeredExclusionManager for *repo* using *config*."""
    docs_root = (repo / config.docs_dir).resolve()
    return LayeredExclusionManager(config, repo_root=repo, docs_root=docs_root)


def _bench(
    label: str,
    docs_root: Path,
    exclusion_mgr: LayeredExclusionManager,
    config: ZenzicConfig,
    workers: int = 1,
    runs: int = 3,
) -> dict:
    """Run scan_docs_references *runs* times and return timing statistics."""
    times: list[float] = []
    n_reports = 0
    for _ in range(runs):
        t0 = time.perf_counter()
        reports, _ = scan_docs_references(docs_root, exclusion_mgr, config=config, workers=workers)
        elapsed = time.perf_counter() - t0
        times.append(elapsed)
        n_reports = len(reports)
    return {
        "label": label,
        "n_files": n_reports,
        "runs": runs,
        "min_s": min(times),
        "mean_s": statistics.mean(times),
        "median_s": statistics.median(times),
        "ms_per_file": statistics.median(times) / n_reports * 1000 if n_reports else 0,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Zenzic performance benchmark")
    parser.add_argument("--files", type=int, default=200, help="Number of synthetic .md files")
    parser.add_argument("--workers", type=int, default=4, help="Worker processes for parallel scan")
    parser.add_argument("--runs", type=int, default=3, help="Benchmark repetitions (best of N)")
    parser.add_argument("--no-parallel", action="store_true", help="Skip parallel benchmark")
    parser.add_argument(
        "--repo",
        type=str,
        default=None,
        help="Path to a real project to benchmark (e.g. . for this repo itself)",
    )
    args = parser.parse_args()

    use_real_repo = args.repo is not None

    if use_real_repo:
        repo = Path(args.repo).resolve()
        if not repo.exists():
            console.print(f"[red]Error:[/] repo path does not exist: {repo}")
            raise SystemExit(1)
        console.print(
            f"\n[bold cyan]Zenzic Benchmark[/] — real project [bold]{repo.name}[/], "
            f"{args.runs} run(s) each\n"
        )
    else:
        console.print(
            f"\n[bold cyan]Zenzic Benchmark[/] — {args.files} synthetic files, "
            f"{args.runs} run(s) each\n"
        )
        console.print("[dim]Generating synthetic repo…[/]")
        repo = _create_synthetic_repo(args.files)
    config = ZenzicConfig()
    docs_root = (repo / config.docs_dir).resolve()
    exclusion_mgr = _make_exclusion_manager(config, repo)

    results: list[dict] = []

    console.print("[dim]Running sequential scan (workers=1)…[/]")
    results.append(
        _bench(
            "Sequential (single-thread)",
            docs_root,
            exclusion_mgr,
            config,
            workers=1,
            runs=args.runs,
        )
    )

    if not args.no_parallel:
        console.print(f"[dim]Running parallel scan ({args.workers} workers)…[/]")
        results.append(
            _bench(
                f"Parallel ({args.workers} workers)",
                docs_root,
                exclusion_mgr,
                config,
                workers=args.workers,
                runs=args.runs,
            )
        )

    # ── Output table ───────────────────────────────────────────────────────────
    n_label = repo.name if use_real_repo else f"{args.files} synthetic files"
    table = Table(title=f"Results — {n_label}, {args.runs} run(s)")
    table.add_column("Strategy", style="bold")
    table.add_column("Files", justify="right")
    table.add_column("Median (s)", justify="right")
    table.add_column("Min (s)", justify="right")
    table.add_column("ms / file", justify="right", style="cyan")

    for r in results:
        speedup = ""
        if len(results) > 1 and r is not results[0]:
            factor = results[0]["median_s"] / r["median_s"] if r["median_s"] > 0 else 0
            speedup = f" [green]({factor:.1f}×)[/]"
        table.add_row(
            r["label"],
            str(r["n_files"]),
            f"{r['median_s']:.3f}",
            f"{r['min_s']:.3f}",
            f"{r['ms_per_file']:.2f}{speedup}",
        )

    console.print(table)

    # ── Speedup summary ────────────────────────────────────────────────────────
    if len(results) == 2:
        speedup = (
            results[0]["median_s"] / results[1]["median_s"] if results[1]["median_s"] > 0 else 0
        )
        console.print(
            f"\n[bold]Speedup:[/] parallel is [cyan]{speedup:.2f}×[/] faster than sequential "
            f"({args.workers} workers, {n_label})\n"
        )

    # Cleanup (only remove synthetic repos, never real ones)
    import shutil

    if not use_real_repo:
        shutil.rmtree(repo, ignore_errors=True)


if __name__ == "__main__":
    main()
