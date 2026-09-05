---
description: "Walk through the z514-generic-image-alt fixture: an image whose alt text is the word 'image', triggering Z514 GENERIC_IMAGE_ALT_TEXT."
---
<!-- SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev> -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Z514 — Generic Image Alt Text

**Z-Code:** `Z514 GENERIC_IMAGE_ALT_TEXT` · **Engine:** `standalone` · **Exit:** `1` (under strict mode) / `0` (warnings only)

---

## The Fixture

An image with alt text that describes nothing.

| File | Role |
| :--- | :--- |
| `.zenzic.toml` | Minimal standalone configuration |
| `docs/index.md` | An image with the alt text `image` |
| `docs/assets/logo.png` | The referenced asset |

```markdown
![image](assets/logo.png)
```

The alt attribute is present, so an accessibility checker that only tests for
presence passes this. It says nothing: a screen-reader user hears "image", which
conveys exactly as much as silence while taking longer.

Generic placeholders — `image`, `picture`, `screenshot`, `logo` — are the usual
output of writing the syntax before deciding what the image is for. `Z514`
catches the shape of that habit rather than judging prose quality.

---

## Running the Example

```bash
# Clone the Zenzic repository — no install required
cd examples/z514-generic-image-alt
uvx zenzic check all
```

Expected output:

```text
standalone • 2 files (1 pages, 1 assets) • 0.1s • 35 files/s

docs/index.md:3  ⚠  [Z514]  Image 'assets/logo.png' uses generic alt text
'image'. Provide descriptive alt text for accessibility.
    1  │  # Generic Alt Text Example
    2  │
    3  ❱  ![image](assets/logo.png)
       │  ^^^^^
```

The caret underlines the alt text itself, not the whole image syntax.

---

## Interpreting the Output

- **Severity:** `Warning`
- **Impact:** Deducts **2.0 DQS points** (content category).
- **Auto-Fixable:** No. Zenzic does not know what the image depicts.

Empty alt text (`![](...)`) is a different case and deliberately valid: it marks
an image as decorative, telling assistive technology to skip it. That is a real
choice, so `Z514` does not flag it.

---

## Resolve the Issue

Describe the image's purpose in context:

```markdown
![Zenzic shield logo](assets/logo.png)
```

The test is whether a reader who cannot see the image still gets what the
sentence around it needs. For a decorative image, use empty alt text
deliberately.

Re-run `zenzic check all`; the finding clears.

---

## See Also

- [Z104 — File Not Found](../z1xx-links/z104-file-not-found) — the image
  reference itself pointing nowhere.
- [Z405 — Unused Assets](../z4xx-topology/z405-unused-assets) — assets no page
  references.
- [Checks Reference](../../../reference/checks) — full rule specification.
