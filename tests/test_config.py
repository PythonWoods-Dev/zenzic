# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""Tests for Zenzic config loading and generator detection."""

from __future__ import annotations

from io import StringIO
from pathlib import Path

import pytest

from zenzic.core.exceptions import ConfigurationError
from zenzic.models.config import SYSTEM_EXCLUDED_DIRS, ZenzicConfig


def test_load_config_default(tmp_path: Path) -> None:
    config, loaded = ZenzicConfig.load(tmp_path)
    assert config.docs_dir == Path("docs")
    assert config.snippet_min_lines == 1
    assert loaded is False


def test_load_config_custom(tmp_path: Path) -> None:
    toml_content = """
    docs_dir = "my_docs"
    snippet_min_lines = 5
    placeholder_max_words = 100
    placeholder_patterns = ["tbd", "wip"]
    """
    (tmp_path / ".zenzic.toml").write_text(toml_content)

    config, loaded = ZenzicConfig.load(tmp_path)
    assert config.docs_dir == Path("my_docs")
    assert config.snippet_min_lines == 5
    assert config.placeholder_max_words == 100
    assert config.placeholder_patterns == ["tbd", "wip"]
    # excluded_dirs not set in TOML → inherits system defaults
    assert "includes" in config.excluded_dirs
    assert ".git" in config.excluded_dirs
    assert ".venv" in config.excluded_dirs
    assert "node_modules" in config.excluded_dirs
    assert loaded is True


def test_load_config_file_override_takes_priority_over_zenzic_toml(tmp_path: Path) -> None:
    """An explicit config_file override wins over .zenzic.toml at repo_root (priority 0)."""
    (tmp_path / ".zenzic.toml").write_text('docs_dir = "root_docs"\n')
    override_dir = tmp_path / "configs"
    override_dir.mkdir()
    override_path = override_dir / "prod.zenzic.toml"
    override_path.write_text('docs_dir = "override_docs"\n')

    config, loaded = ZenzicConfig.load(tmp_path, config_file=override_path)
    assert config.docs_dir == Path("override_docs")
    assert loaded is True
    assert config.origin_file == override_path


def test_load_config_file_override_used_when_no_repo_root_config_exists(tmp_path: Path) -> None:
    """An explicit config_file override works even when repo_root has no config at all."""
    override_path = tmp_path / "custom-name.toml"
    override_path.write_text('docs_dir = "custom_docs"\n')

    config, loaded = ZenzicConfig.load(tmp_path, config_file=override_path)
    assert config.docs_dir == Path("custom_docs")
    assert loaded is True


def test_load_config_file_override_missing_file_raises(tmp_path: Path) -> None:
    """An explicit config_file override pointing at a nonexistent file must raise, not fall back."""
    missing = tmp_path / "does-not-exist.toml"
    with pytest.raises(ConfigurationError, match="does not exist|not found"):
        ZenzicConfig.load(tmp_path, config_file=missing)


def test_load_config_file_override_invalid_toml_raises(tmp_path: Path) -> None:
    """An explicit config_file override with malformed TOML must raise — not silently fall back."""
    override_path = tmp_path / "broken.toml"
    override_path.write_text("invalid [ toml")
    with pytest.raises(ConfigurationError, match="syntax error"):
        ZenzicConfig.load(tmp_path, config_file=override_path)


def test_load_config_file_override_applies_local_toml_overlay(tmp_path: Path) -> None:
    """An explicit config_file override still layers .zenzic.local.toml on top."""
    override_path = tmp_path / "shared.zenzic.toml"
    override_path.write_text('docs_dir = "shared_docs"\nfail_under = 0\n')
    (tmp_path / ".zenzic.local.toml").write_text("[core]\nfail_under = 80\n")

    config, _ = ZenzicConfig.load(tmp_path, config_file=override_path)
    assert config.docs_dir == Path("shared_docs")
    assert config.fail_under == 80


def test_excluded_dirs_always_contains_system_guardrails(tmp_path: Path) -> None:
    """User-defined excluded_dirs must never remove system guardrails (.git, .venv, etc.)."""
    toml_content = """\
    docs_dir = "docs"
    excluded_dirs = ["custom_stuff"]
    """
    (tmp_path / ".zenzic.toml").write_text(toml_content)

    config, _ = ZenzicConfig.load(tmp_path)
    # User entry is preserved
    assert "custom_stuff" in config.excluded_dirs
    # System guardrails are always present
    for guardrail in SYSTEM_EXCLUDED_DIRS:
        assert guardrail in config.excluded_dirs, f"System guardrail {guardrail!r} missing"


def test_load_config_invalid_toml_raises(tmp_path: Path) -> None:
    """A malformed .zenzic.toml must raise ConfigurationError — not silently fall back."""
    (tmp_path / ".zenzic.toml").write_text("invalid [ toml")
    with pytest.raises(ConfigurationError, match="syntax error"):
        ZenzicConfig.load(tmp_path)


def test_load_config_missing_file_uses_defaults(tmp_path: Path) -> None:
    """When .zenzic.toml does not exist, defaults are returned silently."""
    config, loaded = ZenzicConfig.load(tmp_path)
    assert config.docs_dir == Path("docs")
    assert loaded is False


def test_load_config_custom_rules(tmp_path: Path) -> None:
    """[[custom_rules]] entries are parsed and available as CustomRuleConfig instances."""
    toml_content = """
[[custom_rules]]
id = "ZZ-NOINTERNAL"
pattern = "internal\\\\.corp"
message = "Internal hostname in docs."
severity = "error"

[[custom_rules]]
id = "ZZ-NODRAFT"
pattern = "(?i)\\\\bDRAFT\\\\b"
message = "Remove DRAFT marker."
severity = "warning"
"""
    (tmp_path / ".zenzic.toml").write_text(toml_content)
    config, loaded = ZenzicConfig.load(tmp_path)
    assert len(config.custom_rules) == 2
    assert config.custom_rules[0].id == "ZZ-NOINTERNAL"
    assert config.custom_rules[0].severity == "error"
    assert config.custom_rules[1].id == "ZZ-NODRAFT"
    assert config.custom_rules[1].severity == "warning"
    assert loaded is True


def test_load_config_plugins_list(tmp_path: Path) -> None:
    """plugins = [...] is parsed from .zenzic.toml."""
    (tmp_path / ".zenzic.toml").write_text("plugins = ['no-internal-hostname', 'acme-style']\n")
    config, loaded = ZenzicConfig.load(tmp_path)
    assert config.plugins == ["no-internal-hostname", "acme-style"]
    assert loaded is True


def test_placeholder_patterns_compiled_on_init(tmp_path: Path) -> None:
    """placeholder_patterns_compiled is populated automatically from placeholder_patterns."""
    config = ZenzicConfig(placeholder_patterns=[r"\btodo\b", r"\bwip\b"])
    assert len(config.placeholder_patterns_compiled) == 2
    assert config.placeholder_patterns_compiled[0].search("this is a TODO item")
    assert not config.placeholder_patterns_compiled[0].search("pseudotodo")
    assert config.placeholder_patterns_compiled[1].search("WIP section")
    assert not config.placeholder_patterns_compiled[1].search("wipe the floor")


def test_baseline_stale_days_defaults_to_none(tmp_path: Path) -> None:
    """baseline_stale_days is None when not set — Core's own constant is the fallback."""
    config, _ = ZenzicConfig.load(tmp_path)
    assert config.baseline_stale_days is None


def test_baseline_stale_days_loaded_from_zenzic_toml(tmp_path: Path) -> None:
    """baseline_stale_days overrides the Core default when set in .zenzic.toml."""
    (tmp_path / ".zenzic.toml").write_text("baseline_stale_days = 14\n")
    config, loaded = ZenzicConfig.load(tmp_path)
    assert config.baseline_stale_days == 14
    assert loaded is True


# ─── pyproject.toml support (ISSUE #5) ───────────────────────────────────────


def test_load_config_from_pyproject_toml(tmp_path: Path) -> None:
    """[tool.zenzic] in pyproject.toml is used when .zenzic.toml is absent."""
    (tmp_path / "pyproject.toml").write_text(
        "[tool.zenzic]\ndocs_dir = 'my_docs'\nfail_under = 75\n"
    )
    config, loaded = ZenzicConfig.load(tmp_path)
    assert config.docs_dir == Path("my_docs")
    assert config.fail_under == 75
    assert loaded is True


def test_load_config_pyproject_build_context(tmp_path: Path) -> None:
    """[tool.zenzic.build_context] is parsed correctly from pyproject.toml."""
    (tmp_path / "pyproject.toml").write_text(
        "[tool.zenzic]\n"
        "[tool.zenzic.build_context]\n"
        "engine = 'zensical'\n"
        "default_locale = 'en'\n"
        "locales = ['it']\n"
    )
    config, loaded = ZenzicConfig.load(tmp_path)
    assert config.build_context.engine == "zensical"
    assert config.build_context.locales == ["it"]
    assert loaded is True


def test_load_config_pyproject_custom_rules(tmp_path: Path) -> None:
    """[[tool.zenzic.custom_rules]] entries are parsed from pyproject.toml."""
    (tmp_path / "pyproject.toml").write_text(
        "[tool.zenzic]\n"
        "[[tool.zenzic.custom_rules]]\n"
        'id = "ZZ-PY"\n'
        'pattern = "TODO"\n'
        'message = "No TODOs."\n'
        'severity = "warning"\n'
    )
    config, loaded = ZenzicConfig.load(tmp_path)
    assert len(config.custom_rules) == 1
    assert config.custom_rules[0].id == "ZZ-PY"
    assert config.custom_rules[0].severity == "warning"
    assert loaded is True


def test_load_config_pyproject_plugins_list(tmp_path: Path) -> None:
    """plugins list is parsed from [tool.zenzic] in pyproject.toml."""
    (tmp_path / "pyproject.toml").write_text(
        "[tool.zenzic]\nplugins = ['no-internal-hostname', 'acme-style']\n"
    )
    config, loaded = ZenzicConfig.load(tmp_path)
    assert config.plugins == ["no-internal-hostname", "acme-style"]
    assert loaded is True


def test_load_config_zenzic_toml_wins_over_pyproject(tmp_path: Path) -> None:
    """.zenzic.toml takes priority over [tool.zenzic] in pyproject.toml."""
    (tmp_path / ".zenzic.toml").write_text("fail_under = 90\n")
    (tmp_path / "pyproject.toml").write_text("[tool.zenzic]\nfail_under = 42\n")
    config, loaded = ZenzicConfig.load(tmp_path)
    assert config.fail_under == 90  # .zenzic.toml wins
    assert loaded is True


def test_load_config_pyproject_without_tool_zenzic_uses_defaults(tmp_path: Path) -> None:
    """pyproject.toml without [tool.zenzic] falls back to built-in defaults."""
    (tmp_path / "pyproject.toml").write_text("[tool.other]\nfoo = 'bar'\n")
    config, loaded = ZenzicConfig.load(tmp_path)
    assert config.docs_dir == Path("docs")
    assert loaded is False


def test_load_config_invalid_pyproject_raises(tmp_path: Path) -> None:
    """A malformed pyproject.toml raises ConfigurationError — not silent fallback."""
    (tmp_path / "pyproject.toml").write_text("invalid [ toml")
    with pytest.raises(ConfigurationError, match="syntax error"):
        ZenzicConfig.load(tmp_path)


# ─── _apply_local_toml coverage ──────────────────────────────────────────────


def test_apply_local_toml_overrides_core_fields(tmp_path: Path) -> None:
    """[core] section in .zenzic.local.toml overrides docs_dir, strict, exit_zero, fail_under."""
    (tmp_path / ".zenzic.toml").write_text("docs_dir = 'docs'\n")
    (tmp_path / ".zenzic.local.toml").write_text(
        "[core]\ndocs_dir = 'local_docs'\nstrict = true\nexit_zero = true\nfail_under = 42\n"
    )
    config, _ = ZenzicConfig.load(tmp_path)
    assert config.docs_dir.as_posix() == "local_docs"
    assert config.strict is True
    assert config.exit_zero is True
    assert config.fail_under == 42


def test_apply_local_toml_overrides_build_context(tmp_path: Path) -> None:
    """[build_context] in .zenzic.local.toml is merged into config.build_context."""

    (tmp_path / ".zenzic.toml").write_text("docs_dir = 'docs'\n")
    (tmp_path / ".zenzic.local.toml").write_text(
        "[build_context]\nengine = 'mkdocs'\ndefault_locale = 'it'\n"
    )
    config, _ = ZenzicConfig.load(tmp_path)
    assert config.build_context.engine == "mkdocs"
    assert config.build_context.default_locale == "it"


def test_apply_local_toml_malformed_silently_skipped(tmp_path: Path) -> None:
    """A malformed .zenzic.local.toml is silently ignored — no exception raised."""
    (tmp_path / ".zenzic.toml").write_text("docs_dir = 'docs'\n")
    (tmp_path / ".zenzic.local.toml").write_text("invalid [ toml !!!")
    config, loaded = ZenzicConfig.load(tmp_path)
    assert config.docs_dir == Path("docs")
    assert loaded is True


def test_apply_local_toml_legacy_dev_toml_raises(tmp_path: Path) -> None:
    """.zenzic.dev.toml (legacy) must raise ConfigurationError."""
    (tmp_path / ".zenzic.dev.toml").write_text("# legacy\n")
    with pytest.raises(ConfigurationError, match="no longer supported"):
        ZenzicConfig.load(tmp_path)


def test_apply_local_toml_forbidden_patterns_merged(tmp_path: Path) -> None:
    """forbidden_patterns from [core], [governance], and top-level are merged additively."""
    (tmp_path / ".zenzic.toml").write_text("forbidden_patterns = ['secret-a']\n")
    (tmp_path / ".zenzic.local.toml").write_text(
        "forbidden_patterns = ['secret-b']\n[core]\nforbidden_patterns = ['secret-c']\n[governance]\nforbidden_patterns = ['secret-d']\n"
    )
    config, _ = ZenzicConfig.load(tmp_path)
    assert "secret-a" in config.forbidden_patterns
    assert "secret-b" in config.forbidden_patterns
    assert "secret-c" in config.forbidden_patterns
    assert "secret-d" in config.forbidden_patterns


def test_apply_local_toml_overrides_governance(tmp_path: Path) -> None:
    """[governance] in .zenzic.local.toml merges into config.governance."""
    (tmp_path / ".zenzic.toml").write_text(
        "docs_dir = 'docs'\n[governance]\nbrand_obsolescence = ['GlobalTerm']\n"
    )
    (tmp_path / ".zenzic.local.toml").write_text(
        "[governance]\nbrand_obsolescence = ['OldName']\nsuppression_cap = 10\n"
    )
    config, _ = ZenzicConfig.load(tmp_path)
    assert "OldName" in config.governance.brand_obsolescence
    assert "GlobalTerm" in config.governance.brand_obsolescence  # ADDITIVE: global preserved
    assert config.governance.suppression_cap == 10


def test_apply_local_toml_brand_obsolescence_additive(tmp_path: Path) -> None:
    """Local brand_obsolescence extends global — cannot remove global terms."""
    (tmp_path / ".zenzic.toml").write_text(
        "docs_dir = 'docs'\n[governance]\nbrand_obsolescence = ['TermA', 'TermB']\n"
    )
    (tmp_path / ".zenzic.local.toml").write_text("[governance]\nbrand_obsolescence = ['TermC']\n")
    config, _ = ZenzicConfig.load(tmp_path)
    assert "TermA" in config.governance.brand_obsolescence
    assert "TermB" in config.governance.brand_obsolescence
    assert "TermC" in config.governance.brand_obsolescence
    # No duplicates
    assert config.governance.brand_obsolescence.count("TermA") == 1


def test_apply_local_toml_excluded_dirs_additive(tmp_path: Path) -> None:
    """excluded_dirs from .zenzic.local.toml are merged additively with global dirs."""
    (tmp_path / ".zenzic.toml").write_text("docs_dir = 'docs'\nexcluded_dirs = ['legacy/']\n")
    (tmp_path / ".zenzic.local.toml").write_text("excluded_dirs = ['wip/']\n")
    config, _ = ZenzicConfig.load(tmp_path)
    assert "legacy/" in config.excluded_dirs
    assert "wip/" in config.excluded_dirs
    # SYSTEM_EXCLUDED_DIRS must remain intact (e.g. .venv is always excluded)
    from zenzic.models.config import SYSTEM_EXCLUDED_DIRS

    for sys_dir in SYSTEM_EXCLUDED_DIRS:
        assert sys_dir in config.excluded_dirs


def test_apply_local_toml_excluded_file_patterns_additive(tmp_path: Path) -> None:
    """excluded_file_patterns from .zenzic.local.toml are merged additively with global patterns."""
    (tmp_path / ".zenzic.toml").write_text(
        "docs_dir = 'docs'\nexcluded_file_patterns = ['*.log']\n"
    )
    (tmp_path / ".zenzic.local.toml").write_text("excluded_file_patterns = ['*.tmp']\n")
    config, _ = ZenzicConfig.load(tmp_path)
    assert "*.log" in config.excluded_file_patterns
    assert "*.tmp" in config.excluded_file_patterns


def test_apply_local_toml_custom_rules_additive(tmp_path: Path) -> None:
    """custom_rules from .zenzic.local.toml are merged additively; local overrides same-id rule."""
    global_toml = (
        "docs_dir = 'docs'\n"
        "[[custom_rules]]\n"
        'id = "ZZ-GLOBAL"\n'
        'pattern = "global-pattern"\n'
        'message = "Global rule."\n'
    )
    local_toml = (
        "[[custom_rules]]\n"
        'id = "ZZ-LOCAL"\n'
        'pattern = "local-pattern"\n'
        'message = "Local rule."\n'
        "[[custom_rules]]\n"
        'id = "ZZ-GLOBAL"\n'
        'pattern = "overridden-pattern"\n'
        'message = "Local override of global rule."\n'
    )
    (tmp_path / ".zenzic.toml").write_text(global_toml)
    (tmp_path / ".zenzic.local.toml").write_text(local_toml)
    config, _ = ZenzicConfig.load(tmp_path)
    ids = [r.id for r in config.custom_rules]
    assert "ZZ-GLOBAL" in ids
    assert "ZZ-LOCAL" in ids
    # Global rule base count: 1 (ZZ-GLOBAL) + 1 new local (ZZ-LOCAL) = 2 total
    assert len(config.custom_rules) == 2
    # Local override wins for ZZ-GLOBAL
    global_rule = next(r for r in config.custom_rules if r.id == "ZZ-GLOBAL")
    assert global_rule.pattern == "overridden-pattern"


# ─── ADR-012 namespace contract ──────────────────────────────────────────────


def test_custom_rule_id_namespace_rejects_core_codes(tmp_path: Path) -> None:
    """Custom rule IDs that collide with Core namespace (Z1xx–Z9xx) are rejected at load-time."""
    (tmp_path / ".zenzic.toml").write_text(
        "docs_dir = 'docs'\n"
        "[[custom_rules]]\n"
        'id = "Z101"\n'
        'pattern = "bad"\n'
        'message = "This should fail."\n'
    )
    with pytest.raises((ConfigurationError, Exception), match="ZZ-"):
        ZenzicConfig.load(tmp_path)


def test_custom_rule_id_namespace_rejects_lowercase_prefix(tmp_path: Path) -> None:
    """Lowercase 'zz-' prefix is rejected — namespace contract is strict case-sensitive."""
    (tmp_path / ".zenzic.toml").write_text(
        "docs_dir = 'docs'\n"
        "[[custom_rules]]\n"
        'id = "zz-mycheck"\n'
        'pattern = "bad"\n'
        'message = "This should fail."\n'
    )
    with pytest.raises((ConfigurationError, Exception), match="ZZ-"):
        ZenzicConfig.load(tmp_path)


def test_custom_rule_id_namespace_accepts_valid_prefix(tmp_path: Path) -> None:
    """Custom rule IDs starting with 'ZZ-' are accepted without error."""
    (tmp_path / ".zenzic.toml").write_text(
        "docs_dir = 'docs'\n"
        "[[custom_rules]]\n"
        'id = "ZZ-MYCHECK"\n'
        'pattern = "bad-word"\n'
        'message = "Do not use bad-word."\n'
    )
    config, _ = ZenzicConfig.load(tmp_path)
    assert len(config.custom_rules) == 1
    assert config.custom_rules[0].id == "ZZ-MYCHECK"


# ─── _build_from_data coverage ───────────────────────────────────────────────


def test_build_from_data_unknown_section_warning(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """Unknown dict-valued keys in .zenzic.toml emit a warning."""
    import logging

    (tmp_path / ".zenzic.toml").write_text("[unknown_section]\nfoo = 'bar'\n")
    with caplog.at_level(logging.WARNING, logger="zenzic"):
        ZenzicConfig.load(tmp_path)
    assert any("unknown section" in r.message for r in caplog.records)


def test_build_from_data_unknown_scalar_key_warning(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """Unknown scalar keys in .zenzic.toml emit a warning."""
    import logging

    (tmp_path / ".zenzic.toml").write_text("totally_unknown_key = 42\n")
    with caplog.at_level(logging.WARNING, logger="zenzic"):
        ZenzicConfig.load(tmp_path)
    assert any("unknown key" in r.message for r in caplog.records)


def test_validate_same_page_anchors_field_removed_from_model() -> None:
    """validate_same_page_anchors was a dead, never-read field; removed entirely
    rather than wired up, since the current (stricter-than-documented) behavior
    of always validating same-page anchors is the intended permanent behavior.
    """
    assert "validate_same_page_anchors" not in ZenzicConfig.model_fields


def test_validate_same_page_anchors_key_in_toml_is_ignored_with_warning(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """A .zenzic.toml still setting the removed key loads successfully (not a
    breaking config change) and is reported via the generic unknown-key warning.
    """
    import logging

    (tmp_path / ".zenzic.toml").write_text("validate_same_page_anchors = false\n")
    with caplog.at_level(logging.WARNING, logger="zenzic"):
        config, _ = ZenzicConfig.load(tmp_path)
    assert any(
        "unknown key" in r.message and "validate_same_page_anchors" in r.message
        for r in caplog.records
    )
    assert not hasattr(config, "validate_same_page_anchors")


def test_build_from_data_legacy_obsolete_names_migrated(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """[project_metadata].obsolete_names is migrated to [governance].brand_obsolescence."""
    import logging

    (tmp_path / ".zenzic.toml").write_text(
        "[project_metadata]\nobsolete_names = ['OldBrand', 'AnotherOld']\n"
    )
    with caplog.at_level(logging.WARNING, logger="zenzic"):
        config, _ = ZenzicConfig.load(tmp_path)
    assert "OldBrand" in config.governance.brand_obsolescence
    assert "AnotherOld" in config.governance.brand_obsolescence
    assert any("Deprecated" in r.message for r in caplog.records)


def test_build_from_data_unknown_section_warning_survives_rich_markup(
    tmp_path: Path,
) -> None:
    """The unknown-section warning must render intact through RichHandler(markup=True).

    Regression for: ``setup_cli_logging()`` attaches a ``RichHandler`` with
    ``markup=True`` (see ``core/logging.py``). The warning's ``[%s]``
    interpolation and its literal ``"[section]"`` text are both valid-looking
    Rich markup tags (e.g. ``[project]``, ``[section]``) — unescaped, Rich
    silently strips them instead of printing them, so the actual offending
    section name never reaches the user. ``caplog`` captures the raw log
    record before Rich rendering and cannot see this; this test renders
    through a real ``RichHandler`` to catch it.
    """
    import logging

    from rich.console import Console
    from rich.logging import RichHandler

    (tmp_path / ".zenzic.toml").write_text("[project]\nname = 'foo'\n")

    logger = logging.getLogger("zenzic")
    buf = StringIO()
    handler = RichHandler(
        console=Console(file=buf, no_color=True, width=200),
        show_time=False,
        show_path=False,
        markup=True,
    )
    logger.addHandler(handler)
    logger.setLevel(logging.WARNING)
    try:
        ZenzicConfig.load(tmp_path)
    finally:
        logger.removeHandler(handler)

    rendered = buf.getvalue()
    assert "[project]" in rendered, (
        f"Section name 'project' swallowed by Rich markup rendering, got:\n{rendered!r}"
    )
    assert "[section]" in rendered, (
        f"Literal '[section]' text swallowed by Rich markup rendering, got:\n{rendered!r}"
    )


def test_config_rejects_swallowed_root_keys(tmp_path: Path) -> None:
    """A root key placed after a table declaration is swallowed by TOML.

    The config loader must detect this and crash with a fatal error
    instead of silently ignoring the configuration.
    """
    toml_content = """\
[network]
cache_ttl_hours = 24
excluded_dirs = ["docs/"]
"""
    (tmp_path / ".zenzic.toml").write_text(toml_content)

    with pytest.raises(ConfigurationError, match="FATAL CONFIGURATION ERROR") as exc_info:
        ZenzicConfig.load(tmp_path)

    assert "excluded_dirs" in str(exc_info.value)
    assert "network" in str(exc_info.value)


def test_config_rejects_swallowed_root_keys_in_pyproject(tmp_path: Path) -> None:
    """Namespace isolation audit for pyproject.toml."""
    # Valid pyproject.toml: root keys under [tool.zenzic]
    valid_pyproject = """\
[tool.poetry]
name = "my-project"
[tool.zenzic]
excluded_dirs = ["docs/"]
[tool.zenzic.network]
cache_ttl_hours = 24
"""
    pyproject_file = tmp_path / "pyproject.toml"
    pyproject_file.write_text(valid_pyproject)

    config, loaded = ZenzicConfig.load(tmp_path)
    assert loaded is True
    assert "docs/" in config.excluded_dirs
    assert config.network.cache_ttl_hours == 24

    # Invalid pyproject.toml: root key swallowed by [tool.zenzic.network]
    invalid_pyproject = """\
[tool.poetry]
name = "my-project"
[tool.zenzic]
fail_under = 80
[tool.zenzic.network]
cache_ttl_hours = 24
excluded_dirs = ["docs/"]
"""
    pyproject_file.write_text(invalid_pyproject)

    with pytest.raises(ConfigurationError, match="FATAL CONFIGURATION ERROR") as exc_info:
        ZenzicConfig.load(tmp_path)

    assert "excluded_dirs" in str(exc_info.value)
    assert "network" in str(exc_info.value)


def test_config_raises_zenzic_config_error_on_swallowed_keys(tmp_path: Path) -> None:
    """Verify that a swallowed key error raises ZenzicConfigError with Z001 code."""
    from zenzic.core.exceptions import ZenzicConfigError

    toml_content = """\
[network]
cache_ttl_hours = 24
excluded_dirs = ["docs/"]
"""
    (tmp_path / ".zenzic.toml").write_text(toml_content)

    with pytest.raises(ZenzicConfigError) as exc_info:
        ZenzicConfig.load(tmp_path)

    assert exc_info.value.code == "Z001"
    assert "FATAL CONFIGURATION ERROR" in str(exc_info.value)


def test_config_raises_zenzic_config_error_on_validation_error(tmp_path: Path) -> None:
    """Verify that a validation error raises ZenzicConfigError with Z001 code."""
    from zenzic.core.exceptions import ZenzicConfigError

    # suppression_cap must be >= 0 (governed by ge=0)
    toml_content = """\
[governance]
suppression_cap = -10
"""
    (tmp_path / ".zenzic.toml").write_text(toml_content)

    with pytest.raises(ZenzicConfigError) as exc_info:
        ZenzicConfig.load(tmp_path)

    assert exc_info.value.code == "Z001"
    assert "Configuration validation failed" in str(exc_info.value)


def test_config_raises_zenzic_config_error_on_local_strict_keys(tmp_path: Path) -> None:
    """Verify that an unknown key in .zenzic.local.toml raises ZenzicConfigError with Z001 code."""
    from zenzic.core.exceptions import ZenzicConfigError

    (tmp_path / ".zenzic.toml").write_text("[core]\n")
    # Write an invalid key in local config
    (tmp_path / ".zenzic.local.toml").write_text("[rules.governance.banned_terms]\nfoo = 'bar'\n")

    with pytest.raises(ZenzicConfigError) as exc_info:
        ZenzicConfig.load(tmp_path)

    assert exc_info.value.code == "Z001"
    assert "[LOCAL-TOML-STRICT]" in str(exc_info.value)
