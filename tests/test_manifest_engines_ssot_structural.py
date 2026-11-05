# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""Which engines read a route manifest is derived from the registry, not restated.

`cli/_shared.py` gates the "a declared `prebuilt` without `.zenzic-vsm.json` is a
configuration error" check. It spelled the set as a literal — `("prebuilt",
"vsm")` — which is the same shape as two defects already closed in this
repository: `_INIT_VALID_ENGINES`, where `--engine` refused two engines its own
help text advertised, and `Z503`, where a gate existed on one call path and not
the other.

The failure mode a literal has here is specific: register a third adapter that
reads the manifest, and the check silently skips it. No error, no warning — a
project declaring that engine without a manifest would be analysed as something
else instead of being stopped.

The registry already holds the answer. `_BUILTIN_ADAPTERS` maps each engine name
to its adapter class, and the manifest-driven ones are exactly those resolving to
`PrebuiltVSMAdapter`. `manifest_driven_engines()` derives it, entry-point
adapters included, so a third-party adapter reaches the gate without this file
changing.
"""

from __future__ import annotations

import inspect

import pytest

from zenzic.core.adapters import _factory
from zenzic.core.adapters._factory import manifest_driven_engines
from zenzic.core.adapters._prebuilt import PrebuiltVSMAdapter


def test_the_gate_derives_instead_of_restating() -> None:
    """Structural: a literal here agreed with the registry until it did not."""
    from zenzic.cli import _shared

    source = inspect.getsource(_shared)
    assert "manifest_driven_engines" in source, (
        "cli/_shared.py must derive the manifest-driven engine set from the adapter "
        "registry rather than restating it."
    )
    assert '("prebuilt", "vsm")' not in source, (
        "cli/_shared.py still carries the literal engine tuple. A third adapter "
        "reading the manifest would be skipped by the check in silence."
    )


def test_it_names_the_engines_the_registry_actually_maps() -> None:
    """Positive control: a derivation that returned nothing would pass the test above."""
    derived = manifest_driven_engines()
    assert {"prebuilt", "vsm"} <= derived, (
        f"the two built-in manifest-driven engines must be in the derived set; got {sorted(derived)}"
    )
    assert "mkdocs" not in derived and "standalone" not in derived, (
        f"generator-config engines must not be in the manifest-driven set; got {sorted(derived)}"
    )


def test_a_third_manifest_engine_is_picked_up_without_editing_anything(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The planted regression, which is the whole point of deriving.

    A literal tuple cannot see this engine. The derived predicate must, because
    the registry is where the fact lives.
    """
    before = manifest_driven_engines()
    assert "astro-manifest" not in before

    class AstroManifestAdapter(PrebuiltVSMAdapter):
        """A third-party adapter that also reads `.zenzic-vsm.json`."""

    monkeypatch.setitem(_factory._BUILTIN_ADAPTERS, "astro-manifest", AstroManifestAdapter)

    after = manifest_driven_engines()
    assert "astro-manifest" in after, (
        "a newly registered manifest-driven adapter was not picked up: the set is "
        "not actually derived from the registry."
    )
    assert after == before | {"astro-manifest"}, (
        f"deriving must add exactly the new engine; before={sorted(before)} after={sorted(after)}"
    )
