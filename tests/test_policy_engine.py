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
) -> ZenzicConfig:
    """Build a ZenzicConfig with the given [policies] settings."""
    policies = PoliciesConfig(
        required_frontmatter_keys=required_keys or [],
        forbidden_external_domains=forbidden_domains or [],
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
