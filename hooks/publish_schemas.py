# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""MkDocs build hook: publish the JSON Schemas at the URL they declare as canonical.

`zenzic-baseline.schema.json` and `zenzic-output.schema.json` live at the
repository root (where `pyproject.toml`'s packaging config, `REUSE.toml`, and
`tests/test_baseline.py` all reference them) and each declares

    "$id": "https://zenzic.dev/schemas/<name>.schema.json"

as its canonical identifier. Nothing ever published them there: `docs/schemas/`
has never existed, so the built site never contained them and both URLs 404.

That is not cosmetic. `zenzic.core.baseline.save_baseline` stamps
`"$schema": "https://zenzic.dev/schemas/zenzic-baseline.schema.json"` into every
`.zenzic-baseline.json` it writes, so every user's generated baseline file points
at a dead URL — editors that resolve `$schema` to provide validation and
autocompletion (VS Code, IntelliJ) silently get nothing back.

This hook copies the schemas into `site_dir/schemas/` after the build, so the
advertised `$id` resolves for real. Copying at build time — rather than keeping a
second copy under `docs/` — keeps exactly one source of truth for each schema.

Runs as `on_post_build` for the same reason as the sibling RSS hook: it operates
on `site_dir` directly, outside the per-page render pipeline.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from mkdocs.config.defaults import MkDocsConfig

#: Root-relative schema files to publish, and the site path they claim as `$id`.
_SCHEMAS = ("zenzic-baseline.schema.json", "zenzic-output.schema.json")
_SITE_SUBDIR = "schemas"


def on_post_build(*, config: MkDocsConfig) -> None:
    repo_root = Path(config["config_file_path"]).parent
    target_dir = Path(config["site_dir"]) / _SITE_SUBDIR
    target_dir.mkdir(parents=True, exist_ok=True)
    for name in _SCHEMAS:
        source = repo_root / name
        if not source.is_file():
            raise FileNotFoundError(
                f"{name} is missing from the repository root — it is published to "
                f"/{_SITE_SUBDIR}/{name}, which its own $id declares as canonical."
            )
        shutil.copy2(source, target_dir / name)
