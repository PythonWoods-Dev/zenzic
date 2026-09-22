---
description: "The schema of .zenzic-vsm.json, the route manifest read by the prebuilt engine."
---

<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Route Manifest Schema (`.zenzic-vsm.json`)

**Schema version 1.** This page documents what the engine reads **today**, field by field,
verified against the implementation rather than against an example. Where the engine accepts
something and does nothing with it, this page says so.

`.zenzic-vsm.json` is the route manifest of the `prebuilt` engine. It lives at the
**repository root**, not in `docs_dir`, and it answers one question the engine cannot answer
for a generator it does not model: **which URL does each source file publish at?**

For how to generate one for your generator, see
[Configure your adapter](../how-to/configure-adapter.md#prebuilt-route-manifest). This page is
the contract; that page is the recipe.

## Shape

A JSON object whose **keys are source paths relative to `docs_dir`**, written with forward
slashes, and whose values are objects:

```json
{
  "index.mdx":         { "url": "/",                "status": "REACHABLE" },
  "guides/example.md": { "url": "/guides/example/", "status": "REACHABLE" }
}
```

A file that fails to parse is a configuration error, not a warning: the run stops and names
the file.

## Fields

| Field | Type | Default when absent | Effect |
| :--- | :--- | :--- | :--- |
| `url` | string | the URL the standalone mapping would produce | The canonical URL this source publishes at. Write it the way an author writes it in a link, trailing slash included if your generator emits one. |
| `status` | `"REACHABLE"`, `"ORPHAN_BUT_EXISTING"`, `"IGNORED"`, `"CONFLICT"` | `"REACHABLE"` | How the route is treated in the site map. |
| `slug` | string | *(none)* | **Accepted and currently inert on this path.** See below. |

### `slug` is read and not used

The manifest reader passes `slug` into the route metadata, and the site map is then built from
the canonical URL, the status and the file's anchors — **`slug` is not among them**. Nothing
downstream reads it back.

It is documented rather than omitted because the reader accepts it, and a field a parser
accepts is part of the contract whether or not it does anything. Supplying it is harmless;
expecting it to change a URL is not supported. For the `prebuilt` engine the URL is already
stated outright by `url`, which is why the slug has nothing left to decide.

## Behaviour this schema defines

| Situation | What happens | Exit |
| :--- | :--- | ---: |
| `engine = "prebuilt"` and **no manifest** | `Z111` — a configuration error naming the file to create and linking the recipe | **1** |
| A source on disk that the manifest **does not list** | `Z115 STALE_ROUTE_MANIFEST`, per source | 0 |
| A key in the manifest with **no file on disk** | The entry is simply never matched | 0 |
| An **unknown field** inside an entry | Silently ignored — see *Versioning* | 0 |

The second row is the one to know: a manifest goes out of date the moment a page is added, and
the engine says so by name instead of reporting the new page's links as broken.

## Versioning

**The file carries no version field today, and adding one has no effect** — unknown keys inside
an entry are accepted and ignored, with no warning. That is measured behaviour, not an
intention.

The consequence for anyone writing a manifest, and for any future extension of this schema:

- **A manifest written for schema 1 stays valid.** Fields are read by name with defaults, so an
  entry that omits everything but `url` is well-formed.
- **A manifest carrying a field a newer schema defines is silently accepted by an older engine**,
  which will ignore it. There is no negotiation and no warning, so a field cannot be relied on
  to be honoured merely because the file declares it.
- **This page's version number is the contract's version.** Until the engine reads a version
  marker, the version lives here and in the release notes, not in the file.

Whether the manifest should carry its own version marker — and what an engine should do with a
version it does not know — is an open design question, not settled by this page.
