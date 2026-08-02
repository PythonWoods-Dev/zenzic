# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""Tests for topological graph analysis."""

from zenzic.core.topology import detect_dead_ends, detect_orphans
from zenzic.models.vsm import Route, VirtualSiteMap


def test_detect_orphans():
    vsm = VirtualSiteMap()
    vsm["/index.html"] = Route(
        url="/index.html", source="index.md", status="REACHABLE", anchors=set()
    )
    vsm["/a.html"] = Route(url="/a.html", source="a.md", status="REACHABLE", anchors=set())
    vsm["/b.html"] = Route(url="/b.html", source="b.md", status="REACHABLE", anchors=set())
    vsm["/orphan.html"] = Route(
        url="/orphan.html", source="orphan.md", status="REACHABLE", anchors=set()
    )

    # Adjacency list setup
    vsm.outgoing_links["/index.html"] = ["/a.html"]
    vsm.outgoing_links["/a.html"] = ["/b.html"]

    entry_points = ["/index.html"]
    orphans = detect_orphans(vsm, entry_points)

    assert orphans == ["/orphan.html"]


def test_detect_dead_ends():
    vsm = VirtualSiteMap()
    vsm["/index.html"] = Route(
        url="/index.html", source="index.md", status="REACHABLE", anchors=set()
    )
    vsm["/a.html"] = Route(url="/a.html", source="a.md", status="REACHABLE", anchors=set())
    vsm["/dead_end.html"] = Route(
        url="/dead_end.html", source="dead_end.md", status="REACHABLE", anchors=set()
    )
    vsm["/asset.png"] = Route(
        url="/asset.png", source="asset.png", status="REACHABLE", anchors=set()
    )

    # Adjacency list setup
    vsm.outgoing_links["/index.html"] = ["/a.html"]
    vsm.outgoing_links["/a.html"] = ["/dead_end.html"]
    # /dead_end.html has no outgoing links

    dead_ends = detect_dead_ends(vsm)
    assert dead_ends == ["/dead_end.html"]
