#!/usr/bin/env bash
# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
#
# generate_blog_headers.sh — regenerate the Foundations series header images.
#
# Every image is a real `freeze` capture of real Zenzic output against a real
# fixture built here — never a mock, never hand-edited (Rule 27). Run it and the
# images are reproduced; nothing has to be reverse-engineered from a .webp.
#
#     bash scripts/generate_blog_headers.sh
#
# Two implementation notes that matter if you edit this:
#
#   1. It calls .venv/bin/zenzic directly, NOT `uv run zenzic`. Nesting `uv run`
#      inside freeze's pseudo-terminal hangs indefinitely — a first attempt at
#      this took >10 minutes and produced nothing, while the direct binary
#      completes a scan in ~0.4s. Each capture also carries a hard timeout so a
#      regression can never wedge the whole run again.
#   2. The recipe below is not arbitrary. It was derived by measuring the
#      already-published captures under docs/assets/images/terminal/ and matching
#      them: background #18181a and a rounded corner reproduce their exact pixel
#      values, and font.size 32 lands in their 1400-2040px width band. The
#      earlier, removed headers were ~715px wide — that low pixel density is what
#      made them look soft at blog display width.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ZBIN="$REPO_ROOT/.venv/bin/zenzic"
OUT="$REPO_ROOT/docs/assets/images/blog"
WORK="${TMPDIR:-/tmp}/zenzic-blog-headers"
PER_IMAGE_TIMEOUT=90

# Canonical capture recipe — keep in sync with scripts/BLOG_HEADERS.md.
FREEZE_OPTS=(--background "#18181a" --border.radius 8 --padding 20 --font.size 32)

[[ -x "$ZBIN" ]] || { echo "error: $ZBIN not found — run 'uv sync' first" >&2; exit 1; }
command -v freeze >/dev/null || { echo "error: freeze is not installed" >&2; exit 1; }
command -v ffmpeg >/dev/null || { echo "error: ffmpeg is required to convert captures to webp" >&2; exit 1; }
mkdir -p "$OUT"

prose() {
  echo "This page carries a comfortable amount of prose so the minimum word-count check stays quiet and the capture shows only the finding under discussion."
}

# capture <fixture-dir> <output-name> <zenzic args...>
capture() {
  local dir="$1" name="$2"; shift 2
  # freeze refuses to write an image when the captured command exits non-zero
  # ("could not execute: exit status 1"), and every fixture here deliberately
  # produces findings — exit 1, or exit 2 for the security-breach capture. The
  # command therefore runs through a tiny runner script that always ends 0; the
  # rendered output is unchanged. A runner file avoids nested shell quoting,
  # which silently mangles the command when embedded in freeze's -x string.
  local runner="$dir/.capture.sh"
  { echo '#!/usr/bin/env bash'; echo "$ZBIN $* --no-header"; echo "true"; } > "$runner"
  chmod +x "$runner"
  # freeze v0.2.2 renders SVG and PNG only. Given a .webp path it writes an SVG
  # with a .webp extension and exits 0 -- no error, no warning -- despite --help
  # advertising webp. That produced six files browsers refused to display. So we
  # capture PNG (a format freeze genuinely implements) and convert to real webp,
  # matching the house format of the published captures under
  # docs/assets/images/terminal/. Verify with `file`, not ffprobe: ffprobe parses
  # an SVG's width/height happily and reports plausible dimensions for a file no
  # browser can render, which is exactly how the broken output first passed review.
  ( cd "$dir" && timeout "$PER_IMAGE_TIMEOUT" freeze \
      -x "$runner" \
      --output "$dir/$name.png" "${FREEZE_OPTS[@]}" 2>&1 | head -2 ) || true
  # NOTE: keep the pipe above. With `>/dev/null` freeze writes nothing at all --
  # it behaves differently when stdout is not a pipe. Reproduced repeatedly.
  #
  # freeze renders PNG at roughly 4x the nominal size (~6332px wide here), so the
  # capture is downscaled to the 1582px the published captures use. Downscaling
  # from a hi-DPI render is what makes the text crisp rather than soft -- the
  # removed originals were rendered at ~715px natively, which was the real defect.
  if [[ -s "$dir/$name.png" ]]; then
    ffmpeg -v error -y -i "$dir/$name.png" -vf "scale=1582:-1:flags=lanczos" \
      -c:v libwebp -lossless 0 -quality 92 "$OUT/$name.webp" >/dev/null 2>&1 || true
  fi
  [[ -s "$OUT/$name.webp" ]] || { echo "  FAILED (no image written): $name" >&2; return 1; }
  # Guard the exact defect above: assert the bytes really are WebP, not SVG.
  file -b "$OUT/$name.webp" | grep -q "Web/P" \
    || { echo "  FAILED (not a real WebP): $name" >&2; return 1; }
  printf '  %-28s %s\n' "$name" "$(ffprobe -v error -select_streams v:0 \
      -show_entries stream=width,height -of csv=p=0 "$OUT/$name.webp" 2>/dev/null)"
}

rm -rf "$WORK"; mkdir -p "$WORK"

# 1 — Snapshot Your Debt: baseline freezes existing findings, gate goes green.
d="$WORK/baseline"; mkdir -p "$d/docs"
printf 'docs_dir = "docs"\n' > "$d/.zenzic.toml"
printf '# Home\n\n%s\n\n[missing](gone.md)\n[also missing](nope.md)\n' "$(prose)" > "$d/docs/index.md"
( cd "$d" && "$ZBIN" check all --update-baseline --no-header >/dev/null 2>&1 ) || true
capture "$d" baseline_tracking_demo check all

# 2 — Enforce What Matters First: --only narrows what blocks CI.
d="$WORK/only"; mkdir -p "$d/docs"
printf 'docs_dir = "docs"\n' > "$d/.zenzic.toml"
printf '# Home\n\nshort page\n\n[missing](gone.md)\n' > "$d/docs/index.md"
capture "$d" progressive_gates_demo check all --only Z101

# 3 — Bring Your Own Rules: an org-specific rule via the TOML DSL.
d="$WORK/custom"; mkdir -p "$d/docs"
cat > "$d/.zenzic.toml" <<'EOF'
docs_dir = "docs"

[[custom_rules]]
code = "ZZ-NOINTERNAL"
pattern = "internal\\.corp\\.example"
message = "Internal hostname must not appear in public documentation"
severity = "error"
EOF
printf '# Home\n\n%s\n\nContact internal.corp.example for access.\n' "$(prose)" > "$d/docs/index.md"
capture "$d" custom_rules_demo check all

# 4 — The Quality Pyramid: four scored categories, one zero-tolerance gate.
#     Plain `score` (not --breakdown): the compact table plus the security
#     override is the article's subject, and --breakdown's long detail
#     sections produced a 2328px-tall portrait image, unusable as a header.
d="$WORK/pyramid"; mkdir -p "$d/docs"
printf 'docs_dir = "docs"\n' > "$d/.zenzic.toml"
printf '# Home\n\n%s\n\naws_key = "AKIAIOSFODNN7EXAMPLE"\n' "$(prose)" > "$d/docs/index.md"
capture "$d" quality_pyramid_demo score docs

# 5 — Zero Network, By Default: the Z204 Privacy Gate.
d="$WORK/privacy"; mkdir -p "$d/docs"
printf 'docs_dir = "docs"\nforbidden_patterns = ["ProjectOmniInternal"]\n' > "$d/.zenzic.toml"
printf '# Home\n\n%s\n\nThe ProjectOmniInternal rollout begins next quarter.\n' "$(prose)" > "$d/docs/index.md"
capture "$d" privacy_gate_demo check all

# 6 — Archived on Purpose: one code exempted, every other check still running.
d="$WORK/governance"; mkdir -p "$d/docs/archive"
cat > "$d/.zenzic.toml" <<'EOF'
docs_dir = "docs"

[governance.directory_policies]
"archive/**" = ["Z402"]
EOF
printf '# Home\n\n%s\n\n[Guide](guide.md)\n' "$(prose)" > "$d/docs/index.md"
printf '# Guide\n\n%s\n\n[Home](index.md)\n' "$(prose)" > "$d/docs/guide.md"
printf '# Retired Migration Guide\n\nNo longer linked from navigation. It references a [removed page](removed-target.md).\n' \
  > "$d/docs/archive/old-migration-guide.md"
capture "$d" governance_exemption_demo check all

rm -rf "$WORK"
echo "Done — 6 headers written to docs/assets/images/blog/"
