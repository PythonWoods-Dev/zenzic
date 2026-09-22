# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""PrebuiltVSMAdapter — ingests a precomputed .zenzic-vsm.json routing table."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

from zenzic.core.adapters._standalone import StandaloneAdapter
from zenzic.core.exceptions import ZenzicConfigError


if TYPE_CHECKING:
    from zenzic.core.adapters._base import RouteMetadata
    from zenzic.models.config import BuildContext


class PrebuiltVSMAdapter(StandaloneAdapter):
    """Adapter that reads a static .zenzic-vsm.json file for routing.

    This is used for the Bridge Architecture (ADR-080), where a TS plugin
    generates the routing map and Zenzic simply consumes it.
    """

    def __init__(
        self, context: BuildContext, docs_root: Path, repo_root: Path | None = None
    ) -> None:
        self._routes: dict[str, dict[str, str]] = {}
        self._has_config = False

        # Loud rather than silent. The manifest below already carries whatever
        # prefix the real build produced, so a `base_url` on top would double it
        # or contradict it. Ignoring it here would be the same defect this field
        # was fixed for -- a setting that is accepted and does nothing -- moved
        # one adapter to the left. `zenzic init` does not offer `base_url` when
        # it writes a prebuilt config, so this is a backstop, not the usual path.
        if str(getattr(context, "base_url", "") or "").strip() not in ("", "/"):
            raise ZenzicConfigError(
                "base_url is set while engine = 'prebuilt'. Routes come from "
                ".zenzic-vsm.json, which already carries the prefix the build "
                "produced, so a second one would be applied twice. Remove "
                "base_url, or emit the manifest with the URLs you want."
            )

        root = repo_root if repo_root else docs_root.parent
        vsm_file = root / ".zenzic-vsm.json"

        if vsm_file.is_file():
            self._has_config = True
            try:
                with vsm_file.open("r", encoding="utf-8") as f:
                    data = json.load(f)
                    # Assume JSON is a dict of rel_path -> { "url": "...", "status": "..." }
                    self._routes = data
            except Exception as e:
                raise ZenzicConfigError(f"Failed to parse {vsm_file}: {e}") from e

    @classmethod
    def from_repo(
        cls, context: BuildContext, docs_root: Path, repo_root: Path
    ) -> PrebuiltVSMAdapter:
        return cls(context, docs_root, repo_root)

    def has_engine_config(self) -> bool:
        return self._has_config

    def declared_anchors(self) -> dict[str, set[str]]:
        """The `anchors` array of each manifest entry, where present.

        Declared anchors **replace** the predicted set for that source rather
        than extending it. A generator that states them is authoritative, and
        merging would let a wrong prediction keep passing fragments the site
        does not serve -- which would make the field a suppression mechanism
        wearing a schema's name.
        """
        out: dict[str, set[str]] = {}
        for rel, entry in self._routes.items():
            if not isinstance(entry, dict):
                continue
            declared = entry.get("anchors")
            if isinstance(declared, list):
                out[rel] = {str(a).lstrip("#") for a in declared}
        return out

    def declared_sources(self) -> set[str] | None:
        """Return the manifest's declared source paths, or ``None`` when there
        is no manifest to be stale against.

        The no-manifest case is deliberately ``None`` and not ``set()``. With
        no ``.zenzic-vsm.json`` this adapter falls back to standalone routing
        (`get_route_info` below returns REACHABLE rather than IGNORED), which
        is its own defect and carries its own warning; reporting it a second
        time as "every source is undeclared" would name the wrong fix.
        """
        if not self._has_config:
            return None
        return set(self._routes)

    def get_route_info(self, rel: Path) -> RouteMetadata:
        from zenzic.core.adapters._base import RouteMetadata

        rel_str = rel.as_posix()
        if rel_str in self._routes:
            data = self._routes[rel_str]
            return RouteMetadata(
                canonical_url=data.get("url", super()._map_url(rel)),
                status=data.get("status", "REACHABLE"),  # type: ignore
                slug=data.get("slug"),
            )

        return RouteMetadata(
            canonical_url=super()._map_url(rel),
            status="IGNORED" if self._has_config else "REACHABLE",
        )
