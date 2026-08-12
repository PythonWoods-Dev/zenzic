#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0

"""Fetch Zenzic download statistics from PyPI Stats API with strict netiquette.

Maintains a compact historical dataset in `docs/assets/data/pypi-stats.json`.
Uses a single API call (`overall?mirrors=false`) to minimize network overhead
and avoid rate limits.
"""

from __future__ import annotations

import json
import pathlib
import sys
import time
import urllib.request
from datetime import datetime, timezone

PACKAGE_NAME = "zenzic"
USER_AGENT = "zenzic-stats-bot/1.0 (+https://github.com/PythonWoods/zenzic)"
DATA_FILE = pathlib.Path(__file__).resolve().parent.parent / "docs" / "assets" / "data" / "pypi-stats.json"


def fetch_json(url: str, retries: int = 3) -> dict:
    """Fetch JSON from URL with netiquette headers, rate-limit backoff, and safety handling."""
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    for attempt in range(1, retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception as exc:
            if attempt < retries:
                time.sleep(attempt * 2.0)
            else:
                print(f"Warning: Failed to fetch {url} after {retries} attempts: {exc}", file=sys.stderr)
    return {}


def main() -> int:
    print(f"Fetching PyPI download metrics for '{PACKAGE_NAME}' (single API call)...")

    existing_data: dict = {}
    if DATA_FILE.exists():
        try:
            existing_data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
        except Exception:
            existing_data = {}

    daily_map: dict[str, int] = {}
    for entry in existing_data.get("daily", []):
        if isinstance(entry, list) and len(entry) == 2:
            daily_map[entry[0]] = int(entry[1])

    # Single efficient API call (without mirrors)
    overall_raw = fetch_json(f"https://pypistats.org/api/packages/{PACKAGE_NAME}/overall?mirrors=false")
    overall_entries = overall_raw.get("data", [])

    for entry in overall_entries:
        date_str = entry.get("date")
        downloads = entry.get("downloads", 0)
        if date_str and isinstance(downloads, int):
            daily_map[date_str] = downloads

    # Chronologically sorted daily tuples
    sorted_daily = [[date, daily_map[date]] for date in sorted(daily_map.keys())]

    total_downloads = sum(count for _, count in sorted_daily)
    peak_daily = max((count for _, count in sorted_daily), default=0)

    # Compute 1d, 7d, 30d recent totals dynamically from latest daily records
    last_day = sorted_daily[-1][1] if sorted_daily else 0
    last_week = sum(count for _, count in sorted_daily[-7:]) if len(sorted_daily) >= 7 else total_downloads
    last_month = sum(count for _, count in sorted_daily[-30:]) if len(sorted_daily) >= 30 else total_downloads

    dataset = {
        "package": PACKAGE_NAME,
        "last_updated": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "summary": {
            "total_downloads": total_downloads,
            "last_day": last_day,
            "last_week": last_week,
            "last_month": last_month,
            "peak_daily": peak_daily,
        },
        "daily": sorted_daily,
    }

    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    DATA_FILE.write_text(json.dumps(dataset, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(f"Successfully updated PyPI stats dataset: {DATA_FILE.relative_to(DATA_FILE.parent.parent.parent)}")
    print(f"Summary: {total_downloads:,} total downloads | 30d: {last_month:,} | 7d: {last_week:,} | Peak: {peak_daily:,}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
