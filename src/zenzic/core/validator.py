# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""Validation logic: native link checking (internal + external) and snippet checks.

Link validation no longer invokes any external process.  Instead it uses a
pure-Python two-pass approach:

1. Read every ``.md`` file under ``docs/`` into memory, extract all Markdown
   links while skipping fenced code blocks and inline code spans.
2. *Internal links* (relative or site-absolute paths) are resolved against the
   pre-built in-memory file map; ``#anchor`` fragments are validated against
   heading slugs extracted from the target file.
3. *External links* (``http://`` / ``https://``) are validated lazily — only
   when ``strict=True`` — via concurrent HEAD requests through ``httpx``.

Snippet validation supports four languages using pure-Python parsers:

- **Python** (``python``, ``py``) — ``compile()`` in ``exec`` mode
- **YAML** (``yaml``, ``yml``) — ``yaml.safe_load()``
- **JSON** (``json``) — ``json.loads()``
- **TOML** (``toml``) — ``tomllib.loads()`` (stdlib 3.11+)

No subprocesses are spawned for any language.
"""

from __future__ import annotations

import asyncio
import contextlib
import html
import json
import sys
import textwrap
import time
from collections.abc import Iterator, Mapping


if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib  # PEP 680 backport
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal, NamedTuple

import httpx
import yaml

from zenzic.core import regex as re
from zenzic.core.ast import ExtractedLink
from zenzic.core.discovery import (
    DOC_SUFFIXES,
    iter_markdown_sources,
    walk_files,
)
from zenzic.core.resolver import (
    InMemoryPathResolver,
    Resolved,
)
from zenzic.models.config import ZenzicConfig
from zenzic.models.references import IntegrityReport, ReferenceMap


if TYPE_CHECKING:
    from zenzic.core.exclusion import LayeredExclusionManager
    from zenzic.core.suppressions import SuppressionTracker


# ─── YAML loader (boundary layer — ignores unknown tags like MkDocs !ENV) ────


class _PermissiveSafeLoader(yaml.SafeLoader):
    """SafeLoader that silently ignores unknown YAML tags (e.g. MkDocs !ENV)."""


def _construct_undefined(loader: yaml.SafeLoader, tag_suffix: str, node: yaml.Node) -> Any:
    if isinstance(node, yaml.ScalarNode):
        return loader.construct_scalar(node)
    elif isinstance(node, yaml.SequenceNode):
        return loader.construct_sequence(node)
    elif isinstance(node, yaml.MappingNode):
        return loader.construct_mapping(node)
    return None


_PermissiveSafeLoader.add_multi_constructor("!", _construct_undefined)  # type: ignore[no-untyped-call]
_PermissiveSafeLoader.add_multi_constructor("tag:yaml.org,2002:python/", _construct_undefined)  # type: ignore[no-untyped-call]


# ─── Regexes ──────────────────────────────────────────────────────────────────

# Matches inline Markdown links [text](url) and images ![alt](url).
# Captures the raw content inside the parentheses (group 1).
# Does NOT match reference-style links [text][id] or auto-links <url>.
_MARKDOWN_LINK_RE = re.compile(r"!?\[[^\[\]]*\]\(([^)]+)\)")

# Empty link-label detectors used for Z108. Images are excluded; Z403 covers
# missing image alt text separately.
_EMPTY_INLINE_LINK_TEXT_RE = re.compile(r"\[[\s*_~`]*\]\(([^)]*)\)")
_EMPTY_REF_LINK_TEXT_RE = re.compile(r"\[[\s*_~`]*\]\[[^\]]*\]")


class LinkInfo(NamedTuple):
    """Extracted link with source position for surgical caret rendering."""

    url: str
    lineno: int
    col_start: int = 0
    match_text: str = ""


# Matches ATX headings: ``# Heading``, ``## Sub``, etc. (multiline mode).
_HEADING_RE = re.compile(r"^#{1,6}\s+(.+)", re.MULTILINE)

# Matches MkDocs Material explicit anchor attribute: ``{ #custom-id }``
_EXPLICIT_ANCHOR_RE = re.compile(r"\{[^}]*#([\w-]+)[^}]*\}")
_ATTR_LIST_RE = re.compile(r"\s+\{[^}]*\}$")
_FN_DEF_RE = re.compile(r"^ {0,3}\[\^([^\]]+)\]:")

# Matches HTML tags to strip from heading text before slugification.
_HTML_TAG_RE = re.compile(r"<[^>]+>")
# Matches id="..." or id='...' attributes inside standard HTML tags
_HTML_ID_RE = re.compile(r"""<[^>]*\bid\s*=\s*['"]([^'"]+)['"]""", re.IGNORECASE)

# Reference definition: [id]: url  (up to 3 leading spaces per CommonMark §4.7)
_REF_DEF_RE = re.compile(r"^ {0,3}\[([^\]]+)\]:\s+(\S+)")

# Reference link: [text][id] or [text][] (collapsed reference)
_REF_LINK_RE = re.compile(r"\[([^\]]*)\]\[([^\]]*)\]")

# Shortcut reference link: [text] (semantic filters applied in code).
_REF_SHORTCUT_RE = re.compile(r"\[([^\]]+)\]")

# Inline code span — erased before link extraction to avoid false positives.
_INLINE_CODE_RE = re.compile(r"`[^`\n]+`")
# Strips Markdown link title from href: "url 'title'" → "url".
_TITLE_STRIP_RE = re.compile(r"""\s+["'].*$""")
# Slugification helpers used in _slugify_heading().
_SLUG_NONWORD_RE = re.compile(r"[^\w\s-]")
_SLUG_SPACES_RE = re.compile(r"\s+")

# URL schemes that are valid syntax but point to non-HTTP targets we skip.
_SKIP_SCHEMES = ("mailto:", "data:", "ftp:", "tel:", "javascript:", "irc:", "xmpp:")

# Matches Docusaurus highlighting comments within snippets
_HIGHLIGHT_COMMENT_RE = re.compile(
    r"^\s*(?://|#|/\*|\*)\s*highlight-(?:start|end|next-line)(?:\s*\*/)?\s*$",
    re.IGNORECASE,
)

# Maximum number of simultaneous outbound HTTP connections during external link checks.
# Prevents exhausting OS file descriptors and avoids triggering rate-limits on target servers.
_MAX_CONCURRENT_REQUESTS = 20

# Files at or above this threshold use parallel worker indexing for anchors
# and resolved links before the global validation phase runs.
VALIDATION_PARALLEL_THRESHOLD = 50


# ─── PolyglotExtractor — RE2 constants (v0.17.0) ─────────────────────────────

# Stadio 1: cattura atomica <a> e <img> (multilinea, DFA-pure, O(N)).
# Vincolo: il carattere '>' termina il tag e non è ammesso nei valori degli attributi.
_RE_POLY_TAG: re.RegexPattern = re.compile(r"(?s)<(a|img)\b(?P<attrs>[^>]*?)>")

# Stadio 2: parsing lineare coppie attributo=valore.
_RE_POLY_ATTR: re.RegexPattern = re.compile(
    r"(?P<key>[\w:@-]+)"
    r"(?:\s*=\s*"
    r'(?P<val>"[^"]*"|'  # double-quoted
    r"'[^']*'|"  # single-quoted
    r"[^\s>]+"
    r"))?",
)

# Attributi Safe-Core: pass senza diagnostica (ADR-075 — nessun parser esterno).
_POLY_SAFE_CORE: frozenset[str] = frozenset(
    {
        "href",
        "src",
        "id",
        "class",
        "title",
        "rel",
        "target",
        "lang",
        "download",
        "alt",
        "width",
        "height",
        "loading",
        "decoding",
        "data-zenzic-ignore",
    }
)
_POLY_ARIA_PREFIX = "aria-"  # aria-* è sempre Safe-Core

# Attributi Blacklist: Z124 OPAQUE_HTML_CONTEXT.
_POLY_BLACKLIST: frozenset[str] = frozenset(
    {
        "data-url",
        "data-path",
        "data-target",
        "data-route",
    }
)
_POLY_ON_PREFIX = "on"  # on* event-handlers → Z124

# Schemi vietati (Security Gate — Z205, non sopprimibile, Exit 2).
_POLY_FORBIDDEN_SCHEMES: frozenset[str] = frozenset({"javascript:", "data:"})
# Schemi informativi (Z123, nessuna risoluzione path).
_POLY_INFO_SCHEMES: frozenset[str] = frozenset({"mailto:", "tel:", "ftp:"})

# Pattern fence per PolyglotExtractor._mask_fences (subset di SuppressionTracker).
_POLY_FENCE_RE: re.RegexPattern = re.compile(r"^\s*(?P<fence>[`~]{3,})(?P<info>.*)$")


# HTML and MDX Comment Regex Patterns for masking
_POLY_COMMENT_RE: re.RegexPattern = re.compile(r"<!--.*?-->", re.DOTALL)
_POLY_MDX_COMMENT_RE: re.RegexPattern = re.compile(r"\{\/\*.*?\*\/\}", re.DOTALL)

# Math block patterns for masking (display math $$...$$ and inline math $...$)
_POLY_DISPLAY_MATH_RE: re.RegexPattern = re.compile(r"\$\$.*?\$\$", re.DOTALL)
_POLY_INLINE_MATH_RE: re.RegexPattern = re.compile(r"\$[^$\n]+\$")

# Strip whitespaces and control characters from URLs prima del check Z205.
_POLY_CLEAN_URL_RE: re.RegexPattern = re.compile(r"[\s\x00-\x1F]+")


@dataclass(frozen=True, slots=True)
class HtmlNodeInfo:
    """Nodo HTML estratto dal PolyglotExtractor (tag ``<a>`` o ``<img>``).

    Contiene tutti i dati necessari all'emissione di Z120–Z124 e Z205
    senza ulteriori accessi al testo sorgente.

    Attributes:
        tag:               ``"a"`` oppure ``"img"``.
        href:              Valore di ``href`` (per ``<a>``) o ``src`` (per ``<img>``).
                           ``None`` se l'attributo è assente.
        line_no:           Numero di riga 1-based nel sorgente originale.
        suppressed:        ``True`` se ``data-zenzic-ignore`` è presente sul tag.
        z205_scheme:       Schema vietato rilevato (``"javascript:"`` / ``"data:"``);
                           ``None`` se il tag non è un vettore Z205.
        unknown_attrs:     Attributi non censiti nella Safe-Core list → Z120.
        blacklisted_attrs: Attributi blacklistati (event-handler, shadow-routing) → Z124.
        is_missing_href:   ``True`` se ``href``/``src`` è assente o vuoto → Z121.
        is_jump_link:      ``True`` se ``href="#"`` → Z122.
        info_scheme:       Schema informativo (``mailto:``, ``tel:``, ``ftp:``)
                           se rilevato → Z123; ``None`` altrimenti.
        raw_tag:           Testo originale del tag (per messaggi diagnostici).
    """

    tag: str
    href: str | None
    line_no: int
    suppressed: bool
    z205_scheme: str | None
    unknown_attrs: list[str]
    blacklisted_attrs: list[str]
    is_missing_href: bool
    is_jump_link: bool
    info_scheme: str | None
    raw_tag: str


@dataclass
class ReferenceLinkNode:
    """Nodo estratto dal PolyglotExtractor per una definizione di link di riferimento ([label]: dest)."""

    label: str
    dest: str
    line_no: int
    raw: str


class PolyglotExtractor:
    """Estrattore a due stadi per tag HTML nativi e definizioni di riferimento Markdown.

    Implementa la **Uniform Resolver Pipeline** (URP) di Zenzic v0.17.0:
    la forma sintattica (Markdown vs HTML vs Reference Defs) è un dettaglio di trasporto;
    l'analisi avviene sul valore risolto del puntamento.

    **Invarianti (ADR-075 / ADR-020):**

    * Complessità O(N): RE2/DFA-pure, nessun backtracking, nessun subprocess.
    * Z205 (FORBIDDEN_SCHEME) è verificato **prima** di ``data-zenzic-ignore``
      (sicurezza ha precedenza assoluta sulla soppressione).
    * Supporta tag ``<a>``, ``<img>`` e definizioni di riferimento Markdown (CommonMark §4.7).
    * Fence-skipping obbligatorio: i blocchi ``code``/``pre`` vengono oscurati
      prima dell'estrazione per evitare falsi positivi in esempi di codice.
    """

    def extract(self, text: str, *, _premasked: str | None = None) -> list[HtmlNodeInfo]:
        """Estrae tutti i nodi HTML rilevanti dal testo sorgente.

        Args:
            text: Contenuto Markdown grezzo (no I/O).
            _premasked: Optional pre-computed buffer with comments, fences, and math masked.

        Returns:
            Lista di :class:`HtmlNodeInfo`, uno per ogni tag ``<a>``/``<img>``
            trovato fuori dai blocchi di codice.
        """
        if _premasked is not None:
            masked = self._mask_inline_code(_premasked)
        else:
            masked = self._mask_math(
                self._mask_inline_code(self._mask_fences(self._mask_comments(text)))
            )
        nodes: list[HtmlNodeInfo] = []
        for m in _RE_POLY_TAG.finditer(masked):
            tag = m.group(1).lower()
            attrs_str = m.group("attrs")
            # Calcolare line_no dal testo originale (non mascherato)
            line_no = text[: m.start()].count("\n") + 1
            nodes.append(self._parse_node(tag, attrs_str, line_no, m.group(0)))
        return nodes

    def extract_ref_defs(
        self, text: str, *, _premasked: str | None = None
    ) -> list[ReferenceLinkNode]:
        """Estrae tutte le definizioni di link di riferimento ([label]: dest) fuori dai blocchi di codice.

        Implementa CommonMark §4.7 Reference Link Definition parsing via PolyglotExtractor.
        Fence-skipping obbligatorio tramite _mask_fences() e _mask_comments().
        First-definition-wins per la risoluzione dei duplicati.
        """
        masked = (
            _premasked
            if _premasked is not None
            else self._mask_math(self._mask_fences(self._mask_comments(text)))
        )
        nodes: list[ReferenceLinkNode] = []
        seen_labels: set[str] = set()

        for lineno, line in enumerate(masked.splitlines(), start=1):
            m = _REF_DEF_RE.match(line)
            if not m:
                continue
            label = m.group(1)
            if label.startswith("^"):
                continue
            norm_label = label.lower().strip()
            if norm_label in seen_labels:
                continue
            seen_labels.add(norm_label)
            dest = m.group(2).strip()
            nodes.append(
                ReferenceLinkNode(
                    label=norm_label,
                    dest=dest,
                    line_no=lineno,
                    raw=line,
                )
            )
        return nodes

    def extract_inline_links(
        self, text: str, *, _premasked: str | None = None
    ) -> list[ExtractedLink]:
        """Extract standard Markdown inline links ([text](url)) and images (![alt](url)).

        Fences, HTML/MDX comments, and inline code spans are masked out prior to extraction
        to avoid false positives in code examples. Optional link titles are stripped.

        Args:
            text: Raw markdown content.
            _premasked: Optional pre-computed buffer with comments, fences, and math masked.

        Returns:
            List of :class:`ExtractedLink` with node_type="inline" or "image".
        """
        masked = (
            _premasked
            if _premasked is not None
            else self._mask_math(self._mask_fences(self._mask_comments(text)))
        )
        clean_text = self._mask_inline_code(masked)
        results: list[ExtractedLink] = []

        for lineno, line in enumerate(clean_text.splitlines(), start=1):
            for m in _MARKDOWN_LINK_RE.finditer(line):
                raw = m.group(1).strip()
                if not raw:
                    continue
                url = _TITLE_STRIP_RE.sub("", raw).strip()
                if url:
                    is_img = m.group(0).startswith("!")
                    node_type = "image" if is_img else "inline"
                    results.append(
                        ExtractedLink(
                            url=url,
                            line_no=lineno,
                            is_html=False,
                            node_type=node_type,
                            raw_text=m.group(0),
                            col_start=m.start(),
                        )
                    )
        return results

    def extract_all_links(self, text: str) -> list[ExtractedLink]:
        """Single source of truth for extracting all link candidate nodes from Markdown & HTML.

        Aggregates:
        1. HTML tag href/src attributes (<a>, <img>) from `extract(...)`
        2. Reference link definitions ([label]: dest) from `extract_ref_defs(...)`
        3. Inline Markdown links ([text](url), ![alt](url)) from `extract_inline_links(...)`

        Args:
            text: Raw markdown/HTML text.

        Returns:
            Flat, ordered list of :class:`ExtractedLink` objects sorted by line_no and col_start.
        """
        masked_base = self._mask_math(self._mask_fences(self._mask_comments(text)))
        extracted: list[ExtractedLink] = []

        # 1. HTML nodes
        for html_node in self.extract(text, _premasked=masked_base):
            if html_node.href is not None and not html_node.is_missing_href:
                extracted.append(
                    ExtractedLink(
                        url=html_node.href,
                        line_no=html_node.line_no,
                        is_html=True,
                        node_type=f"html_{html_node.tag}",
                        raw_text=html_node.raw_tag,
                        col_start=0,
                        suppressed=html_node.suppressed,
                        html_node=html_node,
                    )
                )

        # 2. Reference definitions
        for ref_node in self.extract_ref_defs(text, _premasked=masked_base):
            extracted.append(
                ExtractedLink(
                    url=ref_node.dest,
                    line_no=ref_node.line_no,
                    is_html=False,
                    node_type="ref_def",
                    raw_text=ref_node.raw,
                    col_start=0,
                )
            )

        # 3. Inline Markdown links and images
        extracted.extend(self.extract_inline_links(text, _premasked=masked_base))

        # Deterministic ordering by line number and column position
        extracted.sort(key=lambda item: (item.line_no, item.col_start))
        return extracted

    def _mask_comments(self, text: str) -> str:
        """Mask HTML and MDX comments with spaces of equal length, preserving newlines to maintain line offsets."""

        def _repl(m: Any) -> str:
            return "".join("\n" if c == "\n" else " " for c in m.group(0))

        text = _POLY_COMMENT_RE.sub(_repl, text)
        text = _POLY_MDX_COMMENT_RE.sub(_repl, text)
        return text

    def _mask_inline_code(self, text: str) -> str:
        """Sostituisce blocchi inline code con spazi bianchi preservando gli offset."""
        from zenzic.core.validator import _INLINE_CODE_RE

        return _INLINE_CODE_RE.sub(
            lambda m: "".join("\n" if c == "\n" else " " for c in m.group(0)), text
        )

    def _mask_fences(self, text: str) -> str:
        """Sostituisce blocchi code/pre con spazi bianchi preservando gli offset.

        Utilizza la stessa logica di fence-detection di :class:`SuppressionTracker`
        (tre o più backtick/tilde) per garantire coerenza nel trattamento dei
        blocchi di codice a livello di codebase.
        """
        lines = text.split("\n")
        result: list[str] = []
        inside = False
        open_char = ""
        open_len = 0
        for line in lines:
            fm = _POLY_FENCE_RE.match(line)
            if not inside:
                if fm:
                    inside = True
                    fence = fm.group("fence")
                    open_char = fence[0]
                    open_len = len(fence)
                    result.append(" " * len(line))
                else:
                    result.append(line)
            else:
                if fm:
                    fence = fm.group("fence")
                    info = fm.group("info").strip()
                    if fence[0] == open_char and len(fence) >= open_len and not info:
                        inside = False
                result.append(" " * len(line))
        return "\n".join(result)

    def _mask_math(self, text: str) -> str:
        """Sostituisce blocchi matematici ($$...$$ e $...$) con spazi bianchi preservando i caratteri di a capo."""
        text = _POLY_DISPLAY_MATH_RE.sub(
            lambda m: "".join("\n" if c == "\n" else " " for c in m.group(0)), text
        )
        text = _POLY_INLINE_MATH_RE.sub(
            lambda m: "".join("\n" if c == "\n" else " " for c in m.group(0)), text
        )
        return text

    def _parse_node(self, tag: str, attrs_str: str, line_no: int, raw_tag: str) -> HtmlNodeInfo:
        """Parsing lineare della stringa ``attrs`` e classificazione governance.

        **Ordine di priorità:**

        1. Estrae ``href``/``src``.
        2. **Verifica Z205** (schema vietato) — avviene PRIMA di tutto il resto.
        3. Rileva ``data-zenzic-ignore``.
        4. Classifica ogni attributo: Safe-Core / Blacklist / Unknown.
        5. Determina Z121/Z122/Z123.
        """
        href_key = "src" if tag == "img" else "href"
        href: str | None = None
        suppressed = False
        unknown: list[str] = []
        blacklisted: list[str] = []
        seen_attrs: set[str] = set()

        for m in _RE_POLY_ATTR.finditer(attrs_str):
            key_raw = m.group("key")
            if not key_raw:
                continue
            key = key_raw.lower()
            if key in seen_attrs:
                continue
            seen_attrs.add(key)

            val_raw = m.group("val") or ""
            val = val_raw.strip("\"'")

            if key == href_key:
                href = val.strip() if val.strip() else None
            elif key == "data-zenzic-ignore":
                suppressed = True
            elif key.startswith(_POLY_ARIA_PREFIX):
                pass  # aria-* è sempre Safe-Core
            elif key in _POLY_SAFE_CORE:
                pass  # Safe-Core: pass senza diagnostica
            elif key in _POLY_BLACKLIST or key.startswith(_POLY_ON_PREFIX):
                blacklisted.append(key)
            else:
                unknown.append(key)

        # ── Security Gate Z205: check PRIMA di data-zenzic-ignore ─────────────────
        z205_scheme: str | None = None
        clean_href: str | None = None
        if href:
            clean_href = _POLY_CLEAN_URL_RE.sub("", html.unescape(href)).lower()
            for scheme in _POLY_FORBIDDEN_SCHEMES:
                if clean_href.startswith(scheme):
                    z205_scheme = scheme
                    break

        # ── Classificazione link ───────────────────────────────────────────────────
        is_missing_href = href is None
        is_jump_link = href == "#"
        info_scheme: str | None = None
        if clean_href and not is_jump_link and z205_scheme is None:
            for scheme in _POLY_INFO_SCHEMES:
                if clean_href.startswith(scheme):
                    info_scheme = scheme
                    break

        return HtmlNodeInfo(
            tag=tag,
            href=href,
            line_no=line_no,
            suppressed=suppressed,
            z205_scheme=z205_scheme,
            unknown_attrs=unknown,
            blacklisted_attrs=blacklisted,
            is_missing_href=is_missing_href,
            is_jump_link=is_jump_link,
            info_scheme=info_scheme,
            raw_tag=raw_tag,
        )


# Singleton per l'uso nel pipeline di validazione.
_POLYGLOT_EXTRACTOR = PolyglotExtractor()


# ─── Data classes ─────────────────────────────────────────────────────────────


@dataclass(slots=True)
class SnippetError:
    file_path: Path
    line_no: int
    message: str
    code: str = field(init=False, default="Z503")

    def __post_init__(self) -> None:
        self.code = "Z503"


@dataclass(slots=True)
class LinkError:
    """A single link validation finding with source context for rich rendering.

    Attributes:
        file_path:   Absolute path of the source file containing the link.
        line_no:     1-based line number of the offending link.
        message:     Human-readable error description.
        source_line: The raw source line from the file (stripped), used by
                     the CLI to render the Visual Snippet indicator ``│``.
                     Empty string when the line cannot be retrieved.
        error_type:  Machine-readable category, e.g. ``'UNREACHABLE_LINK'``,
                     ``'FILE_NOT_FOUND'``, ``'ANCHOR_MISSING'``, etc.
    """

    file_path: Path
    line_no: int
    message: str
    source_line: str = ""
    error_type: str = "Z101"
    col_start: int = 0
    match_text: str = ""
    code: str = field(init=False, default="Z101")

    def __post_init__(self) -> None:
        self.code = self.error_type

    def __str__(self) -> str:
        """Flat string form — backwards-compatible with the old list[str] API."""
        return self.message


# ─── Path-traversal intent classifier ────────────────────────────────────────

# Detects hrefs that, after traversal, would reach an OS system directory.
# Triggering this classifier upgrades a PATH_TRAVERSAL error to a
# PATH_TRAVERSAL_SUSPICIOUS security incident (Exit Code 3).
_RE_SYSTEM_PATH: re.RegexPattern = re.compile(r"/(?:etc|root|var|proc|sys|usr)/")


def _classify_traversal_intent(href: str) -> Literal["suspicious", "boundary"]:
    """Return 'suspicious' when *href* appears to target an OS system directory.

    A traversal to ``../../../../etc/passwd`` is a potential attack vector.
    A traversal to ``../../sibling-repo/README.md`` is a boundary violation
    but has no OS-exploitation intent.  Only the former warrants Exit Code 3.

    This check intentionally remains a fast regex scan over the raw href
    string — no filesystem calls, no Path resolution — to stay within the
    Zero I/O constraint of the validator hot-path.
    """
    return "suspicious" if _RE_SYSTEM_PATH.search(href) else "boundary"


def _build_link_graph(
    links_cache: dict[Path, list[LinkInfo]],
    resolver: InMemoryPathResolver,
    source_files: frozenset[Path],
) -> dict[Path, set[Path]]:
    """Build the adjacency map of internal Markdown→Markdown links.

    Only edges between files present in *source_files* are recorded.
    External links, fragment-only links, and links to Ghost Routes are
    excluded — Ghost Routes have no outgoing edges so they cannot be
    members of a cycle.

    This is called once after the InMemoryPathResolver is constructed
    (Phase 1.5).  The resolver is already warm; no additional I/O occurs.
    """
    adj: dict[Path, set[Path]] = {f: set() for f in source_files}
    for md_file, links in links_cache.items():
        for link in links:
            url = link.url
            # Skip external URLs, non-navigable schemes, and fragment-only links
            if (
                url.startswith(_SKIP_SCHEMES)
                or url.startswith(("http://", "https://"))
                or not url
                or url.startswith("#")
            ):
                continue
            outcome = resolver.resolve(md_file, url)
            if isinstance(outcome, Resolved) and outcome.target in source_files:
                adj.setdefault(md_file, set()).add(outcome.target)
    return adj


def _find_cycles_iterative(adj: dict[Path, set[Path]]) -> frozenset[str]:
    """Return canonical Path strings of all nodes that participate in at least one cycle.

    Iterative DFS with WHITE/GREY/BLACK colouring — avoids RecursionError on
    large documentation graphs (Pillar 2: Zero Subprocess / total portability).
    """
    WHITE, GREY, BLACK = 0, 1, 2
    color: dict[Path, int] = dict.fromkeys(adj, WHITE)
    in_cycle: set[str] = set()

    for start in list(adj):
        if color[start] != WHITE:
            continue
        stack: list[tuple[Path, Iterator[Path]]] = [(start, iter(adj[start]))]
        path: list[Path] = [start]
        path_set: set[Path] = {start}
        color[start] = GREY

        while stack:
            node, nbrs = stack[-1]
            try:
                nbr = next(nbrs)
                if nbr not in color:
                    color[nbr] = WHITE
                    adj.setdefault(nbr, set())
                if color[nbr] == GREY:  # back edge → cycle
                    idx = path.index(nbr)
                    in_cycle.update(p.as_posix() for p in path[idx:])
                    in_cycle.add(nbr.as_posix())
                elif color[nbr] == WHITE:
                    color[nbr] = GREY
                    stack.append((nbr, iter(adj.get(nbr, set()))))
                    path.append(nbr)
                    path_set.add(nbr)
            except StopIteration:
                done = path[-1]
                color[done] = BLACK
                path.pop()
                path_set.discard(done)
                stack.pop()

    return frozenset(in_cycle)


class _ValidationPayload(NamedTuple):
    """Worker output for one markdown file in link validation phase 1.

    Attributes:
        file_path: Absolute markdown file path.
        anchors: Heading anchor slugs extracted from the file.
        links: Resolved links from inline and reference-style syntax.
        source_lines: Source split by lines for O(1) error-context lookup.
    """

    file_path: Path
    anchors: set[str]
    links: list[LinkInfo]
    source_lines: list[str]


def _index_file_for_validation(args: tuple[Path, str]) -> _ValidationPayload:
    """Phase 1 worker: extract anchors and links for one markdown file.

    Runs as a pure function so it can be dispatched safely to a process pool.
    """
    md_file, content = args
    ref_map = _build_ref_map(content)
    extractor = PolyglotExtractor()
    extracted = extractor.extract_all_links(content)

    links = [
        LinkInfo(
            url=link.url,
            lineno=link.line_no,
            col_start=link.col_start,
            match_text=link.raw_text,
        )
        for link in extracted
        if link.node_type != "ref_def" and not link.suppressed
    ] + extract_ref_links(content, ref_map)

    return _ValidationPayload(
        file_path=md_file,
        anchors=anchors_in_file(content),
        links=links,
        source_lines=content.splitlines(),
    )


# ─── Pure / I/O-agnostic functions ────────────────────────────────────────────


def extract_links(text: str) -> list[LinkInfo]:
    """Extract ``[text](url)`` and ``![alt](url)`` links from raw Markdown.

    .. deprecated:: 0.26.1
       Use :meth:`PolyglotExtractor.extract_all_links` or :meth:`PolyglotExtractor.extract_inline_links` instead.

    Args:
        text: Raw markdown content.

    Returns:
        List of :class:`LinkInfo` with URL, line number, column, and match text.
    """
    extractor = PolyglotExtractor()
    inline_links = extractor.extract_inline_links(text)
    return [
        LinkInfo(
            url=link.url,
            lineno=link.line_no,
            col_start=link.col_start,
            match_text=link.raw_text,
        )
        for link in inline_links
    ]


def _extract_empty_link_texts(text: str) -> list[tuple[int, int, str]]:
    """Return empty-text Markdown links for Z108 detection.

    The helper skips fenced code blocks and inline code spans, mirroring the
    main link extractor, but only reports link syntaxes whose label is empty or
    whitespace-only. Images are intentionally excluded from this rule.
    """
    results: list[tuple[int, int, str]] = []
    in_block = False

    for lineno, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        if not in_block:
            if stripped.startswith("```") or stripped.startswith("~~~"):
                in_block = True
                continue
        else:
            if stripped.startswith("```") or stripped.startswith("~~~"):
                in_block = False
            continue

        if "[" not in line:
            continue

        clean = _INLINE_CODE_RE.sub(lambda m: " " * len(m.group()), line)
        for pattern in (_EMPTY_INLINE_LINK_TEXT_RE, _EMPTY_REF_LINK_TEXT_RE):
            for m in pattern.finditer(clean):
                # Skip image links (![](url)); those are covered by Z403.
                if m.start() > 0 and clean[m.start() - 1] == "!":
                    continue
                # Only report if the bracket is also empty in the original line.
                # This prevents false positives from labels like [`code`][ref]
                # whose inline code was stripped to spaces by the cleaner above.
                if not pattern.match(line[m.start() :]):
                    continue
                results.append((lineno, m.start(), line.strip()))

    return results


def slug_heading(heading: str) -> str:
    """Convert heading text to a URL-safe anchor slug (GitHub / MkDocs compatible).

    Handles MkDocs Material explicit anchor syntax (``{ #custom-id }``) and
    strips HTML tags (e.g. ``<small>``) before slugification.

    Resolution order:
    1. If the heading contains ``{ #custom-id }``, return ``custom-id`` directly.
    2. Otherwise strip HTML tags, lowercase, apply NFKD Unicode normalisation to
       decompose accented characters (e.g. ``à`` → ``a`` + combining grave), drop
       all combining/non-ASCII characters, then drop remaining non-word characters
       (keeping hyphens) and collapse whitespace into single hyphens — matching
       the behaviour of Python-Markdown's ``toc`` extension and GitHub heading IDs.

    Args:
        heading: Raw heading text without leading ``#`` characters.

    Returns:
        Lowercase hyphenated anchor slug (e.g. ``'quick-start'``).
    """
    import unicodedata

    explicit = _EXPLICIT_ANCHOR_RE.search(heading)
    if explicit:
        return explicit.group(1).lower()
    heading_clean = _ATTR_LIST_RE.sub("", heading).strip()
    slug = _HTML_TAG_RE.sub("", heading_clean).strip()
    # Decompose accented characters and drop combining marks so that e.g.
    # "Integrità" → "integrita" (matching MkDocs toc extension behaviour).
    # Lowercase AFTER NFKD so that mathematical/styled Unicode codepoints
    # (e.g. U+1D400 𝐀 → A) are correctly lowered.
    slug = unicodedata.normalize("NFKD", slug)
    slug = "".join(c for c in slug if not unicodedata.combining(c))
    slug = slug.lower()
    slug = _SLUG_NONWORD_RE.sub("", slug)
    slug = _SLUG_SPACES_RE.sub("-", slug).strip("-")
    return slug


def anchors_in_file(content: str) -> set[str]:
    """Return anchor slugs for every ATX heading and custom/footnote anchor in *content*.

    Recognises MkDocs Material explicit anchors (``{ #id }``), block-level custom ID
    anchors, footnote targets, and strips HTML tags from heading text before slugification.

    Args:
        content: Raw markdown content (no I/O).

    Returns:
        Set of lowercase anchor slugs, e.g. ``{'introduction', 'quick-start'}``.
    """
    anchors: set[str] = set()
    # 1. Extract heading slugs
    for m in _HEADING_RE.finditer(content):
        anchors.add(slug_heading(m.group(1)))

    # 2. Extract block-level explicit anchors & footnote anchors (skipping code blocks)
    in_block = False
    for line in content.splitlines():
        stripped = line.strip()
        if not in_block:
            if stripped.startswith("```") or stripped.startswith("~~~"):
                in_block = True
                continue
            # Remove inline code spans to avoid false positives inside backticks
            clean_line = _INLINE_CODE_RE.sub("", line)
            # Search for explicit inline/block anchors { #id }
            for m in _EXPLICIT_ANCHOR_RE.finditer(clean_line):
                anchors.add(m.group(1).lower())
            # Search for footnote definitions [^label]:
            fn_match = _FN_DEF_RE.match(clean_line)
            if fn_match:
                label = fn_match.group(1).strip()
                anchors.add(f"fn:{label}")
            # Search for HTML inline anchors: id="..." inside tags
            for m in _HTML_ID_RE.finditer(clean_line):
                anchors.add(m.group(1).lower())
        else:
            if stripped.startswith("```") or stripped.startswith("~~~"):
                in_block = False
    return anchors


# ─── Reference link pure helpers (S4-4) ──────────────────────────────────────


def _build_ref_map(text: str) -> dict[str, str]:
    """Extract link reference definitions from markdown content.  No I/O.

    Skips fenced code blocks so that reference definitions inside example
    code are never collected.  First-definition-wins per CommonMark §4.7.
    Reference IDs are lowercased for case-insensitive lookup.

    Args:
        text: Raw markdown content.

    Returns:
        Mapping of lowercase-normalised reference IDs to their URL targets.
    """
    ref_map: dict[str, str] = {}
    in_block = False
    for line in text.splitlines():
        stripped = line.strip()
        if not in_block:
            if stripped.startswith("```") or stripped.startswith("~~~"):
                in_block = True
                continue
            m = _REF_DEF_RE.match(line)
            if m:
                label = m.group(1)
                if label.startswith("^"):
                    continue
                norm_id = label.lower().strip()
                if norm_id not in ref_map:  # first-definition-wins
                    ref_map[norm_id] = m.group(2)
        else:
            if stripped.startswith("```") or stripped.startswith("~~~"):
                in_block = False
    return ref_map


def extract_ref_links(text: str, ref_map: dict[str, str]) -> list[LinkInfo]:
    """Resolve reference-style links against *ref_map* and return :class:`LinkInfo` items.

    Handles ``[text][id]`` and collapsed ``[text][]`` syntax.  Skips fenced
    code blocks and inline code spans.  Only links whose normalised ID appears
    in *ref_map* are returned — undefined IDs are the responsibility of
    :class:`~zenzic.core.scanner.ReferenceScanner`.

    Reference IDs are compared case-insensitively per CommonMark §4.7.

    Args:
        text: Raw markdown content.
        ref_map: Mapping returned by :func:`_build_ref_map` (lowercase IDs).

    Returns:
        List of :class:`LinkInfo` with resolved URLs and source positions.
    """
    results: list[LinkInfo] = []
    in_block = False
    for lineno, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        if not in_block:
            if stripped.startswith("```") or stripped.startswith("~~~"):
                in_block = True
                continue
        else:
            if stripped.startswith("```") or stripped.startswith("~~~"):
                in_block = False
            continue
        clean = _INLINE_CODE_RE.sub(lambda m: " " * len(m.group()), line)
        for m in _REF_LINK_RE.finditer(clean):
            text_part = m.group(1)
            raw_id = m.group(2) if m.group(2) else text_part
            ref_id = raw_id.lower().strip()
            if not ref_id:
                continue
            url = ref_map.get(ref_id)
            if url:
                results.append(
                    LinkInfo(
                        url=url,
                        lineno=lineno,
                        col_start=m.start(),
                        match_text=m.group(0),
                    )
                )
        # Shortcut reference links: [text] (CommonMark §4.7)
        for m in _REF_SHORTCUT_RE.finditer(clean):
            if m.start() > 0 and clean[m.start() - 1] in "!]":
                continue
            tail = clean[m.end() : m.end() + 1]
            if tail in "[:(":
                continue
            ref_id = m.group(1).lower().strip()
            url = ref_map.get(ref_id)
            if url:
                results.append(
                    LinkInfo(
                        url=url,
                        lineno=lineno,
                        col_start=m.start(),
                        match_text=m.group(0),
                    )
                )
    return results


# ─── Async I/O helpers ────────────────────────────────────────────────────────


async def _ping_url(
    client: httpx.AsyncClient, url: str, cache: dict[str, Any], timestamp: float
) -> str | None:
    """HEAD-ping a single URL; returns an error string or ``None`` if reachable.

    Falls back to GET when the server returns 405 Method Not Allowed.
    Treats HTTP 401 / 403 / 429 as "alive" — the server is responding but
    restricting access, which is common for GitHub, StackOverflow, etc.
    """
    try:
        response = await client.head(url)
        if response.status_code == 405:
            async with client.stream("GET", url) as stream_resp:
                if stream_resp.status_code in (401, 403, 429):
                    cache[url] = {"status": 200, "timestamp": timestamp}
                    return None
                if stream_resp.status_code >= 400:
                    return f"external link '{url}' returned HTTP {stream_resp.status_code}"
                cache[url] = {"status": 200, "timestamp": timestamp}
                return None

        if response.status_code in (401, 403, 429):
            cache[url] = {"status": 200, "timestamp": timestamp}
            return None
        if response.status_code >= 400:
            return f"external link '{url}' returned HTTP {response.status_code}"

        cache[url] = {"status": 200, "timestamp": timestamp}
        return None
    except httpx.TimeoutException:
        return f"external link '{url}' timed out (>10 s)"
    except httpx.RequestError as exc:
        return f"external link '{url}' — connection error: {exc}"


async def _check_external_links(
    entries: list[tuple[str, str, int]],
    config: ZenzicConfig,
    repo_root: Path,
    *,
    progress_callback: Any | None = None,
) -> list[str]:
    """Concurrently validate a batch of external URLs.

    Deduplicates URLs so each is pinged exactly once, then maps any error back
    to every ``(file_label, lineno)`` pair that referenced that URL.
    """
    if not entries:
        return []

    excluded = [
        p.strip() for p in (getattr(config, "excluded_external_urls", None) or []) if p.strip()
    ]
    global_tracker = getattr(config, "_global_tracker", None)

    # Deduplicate: url → list[(label, lineno)]
    url_occurrences: dict[str, list[tuple[str, int]]] = {}
    for url, label, lineno in entries:
        # Defense-in-depth: skip excluded external URLs even if not pre-filtered by caller
        is_excluded = False
        for prefix in excluded:
            if url.startswith(prefix):
                is_excluded = True
                if global_tracker:
                    global_tracker.mark_excluded_external_url_used(prefix)
                break
        if is_excluded:
            continue
        url_occurrences.setdefault(url, []).append((label, lineno))

    cache_file = repo_root / ".zenzic_cache" / "external_links.json"
    cache: dict[str, Any] = {}
    if config.network.cache_ttl_hours > 0:
        try:
            if cache_file.is_file():
                with cache_file.open("r", encoding="utf-8") as f:
                    cache = json.load(f)
        except Exception:
            cache = {}

    current_time = time.time()
    ttl_seconds = config.network.cache_ttl_hours * 3600
    urls_to_check: list[str] = []

    for url in url_occurrences:
        if config.network.cache_ttl_hours > 0 and url in cache:
            entry = cache[url]
            if isinstance(entry, dict) and "timestamp" in entry and "status" in entry:
                if current_time - entry["timestamp"] < ttl_seconds and entry["status"] == 200:
                    if progress_callback:
                        progress_callback()
                    continue  # Valid and fresh
        urls_to_check.append(url)

    headers = {
        "User-Agent": (
            "Zenzic-Document-Integrity-Engine/0.1.0 (+https://github.com/PythonWoods/zenzic)"
        ),
        "Accept": "text/html,application/xhtml+xml,*/*",
    }

    semaphore = asyncio.Semaphore(_MAX_CONCURRENT_REQUESTS)

    async def _bounded_ping(client: httpx.AsyncClient, url: str) -> str | None:
        async with semaphore:
            res = await _ping_url(client, url, cache, current_time)
            if progress_callback:
                progress_callback()
            return res

    errors: list[str] = []
    if urls_to_check:
        async with httpx.AsyncClient(
            follow_redirects=True,
            timeout=10.0,
            headers=headers,
        ) as client:
            results = await asyncio.gather(
                *(_bounded_ping(client, u) for u in urls_to_check),
                return_exceptions=True,
            )

            for url, result in zip(urls_to_check, results, strict=True):
                if result is None:
                    continue
                msg = str(result) if isinstance(result, Exception) else result
                for label, lineno in url_occurrences[url]:
                    errors.append(f"{label}:{lineno}: {msg}")

        if config.network.cache_ttl_hours > 0:
            with contextlib.suppress(Exception):
                cache_file.parent.mkdir(parents=True, exist_ok=True)
                temp_file = cache_file.with_suffix(".tmp")
                with temp_file.open("w", encoding="utf-8") as f:
                    json.dump(cache, f)
                temp_file.replace(cache_file)

    return sorted(errors)


def generate_virtual_site_map(
    docs_root: Path,
    docs_structure: str,
    exclusion_manager: LayeredExclusionManager,
) -> frozenset[str]:
    """Project the set of URL paths the build engine will generate.

    Uses :func:`walk_files` instead of ``rglob`` to respect system guardrails
    and the full 4-level Layered Exclusion model.

    Args:
        docs_root: Path to the ``docs/`` directory.
        docs_structure: Value of ``docs_structure`` from the i18n plugin config.
        exclusion_manager: Layered Exclusion Manager for directory pruning.

    Returns:
        Frozenset of URL path strings (e.g. ``{"/", "/checks.it/", ...}``).
    """
    from zenzic.models.config import SYSTEM_EXCLUDED_DIRS

    urls: set[str] = set()
    if not docs_root.is_dir():
        return frozenset()
    for md_file in walk_files(docs_root, SYSTEM_EXCLUDED_DIRS, exclusion_manager):
        if md_file.suffix not in DOC_SUFFIXES or md_file.is_symlink():
            continue
        rel = md_file.relative_to(docs_root)
        stem = rel.with_suffix("")
        parts = list(stem.parts)
        if not parts:
            continue
        if parts[-1] == "index":
            parts = parts[:-1]
        if not parts:
            urls.add("/")
        else:
            urls.add("/" + "/".join(parts) + "/")
    return frozenset(urls)


def check_nav_contract(
    repo_root: Path,
    exclusion_manager: LayeredExclusionManager,
) -> list[str]:
    """Validate ``extra.alternate`` links against the Virtual Site Map.

    Loads ``mkdocs.yml``, projects the full set of URLs the build engine will
    generate via :func:`generate_virtual_site_map`, then checks that every
    ``extra.alternate`` link resolves to a URL that exists in that map.

    No heuristics, no regex on URL patterns.  If a link is not in the VSM,
    it is a 404 — regardless of *why* the author wrote it.

    Args:
        repo_root: Repository root directory.

    Returns:
        List of human-readable error strings (empty = no violations).
    """
    from zenzic.core.adapter import find_config_file

    errors: list[str] = []
    config_file = find_config_file(repo_root)
    if config_file is None:
        return errors
    with config_file.open(encoding="utf-8") as f:
        try:
            doc_config: dict[str, Any] = (
                yaml.load(f, Loader=_PermissiveSafeLoader) or {}  # noqa: S506  # SafeLoader subclass
            )
        except yaml.YAMLError:
            return errors

    # ── Extract docs_structure ────────────────────────────────────────────────
    docs_structure: str = "suffix"  # default assumption
    plugins = doc_config.get("plugins", [])
    if isinstance(plugins, list):
        for plugin in plugins:
            if not isinstance(plugin, dict):
                continue
            i18n = plugin.get("i18n")
            if not isinstance(i18n, dict):
                continue
            docs_structure = i18n.get("docs_structure", "suffix")
            break

    # ── Build the Virtual Site Map ────────────────────────────────────────────
    docs_dir = doc_config.get("docs_dir", "docs")
    docs_root_path = repo_root / docs_dir
    vsm = generate_virtual_site_map(docs_root_path, docs_structure, exclusion_manager)

    # ── Validate every extra.alternate link against the VSM ──────────────────
    extra = doc_config.get("extra") or {}
    alternate = extra.get("alternate", []) if isinstance(extra, dict) else []
    if not isinstance(alternate, list):
        return errors

    for entry in alternate:
        if not isinstance(entry, dict):
            continue
        link: str = entry.get("link", "")
        lang: str = entry.get("lang", "")
        if not link:
            continue
        # Normalise: ensure trailing slash for directory-style URLs
        normalised = link if link.endswith("/") else link + "/"
        if normalised not in vsm:
            errors.append(
                f"mkdocs.yml extra.alternate[{lang}]: link '{link}' does not "
                f"correspond to any URL the build engine will generate. "
                f"The Virtual Site Map contains no entry for '{normalised}'. "
                f"Use a path that maps to an existing source file "
                f"(e.g. '/index.{lang}/' for the {lang} home page)."
            )
    return errors


def validate_links_structured(
    docs_root: Path,
    exclusion_manager: LayeredExclusionManager,
    *,
    repo_root: Path,
    config: ZenzicConfig,
    strict: bool = False,
    locale_roots: list[tuple[Path, str]] | None = None,
    check_external: bool = True,
    trackers: dict[Path, SuppressionTracker] | None = None,
    reports: list[IntegrityReport] | None = None,
    ext_errors: list[str] | None = None,
) -> list[LinkError]:
    """Unified link validation entry point using scan_docs_references and URP rules."""
    from zenzic.core.adapters import get_adapter
    from zenzic.core.scanner import scan_docs_references

    if reports is None:
        if locale_roots is None:
            adapter = get_adapter(config.build_context, docs_root, repo_root)
            locale_roots = adapter.get_locale_source_roots(repo_root)

        reports, ext_errors = scan_docs_references(
            docs_root,
            exclusion_manager,
            repo_root=repo_root,
            config=config,
            validate_links=strict and check_external,
            locale_roots=locale_roots,
        )
    elif ext_errors is None:
        ext_errors = []

    link_errors: list[LinkError] = []
    link_codes = {
        "Z101",
        "Z102",
        "Z103",
        "Z104",
        "Z105",
        "Z106",
        "Z108",
        "Z110",
        "Z620",
        "Z120",
        "Z121",
        "Z122",
        "Z123",
        "Z124",
        "Z202",
        "Z203",
        "Z205",
    }

    for report in reports:
        for rf in report.rule_findings:
            if rf.rule_id in link_codes:
                link_errors.append(
                    LinkError(
                        file_path=rf.file_path,
                        line_no=rf.line_no,
                        message=rf.message,
                        source_line=rf.matched_line,
                        error_type=rf.rule_id,
                        col_start=rf.col_start,
                        match_text=rf.match_text,
                    )
                )

    for ext_msg in ext_errors:
        link_errors.append(
            LinkError(
                file_path=docs_root,
                line_no=0,
                message=ext_msg,
                source_line="",
                error_type="Z101",
            )
        )
    return link_errors


def validate_links(
    docs_root: Path,
    exclusion_manager: LayeredExclusionManager,
    *,
    repo_root: Path,
    config: ZenzicConfig,
    strict: bool = False,
    check_external: bool = True,
) -> list[str]:
    """Synchronous wrapper returning flat error messages."""
    errors = validate_links_structured(
        docs_root,
        exclusion_manager,
        repo_root=repo_root,
        config=config,
        strict=strict,
        check_external=check_external,
    )
    return sorted([str(e) for e in errors])


# ─── Decoupled URP for Language Server (In-Memory) ────────────────────────────
# Removed: Graph topology is the only source of truth. No single-file bypasses.


# ─── Multi-language snippet validation ────────────────────────────────────────

_VALIDATABLE_LANGS = frozenset({"python", "py", "yaml", "yml", "json", "toml"})


def _extract_code_blocks(text: str) -> list[tuple[str, str, int]]:
    """Return (lang, snippet, fence_line_no) triples for every validatable fenced block.

    Only blocks whose language tag is in ``_VALIDATABLE_LANGS`` are returned.
    Uses a deterministic line-by-line state machine rather than a regex so that
    inline triple-backtick code spans (e.g. `` ` ```python ` ``) cannot cause
    the matcher to run away across the rest of the file.

    *fence_line_no* is the 1-based line number of the opening fence.  The closing
    fence must be a line whose stripped content is exactly three or more backticks
    (per CommonMark §4.5).
    """
    blocks: list[tuple[str, str, int]] = []
    in_block = False
    current_lang = ""
    block_lines: list[str] = []
    fence_line_no = 0

    for lineno, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        if not in_block:
            if stripped.startswith("```"):
                info = stripped[3:].strip()
                lang = info.split()[0].lower() if info else ""
                if lang in _VALIDATABLE_LANGS:
                    in_block = True
                    current_lang = lang
                    block_lines = []
                    fence_line_no = lineno
        else:
            # Closing fence: line is only backtick characters (at least 3)
            if stripped.startswith("```") and not stripped.lstrip("`"):
                blocks.append((current_lang, "\n".join(block_lines), fence_line_no))
                in_block = False
                block_lines = []
            else:
                block_lines.append(line)

    return blocks


def check_snippet_content(
    text: str,
    file_path: Path | str,
    config: ZenzicConfig | None = None,
) -> list[SnippetError]:
    """Pure function: validate fenced code blocks in text using pure-Python parsers. No I/O.

    Supported languages:

    - **Python** (``python``, ``py``) — ``compile()`` in ``exec`` mode
    - **YAML** (``yaml``, ``yml``) — ``yaml.safe_load()``
    - **JSON** (``json``) — ``json.loads()``
    - **TOML** (``toml``) — ``tomllib.loads()``

    Args:
        text: Raw markdown content to analyse.
        file_path: Path identifier used to label errors (no disk access).
        config: Optional Zenzic configuration.

    Returns:
        List of SnippetError instances for each invalid code block.
    """
    if config is None:
        config = ZenzicConfig()

    path = Path(file_path)
    errors: list[SnippetError] = []

    for lang, snippet, fence_line in _extract_code_blocks(text):
        lines = snippet.splitlines()
        cleaned_lines = ["" if _HIGHLIGHT_COMMENT_RE.match(line) else line for line in lines]
        snippet = "\n".join(cleaned_lines)

        if len(snippet.strip().splitlines()) < config.snippet_min_lines:
            continue

        snippet = textwrap.dedent(snippet)  # Remove common leading whitespace for accurate parsing

        if lang in ("python", "py"):
            try:
                compile(snippet, str(path), "exec")
            except SyntaxError as exc:
                errors.append(
                    SnippetError(
                        file_path=path,
                        line_no=fence_line + (exc.lineno or 1),
                        message=f"SyntaxError in Python snippet — {exc.msg}",
                    )
                )
            except Exception as exc:
                errors.append(
                    SnippetError(
                        file_path=path,
                        line_no=fence_line + 1,
                        message=f"ParserError in Python snippet — {type(exc).__name__}: {exc}",
                    )
                )

        elif lang in ("yaml", "yml"):
            try:
                list(yaml.load_all(snippet, Loader=_PermissiveSafeLoader))
            except yaml.YAMLError as exc:
                mark = getattr(exc, "problem_mark", None)
                offset = (mark.line + 1) if mark is not None else 1
                errors.append(
                    SnippetError(
                        file_path=path,
                        line_no=fence_line + offset,
                        message=f"SyntaxError in YAML snippet — {exc}",
                    )
                )

        elif lang == "json":
            try:
                json.loads(snippet)
            except json.JSONDecodeError as exc:
                errors.append(
                    SnippetError(
                        file_path=path,
                        line_no=fence_line + exc.lineno,
                        message=f"SyntaxError in JSON snippet — {exc.msg}",
                    )
                )

        elif lang == "toml":
            try:
                tomllib.loads(snippet)
            except tomllib.TOMLDecodeError as exc:
                errors.append(
                    SnippetError(
                        file_path=path,
                        line_no=fence_line + 1,
                        message=f"SyntaxError in TOML snippet — {exc}",
                    )
                )

    return errors


# ─── Global reference-URL validator ──────────────────────────────────────────


class LinkValidator:
    """Cross-file URL deduplicator and async validator for reference definitions.

    Collects URLs registered from multiple :class:`~zenzic.models.references.ReferenceMap`
    instances and validates each *unique* URL exactly once via concurrent HEAD
    requests.  This guarantees that even if 50 docs all reference
    ``https://github.com``, only one HTTP ping is issued per session.

    Rate limiting is handled by a shared asyncio semaphore (inherited from
    ``_check_external_links``).  HTTP 429 and 401/403 responses are treated as
    "alive" to avoid false positives from access-restricted servers.

    Usage::

        validator = LinkValidator()

        # Register from each file's ReferenceMap after Pass 1
        for report_scanner in scanners:
            validator.register_from_map(report_scanner.ref_map, report_scanner.file_path)

        # One async pass — each unique URL pinged exactly once
        errors = validator.validate()

    Attributes:
        _registrations: Mapping of URL to the list of ``(file_path, line_no)``
            pairs that reference it.  The list enables accurate error attribution
            when multiple files define the same URL.
    """

    def __init__(self, config: ZenzicConfig, repo_root: Path) -> None:
        self._config = config
        self._repo_root = repo_root
        # url → [(file_path, line_no), ...]  — deduplication key is the URL
        self._registrations: dict[str, list[tuple[Path, int]]] = {}

    def register(self, url: str, source: Path, line_no: int) -> None:
        """Register a single external URL for validation.

        Only ``http://`` and ``https://`` URLs are accepted; all others are
        silently ignored so callers do not need to pre-filter.

        Args:
            url: The raw URL string from the reference definition.
            source: Path to the file that contains the definition.
            line_no: 1-based line number of the definition.
        """
        if not url.startswith(("http://", "https://")):
            return
        # ── Z620 exclusion tracking ──────────────────────────────────────────────
        # If the URL matches a prefix declared in excluded_external_urls, mark the
        # exclusion as "used" on the GlobalUsageTracker so it is not later flagged
        # as stale (Z620), and skip HTTP validation for this URL.
        # This mirrors the identical filter that validate_links_async used to apply
        # before the URP unification removed that code path.
        excluded = [
            p.strip()
            for p in (getattr(self._config, "excluded_external_urls", None) or [])
            if p.strip()
        ]
        if excluded:
            global_tracker = getattr(self._config, "_global_tracker", None)
            for prefix in excluded:
                if url.startswith(prefix):
                    if global_tracker:
                        global_tracker.mark_excluded_external_url_used(prefix)
                    return  # do not schedule for HTTP validation
        self._registrations.setdefault(url, []).append((source, line_no))

    def register_from_map(self, ref_map: ReferenceMap, file_path: Path) -> None:
        """Register all HTTP/HTTPS URLs found in a :class:`ReferenceMap`.

        Iterates over every *accepted* definition in the map (first-wins entries
        only) and delegates to :meth:`register`.

        Args:
            ref_map: Fully-populated ReferenceMap from Pass 1.
            file_path: Source file that owns this map (used for error labels).
        """
        for _norm_id, (url, line_no) in ref_map.definitions.items():
            self.register(url, file_path, line_no)

    @property
    def unique_url_count(self) -> int:
        """Number of distinct URLs scheduled for validation."""
        return len(self._registrations)

    async def validate_async(self, progress_callback: Any | None = None) -> list[str]:
        """Ping every registered URL exactly once and return error strings.

        Delegates to :func:`_check_external_links` which:
        - Enforces the semaphore cap (``_MAX_CONCURRENT_REQUESTS = 20``)
        - Falls back from HEAD to GET on 405 responses
        - Treats 401/403/429 as alive (access-restricted, not broken)
        - Maps each URL error back to *all* files that referenced it

        Returns:
            Sorted list of ``"file:lineno: <error message>"`` strings.
            Empty list when all URLs are reachable.
        """
        if not self._registrations:
            return []

        entries: list[tuple[str, str, int]] = [
            (url, str(occurrences[0][0]), occurrences[0][1])
            for url, occurrences in self._registrations.items()
        ]
        return await _check_external_links(
            entries, self._config, self._repo_root, progress_callback=progress_callback
        )

    def validate(self, progress_callback: Any | None = None) -> list[str]:
        """Synchronous wrapper around :meth:`validate_async`.

        Returns:
            Sorted list of error strings (empty when all URLs pass).
        """
        return asyncio.run(self.validate_async(progress_callback=progress_callback))


# ─── CLI / I/O wrappers ───────────────────────────────────────────────────────


def validate_snippets(
    docs_root: Path,
    exclusion_manager: LayeredExclusionManager,
    *,
    config: ZenzicConfig,
    md_contents: Mapping[Path, str] | None = None,
) -> list[SnippetError]:
    """Validate every fenced code block (Python, YAML, JSON, TOML) in docs.

    Args:
        docs_root: Resolved path to the documentation root.
        exclusion_manager: Layered exclusion manager (mandatory).
        config: Zenzic configuration model.
        md_contents: Optional pre-loaded mapping of Markdown file contents.

    Returns:
        List of SnippetError objects detailing the issues.
    """
    errors: list[SnippetError] = []

    if not docs_root.exists() or not docs_root.is_dir():
        return errors

    if md_contents is None:
        md_contents = getattr(config, "_md_contents", None)

    if md_contents is not None:
        for md_file, content in sorted(md_contents.items(), key=lambda x: x[0]):
            errors.extend(check_snippet_content(content, md_file, config))
        return errors

    for md_file in sorted(iter_markdown_sources(docs_root, config, exclusion_manager)):
        content = md_file.read_text(encoding="utf-8")
        errors.extend(check_snippet_content(content, md_file, config))

    return errors
