# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""Unit tests for the Policy-as-Code Engine (v0.28.0).

Covers:
- PolicyEvaluator.check() — Z610 REQUIRED_FRONTMATTER_MISSING
- PolicyEvaluator.check() — Z611 FORBIDDEN_DOMAIN_REFERENCE
- _parse_frontmatter_keys() — frontmatter extraction helper
- _extract_links() — link extraction from Markdown + HTML
- check_policies() — convenience wrapper (zero-cost opt-in)
- PoliciesConfig schema — TOML parsing via ZenzicConfig
"""

from __future__ import annotations

from pathlib import Path

from zenzic.core.governance import (
    PolicyEvaluator,
    _extract_links,
    _parse_frontmatter_keys,
    check_policies,
)
from zenzic.models.config import PoliciesConfig, ZenzicConfig


# ── Helpers ──────────────────────────────────────────────────────────────────


def _config_with_policies(
    required_keys: list[str] | None = None,
    forbidden_domains: list[str] | None = None,
    forbidden_keys: list[str] | None = None,
    schema_match: dict[str, str] | None = None,
    forbidden_content: list[str] | None = None,
    required_headings: list[str] | None = None,
    max_complexity: int = 0,
) -> ZenzicConfig:
    """Build a ZenzicConfig with the given [policies] settings."""
    policies = PoliciesConfig(
        required_frontmatter_keys=required_keys or [],
        forbidden_external_domains=forbidden_domains or [],
        forbidden_frontmatter_keys=forbidden_keys or [],
        frontmatter_schema_match=schema_match or {},
        forbidden_content_patterns=forbidden_content or [],
        required_heading_patterns=required_headings or [],
        max_document_complexity=max_complexity,
    )
    config = ZenzicConfig()
    config.policies = policies
    return config


DUMMY_FILE = Path("docs/sample.md")

# ── _parse_frontmatter_keys ───────────────────────────────────────────────────


def test_parse_frontmatter_keys_returns_all_keys() -> None:
    content = "---\ntitle: Hello\ndescription: World\nauthor: PythonWoods\n---\nBody."
    keys = _parse_frontmatter_keys(content)
    assert keys == {"title", "description", "author"}


def test_parse_frontmatter_keys_empty_when_no_frontmatter() -> None:
    content = "# No frontmatter here\n\nJust body text."
    keys = _parse_frontmatter_keys(content)
    assert keys == set()


def test_parse_frontmatter_keys_empty_block() -> None:
    content = "---\n---\nBody."
    keys = _parse_frontmatter_keys(content)
    assert keys == set()


# ── _extract_links ────────────────────────────────────────────────────────────


def test_extract_links_markdown_native() -> None:
    content = "See [Foo](https://example.com/foo) and [Bar](https://bar.io)."
    links = _extract_links(content)
    assert links == ["https://example.com/foo", "https://bar.io"]


def test_extract_links_html_href() -> None:
    content = 'Click <a href="https://legacy.corp/docs">here</a>.'
    links = _extract_links(content)
    assert links == ["https://legacy.corp/docs"]


def test_extract_links_both_types() -> None:
    content = (
        '[Native](https://native.example.com) and <a href="https://html.example.com">HTML</a>.'
    )
    links = _extract_links(content)
    assert links == ["https://native.example.com", "https://html.example.com"]


def test_extract_links_deduplication() -> None:
    content = "[A](https://dup.com) [B](https://dup.com)"
    links = _extract_links(content)
    assert links.count("https://dup.com") == 1


def test_extract_links_no_links() -> None:
    content = "# Heading\n\nPlain text with no links."
    links = _extract_links(content)
    assert links == []


# ── Z610 REQUIRED_FRONTMATTER_MISSING ────────────────────────────────────────


def test_policy_evaluator_z610_missing_single_key() -> None:
    config = _config_with_policies(required_keys=["title", "description"])
    content = "---\ntitle: My Doc\n---\nBody."  # missing 'description'
    evaluator = PolicyEvaluator(config)
    findings = evaluator.check(DUMMY_FILE, content)
    codes = [f.rule_id for f in findings]
    assert "Z610" in codes
    assert len([f for f in findings if f.rule_id == "Z610"]) == 1
    assert "description" in findings[0].message


def test_policy_evaluator_z610_multiple_missing_keys() -> None:
    config = _config_with_policies(required_keys=["title", "description", "author"])
    content = "---\ntitle: My Doc\n---\nBody."  # missing 'description' and 'author'
    evaluator = PolicyEvaluator(config)
    findings = evaluator.check(DUMMY_FILE, content)
    z610_findings = [f for f in findings if f.rule_id == "Z610"]
    assert len(z610_findings) == 2
    missing_keys_mentioned = {f.message.split("'")[1] for f in z610_findings}
    assert "description" in missing_keys_mentioned
    assert "author" in missing_keys_mentioned


def test_policy_evaluator_z610_all_keys_present() -> None:
    config = _config_with_policies(required_keys=["title", "description"])
    content = "---\ntitle: My Doc\ndescription: Short desc\n---\nBody."
    evaluator = PolicyEvaluator(config)
    findings = evaluator.check(DUMMY_FILE, content)
    assert not any(f.rule_id == "Z610" for f in findings)


def test_policy_evaluator_z610_empty_policy_is_noop() -> None:
    """Z610 must be completely inactive when required_frontmatter_keys = []."""
    config = _config_with_policies(required_keys=[])
    content = "# Heading\n\nNo frontmatter at all."
    evaluator = PolicyEvaluator(config)
    findings = evaluator.check(DUMMY_FILE, content)
    assert findings == []


def test_policy_evaluator_z610_no_frontmatter_emits_finding() -> None:
    """A file without any frontmatter block violates ALL required key policies."""
    config = _config_with_policies(required_keys=["title"])
    content = "# No Frontmatter\n\nBody."
    evaluator = PolicyEvaluator(config)
    findings = evaluator.check(DUMMY_FILE, content)
    assert any(f.rule_id == "Z610" and "title" in f.message for f in findings)


# ── Z611 FORBIDDEN_DOMAIN_REFERENCE ──────────────────────────────────────────


def test_policy_evaluator_z611_forbidden_domain_markdown_link() -> None:
    config = _config_with_policies(forbidden_domains=["competitor.example.com"])
    content = "See [this](https://competitor.example.com/page)."
    evaluator = PolicyEvaluator(config)
    findings = evaluator.check(DUMMY_FILE, content)
    assert len(findings) == 1
    assert findings[0].rule_id == "Z611"
    assert findings[0].message.startswith("Link to 'https://competitor.example.com/page'")


def test_policy_evaluator_z611_forbidden_domain_html_link() -> None:
    config = _config_with_policies(forbidden_domains=["legacy.corp"])
    content = '<a href="https://legacy.corp/docs">old docs</a>'
    evaluator = PolicyEvaluator(config)
    links = _extract_links(content)
    findings = evaluator.check(DUMMY_FILE, content, links=links)
    assert any(f.rule_id == "Z611" for f in findings)


def test_policy_evaluator_z611_subdomain_match() -> None:
    """Forbidden domains must match subdomains (api.competitor.example.com)."""
    config = _config_with_policies(forbidden_domains=["competitor.example.com"])
    content = "See [API](https://api.competitor.example.com/v1)."
    evaluator = PolicyEvaluator(config)
    findings = evaluator.check(DUMMY_FILE, content)
    assert any(f.rule_id == "Z611" for f in findings)


def test_policy_evaluator_z611_allowed_domain_no_finding() -> None:
    config = _config_with_policies(forbidden_domains=["legacy.corp"])
    content = "See [docs](https://docs.myproject.dev/guide)."
    evaluator = PolicyEvaluator(config)
    findings = evaluator.check(DUMMY_FILE, content)
    assert not any(f.rule_id == "Z611" for f in findings)


def test_policy_evaluator_z611_empty_policy_is_noop() -> None:
    """Z611 must be completely inactive when forbidden_external_domains = []."""
    config = _config_with_policies(forbidden_domains=[])
    content = "See [legacy](https://anything.example.com)."
    evaluator = PolicyEvaluator(config)
    findings = evaluator.check(DUMMY_FILE, content)
    assert findings == []


def test_policy_evaluator_z611_non_http_scheme_ignored() -> None:
    """Z611 must not flag mailto: or ftp: links — only http/https."""
    config = _config_with_policies(forbidden_domains=["example.com"])
    content = "Mail [us](mailto:info@example.com) or [ftp](ftp://example.com)."
    evaluator = PolicyEvaluator(config)
    findings = evaluator.check(DUMMY_FILE, content)
    assert not any(f.rule_id == "Z611" for f in findings)


def test_policy_evaluator_z611_case_insensitive_domain() -> None:
    """Domain matching must be case-insensitive."""
    config = _config_with_policies(forbidden_domains=["Legacy.Corp"])
    content = "See [this](https://LEGACY.CORP/docs)."
    evaluator = PolicyEvaluator(config)
    findings = evaluator.check(DUMMY_FILE, content)
    assert any(f.rule_id == "Z611" for f in findings)


# ── Z612 FORBIDDEN_FRONTMATTER_KEY ───────────────────────────────────────────


def test_policy_evaluator_z612_forbidden_key_present() -> None:
    config = _config_with_policies(forbidden_keys=["draft", "internal_notes"])
    content = "---\ntitle: My Doc\ndraft: true\n---\nBody."
    evaluator = PolicyEvaluator(config)
    findings = evaluator.check(DUMMY_FILE, content)
    z612_findings = [f for f in findings if f.rule_id == "Z612"]
    assert len(z612_findings) == 1
    assert "draft" in z612_findings[0].message
    assert z612_findings[0].severity == "warning"


def test_policy_evaluator_z612_no_forbidden_key_present() -> None:
    config = _config_with_policies(forbidden_keys=["draft", "internal_notes"])
    content = "---\ntitle: My Doc\n---\nBody."
    evaluator = PolicyEvaluator(config)
    findings = evaluator.check(DUMMY_FILE, content)
    assert not any(f.rule_id == "Z612" for f in findings)


# ── Z613 FRONTMATTER_SCHEMA_MISMATCH ─────────────────────────────────────────


def test_policy_evaluator_z613_schema_mismatch_detected() -> None:
    config = _config_with_policies(schema_match={"version": r"^v\d+\.\d+\.\d+$"})
    content = "---\ntitle: Release\nversion: 1.0\n---\nBody."
    evaluator = PolicyEvaluator(config)
    findings = evaluator.check(DUMMY_FILE, content)
    z613_findings = [f for f in findings if f.rule_id == "Z613"]
    assert len(z613_findings) == 1
    assert "version" in z613_findings[0].message
    assert z613_findings[0].severity == "error"


def test_policy_evaluator_z613_schema_match_valid() -> None:
    config = _config_with_policies(schema_match={"version": r"^v\d+\.\d+\.\d+$"})
    content = "# Heading\n\nNo frontmatter."
    evaluator = PolicyEvaluator(config)
    findings = evaluator.check(DUMMY_FILE, content)
    assert not any(f.rule_id == "Z613" for f in findings)


# ── Z614 UNAPPROVED_DOMAIN_REFERENCE ──────────────────────────────────────────


def test_policy_evaluator_z614_unapproved_domain() -> None:
    policies = PoliciesConfig(allowed_external_domains=["pythonwoods.dev"])
    config = ZenzicConfig()
    config.policies = policies
    content = "See [Unvetted](https://unapproved.example.org/spec) and [Valid](https://pythonwoods.dev/docs)."
    evaluator = PolicyEvaluator(config)
    findings = evaluator.check(DUMMY_FILE, content)
    z614 = [f for f in findings if f.rule_id == "Z614"]
    assert len(z614) == 1
    assert (
        z614[0].message
        == "Link to 'https://unapproved.example.org/spec' references external domain "
        "'unapproved.example.org' which is not in [policies].allowed_external_domains whitelist. "
        "Replace or add to whitelist."
    )


def test_policy_evaluator_z614_whitelisted_domain_passes() -> None:
    policies = PoliciesConfig(allowed_external_domains=["pythonwoods.dev", "github.com"])
    config = ZenzicConfig()
    config.policies = policies
    content = (
        "See [Doc](https://pythonwoods.dev/docs) and [Repo](https://github.com/PythonWoods/zenzic)."
    )
    evaluator = PolicyEvaluator(config)
    findings = evaluator.check(DUMMY_FILE, content)
    assert not any(f.rule_id == "Z614" for f in findings)


# ── Z615 FORBIDDEN_URL_SCHEME ──────────────────────────────────────────────────


def test_policy_evaluator_z615_forbidden_scheme() -> None:
    policies = PoliciesConfig(required_url_schemes=["https", "mailto"])
    config = ZenzicConfig()
    config.policies = policies
    content = "Check [site](http://example.com/docs) and [email](mailto:dev@pythonwoods.dev)."
    evaluator = PolicyEvaluator(config)
    findings = evaluator.check(DUMMY_FILE, content)
    z615 = [f for f in findings if f.rule_id == "Z615"]
    assert len(z615) == 1
    assert "http" in z615[0].message


def test_policy_evaluator_z615_allowed_scheme_passes() -> None:
    policies = PoliciesConfig(required_url_schemes=["https", "mailto"])
    config = ZenzicConfig()
    config.policies = policies
    content = "Check [site](https://example.com/docs) and [email](mailto:dev@pythonwoods.dev)."
    evaluator = PolicyEvaluator(config)
    findings = evaluator.check(DUMMY_FILE, content)
    assert not any(f.rule_id == "Z615" for f in findings)


# ── Z616 CROSS_NAMESPACE_LINK_FORBIDDEN ───────────────────────────────────────


def test_policy_evaluator_z616_cross_namespace_boundary_violation() -> None:
    from zenzic.core.resolver import InMemoryPathResolver

    policies = PoliciesConfig(cross_namespace_restrictions={"docs/public": ["docs/internal"]})
    config = ZenzicConfig()
    config.policies = policies

    src_file = Path("docs/public/index.md")
    content = "For secret details, see [Secret Spec](../internal/secret.md)."
    md_contents = {
        Path("docs/public/index.md"): content,
        Path("docs/internal/secret.md"): "# Secret\n",
    }
    resolver = InMemoryPathResolver(Path("docs"), md_contents, {p: set() for p in md_contents})
    evaluator = PolicyEvaluator(config)
    findings = evaluator.check(src_file, content, resolver=resolver)
    z616 = [f for f in findings if f.rule_id == "Z616"]
    assert len(z616) == 1
    assert "docs/internal" in z616[0].message


def test_policies_config_invalid_re2_pattern_raises_error() -> None:
    import pytest

    with pytest.raises(ValueError, match="Invalid RE2 regex pattern"):
        PoliciesConfig(frontmatter_schema_match={"version": "[unclosed bracket"})


# ── PolicyEvaluator.is_active ─────────────────────────────────────────────────


def test_policy_evaluator_is_active_false_when_empty() -> None:
    config = _config_with_policies()
    evaluator = PolicyEvaluator(config)
    assert not evaluator.is_active


def test_policy_evaluator_is_active_true_with_required_keys() -> None:
    config = _config_with_policies(required_keys=["title"])
    evaluator = PolicyEvaluator(config)
    assert evaluator.is_active


def test_policy_evaluator_is_active_true_with_forbidden_domains() -> None:
    config = _config_with_policies(forbidden_domains=["bad.example.com"])
    evaluator = PolicyEvaluator(config)
    assert evaluator.is_active


# ── check_policies() convenience wrapper ─────────────────────────────────────


def test_check_policies_wrapper_returns_empty_for_unconfigured() -> None:
    """Zero-cost opt-in: no findings and no overhead when policies are empty."""
    config = ZenzicConfig()
    content = "# Doc\n\nNo links, no frontmatter."
    findings = check_policies(DUMMY_FILE, content, config)
    assert findings == []


def test_check_policies_wrapper_delegates_to_evaluator() -> None:
    config = _config_with_policies(required_keys=["title"])
    content = "# Doc\n\nNo frontmatter."
    findings = check_policies(DUMMY_FILE, content, config)
    assert any(f.rule_id == "Z610" for f in findings)


# ── PoliciesConfig schema ─────────────────────────────────────────────────────


def test_policies_config_defaults_are_empty_lists() -> None:
    policies = PoliciesConfig()
    assert policies.required_frontmatter_keys == []
    assert policies.forbidden_external_domains == []


def test_policies_config_accepts_valid_values() -> None:
    policies = PoliciesConfig(
        required_frontmatter_keys=["title", "description"],
        forbidden_external_domains=["bad.example.com"],
    )
    assert policies.required_frontmatter_keys == ["title", "description"]
    assert policies.forbidden_external_domains == ["bad.example.com"]


def test_zenzic_config_policies_field_defaults() -> None:
    """ZenzicConfig must have a `policies` field with PoliciesConfig defaults."""
    config = ZenzicConfig()
    assert isinstance(config.policies, PoliciesConfig)
    assert config.policies.required_frontmatter_keys == []
    assert config.policies.forbidden_external_domains == []


def test_zenzic_config_backward_compat_no_policies_key() -> None:
    """Existing configs without [policies] must not raise any error."""
    import sys

    if sys.version_info >= (3, 11):
        import tomllib
    else:
        import tomli as tomllib  # type: ignore[no-redef]

    toml_str = b"strict = true\nfail_under = 98\n"
    data = tomllib.loads(toml_str.decode())
    config = ZenzicConfig.model_validate(data)
    assert config.policies.required_frontmatter_keys == []
    assert config.policies.forbidden_external_domains == []


def test_init_template_includes_policies_section() -> None:
    """zenzic init template must include valid [policies] section with empty opt-in lists."""
    import sys

    if sys.version_info >= (3, 11):
        import tomllib
    else:
        import tomli as tomllib  # type: ignore[no-redef]

    from zenzic.cli.templates import GLOBAL_TOML_TEMPLATE

    rendered = GLOBAL_TOML_TEMPLATE.format(engine="mkdocs", hint_name="test-project")
    parsed = tomllib.loads(rendered)

    assert "policies" in parsed
    assert parsed["policies"]["required_frontmatter_keys"] == []
    assert parsed["policies"]["forbidden_external_domains"] == []


def test_policy_evaluator_empty_policies_short_circuit() -> None:
    """PolicyEvaluator internal checkers must return [] immediately when policy lists are empty."""
    config = ZenzicConfig()
    evaluator = PolicyEvaluator(config)

    assert not evaluator.is_active
    assert evaluator._check_frontmatter(DUMMY_FILE, "no frontmatter") == []
    assert evaluator._check_links(DUMMY_FILE, "text", ["https://forbidden.com"]) == []
    assert evaluator._check_forbidden_content(DUMMY_FILE, "text") == []
    assert evaluator._check_required_headings(DUMMY_FILE, "text") == []
    assert evaluator._check_document_complexity(DUMMY_FILE, "text") == []


# ── Z617 FORBIDDEN_CONTENT_PATTERN ────────────────────────────────────────────


def test_policy_evaluator_z617_forbidden_content_detected() -> None:
    config = _config_with_policies(forbidden_content=["(?i)confidential", r"\bTODO\b"])
    content = "# Title\n\nThis contains confidential info.\nAnd a `TODO` in code is ignored?"
    evaluator = PolicyEvaluator(config)
    findings = evaluator.check(DUMMY_FILE, content)
    z617 = [f for f in findings if f.rule_id == "Z617"]
    assert len(z617) >= 1
    assert z617[0].line_no == 3
    assert z617[0].severity == "warning"


# ── Z618 REQUIRED_HEADING_PATTERN ─────────────────────────────────────────────


def test_policy_evaluator_z618_required_heading_missing() -> None:
    config = _config_with_policies(required_headings=["^Overview$", "^License$"])
    content = "# Title\n\n## Overview\n\nSome overview."
    evaluator = PolicyEvaluator(config)
    findings = evaluator.check(DUMMY_FILE, content)
    z618 = [f for f in findings if f.rule_id == "Z618"]
    assert len(z618) == 1
    assert "^License$" in z618[0].message
    assert z618[0].severity == "warning"


def test_policy_evaluator_z618_required_heading_satisfied() -> None:
    config = _config_with_policies(required_headings=["^Overview$", "^License$"])
    content = "# Title\n\n## Overview\n\n## License\n\nMIT"
    evaluator = PolicyEvaluator(config)
    findings = evaluator.check(DUMMY_FILE, content)
    z618 = [f for f in findings if f.rule_id == "Z618"]
    assert len(z618) == 0


# ── Z619 MAX_DOCUMENT_COMPLEXITY ──────────────────────────────────────────────


def test_policy_evaluator_z619_max_complexity_exceeded() -> None:
    config = _config_with_policies(max_complexity=5)
    content = (
        "# Title\n\n"
        "## Sub 1\n\n[Link 1](https://a.com)\n\n"
        "### Sub 2\n\n[Link 2](https://b.com)\n\n"
        "#### Sub 3\n\n[Link 3](https://c.com)\n\n"
    )
    evaluator = PolicyEvaluator(config)
    findings = evaluator.check(DUMMY_FILE, content)
    z619 = [f for f in findings if f.rule_id == "Z619"]
    assert len(z619) == 1
    assert z619[0].rule_id == "Z619"
    assert z619[0].severity == "warning"


def test_policy_evaluator_z619_complexity_under_threshold() -> None:
    config = _config_with_policies(max_complexity=100)
    content = "# Title\n\nSimple content.\n"
    evaluator = PolicyEvaluator(config)
    findings = evaluator.check(DUMMY_FILE, content)
    z619 = [f for f in findings if f.rule_id == "Z619"]
    assert len(z619) == 0

