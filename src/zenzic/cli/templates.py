# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""TOML template constants for ``zenzic init``.

Separating templates from generator logic (SRP) ensures that layout and
wording changes can be made without touching CLI wiring code.
"""

# Split to prevent REUSE from treating the string inside the template as the
# license declaration for this source file.
_SPDX = "SPDX-License-Identifier"


# ===========================================================================
# GLOBAL_TOML_TEMPLATE
# ===========================================================================
# Written to .zenzic.toml by `zenzic init`.
# Dynamic placeholders: {engine}, {hint_name}  (call .format() before write).
# All literal curly braces in the TOML content must be doubled: {{ }}.
# ===========================================================================
def _activation_block() -> str:
    """Render the opt-in section of ``[policies]`` from the code registry.

    Hand-written until now, and it had already diverged: ``enable_circular_link_check``
    was absent entirely, so ``Z106`` was documented in the configuration reference
    and invisible in the file the tool writes. Same shape as ``fixable`` -- a fact
    the registry holds, maintained by hand, drifting the moment the set grows.

    Grouped by code rather than by kind, so a reader sees one code's flag, its
    data requirement and its identity together instead of scattered across the
    file.
    """
    from zenzic.core.codes import CODE_DEFINITIONS, CODE_DESCRIPTIONS, CODE_NAMES

    flag = [(c, d) for c, d in sorted(CODE_DEFINITIONS.items()) if d.activation == "flag"]
    data = [(c, d) for c, d in sorted(CODE_DEFINITIONS.items()) if d.activation == "data"]

    out = [
        "# --- ACTIVATION: WHAT MAKES A CHECK REPORT ---\n",
        "# Three behaviours, and the difference matters when output is empty.\n",
        "#\n",
        "#   on by default  runs unless you suppress it. Most codes.\n",
        "#   opt-in         off until you set its flag to true, below.\n",
        "#   inert          runs already, and finds nothing until you declare the\n",
        "#                  data it works on. NOT the same as off: an empty list\n",
        "#                  below means the check is looking and has nothing to\n",
        "#                  look for, which reads identically to 'no violations'.\n",
        "#\n",
        "# Generated from the code registry (src/zenzic/core/codes.py). Adding a\n",
        "# gated code there changes this block; it is not maintained by hand.\n",
        "\n",
        "# -- opt-in: set to true to enable --\n",
    ]
    for code, defn in flag:
        desc = CODE_DESCRIPTIONS.get(code, CODE_NAMES.get(code, code))
        out.append(f"# {code} {CODE_NAMES.get(code, '')} - {desc}\n")
        out.append(f"{defn.activation_key} = false\n")

    out.append("\n# -- inert until declared: the check runs, the data is yours --\n")
    for code, defn in data:
        desc = CODE_DESCRIPTIONS.get(code, CODE_NAMES.get(code, code))
        out.append(f"# {code} {CODE_NAMES.get(code, '')} - {desc}\n")
        out.append(f"#   declare [policies] {defn.activation_key}\n")
    return "".join(out)


GLOBAL_TOML_TEMPLATE: str = (
    "# SPDX-FileCopyrightText: 2026 [Your Name] <[Your Email]>\n"
    "# " + _SPDX + ": Apache-2.0\n"
    "\n"
    "# Precedence: .zenzic.toml is shared baseline;"
    " .zenzic.local.toml overrides locally.\n"
    "# Keep secrets and workstation-only values in .zenzic.local.toml.\n"
    "\n"
    "# --- PROJECT IDENTITY ---\n"
    "# [project]\n"
    '# name = "{hint_name}" # Used for personalized CLI Governance headers\n'
    "\n"
    "# --- CORE SETTINGS ---\n"
    "# ---------------------------------------------------------------------------\n"
    "# docs_dir\n"
    "# ---------------------------------------------------------------------------\n"
    "# The relative path to your documentation root.\n"
    "#\n"
    "# BEHAVIOR:\n"
    '#   - If omitted, Zenzic uses "docs" as the default directory.\n'
    '#   - Set to "." to scan the entire repository (L1 system exclusions apply).\n'
    "#   - Both .md and .mdx are scanned, in any letter case. MDX is a first-class\n"
    "#     format: JSX components carrying a URL participate in the link graph, and\n"
    # Braces doubled: this template is passed through str.format, which reads a
    # single brace as a field and raised KeyError: '/* zenzic' on the first run.
    "#     {{/* zenzic:ignore: Zxxx */}} works wherever the HTML comment form does.\n"
    "#     Other extensions (.markdown, .txt) are not scanned.\n"
    "#\n"
    '# DEFAULT: "docs"\n'
    "#\n"
    '# docs_dir = "docs"\n'
    "\n"
    "strict = true\n"
    "# ORTHOGONAL CONSTRAINTS (Flat-Cost Model):\n"
    "# - fail_under: Controls the global health of the project (active findings + debt).\n"
    "# - suppression_cap: An absolute hard-fail ceiling for hidden debt.\n"
    "# Mathematical invariant: fail_under <= (100 - suppression_cap)\n"
    "# Example: fail_under = 90 with suppression_cap = 10 (90 <= 100 - 10).\n"
    "# This ensures overall quality never drops below 90, while strictly preventing\n"
    "# the accumulation of more than 30 suppressed errors under any circumstance.\n"
    "fail_under = 100\n"
    "# exit_zero = false\n"
    "# respect_vcs_ignore = true\n"
    "# baseline_stale_days: age (days) after which the saved score snapshot\n"
    "# (.zenzic-score.json) is flagged stale in `zenzic score --json`'s\n"
    "# baseline_status field. Defaults to 7 when unset.\n"
    "# baseline_stale_days = 7\n"
    "\n"
    "# External URLs excluded from the broken-link check"
    " (applies only with --strict)\n"
    '# excluded_external_urls = ["https://github.com/YourOrg/YourRepo"]\n'
    "\n"
    "# Z204 Privacy Gate — terms that must never appear in published docs.\n"
    "# forbidden_patterns = []\n"
    "\n"
    "# --- PLACEHOLDERS & CODE SNIPPETS (Optional) ---\n"
    '# placeholder_patterns = ["coming soon", "work in progress", "wip", "todo"]\n'
    "# placeholder_max_words = 50\n"
    "# snippet_min_lines = 1\n"
    "# max_sentence_length = 40  # Z511 Excessive Sentence Length threshold (words)\n"
    "\n"
    "# --- EXCLUSION ZONES (Full bypass — use sparingly) ---\n"
    "# Paths listed here are INVISIBLE to Zenzic: no findings, no audit trail.\n"
    "# Prefer [governance.per_file_ignores] for targeted suppression with an"
    " audit trail.\n"
    '# excluded_dirs = ["legacy/", "third-party/"]\n'
    '# excluded_file_patterns = ["*.tmp", "*.log"]\n'
    '# excluded_assets = ["favicon.ico"]\n'
    '# excluded_asset_dirs = ["theme/"]\n'
    '# excluded_build_artifacts = ["pdf/*.pdf"]\n'
    "# included_dirs = []\n"
    "# included_file_patterns = []\n"
    "\n"
    "# --- PLUGINS (Optional) ---\n"
    "# plugins = []\n"
    "\n"
    "# --- ENGINE CONTEXT ---\n"
    "#\n"
    "# Four mkdocs.yml keys change what Zenzic reports. They live in your engine\n"
    "# config, not here, and are listed so their effect is not a surprise:\n"
    "#\n"
    "#   site_dir      the build output. Excluded from quality analysis; still\n"
    "#                 scanned for credentials.\n"
    "#   not_in_nav    pages deliberately absent from the navigation. No Z402,\n"
    "#                 and no Z103 on links into them. Still built and served.\n"
    "#   exclude_docs  pages absent from the built site. Out of quality scope\n"
    "#                 entirely; still scanned for credentials.\n"
    "#   draft_docs    same, with build semantics: `mkdocs serve` renders a\n"
    "#                 draft, `mkdocs build` omits it, and Zenzic reads a\n"
    "#                 repository rather than a running command.\n"
    "#\n"
    "# A pattern in the last three that cannot be parsed is reported as Z407\n"
    "# rather than silently ignored. Zensical supports none of the three.\n"
    "[build_context]\n"
    'engine         = "{engine}"'
    " # Supported: mkdocs, zensical, standalone\n"
    'base_url       = "/"\n'
    'default_locale = "en"\n'
    "\n"
    "# --- BRAND INTEGRITY ---\n"
    "[project_metadata]\n"
    '# release_name = "YOUR-RELEASE"\n'
    "# badge_stamp_files = [\"README.md\"]  # files updated by 'zenzic score --stamp'\n"
    "\n"
    "[governance]\n"
    "# ---------------------------------------------------------------------------\n"
    "# suppression_cap\n"
    "# ---------------------------------------------------------------------------\n"
    "# Hard-fail threshold for technical debt.\n"
    "#\n"
    "# BEHAVIOR:\n"
    "#   - If suppressions in use > cap: CI fails immediately (Exit Code 1).\n"
    "#   - Scoring: Every suppression in use costs 1 DQS point (Flat-Cost Model).\n"
    "#\n"
    "# DEFAULT: 30 — not calibrated. It was the free allowance of the model that\n"
    "#   preceded flat-cost debt, kept as the threshold. Declare the cap your project\n"
    "#   defends, and keep fail_under <= 100 - suppression_cap.\n"
    "#\n"
    "suppression_cap = 0\n"
    "suppression_cap_fail_hard = true\n"
    "\n"
    "# Terms that should no longer appear in your documentation.\n"
    "# Keep empty until your governance policy defines deprecated brand terms.\n"
    "brand_obsolescence = []\n"
    '# suppression_cap_scope = "all"  # Options: all, per-file\n'
    "\n"
    "# ---------------------------------------------------------------------------\n"
    "# per_file_ignores\n"
    "# ---------------------------------------------------------------------------\n"
    "# Silence a rule for specific file globs.\n"
    "#\n"
    "# BEHAVIOR: ADDITIVE — each pair in use adds 1 pt of Technical Debt (flat-cost).\n"
    "# IMPACT:   A pair that silences nothing costs nothing; it is reported as Z620.\n"
    "#\n"
    "# [governance.per_file_ignores]\n"
    '# "docs/legacy/**"      = ["Z601"]  # intentional brand refs → -1 pt\n'
    '# "docs/migration/*.md" = ["Z101"]  # known broken links → -1 pt\n'
    "\n"
    "# ---------------------------------------------------------------------------\n"
    "# directory_policies\n"
    "# ---------------------------------------------------------------------------\n"
    "# Strategic exemptions for entire directory trees or specific files.\n"
    "#\n"
    "# BEHAVIOR: Matched findings are dropped — each pair in use adds 1 pt of debt.\n"
    "# IMPACT:   In --audit mode, shown with [POLICY_EXEMPTION] label.\n"
    "#\n"
    "# [governance.directory_policies]\n"
    '# "blog/**"                       = ["Z411", "Z601"]  # historical archive & dead-ends\n'
    '# "docs/specs/**"                 = ["Z412"]          # traceability exemption\n'
    '# "docs/explanation/registry.mdx" = ["Z601", "Z620"]  # SSOT codename registry\n'
    "\n"
    "# Governance Playbook:\n"
    "# https://zenzic.dev/developers/how-to/release-governance-protocol\n"
    "\n"
    "# --- REPOSITORY HEALTH (zenzic doctor) ---\n"
    "# Conventions checked by 'zenzic doctor' and used by 'zenzic adr new'.\n"
    "# All defaults resolve inside your published documentation tree; doctor reads\n"
    "# public repository content only and never inspects gitignored directories.\n"
    "# Every value below is the default — uncomment only to override.\n"
    "#\n"
    "# [doctor]\n"
    '# adr_vault_path = "docs/developers/explanation/adr-vault"  # where decision records live\n'
    '# adr_citation_pattern = "ADR-\\\\d{{3}}"                   # how a citation looks in prose/code\n'
    '# redirects_path = "docs/_redirects"                     # structurally validated if present\n'
    "# redirects_expected_blanks = 8                           # 0 disables the blank-line check\n"
    "\n"
    "# --- POLICY-AS-CODE ENGINE ---\n"
    "[policies]\n"
    "# Enforces declarative structural and security policies across your docs graph.\n"
    "# Opt-in by default: empty lists/dicts bypass evaluation with zero performance overhead.\n"
    "#\n"
    "# required_frontmatter_keys: Markdown files must declare these keys in YAML frontmatter (Z610).\n"
    "# forbidden_external_domains: Links matching these domains emit governance warnings (Z611).\n"
    "# forbidden_frontmatter_keys: Markdown files must not contain these frontmatter keys (Z612).\n"
    "# frontmatter_schema_match: Frontmatter key values must match specified RE2 patterns (Z613).\n"
    "# allowed_external_domains: Zero-Trust whitelist for external link domains (Z614).\n"
    "#   EXCLUSIVE: once non-empty, every link to a domain NOT listed is an error.\n"
    "#   For the opposite rule -- flag only the domains you name -- use\n"
    "#   forbidden_external_domains (Z611), a blacklist.\n"
    "# required_url_schemes: Whitelist of allowed URL protocols (Z615).\n"
    "# cross_namespace_restrictions: Topological boundary restrictions between namespaces (Z616).\n"
    "# forbidden_content_patterns: RE2 regex patterns forbidden in prose (Z617).\n"
    "# required_heading_patterns: RE2 regex patterns required in headings (Z618).\n"
    "# max_document_complexity: Maximum allowed document complexity score (Z619).\n"
    "# weasel_words: List of words to detect in technical prose (Z519).\n"
    "# enable_passive_voice_check: Enable passive voice detection heuristic (Z518).\n"
    "# required_table_columns: Markdown table missing required column header (Z521).\n"
    "# table_cell_enums: Table cell value not in allowed enum list (Z522).\n"
    "# required_heading_order: Headings appear out of configured sequential order (Z523).\n"
    "# traceability_targets: Required cross-directory traceability link missing (Z412).\n"
    "required_frontmatter_keys = []\n"
    "forbidden_external_domains = []\n"
    "forbidden_frontmatter_keys = []\n"
    "allowed_external_domains = []\n"
    "required_url_schemes = []\n"
    "forbidden_content_patterns = []\n"
    "required_heading_patterns = []\n"
    "max_document_complexity = 0\n"
    "weasel_words = []\n" + _activation_block() + "required_heading_order = []\n"
    "# [policies.frontmatter_schema_match]\n"
    '# version = "^v\\\\d+\\\\.\\\\d+\\\\.\\\\d+$"\n'
    "# [policies.cross_namespace_restrictions]\n"
    '# "docs/public" = ["docs/internal"]\n'
    "# [policies.required_table_columns]\n"
    '# "*" = ["Status", "Description"]\n'
    '# "^API Reference$" = ["Method", "Endpoint"]\n'
    "# [policies.table_cell_enums]\n"
    '# Status = ["draft", "review", "stable"]\n'
    "# [policies.traceability_targets]\n"
    '# "docs/specs/**" = ["docs/architecture/**"]\n'
    "\n"
    "# --- NETWORK I/O ---\n"
    "[network]\n"
    "# Cache external link responses to speed up local execution.\n"
    "cache_ttl_hours = 24\n"
    "\n"
    "# --- CUSTOM RULES (Optional) ---\n"
    "# Declares project-specific regex-based lint rules applied line-by-line.\n"
    "# [[custom_rules]]\n"
    '# id       = "ZZ-NOCLICKHERE"\n'
    '# pattern  = "(?i)\\\\bclick here\\\\b"\n'
    '# message  = "Avoid generic link text. Use a meaningful description."\n'
    '# severity = "error"\n'
    '# link     = "https://wiki.example.com/link-text-policy"  # optional\n'
    "\n"
    "# --- HTML POLYGLOT INTEGRITY ---\n"
    "# Zenzic analyses <a>/<img> via the Uniform Resolver Pipeline.\n"
    '# Suppress inline HTML findings with: <a href="..." data-zenzic-ignore>text</a>\n'
    "# Z205 (javascript:, data:) is NEVER suppressible. Absolute security gate.\n"
    "# --- GATE 4: AUTOMATION (Pre-commit & CI/CD) ---\n"
    "# Track 1 — Pre-commit Hook (Recommended: add to .pre-commit-config.yaml):\n"
    "# repos:\n"
    "#   - repo: https://github.com/PythonWoods-Dev/zenzic\n"
    "#     rev: v0.30.0\n"
    "#     hooks:\n"
    "#       - id: zenzic-guard\n"
    "#\n"
    "# Track 2 / CI — GitHub Actions (Optional: add to .github/workflows/zenzic.yml):\n"
    "# name: zenzic\n"
    "# on: [pull_request, push]\n"
    "# jobs:\n"
    "#   audit:\n"
    "#     runs-on: ubuntu-latest\n"
    "#     steps:\n"
    "#       - uses: actions/checkout@v4\n"
    "#       - name: Run Zenzic Action\n"
    "#         uses: pythonwoods/zenzic-action@v2\n"
    "#       - name: Verify Badge Freshness\n"
    "#         run: uvx zenzic score --check-stamp\n"
)

# ===========================================================================
# LOCAL_TOML_TEMPLATE
# ===========================================================================
# Written to .zenzic.local.toml by `zenzic init`.
# No dynamic placeholders — written as-is.
# ===========================================================================
LOCAL_TOML_TEMPLATE: str = (
    "# ===========================================================================\n"
    "# ZENZIC LOCAL OVERRIDES (.zenzic.local.toml)\n"
    "# ===========================================================================\n"
    "# This file is auto-generated and MUST remain in .gitignore.\n"
    "# Use it for workstation-specific paths and private credentials.\n"
    "#\n"
    "# MERGE SEMANTICS:\n"
    "#\n"
    "#   [+] ADDITIVE (Local lists extend the shared configuration):\n"
    "#       - forbidden_patterns\n"
    "#       - brand_obsolescence\n"
    "#       - excluded_dirs\n"
    "#       - excluded_file_patterns\n"
    "#       - custom_rules\n"
    "#\n"
    "#   [=] REPLACEMENT (Local section completely overwrites the shared one):\n"
    "#       - governance (except brand_obsolescence)\n"
    "#       - build_context\n"
    "#       - project_metadata\n"
    "# ===========================================================================\n"
    "\n"
    "# ---------------------------------------------------------------------------\n"
    "# docs_dir\n"
    "# ---------------------------------------------------------------------------\n"
    "# Override the documentation root when working in an isolated branch layout\n"
    "# or a non-standard local folder structure.\n"
    "#\n"
    '# DEFAULT: "docs" (Zenzic model default; inherited from global if not set)\n'
    "#\n"
    '# docs_dir = "my/custom/path/to/docs"\n'
    "\n"
    "# ---------------------------------------------------------------------------\n"
    "# forbidden_patterns\n"
    "# ---------------------------------------------------------------------------\n"
    "# Z204 FORBIDDEN_TERM — Exit 2, non-suppressible.\n"
    "# Literal strings that must never appear in published documentation.\n"
    "# Case-insensitive substring match — single terms and phrases both work:\n"
    '#   "openai"        → matches any line containing "openai"\n'
    '#   "Project Titan" → matches any line containing the full phrase\n'
    "#\n"
    "# BEHAVIOR: ADDITIVE — extends the shared list; does not replace it.\n"
    "#\n"
    '# forbidden_patterns = ["openai", "Project Titan", "internal-api.corp"]\n'
    "forbidden_patterns = []\n"
    "\n"
    "[build_context]\n"
    "# ---------------------------------------------------------------------------\n"
    "# engine\n"
    "# ---------------------------------------------------------------------------\n"
    "# Mirrors global structure for safe local overrides only when needed.\n"
    "#\n"
    '# engine = "zensical"\n'
    '# base_url = "/"\n'
    '# default_locale = "en"\n'
    "\n"
    "[project_metadata]\n"
    "# ---------------------------------------------------------------------------\n"
    "# release_name\n"
    "# ---------------------------------------------------------------------------\n"
    "# Optional local branding experiments without touching team config.\n"
    "#\n"
    '# release_name = "v0.8.0"\n'
    "\n"
    "[governance]\n"
    "# ---------------------------------------------------------------------------\n"
    "# suppression_cap\n"
    "# ---------------------------------------------------------------------------\n"
    "# Raise the CAP only on your workstation to avoid blocking local experiments.\n"
    "# Keep shared governance decisions in .zenzic.toml.\n"
    "#\n"
    "# BEHAVIOR: If total suppressions > cap, CI fails (Exit Code 1).\n"
    "# IMPACT:   Does not affect team config — local machine only.\n"
    "#\n"
    "# DEFAULT: 30 (inherited from .zenzic.toml)\n"
    "#\n"
    "# suppression_cap = 100\n"
    "# suppression_cap_fail_hard = false\n"
    "\n"
    "# Per-file suppression map (local experiments).\n"
    "# [governance.per_file_ignores]\n"
    '# "docs/wip/**" = ["Z101"]\n'
    "\n"
    "# Directory policy — exemption (1 pt debt per pair in use, shown in --audit).\n"
    "# [governance.directory_policies]\n"
    '# "blog/**" = ["Z411", "Z601"]\n'
    "\n"
    "[secrets]\n"
    "# ---------------------------------------------------------------------------\n"
    "# API Tokens\n"
    "# ---------------------------------------------------------------------------\n"
    "# Store credentials here (NEVER in shared .zenzic.toml).\n"
    "# Used by local wrappers for authenticated checks.\n"
    "#\n"
    '# github_pat = "ghp_xxxxxxxxxxxxxxxxxxxx"\n'
    "\n"
    "[debug]\n"
    "# Enable granular diagnostics.\n"
    '# log_level = "DEBUG"\n'
    "\n"
    "[env]\n"
    "# Local environment variables for wrappers and scripts.\n"
    '# ZENZIC_FORCE_COLOR = "true"\n'
)

# ===========================================================================
# PYPROJECT_TOML_SECTION_TEMPLATE
# ===========================================================================
# Appended to pyproject.toml by `zenzic init --pyproject`.
# Dynamic placeholders: {engine}, {hint_name}
#
# THIS IS A POINTER, NOT A CATALOGUE, AND THAT IS THE POINT.
#
# Until 2026-09-16 this template was 173 lines of annotated reference written
# into a file the Python project owns. The reason to shrink it is not that the
# file is shared -- though it is -- but that the same knowledge was written in
# three places: 19 finding codes enumerated by hand here, 31 in the .zenzic.toml
# template, and the registry that actually knows. Two of the three had already
# diverged. A catalogue in three copies is three surfaces that drift, and
# `activation`/`activation_key` exist precisely so enumeration can derive.
#
# So this holds what a project must DECIDE, and points at the reference for
# everything it can look up. The reference page is built and verified:
# docs/reference/configuration-reference/.
# ===========================================================================
PYPROJECT_TOML_SECTION_TEMPLATE: str = (
    "\n"
    "# ---------------------------------------------------------------------------\n"
    "# Zenzic — Documentation Quality System\n"
    "# Full reference: https://zenzic.dev/reference/configuration-reference/\n"
    "# Precedence: pyproject.toml is shared baseline; .zenzic.local.toml overrides locally.\n"
    "# Keep secrets and workstation-only values in .zenzic.local.toml.\n"
    "#\n"
    "# This section carries the decisions. Every other setting -- suppression\n"
    "# policies, per-file ignores, custom rules, the policy engine, opt-in codes --\n"
    "# is documented at the reference above. Run `zenzic init` in a scratch\n"
    "# directory to read the fully annotated form. Policy keys go under\n"
    "# [tool.zenzic.policies]: a [policies] table at the root of this file is\n"
    "# outside [tool.zenzic] and is not read.\n"
    "# ---------------------------------------------------------------------------\n"
    "\n"
    "[tool.zenzic]\n"
    "# docs_dir — your documentation root.\n"
    '#   Default: "docs" | Use "." to scan the whole repository.\n'
    '# docs_dir = "docs"\n'
    "\n"
    "strict = true\n"
    "\n"
    "# The two gates, and the invariant that binds them:\n"
    "#     fail_under <= (100 - suppression_cap)\n"
    "#\n"
    "# fail_under — the score your project defends.\n"
    "fail_under = 100\n"
    "\n"
    "\n"
    "[tool.zenzic.governance]\n"
    "# suppression_cap — the ceiling on hidden debt. Every suppression in use\n"
    "# costs 1 point (flat-cost model), and exceeding the cap fails the run.\n"
    "#\n"
    "# Starts at 0 because a new project genuinely has no suppressions: the\n"
    "# number measures your real state instead of granting an allowance. The\n"
    "# first suppression then forces a deliberate choice rather than quietly\n"
    "# consuming an uncalibrated 30 -- which is the engine default, inherited\n"
    "# from the model that preceded flat-cost debt and never calibrated since.\n"
    "# Raise it to the debt your project defends, keeping the invariant above.\n"
    "suppression_cap = 0\n"
    "suppression_cap_fail_hard = true\n"
    "\n"
    "[tool.zenzic.build_context]\n"
    "# engine — auto-detected from project files; override with --engine.\n"
    "#   Supported: mkdocs, zensical, standalone\n"
    'engine         = "{engine}"\n'
    'base_url       = "/"\n'
    'default_locale = "en"\n'
    "\n"
    "[tool.zenzic.project_metadata]\n"
    '# name = "{hint_name}"\n'
    '# release_name = "YOUR-RELEASE"\n'
    '# badge_stamp_files = ["README.md"]  # updated by `zenzic score --stamp`\n'
)
