# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""Zenzic credential scanner: secret-detection engine integrated into the Pass 1 harvesting phase.

All functions are pure (no I/O). The credential scanner is intentionally "lazy but effective":
regex patterns are pre-compiled once at import time and applied line-by-line via
the generator pipeline, so secrets are flagged the moment a line is processed —
never after loading the full file.

Supported patterns
------------------
- OpenAI API key:       ``sk-[a-zA-Z0-9]{48}``
- GitHub token:         ``(?i)\b(?:ghp|gho|ghu|ghs|ghr)_[a-zA-Z0-9_.-]+\b``
- AWS access key:       ``AKIA[0-9A-Z]{16}``
- Stripe live key:      ``sk_live_[0-9a-zA-Z]{24}``
- Slack token:          ``xox[baprs]-[0-9a-zA-Z]{10,48}``
- Google API key:       ``AIza[0-9A-Za-z\\-_]{35}``
- Generic private key:  ``-----BEGIN [A-Z ]+ PRIVATE KEY-----``
- GitLab PAT:           ``glpat-[A-Za-z0-9\\-_]{20,}``

Exit code contract
------------------
Any secret detected **must** cause the CLI to exit with **code 2**.
The credential scanner itself returns findings; callers are responsible for the exit.
"""

from __future__ import annotations

import base64
import binascii
import html
import unicodedata
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

from zenzic.core import regex as re


# ─── Pre-scan Normalizer (ZRT-003: split-token bypass defence) ────────────────

# Unwrap inline code spans: `AKIA` → AKIA
_BACKTICK_INLINE_RE = re.compile(r"`([^`]*)`")
# Remove concatenation operators that split tokens: `AKIA` + `KEY` → AKIAKEY
_CONCAT_OP_RE = re.compile(r"[`'\"\s]*\+[`'\"\s]*")
# Replace table-cell separators with spaces
_TABLE_PIPE_RE = re.compile(r"\|")
# ZRT-007: strip HTML comments <!-- ... --> and MDX comments {/* ... */}
_HTML_COMMENT_RE = re.compile(r"<!--.*?-->")
_MDX_COMMENT_RE = re.compile(r"\{/\*.*?\*/\}")


def _normalize_line_for_scan(line: str) -> str:
    """Strip Markdown noise tokens to reconstruct secrets split by obfuscation.

    Applies three transformations in order:

    1. Unwrap backtick code spans — ``AKIA`` → ``AKIA``.
    2. Remove string-concatenation operators (`` ` `` + `` ` ``) that authors
       sometimes place between key fragments in documentation tables.
    3. Replace table-pipe separators with spaces and collapse whitespace.

    This allows the credential scanner to catch split-token patterns such as::

        | Key ID | `AKIA` + `1234567890ABCDEF` |

    while leaving detection of normal clean lines unaffected.

    Args:
        line: Raw text line from the Markdown source.

    Returns:
        Normalised string ready for regex scanning.
    """
    # ZRT-006 hardening: strip Unicode format characters (category Cf) that
    # can be inserted invisibly to break regex matches (zero-width joiners,
    # zero-width spaces, etc.).
    normalized = "".join(c for c in line if unicodedata.category(c) != "Cf")
    # ZRT-006 hardening: decode HTML character references (&#NNN; / &#xHH;)
    # that can obfuscate secret prefixes in Markdown/MDX prose.
    normalized = html.unescape(normalized)
    # ZRT-007 hardening: strip HTML/MDX comments that can interleave tokens
    # e.g. ghp_ABC{/* comment */}DEF or ghp_ABC<!-- comment -->DEF
    normalized = _HTML_COMMENT_RE.sub("", normalized)
    normalized = _MDX_COMMENT_RE.sub("", normalized)
    normalized = _BACKTICK_INLINE_RE.sub(r"\1", normalized)  # unwrap `...` spans
    normalized = _CONCAT_OP_RE.sub("", normalized)  # remove + concat ops
    normalized = _TABLE_PIPE_RE.sub(" ", normalized)  # collapse table pipes
    return " ".join(normalized.split())  # collapse whitespace


# ─── Pre-compiled secret signatures ───────────────────────────────────────────

_SECRETS: list[tuple[str, re.RegexPattern]] = [
    ("openai-api-key", re.compile(r"sk-[a-zA-Z0-9]{48}")),
    ("github-token", re.compile(r"(?i)\b(?:ghp|gho|ghu|ghs|ghr)_[a-zA-Z0-9_.-]+\b")),
    ("aws-access-key", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("stripe-live-key", re.compile(r"sk_live_[0-9a-zA-Z]{24}")),
    ("slack-token", re.compile(r"xox[baprs]-[0-9a-zA-Z]{10,48}")),
    ("google-api-key", re.compile(r"AIza[0-9A-Za-z\-_]{35}")),
    ("private-key", re.compile(r"-----BEGIN [A-Z ]+ PRIVATE KEY-----")),
    ("hex-encoded-payload", re.compile(r"(?:\\x[0-9a-fA-F]{2}){3,}")),
    ("gitlab-pat", re.compile(r"glpat-[A-Za-z0-9\-_]{20,}")),
]

#: Maximum line length the credential scanner will scan.  Lines exceeding this limit
#: are silently truncated before regex matching to prevent ReDoS or
#: excessive memory consumption from pathological input (F2-1 hardening).
_MAX_LINE_LENGTH: int = 1_048_576  # 1 MiB


# ─── Base64 speculative decoder (CEO-194 / D095) ─────────────────────────────
# Matches properly-padded Base64 tokens.  Length threshold (≥ 20 chars)
# ensures we skip strings too short to encode any known credential type.
_BASE64_CANDIDATE_RE: re.RegexPattern = re.compile(
    r"(?:[A-Za-z0-9+/]{4})+(?:[A-Za-z0-9+/]{2}==|[A-Za-z0-9+/]{3}=|[A-Za-z0-9+/]{4})"
)


def _try_decode_base64(token: str) -> str | None:
    """Attempt to base64-decode a candidate token.

    Uses ``validate=True`` to reject tokens that contain non-Base64 characters
    before decoding.  The decoded bytes are interpreted as UTF-8 so that text
    secrets (API keys, tokens) are recoverable even from binary-looking blobs.

    Args:
        token: A candidate string consisting only of Base64 alphabet characters.

    Returns:
        The decoded string when the token is valid Base64 and the result is
        non-empty; ``None`` otherwise.
    """
    try:
        decoded = base64.b64decode(token, validate=True)
        return decoded.decode("utf-8", errors="ignore") or None
    except (binascii.Error, ValueError):
        return None


# ─── Data classes ─────────────────────────────────────────────────────────────


@dataclass(slots=True)
class SecurityFinding:
    """A single secret detected by the credential scanner during Pass 1 harvesting.

    Attributes:
        file_path: Path to the file where the secret was found.
        line_no: 1-based line number of the offending line.
        secret_type: Human-readable label for the secret kind
            (e.g. ``"openai-api-key"``).
        url: The URL or text fragment in which the secret was embedded.
        col_start: 0-based column index of the match start in the raw line.
            Used by the reporter for surgical caret rendering.
        match_text: The matched secret substring (unredacted).
            The reporter is responsible for obfuscating this before display.
    """

    file_path: Path
    line_no: int
    secret_type: str
    url: str
    col_start: int = 0
    match_text: str = ""


# ─── Pure / I/O-agnostic functions ────────────────────────────────────────────


def scan_url_for_secrets(
    url: str,
    file_path: Path | str,
    line_no: int,
) -> Iterator[SecurityFinding]:
    """Scan a single URL string for known secret patterns.

    Called once per URL discovered during Pass 1 harvesting.  This keeps the
    detection responsibility inside the credential scanner module while the scanner drives
    the iteration.

    Args:
        url: The raw URL string extracted from a reference definition or inline link.
        file_path: Path identifier used to label findings (no disk access).
        line_no: 1-based line number where the URL appeared.

    Yields:
        :class:`SecurityFinding` for each secret pattern that matches.
    """
    path = Path(file_path)
    for secret_type, pattern in _SECRETS:
        m = pattern.search(url)
        if m:
            yield SecurityFinding(
                file_path=path,
                line_no=line_no,
                secret_type=secret_type,
                url=url,
                col_start=m.start(),
                match_text=m.group(0),
            )


def scan_line_for_secrets(
    line: str,
    file_path: Path | str,
    line_no: int,
) -> Iterator[SecurityFinding]:
    """Scan an arbitrary text line for known secret patterns.

    Used for defence-in-depth: even if a secret appears outside a URL (e.g. in
    link text or plain prose), the credential scanner will catch it.

    Two forms of the line are scanned:

    * **Raw** — the line exactly as it appears in the source, ensuring that
      normally-formatted secrets (e.g. in prose or frontmatter values) are
      always caught.
    * **Normalised** (ZRT-003 fix) — the line after stripping Markdown noise
      tokens (backtick spans, table pipes, concatenation operators) so that
      split-token obfuscation patterns are reconstructed before scanning.
      See :func:`_normalize_line_for_credential_scan`.

    Duplicate findings (same secret type on the same line whether matched by
    the raw or normalised form) are suppressed via a ``seen`` set.

    Args:
        line: Raw text line from the Markdown source.
        file_path: Path identifier (no disk access).
        line_no: 1-based line number.

    Yields:
        :class:`SecurityFinding` for each match found.
    """
    path = Path(file_path)
    # F2-1 hardening: truncate pathologically long lines to prevent ReDoS
    # or excessive memory consumption. The constant is defined above.
    line = line[:_MAX_LINE_LENGTH]
    normalized = _normalize_line_for_scan(line)
    seen: set[str] = set()

    for line_form in (line, normalized):
        for secret_type, pattern in _SECRETS:
            if secret_type in seen:
                continue
            m = pattern.search(line_form)
            if m:
                seen.add(secret_type)
                match_text = m.group(0)
                # Prefer col_start from the raw line; fall back to 0 when the
                # secret was only detected in the normalised form (col position
                # is meaningless after stripping Markdown noise).
                raw_m = pattern.search(line)
                yield SecurityFinding(
                    file_path=path,
                    line_no=line_no,
                    secret_type=secret_type,
                    url=line.strip(),  # always report the raw line for context
                    col_start=raw_m.start() if raw_m else 0,
                    match_text=match_text,
                )

    # ── Phase 3: Base64 speculative decoding (CEO-194) ────────────────────────
    # Extract candidate tokens from the normalised line, decode each, then
    # re-scan the decoded text through _SECRETS.  Catches credentials that
    # have been Base64-encoded to bypass the raw-text scan (e.g. a frontmatter
    # field containing base64(ghp_...) or base64(AKIA...)).
    for _b64_match in _BASE64_CANDIDATE_RE.finditer(normalized):
        _candidate = _b64_match.group(0)
        if len(_candidate) < 20:
            continue
        _decoded = _try_decode_base64(_candidate)
        if _decoded is None:
            continue
        for secret_type, pattern in _SECRETS:
            if secret_type in seen:
                continue
            m = pattern.search(_decoded)
            if m:
                seen.add(secret_type)
                yield SecurityFinding(
                    file_path=path,
                    line_no=line_no,
                    secret_type=secret_type,
                    url=line.strip(),
                    col_start=0,  # position in decoded text is meaningless in raw line
                    match_text=m.group(0),
                )


def scan_line_for_forbidden_terms(
    line: str,
    forbidden_patterns: list[str],
    file_path: Path | str,
    line_no: int,
    *,
    compiled_pattern: re.RegexPattern | None = None,
) -> Iterator[SecurityFinding]:
    """Scan a text line for project-specific forbidden terms (Z204).

    Performs a case-insensitive verbatim substring search against every entry
    in *forbidden_patterns*.  Patterns are matched literally — regular
    expressions are **not** supported.  The first matching term per line is
    reported; subsequent terms on the same line are skipped to avoid
    flooding the reporter with duplicate findings.

    When *compiled_pattern* is provided (the pre-compiled RE2 union regex built
    by :meth:`~zenzic.models.config.ZenzicConfig._recompile_forbidden_patterns`),
    the scan reduces from O(N_patterns) string searches per line to a single
    RE2 pass — O(1) regardless of how many forbidden terms are configured.

    Args:
        line: Raw text line from the Markdown source.
        forbidden_patterns: List of literal strings from ``.zenzic.local.toml``.
        file_path: Path identifier (no disk access).
        line_no: 1-based line number.
        compiled_pattern: Optional pre-compiled union regex.  When supplied the
            linear fallback loop is bypassed entirely.

    Yields:
        :class:`SecurityFinding` with ``secret_type="FORBIDDEN_TERM"`` for
        each line that matches at least one pattern.  At most one finding per
        line is yielded (first-match wins).
    """
    if not forbidden_patterns:
        return
    path = Path(file_path)

    # ── Fast path: single RE2 union pass (O(1) per line) ─────────────────────
    if compiled_pattern is not None:
        m = compiled_pattern.search(line)
        if m:
            yield SecurityFinding(
                file_path=path,
                line_no=line_no,
                secret_type="FORBIDDEN_TERM",  # noqa: S106  # Finding category identifier
                url=line.strip(),
                col_start=m.start(),
                match_text=m.group(0),
            )
        return

    # ── Fallback: linear scan (no pre-compiled pattern available) ────────────
    line_lower = line.lower()
    for term in forbidden_patterns:
        idx = line_lower.find(term.lower())
        if idx != -1:
            yield SecurityFinding(
                file_path=path,
                line_no=line_no,
                secret_type="FORBIDDEN_TERM",  # noqa: S106  # Finding category identifier
                url=line.strip(),
                col_start=idx,
                match_text=line[idx : idx + len(term)],
            )
            return  # one finding per line — first-match wins


def scan_lines_with_lookback(
    lines: Iterator[tuple[int, str]],
    file_path: Path | str,
) -> Iterator[SecurityFinding]:
    """Stateful scanner with a 1-line lookback buffer (ZRT-007).

    Scans each individual line *and* the concatenation of the previous line's
    tail with the current line's head.  This catches secrets that an author
    (or attacker) splits across two consecutive lines — e.g. a YAML folded
    scalar or a Markdown line break in the middle of a token.

    The lookback join is performed on **normalised** text (after comment
    stripping, backtick removal, etc.) so that cross-line obfuscation such as::

        api_key: >-
          AKIA
          IOSFODNN7EXAMPLE

    is reconstructed as ``AKIAIOSFODNN7EXAMPLE`` and matched.

    Only *new* secret types found in the joined form (not already found on the
    individual lines) are yielded, avoiding duplicate findings.

    Args:
        lines: Iterator of ``(line_no, raw_line)`` tuples — typically
            ``enumerate(file_handle, start=1)``.
        file_path: Path identifier (no disk access).

    Yields:
        :class:`SecurityFinding` for each match found.
    """
    path = Path(file_path)
    prev_normalized: str = ""
    prev_seen: set[str] = set()

    for lineno, raw_line in lines:
        # 1. Scan individual line (existing logic)
        seen_this_line: set[str] = set()
        for finding in scan_line_for_secrets(raw_line, file_path, lineno):
            seen_this_line.add(finding.secret_type)
            yield finding

        # 2. Lookback: join previous line tail + current line head (normalised)
        if prev_normalized:
            current_normalized = _normalize_line_for_scan(raw_line[:_MAX_LINE_LENGTH])
            # Take last 80 chars of prev + first 80 chars of current.
            # Secret patterns are at most ~50 chars; 80 gives generous margin.
            joined = prev_normalized[-80:] + current_normalized[:80]
            # Skip secrets already found on this line OR the previous line
            already_seen = seen_this_line | prev_seen
            for secret_type, pattern in _SECRETS:
                if secret_type in already_seen:
                    continue
                m = pattern.search(joined)
                if m:
                    yield SecurityFinding(
                        file_path=path,
                        line_no=lineno,
                        secret_type=secret_type,
                        url=raw_line.strip(),
                        col_start=0,
                        match_text=m.group(0),
                    )
                    seen_this_line.add(secret_type)

        # Rotate buffer
        prev_normalized = _normalize_line_for_scan(raw_line[:_MAX_LINE_LENGTH])
        prev_seen = seen_this_line


# ─── Credential Scanner as IO Middleware ──────────────────────────────────────────────────


class CredentialViolation(Exception):
    """Raised by ``safe_read_line()`` when a secret is detected during IO.

    This exception is **intentionally fatal** — it prevents the VSM from
    being constructed when a secret is found in the content that feeds the
    metadata extraction pipeline (e.g. frontmatter slug parsing).

    The caller (CLI layer) must catch this and exit with **code 2**.

    Attributes:
        finding: The :class:`SecurityFinding` that triggered the violation.
    """

    def __init__(self, finding: SecurityFinding) -> None:
        self.finding = finding
        super().__init__(
            f"CREDENTIAL VIOLATION: {finding.secret_type} detected in "
            f"{finding.file_path}:{finding.line_no}"
        )


def safe_read_line(
    line: str,
    file_path: Path | str,
    line_no: int,
) -> str:
    """Credential-scanner-guarded line reader — scans before returning.

    Invokes :func:`scan_line_for_secrets` on *line*.  If a secret is found,
    raises :class:`CredentialViolation` immediately — the line is never returned
    to the caller, preventing the secret from entering any parser (YAML,
    Markdown, Regex).

    This function is the **IO Middleware** mandated by the Tech Lead directive:
    every line read during metadata extraction (frontmatter for slug, tags,
    draft status) must pass through the credential scanner before any parser sees it.

    Args:
        line: Raw text line from the source file.
        file_path: Path identifier (for error reporting — no disk access).
        line_no: 1-based line number.

    Returns:
        The original *line* unchanged, if no secret is detected.

    Raises:
        :class:`CredentialViolation`: When any secret pattern matches.
    """
    for finding in scan_line_for_secrets(line, file_path, line_no):
        raise CredentialViolation(finding)
    return line
