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
    "# Example Hybrid Policy: fail_under = 90, suppression_cap = 30.\n"
    "# This ensures overall quality never drops below 90, while strictly preventing\n"
    "# the accumulation of more than 30 suppressed errors under any circumstance.\n"
    "fail_under = 100\n"
    "# exit_zero = false\n"
    "# respect_vcs_ignore = true\n"
    "# validate_same_page_anchors = true\n"
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
    "#   - If total suppressions > cap: CI fails immediately (Exit Code 1).\n"
    "#   - Scoring: Every suppression costs 1 DQS point (Flat-Cost Model).\n"
    "#\n"
    "# DEFAULT: 30\n"
    "#\n"
    "suppression_cap = 30\n"
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
    "# BEHAVIOR: ADDITIVE — each entry adds 1 pt of Technical Debt (flat-cost).\n"
    "# IMPACT:   Use directory_policies below for zero-debt strategic exemptions.\n"
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
    "# BEHAVIOR: Matched findings are silently dropped — ZERO debt added.\n"
    "# IMPACT:   In --audit mode, shown with [POLICY_EXEMPTION] label.\n"
    "#\n"
    "# [governance.directory_policies]\n"
    '# "blog/**"                       = ["Z601"]  # historical archive\n'
    '# "docs/explanation/registry.mdx" = ["Z601"]  # SSOT codename registry\n'
    "\n"
    "# Governance Playbook:\n"
    "# https://zenzic.dev/developers/how-to/release-governance-protocol\n"
    "\n"
    "# --- POLICY-AS-CODE ENGINE (v0.28.0) ---\n"
    "[policies]\n"
    "# Enforces declarative structural and security policies across your docs graph.\n"
    "# Opt-in by default: empty lists/dicts bypass evaluation with zero performance overhead.\n"
    "#\n"
    "# required_frontmatter_keys: Markdown files must declare these keys in YAML frontmatter (Z610).\n"
    "# forbidden_external_domains: Links matching these domains emit governance warnings (Z611).\n"
    "# forbidden_frontmatter_keys: Markdown files must not contain these frontmatter keys (Z612).\n"
    "# frontmatter_schema_match: Frontmatter key values must match specified RE2 patterns (Z613).\n"
    "# allowed_external_domains: Zero-Trust whitelist for external link domains (Z614).\n"
    "# required_url_schemes: Whitelist of allowed URL protocols (Z615).\n"
    "# cross_namespace_restrictions: Topological boundary restrictions between namespaces (Z616).\n"
    "required_frontmatter_keys = []\n"
    "forbidden_external_domains = []\n"
    "forbidden_frontmatter_keys = []\n"
    "allowed_external_domains = []\n"
    "required_url_schemes = []\n"
    "# [policies.frontmatter_schema_match]\n"
    '# version = "^v\\\\d+\\\\.\\\\d+\\\\.\\\\d+$"\n'
    "# [policies.cross_namespace_restrictions]\n"
    '# "docs/public" = ["docs/internal"]\n'
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
    "\n"
    "# --- HTML POLYGLOT INTEGRITY (v0.17.0) ---\n"
    "# Zenzic v0.17.0 analyses <a>/<img> via the Uniform Resolver Pipeline.\n"
    '# Suppress Z120-Z124 with: <a href="..." data-zenzic-ignore>text</a>\n'
    "# Z205 (javascript:, data:) is NEVER suppressible. Absolute security gate.\n"
    "# Each suppression: -1.0 pts DQS. exclude_patterns=[RELEASE.md, CITATION.cff]\n"
    "\n"
    "# --- GATE 4: CI/CD (GitHub Actions, Optional) ---\n"
    "# Add this workflow snippet to .github/workflows/zenzic.yml\n"
    "#\n"
    "# name: zenzic\n"
    "# on: [pull_request, push]\n"
    "# jobs:\n"
    "#   audit:\n"
    "#     runs-on: ubuntu-latest\n"
    "#     steps:\n"
    "#       - uses: actions/checkout@v4\n"
    "#       - name: Run Zenzic Action\n"
    "#         uses: pythonwoods/zenzic-action@v1\n"
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
    "# Directory policy — silent exemption (0 pt debt, shown in --audit).\n"
    "# [governance.directory_policies]\n"
    '# "blog/**" = ["Z601"]\n'
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
# ===========================================================================
PYPROJECT_TOML_SECTION_TEMPLATE: str = (
    "\n"
    "# ---------------------------------------------------------------------------\n"
    "# Zenzic — Documentation Quality System\n"
    "# Full reference: https://zenzic.dev/docs/reference/configuration/\n"
    "# Precedence: pyproject.toml is shared baseline; .zenzic.local.toml overrides locally.\n"
    "# Keep secrets and workstation-only values in .zenzic.local.toml.\n"
    "# ---------------------------------------------------------------------------\n"
    "\n"
    "[tool.zenzic]\n"
    "# docs_dir — relative path to your documentation root.\n"
    '#   Default: "docs" | Use "." to scan the entire repository (L1 exclusions apply).\n'
    "#\n"
    '# docs_dir = "docs"\n'
    "\n"
    "strict = true\n"
    "# ORTHOGONAL CONSTRAINTS (Flat-Cost Model):\n"
    "#   fail_under:      global health gate (active findings + debt).\n"
    "#   suppression_cap: absolute hard-fail ceiling for hidden debt.\n"
    "#   Invariant:       fail_under <= (100 - suppression_cap)\n"
    "#   Example: fail_under = 90, suppression_cap = 30 → score must stay above 90\n"
    "#            while capping hidden debt at 30 suppressions.\n"
    "fail_under = 100\n"
    "# exit_zero = false\n"
    "# respect_vcs_ignore = true\n"
    "# validate_same_page_anchors = true\n"
    "\n"
    "# External URLs excluded from the broken-link check (--strict only).\n"
    '# excluded_external_urls = ["https://github.com/YourOrg/YourRepo"]\n'
    "\n"
    "# Z204 Privacy Gate — terms that must never appear in published docs.\n"
    "# forbidden_patterns = []\n"
    "\n"
    "# --- PLACEHOLDERS & CODE SNIPPETS (Optional) ---\n"
    '# placeholder_patterns = ["coming soon", "work in progress", "wip", "todo"]\n'
    "# placeholder_max_words = 50\n"
    "# snippet_min_lines = 1\n"
    "\n"
    "# --- EXCLUSION ZONES (Full bypass — use sparingly) ---\n"
    "# Paths listed here are INVISIBLE to Zenzic: no findings, no audit trail.\n"
    "# Prefer [tool.zenzic.governance.per_file_ignores] for targeted suppression with an audit trail.\n"
    '# excluded_dirs          = ["legacy/", "third-party/"]\n'
    '# excluded_file_patterns = ["*.tmp", "*.log"]\n'
    '# excluded_assets        = ["favicon.ico"]\n'
    '# excluded_build_artifacts = ["pdf/*.pdf"]\n'
    "\n"
    "# --- PLUGINS (Optional) ---\n"
    "# plugins = []\n"
    "\n"
    "[tool.zenzic.build_context]\n"
    "# engine — auto-detected from project files; override with --engine if needed.\n"
    "#   Supported: mkdocs, zensical, standalone\n"
    'engine         = "{engine}"\n'
    'base_url       = "/"\n'
    'default_locale = "en"\n'
    "\n"
    "[tool.zenzic.project_metadata]\n"
    '# release_name = "YOUR-RELEASE"\n'
    "# badge_stamp_files = [\"README.md\"]  # files updated by 'zenzic score --stamp'\n"
    "\n"
    "[tool.zenzic.governance]\n"
    "# suppression_cap — hard-fail threshold for technical debt.\n"
    "#   BEHAVIOR: if total suppressions > cap → CI fails immediately (Exit Code 1).\n"
    "#   SCORING:  every suppression costs 1 DQS point (Flat-Cost Model).\n"
    "#   DEFAULT:  30\n"
    "suppression_cap           = 30\n"
    "suppression_cap_fail_hard = true\n"
    "\n"
    "# Terms that should no longer appear in your documentation.\n"
    "# Keep empty until your governance policy defines deprecated brand terms.\n"
    "brand_obsolescence = []\n"
    '# suppression_cap_scope = "all"  # Options: all, per-file\n'
    "\n"
    "# [tool.zenzic.governance.per_file_ignores]\n"
    "# Silence a rule for specific file globs.\n"
    "# BEHAVIOR: ADDITIVE — each entry adds 1 pt of Technical Debt (flat-cost).\n"
    "# IMPACT:   Use directory_policies below for zero-debt strategic exemptions.\n"
    "#\n"
    '# "docs/legacy/**"      = ["Z601"]  # intentional brand refs → -1 pt\n'
    '# "docs/migration/*.md" = ["Z101"]  # known broken links → -1 pt\n'
    "\n"
    "# [tool.zenzic.governance.directory_policies]\n"
    "# Strategic exemptions for entire directory trees or specific files.\n"
    "# BEHAVIOR: Matched findings are silently dropped — ZERO debt added.\n"
    "# IMPACT:   In --audit mode, shown with [POLICY_EXEMPTION] label.\n"
    "#\n"
    '# "blog/**"      = ["Z601"]  # historical archive\n'
    "\n"
    "# --- NETWORK I/O ---\n"
    "[tool.zenzic.network]\n"
    "# Cache external link responses to speed up local execution.\n"
    "cache_ttl_hours = 24\n"
    "\n"
    "# --- CUSTOM RULES (Optional) ---\n"
    "# Declares project-specific regex-based lint rules applied line-by-line.\n"
    "# [[tool.zenzic.custom_rules]]\n"
    '# id       = "ZZ-NOCLICKHERE"\n'
    '# pattern  = "(?i)\\\\bclick here\\\\b"\n'
    '# message  = "Avoid generic link text. Use a meaningful description."\n'
    '# severity = "error"\n'
    "\n"
    "# --- GATE 4: CI/CD (GitHub Actions, Optional) ---\n"
    "# Add this workflow snippet to .github/workflows/zenzic.yml\n"
    "#\n"
    "# name: zenzic\n"
    "# on: [pull_request, push]\n"
    "# jobs:\n"
    "#   audit:\n"
    "#     runs-on: ubuntu-latest\n"
    "#     steps:\n"
    "#       - uses: actions/checkout@v4\n"
    "#       - name: Run Zenzic Action\n"
    "#         uses: pythonwoods/zenzic-action@v1\n"
    "#       - name: Verify Badge Freshness\n"
    "#         run: uvx zenzic score --check-stamp\n"
)
