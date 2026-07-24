# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""Zenzic configuration models and generator detection."""

from __future__ import annotations

import sys
from pathlib import Path


if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib  # PEP 680 backport
from typing import Any, Final, Literal

from pydantic import BaseModel, Field, PrivateAttr, field_validator

import zenzic.core.regex as re
from zenzic.core.regex import RegexPattern
from zenzic.core.ui import ZenzicPalette


# Severity type shared with the rule engine (avoids a circular import).
Severity = Literal["error", "warning", "info"]


class CustomRuleConfig(BaseModel):
    """A single entry in the ``[[custom_rules]]`` TOML array.

    Each entry declares a regex-based lint rule applied line-by-line to every
    Markdown file under ``docs/``.  The rule engine compiles the pattern once
    at config-load time.

    TOML example::

        [[custom_rules]]
        id = "ZZ-NOINTERNAL"
        pattern = "internal\\.corp\\.example\\.com"
        message = "Internal hostname must not appear in public docs."
        severity = "error"
    """

    id: str = Field(description="Stable unique identifier for this rule (e.g. 'ZZ-MY-RULE').")
    pattern: str = Field(description="Regular-expression string applied to each content line.")
    message: str = Field(description="Human-readable explanation shown in the finding.")
    severity: Severity = Field(
        default="error",
        description="Severity level: 'error' (default), 'warning', or 'info'.",
    )

    @field_validator("id", mode="before")
    @classmethod
    def _validate_id_namespace(cls, v: object) -> object:
        """Enforce ADR-012 namespace contract: custom rule IDs must start with 'ZZ-'.

        The 'ZZ-' prefix is reserved exclusively for user-defined custom rules
        to prevent collision with Core finding codes (Z1xx–Z9xx) in findings,
        SARIF reports, and CLI filters.
        """
        if not isinstance(v, str) or not v.startswith("ZZ-"):
            raise ValueError(
                f"Custom rule IDs must start with the 'ZZ-' prefix "
                f"(e.g., 'ZZ-MY-RULE') to prevent collision with Core finding codes (ADR-012). "
                f"Got: {v!r}"
            )
        return v


class ProjectMetadata(BaseModel):
    """Optional brand-integrity metadata declared in ``[project_metadata]``.

    When ``obsolete_names`` is non-empty, Zenzic activates the Z905
    BRAND_OBSOLESCENCE rule, which warns on every occurrence of a deprecated
    brand term found in documentation source files.  Lines carrying a
    ``zenzic:ignore`` comment are silently skipped so intentional historical
    references (e.g. in CHANGELOG files or ADR entries) are not flagged.
    Use ``<!-- zenzic:ignore: Z905 -->`` in ``.md`` files and
    ``{/* zenzic:ignore: Z905 */}`` in ``.mdx`` files.

    TOML example::

        [project_metadata]
        release_name = "MyRelease"
        obsolete_names = ["PreviousRelease"]
        # ADR files contain intentional historical references
        obsolete_names_exclude_patterns = [
            "CHANGELOG*.md",
            "community/developers/explanation/adr-*.mdx",
        ]
    """

    release_name: str = Field(
        default="",
        description="Current canonical brand/release name shown in Z905 remediation hints.",
    )
    # Deprecated in v0.8: canonical source moved to [governance].brand_obsolescence.
    # Kept for runtime compatibility while scanner migration is completed.
    obsolete_names: list[str] = Field(
        default=[],
        description="Deprecated legacy field; populated from [governance].brand_obsolescence.",
    )
    obsolete_names_exclude_patterns: list[str] = Field(
        default=["CHANGELOG*.md", "CHANGELOG*.archive.md"],
        description=(
            "Glob patterns (relative to docs_dir) for files excluded from Z905. "
            "CHANGELOG*.md is excluded by default to allow historical prose."
        ),
    )
    badge_stamp_files: list[str] = Field(
        default=["README.md"],
        description=(
            "Files updated by 'zenzic score --stamp'. Each file must contain a "
            "'<!-- zenzic:audit-badge -->' and/or '<!-- zenzic:score-badge -->' marker; "
            "the next non-empty line after each marker is replaced with deterministic "
            "audit and/or score badge URLs."
        ),
    )


class BuildContext(BaseModel):
    """Build engine context declared in ``[build_context]`` of ``.zenzic.toml``.

    Tells Zenzic which documentation engine produced the site and which locale
    directories are non-default translations.  Used by adapters to resolve
    asset and page paths correctly.
    """

    engine: Literal["prebuilt", "vsm", "mkdocs", "zensical", "standalone", "auto"] = Field(
        default="auto",
        description="The build engine used by the documentation. Can be 'mkdocs', 'zensical', 'standalone', or 'auto'.",
    )
    default_locale: str = Field(default="en", description="ISO 639-1 code of the default locale.")
    locales: list[str] = Field(
        default=[],
        description="Non-default locale directory names (e.g. ['it', 'fr']).",
    )
    base_url: str = Field(
        default="",
        description="The root URL where the documentation is hosted (e.g. `https://docs.pythonwoods.dev/`).",
    )
    fallback_to_default: bool = Field(
        default=True,
        description=(
            "When True, missing locale-tree assets/pages fall back to the "
            "default-locale tree. Set to False to report every missing locale file as an error."
        ),
    )
    offline_mode: bool = Field(
        default=False,
        description="When True, adapters force flat URL structure (e.g. use_directory_urls=False) for offline builds.",
    )


class GovernanceConfig(BaseModel):
    """Governance toggles declared in ``[governance]``.

    This section controls opt-in governance checks introduced in v0.8.
    """

    brand_obsolescence: list[str] = Field(
        default_factory=list,
        description=(
            "Deprecated brand terms that activate Z601 BRAND_OBSOLESCENCE "
            "when present in docs source."
        ),
    )
    per_file_ignores: dict[str, list[str]] = Field(
        default_factory=dict,
        description=(
            "Per-file suppression map (glob pattern -> finding codes). "
            "Example: {'blog/*.md': ['Z601']}. Security findings remain "
            "non-suppressible regardless of this map."
        ),
    )
    directory_policies: dict[str, list[str]] = Field(
        default_factory=dict,
        description=(
            "Strategic directory-level policy exemptions (glob pattern -> finding codes). "
            "Matched findings are removed before display with ZERO suppression debt cost. "
            "In --audit mode, exempted findings appear with a [POLICY_EXEMPTION] label. "
            "Intended for historical archives, SSOT registries, and blog directories. "
            "Security findings (Z201-Z204) bypass this exemption unconditionally."
        ),
    )
    suppression_cap: int = Field(
        default=30,
        ge=0,
        description=(
            "Maximum number of active suppressions allowed before hard-failing the check pipeline."
        ),
    )
    suppression_cap_scope: Literal["all"] = Field(
        default="all",
        description=(
            "Suppression CAP scope. 'all' counts inline suppressions plus "
            "per-file configuration suppressions."
        ),
    )
    suppression_cap_fail_hard: bool = Field(
        default=True,
        description=("When True, exceeding suppression_cap causes immediate exit 1."),
    )


class NetworkConfig(BaseModel):
    """Network I/O toggles declared in ``[network]``."""

    cache_ttl_hours: int = Field(
        default=24,
        description="Time-to-live for cached external links in hours.",
    )


# ── System Guardrails ────────────────────────────────────────────────────────
# Directories that Zenzic ALWAYS ignores.  These are merged into
# ``excluded_dirs`` unconditionally in ``model_post_init``.  User entries
# in ``.zenzic.toml`` are additive — they cannot remove these guardrails.
SYSTEM_EXCLUDED_DIRS: Final[frozenset[str]] = frozenset(
    {
        # VCS and CI/CD
        ".git",
        ".github",
        # Zenzic family dogfooding: sibling core checkout used by self-check CI
        # (ZRT-010 Sovereign Parity). Excluding at L1 eliminates the need for
        # every family repo to declare it in excluded_dirs.
        "_zenzic_core",
        ".zenzic_cache",
        # Virtual environments and package managers
        ".venv",
        "node_modules",
        # Build and cache directories
        ".nox",
        ".tox",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        ".hypothesis",
        # Universal build / temporary artefact directories (v0.7.0, Zero-Config)
        # Previously required users to declare these in `excluded_dirs` of
        # every standalone repo. Promoted to Layer 1 to honour Zero-Config:
        # any project that builds Python wheels, JS bundles, or runs mutation
        # tests should never need to repeat them in TOML.
        "build",
        "dist",
        "temp",
        ".temp",
        "tmp",
        "mutants",
    }
)

# ── System File Guardrails (L1a) ─────────────────────────────────────────────
# Files that Zenzic ALWAYS excludes from asset checks — universal development
# toolchain files that are never documentation content.  Adapters may declare
# additional files via ``BaseAdapter.get_metadata_files()`` (L1b).
SYSTEM_EXCLUDED_FILE_NAMES: Final[frozenset[str]] = frozenset(
    {
        # JavaScript / Node.js
        "package.json",
        "package-lock.json",
        "yarn.lock",
        "pnpm-lock.yaml",
        "tsconfig.json",
        "tsconfig.base.json",
        # Python
        "pyproject.toml",
        "poetry.lock",
        "uv.lock",
        "setup.cfg",
        "setup.py",
        "noxfile.py",
        # Generic toolchain
        "Makefile",
        "justfile",
        "Dockerfile",
        # Licensing & legal (Zero-Config v0.7.0 — never documentation assets)
        "LICENSE",
        "LICENSE.txt",
        "LICENSE.md",
        "NOTICE",
        "NOTICE.txt",
        "COPYING",
        # VCS / coverage / IDE artefacts that may slip into a docs root
        ".git",
        ".gitignore",
        ".gitattributes",
        ".coverage",
        "coverage.xml",
        # Zenzic native files — never documentation assets (ADR-039.1)
        ".zenzic.local.toml",
        # Action wrapper infrastructure file (explicit safeguard for docs_dir='.')
        "zenzic-action-wrapper.sh",
    }
)

SYSTEM_EXCLUDED_FILE_PATTERNS: Final[tuple[str, ...]] = (
    "eslint.config.*",
    ".prettierrc*",
    ".editorconfig",
    # Machine-local override backups must be treated as infrastructure.
    ".zenzic.local.toml.*",
    "*.lock",
    # Shell scripts are infrastructure, not documentation assets (ADR-039.1)
    "*.sh",
    # Project metadata / build manifests promoted to Layer 1 in v0.7.0.
    # Honours Zero-Config for "Prose-only Maintenance" repos (engine = standalone)
    # whose docs_root is the repository root: every TOML/YAML/JSON config file
    # was previously triggering Z405 unless individually declared.
    "*.toml",
    "*.yaml",
    "*.yml",
    "*.json",
    "*.cfg",
    "*.ini",
    "*.cff",
    "*.code-workspace",
)


class ZenzicConfig(BaseModel):
    _global_tracker: Any = PrivateAttr(default=None)
    """Configuration model for Zenzic, typically loaded from .zenzic.toml.

    **Hard Exclusion Policy:** The directories listed in
    :data:`SYSTEM_EXCLUDED_DIRS` are *always* excluded, regardless of what
    the user writes in ``excluded_dirs``.  User entries are additive.
    """

    docs_dir: Path = Field(
        default=Path("docs"), description="Path to docs directory relative to repo root."
    )
    excluded_dirs: list[str] = Field(
        default=["includes", "stylesheets", "overrides"],
        description=(
            "Directories inside docs/ to exclude from orphan and snippet checks. "
            "User-provided entries are merged with the system guardrails "
            "(SYSTEM_EXCLUDED_DIRS) — they can never be removed. "
        ),
    )
    snippet_min_lines: int = Field(
        default=1,
        description="Minimum lines for a code block to be checked (skip trivial one-liners).",
    )
    placeholder_max_words: int = Field(
        default=50,
        description="Pages with fewer than this many words are flagged as placeholders.",
    )
    placeholder_patterns: list[str] = Field(
        default=[
            r"\btodo\b",
            r"\bfixme\b",
            r"\bwip\b",
            r"\btbd\b",
        ],
        description=(
            "RE2-compatible regex patterns matched case-insensitively against each line. "
            "A match flags the page as Z501 PLACEHOLDER. "
            r"Use \b word boundaries to avoid substring false positives "
            r"(e.g. r'\bwip\b' matches 'WIP' but not 'wipe')."
        ),
    )
    excluded_assets: list[str] = Field(
        default=[],
        description=(
            "Asset paths (relative to docs_dir) excluded from the unused-assets check. "
            "Entries may be literal paths or glob patterns (fnmatch syntax: *, ?, []). "
            "Use this for files that are referenced by the build tool or theme templates "
            "rather than by Markdown pages. Ignores files that do not exist such as virtual indices."
        ),
    )
    excluded_asset_dirs: list[str] = Field(
        default=["overrides"],
        description=(
            "Directories inside docs/ whose non-markdown files are excluded from the "
            "unused-assets check. Use this for theme override directories whose files "
            "are consumed by the build tool rather than referenced from Markdown pages."
        ),
    )
    excluded_file_patterns: list[str] = Field(
        default=[],
        description=(
            "Filename glob patterns excluded from all checks (orphan detection, "
            "placeholder scanning, reference pipeline, and credential scanner). "
            "Use this for locale-suffixed files managed by i18n plugins "
            "(e.g. '*.it.md', '*.fr.md') or historical prose that contains "
            "intentional examples of secrets or deprecated syntax "
            "(e.g. 'CHANGELOG*.md')."
        ),
    )
    excluded_build_artifacts: list[str] = Field(
        default=[],
        description=(
            "Glob patterns (relative to docs_dir) for assets generated at build time. "
            "Links to paths matching these patterns are not flagged as broken even when "
            "the file does not exist on disk at lint time — e.g. PDFs produced by the "
            "to-pdf plugin or ZIP archives assembled by CI. "
            'Example: ["pdf/*.pdf", "assets/bundle.zip"]'
        ),
    )
    respect_vcs_ignore: bool = Field(
        default=True,
        description=(
            "When True (default), Zenzic reads .gitignore files from the "
            "repository root and docs directory and excludes matching paths "
            "from all checks. This aligns with industry-grade static analysis standards "
            "(Ruff, Ripgrep, Black, Prettier) where VCS-ignored paths are "
            "transparently excluded. Set to False only to override this "
            "behaviour explicitly. Forced inclusions (included_dirs, "
            "included_file_patterns) override VCS exclusions, but System "
            "Guardrails are always enforced."
        ),
    )
    included_dirs: list[str] = Field(
        default=[],
        description=(
            "Directory names inside docs/ that are forcefully included even when "
            "excluded by VCS ignore patterns or excluded_dirs. "
            "Forced inclusions cannot override System Guardrails (.git, .venv, etc.)."
        ),
    )
    included_file_patterns: list[str] = Field(
        default=[],
        description=(
            "Filename glob patterns (fnmatch syntax) forcefully included even when "
            "excluded by VCS ignore patterns or excluded_file_patterns. "
            "Use for build-generated documentation that should be linted despite "
            "being in .gitignore — e.g. 'api.generated.md'."
        ),
    )
    validate_same_page_anchors: bool = Field(
        default=True,
        description=(
            "When True, same-page anchor links (#section) are validated against the "
            "headings present in the source file. A link like [text](#missing) is "
            "reported as broken when no heading in the file produces that slug. "
            "Disabled by default because single-page anchor IDs can also be generated "
            "by HTML attributes, custom plugins, or build-time macros that are invisible "
            "at source-scan time."
        ),
    )
    excluded_external_urls: list[str] = Field(
        default=[],
        description=(
            "External URLs (or URL prefixes) excluded from the broken-link check. "
            "A URL is skipped when it starts with any entry in this list. "
            "Use this for URLs that are valid but not yet publicly reachable at lint time "
            "(e.g. a GitHub repo not yet created, an internal service behind a firewall). "
            'Example: ["https://github.com/PythonWoods/zenzic"]'
        ),
    )
    absolute_path_allowlist: list[str] = Field(
        default=[],
        description=(
            "List of absolute path prefixes allowed in links. "
            "Absolute path links matching any pattern in this list do not trigger Z105. "
            "If an entry in this list is never matched by any scanned absolute path link, "
            "it is reported as Z110 STALE_ALLOWLIST_ENTRY."
        ),
    )
    origin_file: Path | None = Field(
        default=None,
        exclude=True,
        description="Path to the file this configuration was loaded from.",
    )
    build_context: BuildContext = Field(
        default_factory=BuildContext,
        description="Build engine context for locale-aware path resolution.",
    )
    fail_under: int = Field(
        default=0,
        description=(
            "Minimum quality score (0–100). If the score falls below this value, "
            "zenzic score exits with code 1. 0 means no threshold (observational mode). "
            "The --fail-under CLI flag overrides this value when explicitly provided."
        ),
    )
    strict: bool = Field(
        default=False,
        description=(
            "When True, treat warnings as errors and validate external URLs via network "
            "requests. Equivalent to passing --strict on every check all / score / diff "
            "invocation. The --strict CLI flag overrides this value for a single run."
        ),
    )
    exit_zero: bool = Field(
        default=False,
        description=(
            "When True, zenzic check all always exits with code 0 even when issues are "
            "found. Issues are still printed and scored. Useful for observation-only "
            "pipelines where you want visibility without blocking. "
            "The --exit-zero CLI flag overrides this value for a single run."
        ),
    )
    custom_rules: list[CustomRuleConfig] = Field(
        default=[],
        description=(
            "Project-specific lint rules declared inline in .zenzic.toml.  "
            "Each entry applies a regex pattern line-by-line to every .md file.  "
            "Example:  [[custom_rules]]  id='ZZ001'  pattern='TODO'  "
            "message='Remove before publish.'  severity='warning'"
        ),
    )
    project_metadata: ProjectMetadata = Field(
        default_factory=ProjectMetadata,
        description=("Optional metadata used by remediation messaging and legacy compatibility."),
    )
    governance: GovernanceConfig = Field(
        default_factory=GovernanceConfig,
        description=(
            "Governance toggles for ADR-012 checks. Prefer this section over "
            "legacy [project_metadata].obsolete_names."
        ),
    )
    network: NetworkConfig = Field(
        default_factory=NetworkConfig,
        description="Network I/O settings for external link validation.",
    )
    plugins: list[str] = Field(
        default_factory=list,
        description=(
            "Explicit allow-list of external rule plugins to activate from the "
            "'zenzic.rules' entry-point group. Core rules shipped by Zenzic are "
            "always enabled."
        ),
    )
    forbidden_patterns: list[str] = Field(
        default=[],
        description=(
            "Z204 FORBIDDEN_TERM: literal strings (case-insensitive) whose presence "
            "in any documentation file triggers an exit-2 security breach. "
            "Populated by merging patterns from ``.zenzic.local.toml`` at runtime. "
            "Never declare these in the shared ``.zenzic.toml`` — use the git-ignored "
            "``.zenzic.local.toml`` so private terms are never committed."
        ),
    )
    # Pre-compiled regex patterns (not serializable, runtime only)
    placeholder_patterns_compiled: list[RegexPattern] = Field(
        default_factory=list,
        exclude=True,
        repr=False,
    )
    forbidden_patterns_compiled: RegexPattern | None = Field(
        default=None,
        exclude=True,
        repr=False,
    )

    def model_post_init(self, __context: Any) -> None:
        """Post-init: compile placeholders and enforce system exclusions."""
        self.placeholder_patterns_compiled = [
            re.compile(p, re.IGNORECASE) for p in self.placeholder_patterns
        ]
        self._recompile_forbidden_patterns()
        # Hard Exclusion Policy: system guardrails are always present.
        merged = list(dict.fromkeys([*self.excluded_dirs, *SYSTEM_EXCLUDED_DIRS]))
        self.excluded_dirs = merged

    def _recompile_forbidden_patterns(self) -> None:
        """Pre-compile forbidden_patterns into a single RE2 union regex (O(1) per line).

        Called by :meth:`model_post_init` and at the end of :meth:`_apply_local_toml`
        whenever ``forbidden_patterns`` is mutated.  Using a union pattern reduces the
        Z204 scan from O(N_lines × N_patterns) string searches to a single RE2 pass
        per line — O(N_lines).
        """
        if not self.forbidden_patterns:
            self.forbidden_patterns_compiled = None
            return
        union = "|".join(re.escape(p) for p in self.forbidden_patterns)
        self.forbidden_patterns_compiled = re.compile(f"(?:{union})", re.IGNORECASE)

    @classmethod
    def _build_from_data(cls, data: dict[str, Any]) -> ZenzicConfig:
        """Construct a ``ZenzicConfig`` from a raw TOML dict.

        Shared by :meth:`load` (``.zenzic.toml``) and the ``pyproject.toml``
        fallback path.  Strips unknown keys and promotes sub-tables.
        """
        import logging as _logging

        _cfg_log = _logging.getLogger("zenzic")
        known_fields = cls.model_fields.keys()
        # ── Warn on unrecognised TOML keys so users catch silent-discard bugs ──
        # The most common pitfall: writing root-level settings AFTER a [section]
        # header (e.g. `[project]`) causes TOML to nest them under that table,
        # which is then silently dropped because `project` is not a known field.
        _HANDLED_SECTIONS = frozenset(
            {"build_context", "custom_rules", "project_metadata", "governance", "i18n", "network"}
        )
        for key in data:
            if key not in known_fields and key not in _HANDLED_SECTIONS:
                if isinstance(data[key], dict):
                    _cfg_log.warning(
                        ".zenzic.toml: unknown section [%s] will be ignored — "
                        "all keys nested inside it are silently discarded. "
                        "Root-level settings (e.g. placeholder_patterns, docs_dir) "
                        "must appear BEFORE any [section] header.",
                        key,
                    )
                else:
                    _cfg_log.warning(
                        ".zenzic.toml: unknown key '%s' will be ignored.",
                        key,
                    )
        filtered_data = {k: v for k, v in data.items() if k in known_fields}
        if "build_context" in data and isinstance(data["build_context"], dict):
            filtered_data["build_context"] = BuildContext(
                **{k: v for k, v in data["build_context"].items() if k in BuildContext.model_fields}
            )
        if "custom_rules" in data and isinstance(data["custom_rules"], list):
            filtered_data["custom_rules"] = [
                CustomRuleConfig(
                    **{k: v for k, v in r.items() if k in CustomRuleConfig.model_fields}
                )
                for r in data["custom_rules"]
                if isinstance(r, dict)
            ]
        if "project_metadata" in data and isinstance(data["project_metadata"], dict):
            filtered_data["project_metadata"] = ProjectMetadata(
                **{
                    k: v
                    for k, v in data["project_metadata"].items()
                    if k in ProjectMetadata.model_fields and k != "obsolete_names"
                }
            )
        if "governance" in data and isinstance(data["governance"], dict):
            filtered_data["governance"] = GovernanceConfig(
                **{
                    k: v
                    for k, v in data["governance"].items()
                    if k in GovernanceConfig.model_fields
                }
            )
        if "network" in data and isinstance(data["network"], dict):
            filtered_data["network"] = NetworkConfig(
                **{k: v for k, v in data["network"].items() if k in NetworkConfig.model_fields}
            )

        # Legacy migration path (v0.8): [project_metadata].obsolete_names ->
        # [governance].brand_obsolescence.
        legacy_obsolete: list[str] = []
        if "project_metadata" in data and isinstance(data["project_metadata"], dict):
            raw_legacy = data["project_metadata"].get("obsolete_names", [])
            if isinstance(raw_legacy, list):
                legacy_obsolete = [name for name in raw_legacy if isinstance(name, str)]
        if legacy_obsolete:
            _cfg_log.warning(
                "Deprecated in v0.8: The '[project_metadata].obsolete_names' field is "
                "deprecated. Please move it to '[governance].brand_obsolescence'."
            )
            governance_cfg = filtered_data.get("governance", GovernanceConfig())
            if not governance_cfg.brand_obsolescence:
                governance_cfg.brand_obsolescence = legacy_obsolete
            filtered_data["governance"] = governance_cfg

        # Runtime compatibility bridge for current scanner wiring.
        governance_cfg = filtered_data.get("governance")
        if governance_cfg is not None and governance_cfg.brand_obsolescence:
            metadata_cfg = filtered_data.get("project_metadata", ProjectMetadata())
            metadata_cfg.obsolete_names = list(governance_cfg.brand_obsolescence)
            filtered_data["project_metadata"] = metadata_cfg
        return cls(**filtered_data)

    @staticmethod
    def _validate_no_swallowed_root_keys(data: dict[str, Any]) -> None:
        """Active Defense: intercept root keys swallowed by TOML tables."""
        root_keys = frozenset(
            {
                "docs_dir",
                "strict",
                "fail_under",
                "exit_zero",
                "respect_vcs_ignore",
                "validate_same_page_anchors",
                "excluded_external_urls",
                "forbidden_patterns",
                "excluded_dirs",
                "placeholder_patterns",
                "placeholder_max_words",
                "snippet_min_lines",
                "excluded_file_patterns",
                "excluded_assets",
                "excluded_asset_dirs",
                "excluded_build_artifacts",
                "included_dirs",
                "included_file_patterns",
                "plugins",
                "custom_rules",
            }
        )

        for table_name, value in data.items():
            tables_to_check = []
            if isinstance(value, dict):
                tables_to_check.append(value)
            elif isinstance(value, list) and value:
                tables_to_check.extend(item for item in value if isinstance(item, dict))

            for table in tables_to_check:
                if isinstance(table, dict):
                    swallowed = set(table.keys()) & root_keys
                if swallowed:
                    from rich.markup import escape

                    from zenzic.core.exceptions import ZenzicConfigError

                    swallowed_key = next(iter(swallowed))
                    table_str = escape(f"[{table_name}]")
                    tables_str = escape("[tables]")
                    raise ZenzicConfigError(
                        f"FATAL CONFIGURATION ERROR: The root key '{swallowed_key}' was found inside "
                        f"the '{table_str}' section. In TOML, root keys must be declared at the "
                        f"absolute top of the file before any {tables_str} are opened."
                    )

    @classmethod
    def load(cls, repo_root: Path) -> tuple[ZenzicConfig, bool]:
        """Load configuration following the Agnostic Citizen priority chain.

        Priority order (first match wins):

        1. ``.zenzic.toml`` at *repo_root* — the authoritative sovereign config.
        2. ``[tool.zenzic]`` table in ``pyproject.toml`` at *repo_root*.
        3. Built-in defaults (``loaded_from_file`` returned as ``False``).

        When the winning file exists but cannot be parsed, a
        :class:`~zenzic.core.exceptions.ZenzicConfigError` is raised with a
        Rich-formatted message — silent fallback would hide user mistakes.

        Args:
            repo_root: Repository root that may contain config files.

        Returns:
            A ``(config, loaded_from_file)`` tuple.  ``loaded_from_file`` is
            ``True`` when either ``.zenzic.toml`` or ``pyproject.toml`` was
            found and parsed, ``False`` when built-in defaults are in use.

        Raises:
            :class:`~zenzic.core.exceptions.ZenzicConfigError`: When a
                config file is present but cannot be parsed.
        """
        from pydantic import ValidationError

        from zenzic.core.exceptions import (
            ZenzicConfigError,  # deferred to avoid circular import
        )

        # ── Priority 1: .zenzic.toml ───────────────────────────────────────────
        zenzic_toml = repo_root / ".zenzic.toml"
        if zenzic_toml.is_file():
            try:
                with zenzic_toml.open("rb") as f:
                    data = tomllib.load(f)
            except tomllib.TOMLDecodeError as exc:
                raise ZenzicConfigError(
                    f"[bold red].zenzic.toml[/] contains a syntax error and cannot be loaded.\n"
                    f"  [{ZenzicPalette.DIM}]{zenzic_toml}[/]\n\n"
                    f"  [red]{exc}[/]\n\n"
                    "Fix the TOML syntax error and re-run Zenzic.",
                    context={"config_path": str(zenzic_toml), "file": str(zenzic_toml)},
                ) from exc
            cls._validate_no_swallowed_root_keys(data)
            try:
                config = cls._build_from_data(data)
                config.origin_file = zenzic_toml
                cls._apply_local_toml(config, repo_root)
            except ValidationError as exc:
                errors_str = "\n".join(
                    f"  - {'.'.join(str(loc) for loc in err['loc'])}: {err['msg']}"
                    for err in exc.errors()
                )
                raise ZenzicConfigError(
                    f"Configuration validation failed in [bold red].zenzic.toml[/]:\n{errors_str}",
                    context={"errors": exc.errors(), "file": str(zenzic_toml)},
                ) from exc
            from zenzic.core.suppressions import GlobalUsageTracker

            config._global_tracker = GlobalUsageTracker(config)
            return config, True

        # ── Priority 2: [tool.zenzic] in pyproject.toml ──────────────────────
        pyproject_toml = repo_root / "pyproject.toml"
        if pyproject_toml.is_file():
            try:
                with pyproject_toml.open("rb") as f:
                    pyproject_data = tomllib.load(f)
            except tomllib.TOMLDecodeError as exc:
                raise ZenzicConfigError(
                    f"[bold red]pyproject.toml[/] contains a syntax error and cannot be loaded.\n"
                    f"  [{ZenzicPalette.DIM}]{pyproject_toml}[/]\n\n"
                    f"  [red]{exc}[/]\n\n"
                    "Fix the TOML syntax error and re-run Zenzic.",
                    context={"config_path": str(pyproject_toml), "file": str(pyproject_toml)},
                ) from exc
            tool_section = pyproject_data.get("tool", {})
            zenzic_section = tool_section.get("zenzic", {})
            if zenzic_section:
                cls._validate_no_swallowed_root_keys(zenzic_section)
                try:
                    config = cls._build_from_data(zenzic_section)
                    config.origin_file = pyproject_toml
                    cls._apply_local_toml(config, repo_root)
                except ValidationError as exc:
                    errors_str = "\n".join(
                        f"  - {'.'.join(str(loc) for loc in err['loc'])}: {err['msg']}"
                        for err in exc.errors()
                    )
                    raise ZenzicConfigError(
                        f"Configuration validation failed in [bold red]pyproject.toml[/]:\n{errors_str}",
                        context={"errors": exc.errors(), "file": str(pyproject_toml)},
                    ) from exc
                from zenzic.core.suppressions import GlobalUsageTracker

                config._global_tracker = GlobalUsageTracker(config)
                return config, True

        # ── Priority 3: built-in defaults ─────────────────────────────────────
        try:
            config = cls()
            config.origin_file = repo_root / ".zenzic.toml"
            cls._apply_local_toml(config, repo_root)
        except ValidationError as exc:
            errors_str = "\n".join(
                f"  - {'.'.join(str(loc) for loc in err['loc'])}: {err['msg']}"
                for err in exc.errors()
            )
            raise ZenzicConfigError(
                f"Configuration validation failed for default/local config:\n{errors_str}",
                context={"errors": exc.errors()},
            ) from exc
        from zenzic.core.suppressions import GlobalUsageTracker

        config._global_tracker = GlobalUsageTracker(config)
        return config, False

    @classmethod
    def _apply_local_toml(cls, config: ZenzicConfig, repo_root: Path) -> None:
        """Apply machine-local overrides from ``.zenzic.local.toml``.

        The local file is git-ignored and machine-local.  It can override a
        safe subset of the shared configuration (core/build_context/
        project_metadata/governance/i18n) while preserving the repository
        sovereign defaults for everyone else.

        Legacy compatibility:

        - Top-level ``forbidden_patterns`` remains supported.
        - ``[core].forbidden_patterns`` is also supported.
        - Patterns are merged additively with de-duplication.

        ``.zenzic.dev.toml`` is a hard-removed legacy file in v0.7.0: when
        present, configuration loading fails with an explicit migration error.
        """
        legacy_toml = repo_root / ".zenzic.dev.toml"
        if legacy_toml.is_file():
            from zenzic.core.exceptions import (
                ZenzicConfigError,  # deferred to avoid circular import
            )

            raise ZenzicConfigError(
                "Legacy local config [bold].zenzic.dev.toml[/] is no longer supported in v0.7.0.\n"
                f"  [{ZenzicPalette.DIM}]{legacy_toml}[/]\n\n"
                "Migrate to [bold].zenzic.local.toml[/] and remove the legacy file.\n"
                "Run [bold cyan]zenzic init[/] to scaffold the new local template.",
                context={"file": str(legacy_toml)},
            )

        local_toml = repo_root / ".zenzic.local.toml"
        if not local_toml.is_file():
            return
        try:
            with local_toml.open("rb") as f:
                local_data = tomllib.load(f)
        except tomllib.TOMLDecodeError:
            return  # malformed local file — silently skip to avoid hard failures

        # Note: Z001 is a ZenzicConfigError raised before scanning begins —
        # not a scanner finding code.
        _ALLOWED_LOCAL_KEYS: Final[frozenset[str]] = frozenset(
            {
                "core",
                "build_context",
                "project_metadata",
                "governance",
                "i18n",
                "forbidden_patterns",
                "excluded_dirs",
                "excluded_file_patterns",
                "custom_rules",
                "secrets",
                "debug",
                "env",
            }
        )
        unknown_keys = set(local_data.keys()) - _ALLOWED_LOCAL_KEYS
        if unknown_keys:
            from zenzic.core.exceptions import ZenzicConfigError

            pretty = ", ".join(f"'{k}'" for k in sorted(unknown_keys))
            raise ZenzicConfigError(
                f"[LOCAL-TOML-STRICT] .zenzic.local.toml contains unsupported top-level "
                f"key(s): {pretty}.\n"
                "Allowed sections: core, build_context, project_metadata, governance, i18n, "
                "forbidden_patterns, excluded_dirs, excluded_file_patterns, custom_rules, "
                "secrets, debug, env.\n"
                "Remove the unknown key(s) or run 'zenzic init --local' to regenerate the local config template.",
                context={"unknown_keys": sorted(unknown_keys), "file": str(local_toml)},
            )

        core_local = local_data.get("core")
        if isinstance(core_local, dict):
            docs_dir = core_local.get("docs_dir")
            if isinstance(docs_dir, str) and docs_dir.strip():
                config.docs_dir = Path(docs_dir.strip())

            strict = core_local.get("strict")
            if isinstance(strict, bool):
                config.strict = strict

            exit_zero = core_local.get("exit_zero")
            if isinstance(exit_zero, bool):
                config.exit_zero = exit_zero

            fail_under = core_local.get("fail_under")
            if isinstance(fail_under, int):
                config.fail_under = fail_under

        build_local = local_data.get("build_context")
        if isinstance(build_local, dict):
            merged_build = config.build_context.model_dump()
            for key in BuildContext.model_fields:
                if key in build_local:
                    merged_build[key] = build_local[key]
            try:
                config.build_context = BuildContext(**merged_build)
            except Exception:
                pass

        metadata_local = local_data.get("project_metadata")
        if isinstance(metadata_local, dict):
            merged_meta = config.project_metadata.model_dump()
            for key in ProjectMetadata.model_fields:
                if key in metadata_local:
                    merged_meta[key] = metadata_local[key]
            try:
                config.project_metadata = ProjectMetadata(**merged_meta)
            except Exception:
                pass

        governance_local = local_data.get("governance")
        if isinstance(governance_local, dict):
            merged_governance = config.governance.model_dump()
            # brand_obsolescence uses ADDITIVE merge — local extends global;
            # global terms cannot be removed by an unversioned local file.
            if "brand_obsolescence" in governance_local:
                local_terms = governance_local.get("brand_obsolescence", [])
                if isinstance(local_terms, list):
                    existing = merged_governance.get("brand_obsolescence", [])
                    merged_governance["brand_obsolescence"] = list(
                        dict.fromkeys(existing + [t for t in local_terms if t not in existing])
                    )
            for key in GovernanceConfig.model_fields:
                if key in governance_local and key != "brand_obsolescence":
                    merged_governance[key] = governance_local[key]
            try:
                config.governance = GovernanceConfig(**merged_governance)
            except Exception:
                pass

        merged_forbidden = list(config.forbidden_patterns)

        legacy_extra = local_data.get("forbidden_patterns", [])
        if isinstance(legacy_extra, list):
            merged_forbidden.extend(legacy_extra)

        core_forbidden = (
            core_local.get("forbidden_patterns", []) if isinstance(core_local, dict) else []
        )
        if isinstance(core_forbidden, list):
            merged_forbidden.extend(core_forbidden)

        gov_forbidden = (
            governance_local.get("forbidden_patterns", [])
            if isinstance(governance_local, dict)
            else []
        )
        if isinstance(gov_forbidden, list):
            merged_forbidden.extend(gov_forbidden)

        config.forbidden_patterns = list(dict.fromkeys(merged_forbidden))

        # excluded_dirs — ADDITIVE merge: local directories extend the global list.
        # SYSTEM_EXCLUDED_DIRS are already baked in by model_post_init() before this
        # method runs, so they are preserved unconditionally.
        local_excl_dirs = local_data.get("excluded_dirs", [])
        if isinstance(local_excl_dirs, list) and local_excl_dirs:
            config.excluded_dirs = list(dict.fromkeys([*config.excluded_dirs, *local_excl_dirs]))

        # excluded_file_patterns — ADDITIVE merge: local glob patterns extend the global list.
        local_excl_patterns = local_data.get("excluded_file_patterns", [])
        if isinstance(local_excl_patterns, list) and local_excl_patterns:
            config.excluded_file_patterns = list(
                dict.fromkeys([*config.excluded_file_patterns, *local_excl_patterns])
            )

        # custom_rules — ADDITIVE merge with per-id override semantics:
        #   - Global rules without a matching local id are preserved unchanged.
        #   - A local rule with the same id as a global rule overrides that single rule.
        #   - Local rules with a new id are appended.
        # This prevents a non-versioned local file from silently disabling global lint policy.
        local_custom_rules_raw = local_data.get("custom_rules", [])
        if isinstance(local_custom_rules_raw, list) and local_custom_rules_raw:
            try:
                local_rules = [
                    CustomRuleConfig(**r) for r in local_custom_rules_raw if isinstance(r, dict)
                ]
            except Exception:
                pass  # malformed local rule — silently skip (consistent with other merge blocks)
            else:
                merged_rules: dict[str, CustomRuleConfig] = {r.id: r for r in config.custom_rules}
                for r in local_rules:
                    merged_rules[r.id] = r
                config.custom_rules = list(merged_rules.values())

        # Re-compile forbidden_patterns union regex after all local merges are complete.
        config._recompile_forbidden_patterns()
