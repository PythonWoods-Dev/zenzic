# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""Topological graph analysis for the Virtual Site Map."""

from __future__ import annotations
from collections import deque
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from zenzic.models.vsm import VirtualSiteMap


def _bfs_reachability(vsm: VirtualSiteMap, entry_points: list[str]) -> set[str]:
    """Compute all reachable canonical URLs via a deterministic BFS.
    
    The BFS traversal ensures O(V+E) time complexity and produces deterministic
    reachability sets by sorting nodes and relying on the pre-sorted adjacency list.
    """
    reachable = set()
    queue: deque[str] = deque()
    
    # Sort entry points for strict determinism
    for ep in sorted(entry_points):
        if ep in vsm:
            reachable.add(ep)
            queue.append(ep)
            
    while queue:
        current = queue.popleft()
        outgoing = vsm.outgoing_links.get(current, [])
        # outgoing is already strictly sorted in reindex_outgoing_links
        for neighbor in outgoing:
            if neighbor not in reachable and neighbor in vsm:
                reachable.add(neighbor)
                queue.append(neighbor)
                
    return reachable


def detect_orphans(vsm: VirtualSiteMap, entry_points: list[str]) -> list[str]:
    """Return a deterministically sorted list of canonical URLs that are unreachable.
    
    Orphans (Z410) are Markdown/MDX documents that exist in the VSM but cannot
    be reached from any of the defined entry points.
    """
    reachable = _bfs_reachability(vsm, entry_points)
    orphans = []
    
    for url, route in vsm.items():
        if route.status == "IGNORED" or route.source == "<virtual>":
            continue
            
        lower_source = route.source.lower()
        if not (lower_source.endswith(".md") or lower_source.endswith(".mdx")):
            continue
            
        if url not in reachable:
            orphans.append(url)
            
    return sorted(orphans)


def detect_dead_ends(vsm: VirtualSiteMap) -> list[str]:
    """Return a deterministically sorted list of canonical URLs with no outgoing links.
    
    Dead Ends (Z411) are Markdown/MDX documents that do not link to any other
    resources, representing a structural dead end in the documentation graph.
    Terminal assets (like images or CSS) are excluded.
    """
    dead_ends = []
    
    for url, route in vsm.items():
        if route.status == "IGNORED" or route.source == "<virtual>":
            continue
            
        lower_source = route.source.lower()
        if not (lower_source.endswith(".md") or lower_source.endswith(".mdx")):
            continue
            
        outgoing = vsm.outgoing_links.get(url, [])
        if not outgoing:
            dead_ends.append(url)
            
    return sorted(dead_ends)
