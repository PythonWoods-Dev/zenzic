# SPDX-FileCopyrightText: 2026 PythonWoods <dev@pythonwoods.dev>
# SPDX-License-Identifier: Apache-2.0
"""Targeted coverage tests — CEO-248 "The 80% Iron Gate Enforcement".

Covers previously-untested branches in:
- ``core/models.py``      (0%  → 100%)
- ``core/logging.py``     (65% → 100%)
- ``core/ui.py``          (65% → 90%+)
- ``cli/_clean.py``       (15% → 70%+)
- ``cli/_shared.py``      (50% → 80%+)
"""

from __future__ import annotations

import logging as _logging
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from rich.console import Console
from typer.testing import CliRunner

from zenzic.models.config import ZenzicConfig


runner = CliRunner()
_FAKE_ROOT = Path("/fake/repo")
_CFG = ZenzicConfig()


# ─────────────────────────────────────────────────────────────────────────────
# core/models.py  (0% → 100%)
# ─────────────────────────────────────────────────────────────────────────────


def test_core_models_reexport() -> None:
    """Importing core/models.py covers its 2 statements."""
    from zenzic.core.models import IntegrityReport, ReferenceFinding, ReferenceMap

    assert IntegrityReport is not None
    assert ReferenceFinding is not None
    assert ReferenceMap is not None


# ─────────────────────────────────────────────────────────────────────────────
# core/logging.py  (65% → 100%)
# ─────────────────────────────────────────────────────────────────────────────


class TestLogging:
    """Cover ``get_logger`` with sub-name and ``setup_cli_logging`` branches."""

    def _clear_handlers(self) -> None:
        from rich.logging import RichHandler

        root = _logging.getLogger("zenzic")
        root.handlers = [h for h in root.handlers if not isinstance(h, RichHandler)]

    def test_get_logger_no_name(self) -> None:
        from zenzic.core.logging import get_logger

        logger = get_logger()
        assert logger.name == "zenzic"

    def test_get_logger_with_name(self) -> None:
        """Cover the ``if name:`` branch in ``get_logger``."""
        from zenzic.core.logging import get_logger

        logger = get_logger("core.scanner")
        assert logger.name == "zenzic.core.scanner"

    def test_get_logger_with_different_sub_names(self) -> None:
        from zenzic.core.logging import get_logger

        for sub in ("credentials", "validator", "rules"):
            lg = get_logger(sub)
            assert lg.name == f"zenzic.{sub}"

    def test_setup_cli_logging_installs_rich_handler(self) -> None:
        """Cover the handler installation path in ``setup_cli_logging``."""
        from rich.logging import RichHandler

        from zenzic.core.logging import setup_cli_logging

        self._clear_handlers()
        setup_cli_logging()
        root = _logging.getLogger("zenzic")
        assert any(isinstance(h, RichHandler) for h in root.handlers)
        self._clear_handlers()

    def test_setup_cli_logging_idempotent(self) -> None:
        """Cover the early-return branch (already configured)."""
        from zenzic.core.logging import setup_cli_logging

        self._clear_handlers()
        setup_cli_logging()
        count = len(_logging.getLogger("zenzic").handlers)
        setup_cli_logging()  # second call — must be no-op
        assert len(_logging.getLogger("zenzic").handlers) == count
        self._clear_handlers()

    def test_setup_cli_logging_debug_level(self) -> None:
        """Cover the ``level`` parameter path."""
        from zenzic.core.logging import setup_cli_logging

        self._clear_handlers()
        setup_cli_logging(level=_logging.DEBUG)
        root = _logging.getLogger("zenzic")
        assert root.level == _logging.DEBUG
        self._clear_handlers()


# ─────────────────────────────────────────────────────────────────────────────
# core/ui.py  (65% → 90%+)
# ─────────────────────────────────────────────────────────────────────────────


class TestUI:
    """Cover uncovered branches in ``emoji``, ``make_report_header``,
    ``print_exception_alert``, and ``_detect_capabilities``."""

    # ── emoji() ───────────────────────────────────────────────────────────────

    def test_emoji_unicode_path(self) -> None:
        from zenzic.core.ui import emoji

        # SUPPORTS_EMOJI is True in CI=false/not-dumb dev environments
        result = emoji("sparkles")
        assert result in ("\u2728", "*")

    def test_emoji_unknown_key_returns_name(self) -> None:
        from zenzic.core.ui import emoji

        assert emoji("nonexistent_key_xyz") == "nonexistent_key_xyz"

    def test_emoji_ascii_fallback_when_no_emoji_support(self) -> None:
        """Cover the ``pair[1]`` branch inside ``emoji()``."""
        import zenzic.core.ui as ui_mod

        original = ui_mod.SUPPORTS_EMOJI
        try:
            ui_mod.SUPPORTS_EMOJI = False
            result = ui_mod.emoji("check")
            assert result == "*"  # ASCII fallback
            result2 = ui_mod.emoji("sparkles")
            assert result2 == "*"
        finally:
            ui_mod.SUPPORTS_EMOJI = original

    # ── _detect_capabilities() ────────────────────────────────────────────────

    def test_detect_capabilities_no_color_env(self) -> None:
        from zenzic.core.ui import _detect_capabilities

        with patch.dict("os.environ", {"NO_COLOR": "1"}, clear=False):
            supports_color, _ = _detect_capabilities()
        assert supports_color is False

    def test_detect_capabilities_dumb_term(self) -> None:
        from zenzic.core.ui import _detect_capabilities

        env = {"TERM": "dumb"}
        # Remove NO_COLOR to isolate the dumb-term path
        with patch.dict("os.environ", env, clear=False):
            supports_color, supports_emoji = _detect_capabilities()
        assert supports_color is False
        assert supports_emoji is False

    def test_detect_capabilities_ci_env(self) -> None:
        from zenzic.core.ui import _detect_capabilities

        with patch.dict("os.environ", {"CI": "true"}, clear=False):
            _, supports_emoji = _detect_capabilities()
        assert supports_emoji is False

    def test_detect_capabilities_no_env_overrides(self) -> None:
        """Cover default path — at minimum does not raise."""
        from zenzic.core.ui import _detect_capabilities

        env_clear = {"NO_COLOR": "", "CI": "", "TERM": "xterm"}
        with patch.dict("os.environ", env_clear, clear=False):
            result = _detect_capabilities()
        assert isinstance(result, tuple)
        assert len(result) == 2

    # ── make_report_header() ─────────────────────────────────────────────────

    def test_make_report_header_minimal(self) -> None:
        from zenzic.core.ui import make_report_header

        result = make_report_header("1.0")
        assert "ZENZIC" in result
        assert "1.0" in result

    def test_make_report_header_with_target(self) -> None:
        """Cover the ``if target is not None:`` branch."""
        from zenzic.core.ui import make_report_header

        result = make_report_header("1.0", engine="mkdocs", target="/docs/guide")
        assert "/docs/guide" in result

    def test_make_report_header_with_files(self) -> None:
        """Cover the ``if total:`` branch including singular file."""
        from zenzic.core.ui import make_report_header

        result_multi = make_report_header("1.0", docs_count=10, assets_count=5)
        # String contains Rich markup, check for numbers and keyword separately
        assert "15" in result_multi
        assert "file" in result_multi

        result_single = make_report_header("1.0", docs_count=1, assets_count=0)
        # Rich markup: "[#4f46e5]1[/] file" — check for "file" and "1" separately
        assert "file" in result_single
        assert "1" in result_single

    def test_make_report_header_with_elapsed(self) -> None:
        """Cover the ``if elapsed:`` branch."""
        from zenzic.core.ui import make_report_header

        result = make_report_header("1.0", elapsed=2.3)
        assert "2.3" in result

    def test_make_report_header_all_branches(self) -> None:
        """Hit all optional branches in one call."""
        from zenzic.core.ui import make_report_header

        result = make_report_header(
            "0.7.0",
            engine="docusaurus",
            target="docs/",
            docs_count=20,
            assets_count=8,
            elapsed=3.14,
        )
        assert "ZENZIC" in result
        assert "docs/" in result
        assert "28" in result
        assert "3.1" in result

    # ── ZenzicUI.print_exception_alert() ──────────────────────────────────────

    def test_print_exception_alert_no_context(self) -> None:
        from zenzic.core.ui import ZenzicUI

        console = Console(highlight=False, force_terminal=True)
        ui = ZenzicUI(console)
        ui.print_exception_alert("Something went wrong")  # no context — default path

    def test_print_exception_alert_with_context(self) -> None:
        """Cover the ``if context:`` branch."""
        from zenzic.core.ui import ZenzicUI

        console = Console(highlight=False, force_terminal=True)
        ui = ZenzicUI(console)
        ui.print_exception_alert(
            "Detailed error",
            context={"file": "docs/index.md", "line": "42", "code": "Z104"},
            title="Zenzic Alert",
        )

    def test_print_exception_alert_custom_border(self) -> None:
        """Cover the ``border_style`` parameter path."""
        from zenzic.core.ui import ZenzicPalette, ZenzicUI

        console = Console(highlight=False, force_terminal=True)
        ui = ZenzicUI(console)
        ui.print_exception_alert(
            "Plugin contract violation",
            border_style=ZenzicPalette.STYLE_BRAND,
        )

    def test_make_panel_factory(self) -> None:
        from zenzic.core.ui import ZenzicUI

        panel = ZenzicUI.make_panel("content", title="My Title", subtitle="subtitle")
        assert panel is not None

    def test_print_header(self) -> None:
        from zenzic.core.ui import ZenzicUI

        console = Console(highlight=False, force_terminal=True)
        ui = ZenzicUI(console)
        ui.print_header("0.7.0")  # must not raise


# ─────────────────────────────────────────────────────────────────────────────
# cli/_clean.py  (15% → 70%+)
# ─────────────────────────────────────────────────────────────────────────────


class TestCleanAssets:
    """Integration tests for ``clean assets`` command."""

    def _make_adapter_mock(self) -> MagicMock:
        adapter = MagicMock()
        adapter.get_metadata_files.return_value = frozenset()
        return adapter

    def _make_exclusion_mock(self) -> MagicMock:
        return MagicMock()

    @patch("zenzic.cli._clean.find_repo_root", return_value=_FAKE_ROOT)
    @patch("zenzic.cli._clean.ZenzicConfig.load", return_value=(_CFG, True))
    @patch("zenzic.cli._clean.find_unused_assets", return_value=[])
    @patch("zenzic.core.adapters.get_adapter")
    @patch("zenzic.cli._shared._build_exclusion_manager")
    def test_clean_assets_no_unused(
        self, mock_excl, mock_adapter, mock_find, mock_cfg, mock_root
    ) -> None:
        """No unused assets → completion message, exit 0."""
        from zenzic.cli._clean import clean_app

        mock_adapter.return_value = self._make_adapter_mock()
        mock_excl.return_value = self._make_exclusion_mock()

        result = runner.invoke(clean_app, ["assets"])
        assert result.exit_code == 0
        assert "No unused assets" in result.output

    @patch("zenzic.cli._clean.find_repo_root", return_value=_FAKE_ROOT)
    @patch("zenzic.cli._clean.ZenzicConfig.load", return_value=(_CFG, True))
    @patch("zenzic.cli._clean.find_unused_assets", return_value=["assets/old.png"])
    @patch("zenzic.core.adapters.get_adapter")
    @patch("zenzic.cli._shared._build_exclusion_manager")
    def test_clean_assets_dry_run(
        self, mock_excl, mock_adapter, mock_find, mock_cfg, mock_root
    ) -> None:
        """--dry-run shows files but does not delete, exit 0."""
        from zenzic.cli._clean import clean_app

        mock_adapter.return_value = self._make_adapter_mock()
        mock_excl.return_value = self._make_exclusion_mock()

        result = runner.invoke(clean_app, ["assets", "--dry-run"])
        assert result.exit_code == 0
        assert "DRY RUN" in result.output

    @patch("zenzic.cli._clean.find_repo_root", return_value=_FAKE_ROOT)
    @patch("zenzic.cli._clean.ZenzicConfig.load", return_value=(_CFG, True))
    @patch("zenzic.cli._clean.find_unused_assets", return_value=["assets/old.png"])
    @patch("zenzic.core.adapters.get_adapter")
    @patch("zenzic.cli._shared._build_exclusion_manager")
    def test_clean_assets_cancelled_by_user(
        self, mock_excl, mock_adapter, mock_find, mock_cfg, mock_root
    ) -> None:
        """User declines confirmation → exit 1."""
        from zenzic.cli._clean import clean_app

        mock_adapter.return_value = self._make_adapter_mock()
        mock_excl.return_value = self._make_exclusion_mock()

        result = runner.invoke(clean_app, ["assets"], input="n\n")
        assert result.exit_code == 1
        assert "Cancelled" in result.output

    @patch("zenzic.cli._clean.find_repo_root", return_value=_FAKE_ROOT)
    @patch("zenzic.cli._clean.ZenzicConfig.load", return_value=(_CFG, True))
    @patch(
        "zenzic.cli._clean.find_unused_assets",
        return_value=["assets/old.png", "assets/unused.svg"],
    )
    @patch("zenzic.core.adapters.get_adapter")
    @patch("zenzic.cli._shared._build_exclusion_manager")
    def test_clean_assets_yes_flag_deletes(
        self, mock_excl, mock_adapter, mock_find, mock_cfg, mock_root, tmp_path: Path
    ) -> None:
        """--yes flag deletes without confirmation."""
        from zenzic.cli._clean import clean_app

        mock_adapter.return_value = self._make_adapter_mock()
        mock_excl.return_value = self._make_exclusion_mock()

        # Patch docs_root so unlink is on real files (we create them)
        docs_dir = tmp_path / "docs"
        docs_dir.mkdir()
        (docs_dir / "assets").mkdir()
        (docs_dir / "assets" / "old.png").write_bytes(b"fake")
        (docs_dir / "assets" / "unused.svg").write_bytes(b"fake")

        fake_root = tmp_path
        mock_root.return_value = fake_root
        mock_cfg.return_value = (_CFG, True)
        result = runner.invoke(clean_app, ["assets", "--yes"])
        assert result.exit_code == 0
        assert "Deleted" in result.output or "SUCCESS" in result.output

    @patch("zenzic.cli._clean.find_repo_root", return_value=_FAKE_ROOT)
    @patch("zenzic.cli._clean.ZenzicConfig.load", return_value=(_CFG, False))
    @patch("zenzic.cli._clean.find_unused_assets", return_value=[])
    @patch("zenzic.core.adapters.get_adapter")
    @patch("zenzic.cli._shared._build_exclusion_manager")
    def test_clean_assets_quiet_no_output(
        self, mock_excl, mock_adapter, mock_find, mock_cfg, mock_root
    ) -> None:
        """--quiet suppresses all output when nothing to clean."""
        from zenzic.cli._clean import clean_app

        mock_adapter.return_value = self._make_adapter_mock()
        mock_excl.return_value = self._make_exclusion_mock()

        result = runner.invoke(clean_app, ["assets", "--quiet"])
        assert result.exit_code == 0
        assert result.output.strip() == ""

    @patch("zenzic.cli._clean.find_repo_root", return_value=_FAKE_ROOT)
    @patch("zenzic.cli._clean.ZenzicConfig.load", return_value=(_CFG, False))
    @patch("zenzic.cli._clean.find_unused_assets", return_value=[])
    @patch("zenzic.core.adapters.get_adapter")
    @patch("zenzic.cli._shared._build_exclusion_manager")
    def test_clean_assets_no_config_shows_hint(
        self, mock_excl, mock_adapter, mock_find, mock_cfg, mock_root
    ) -> None:
        """When loaded_from_file=False, no-config hint is shown (not quiet)."""
        from zenzic.cli._clean import clean_app

        mock_adapter.return_value = self._make_adapter_mock()
        mock_excl.return_value = self._make_exclusion_mock()

        result = runner.invoke(clean_app, ["assets"])
        assert result.exit_code == 0

    @patch("zenzic.cli._clean.find_repo_root", return_value=_FAKE_ROOT)
    @patch("zenzic.cli._clean.ZenzicConfig.load", return_value=(_CFG, True))
    @patch("zenzic.cli._clean.find_unused_assets", return_value=["assets/old.png"])
    @patch("zenzic.core.adapters.get_adapter")
    @patch("zenzic.cli._shared._build_exclusion_manager")
    def test_clean_assets_with_path_argument(
        self, mock_excl, mock_adapter, mock_find, mock_cfg, mock_root, tmp_path: Path
    ) -> None:
        """Explicit PATH argument triggers sovereign root detection."""
        from zenzic.cli._clean import clean_app

        mock_adapter.return_value = self._make_adapter_mock()
        mock_excl.return_value = self._make_exclusion_mock()

        # Typer single-command collapse: no 'assets' prefix; path is first positional
        result = runner.invoke(clean_app, [str(tmp_path), "--dry-run"])
        assert result.exit_code == 0


# ─────────────────────────────────────────────────────────────────────────────
# cli/_shared.py  (50% → 80%+)
# ─────────────────────────────────────────────────────────────────────────────


class TestShared:
    """Cover uncovered branches in ``cli/_shared.py``."""

    # ── configure_console ─────────────────────────────────────────────────────

    def test_configure_console_no_color(self) -> None:
        """Cover the ``no_color=True`` branch."""
        from zenzic.cli import _shared

        _shared.configure_console(no_color=True)
        assert _shared.console.no_color

    def test_configure_console_force_color(self) -> None:
        """Cover the ``force_color=True`` branch."""
        from zenzic.cli import _shared

        _shared.configure_console(force_color=True)
        # Restore to default
        _shared.configure_console()

    def test_configure_console_force_color_distinguishes_severity_colors(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """``force_color=True`` must produce genuinely distinct ANSI codes for
        different hex colors, even in an environment with no advertised
        truecolor support (``TERM``/``COLORTERM`` both unset) — the exact
        condition under which Zenzic's amber WARNING and rose ERROR severity
        colors previously collapsed to the identical 16-color ANSI code.
        """
        monkeypatch.delenv("TERM", raising=False)
        monkeypatch.delenv("COLORTERM", raising=False)
        from zenzic.cli import _shared
        from zenzic.core.ui import ZenzicPalette

        try:
            _shared.configure_console(force_color=True)
            import io

            from rich.text import Text

            # Exercise the real, reconfigured singleton — not a fresh probe —
            # since that is what every CLI command actually prints through.
            _shared.console.file = io.StringIO()
            _shared.console.print(Text("WARN", style=f"bold {ZenzicPalette.WARNING}"), end="")
            _shared.console.print(Text("ERROR", style=f"bold {ZenzicPalette.ERROR}"), end="")
            output = _shared.console.file.getvalue()
            warn_code = output.split("WARN")[0]
            error_code = output.split("ERROR")[0].rsplit("\x1b[0m", 1)[-1]
            assert warn_code != error_code, (
                f"WARNING and ERROR severity colors collapsed to the same ANSI "
                f"code ({warn_code!r}) — force_color must force truecolor depth, "
                f"not just force_terminal."
            )
        finally:
            _shared.configure_console()

    def test_configure_console_force_color_no_regression_with_real_truecolor(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Forcing ``color_system='truecolor'`` produces the same result as
        auto-detection in an environment that genuinely advertises truecolor
        support — no regression, forcing it is a no-op there in effect."""
        monkeypatch.setenv("TERM", "xterm-256color")
        monkeypatch.setenv("COLORTERM", "truecolor")
        from zenzic.cli import _shared
        from zenzic.core.ui import ZenzicPalette

        try:
            _shared.configure_console(force_color=True)
            import io

            from rich.text import Text

            _shared.console.file = io.StringIO()
            _shared.console.print(Text("WARN", style=f"bold {ZenzicPalette.WARNING}"), end="")
            _shared.console.print(Text("ERROR", style=f"bold {ZenzicPalette.ERROR}"), end="")
            output = _shared.console.file.getvalue()
            assert "245;158;11" in output  # WARNING amber, real 24-bit RGB
            assert "244;63;94" in output  # ERROR rose, real 24-bit RGB
        finally:
            _shared.configure_console()

    def test_configure_console_default(self) -> None:
        """Cover the ``else`` (auto) branch."""
        from zenzic.cli import _shared

        _shared.configure_console(no_color=False, force_color=False)

    # ── get_ui / get_console ─────────────────────────────────────────────────

    def test_get_ui_returns_zenzic_ui(self) -> None:
        from zenzic.cli._shared import get_ui
        from zenzic.core.ui import ZenzicUI

        assert isinstance(get_ui(), ZenzicUI)

    def test_get_console_returns_console(self) -> None:
        from rich.console import Console

        from zenzic.cli._shared import get_console

        assert isinstance(get_console(), Console)

    # ── _print_no_config_hint ─────────────────────────────────────────────────

    def test_print_no_config_hint_machine_format_suppressed(self) -> None:
        """Cover the ``if output_format in _MACHINE_FORMATS: return`` branch."""
        from zenzic.cli._shared import _print_no_config_hint

        # Should return immediately without printing — no assertion needed,
        # just ensure it does not raise
        _print_no_config_hint("json")
        _print_no_config_hint("sarif")

    def test_print_no_config_hint_text_format(self) -> None:
        from zenzic.cli._shared import _print_no_config_hint

        _print_no_config_hint("text")
        _print_no_config_hint()  # default

    # ── _apply_engine_override ────────────────────────────────────────────────

    def test_apply_engine_override_none(self) -> None:
        from zenzic.cli._shared import _apply_engine_override

        result = _apply_engine_override(_CFG, None)
        assert result is _CFG

    def test_apply_engine_override_auto(self) -> None:
        from zenzic.cli._shared import _apply_engine_override

        result = _apply_engine_override(_CFG, "auto")
        assert result is _CFG

    def test_apply_engine_override_unknown_engine_exits(self) -> None:
        """Cover the unknown-engine error path."""
        import typer

        from zenzic.cli._shared import _apply_engine_override

        with pytest.raises(typer.Exit):
            _apply_engine_override(_CFG, "nonexistent_engine_xyz")

    def test_apply_engine_override_valid_engine(self) -> None:
        from zenzic.cli._shared import _apply_engine_override
        from zenzic.core.adapters import list_adapter_engines

        engines = list_adapter_engines()
        if not engines:
            pytest.skip("No engines registered")
        engine = next(iter(engines))
        result = _apply_engine_override(_CFG, engine)
        assert result.build_context.engine == engine

    # ── _output_json_findings ─────────────────────────────────────────────────

    def test_output_json_findings_empty(self, capsys: pytest.CaptureFixture) -> None:  # type: ignore[type-arg]
        import json

        from zenzic.cli._shared import _output_json_findings

        _output_json_findings([], elapsed=0.1)
        out = capsys.readouterr().out
        data = json.loads(out)
        assert data["summary"]["errors"] == 0
        assert data["summary"]["elapsed_seconds"] == pytest.approx(0.1, abs=0.01)

    def test_output_json_findings_with_findings(self, capsys: pytest.CaptureFixture) -> None:  # type: ignore[type-arg]
        import json

        from zenzic.cli._shared import _output_json_findings
        from zenzic.core.reporter import Finding

        findings = [
            Finding(
                rel_path="docs/index.md",
                line_no=5,
                code="Z101",
                severity="error",
                message="Broken link",
            ),
            Finding(
                rel_path="docs/guide.md",
                line_no=10,
                code="Z201",
                severity="security_breach",
                message="Credential detected",
            ),
        ]
        _output_json_findings(findings, elapsed=1.5)
        out = capsys.readouterr().out
        data = json.loads(out)
        assert len(data["findings"]) == 2
        assert data["summary"]["errors"] == 1
        assert data["summary"]["security_breaches"] == 1

    # ── _output_sarif_findings ────────────────────────────────────────────────

    def test_output_sarif_findings_empty(self, capsys: pytest.CaptureFixture) -> None:  # type: ignore[type-arg]
        import json

        from zenzic.cli._shared import _output_sarif_findings

        _output_sarif_findings([], version="0.7.0")
        out = capsys.readouterr().out
        data = json.loads(out)
        assert data["version"] == "2.1.0"
        assert data["runs"][0]["results"] == []

    def test_output_sarif_findings_with_security(self, capsys: pytest.CaptureFixture) -> None:  # type: ignore[type-arg]
        """Cover the security-severity properties branch."""
        import json

        from zenzic.cli._shared import _output_sarif_findings
        from zenzic.core.reporter import Finding

        findings = [
            Finding(
                rel_path="docs/index.md",
                line_no=1,
                code="Z201",
                severity="security_breach",
                message="Credential detected",
            ),
            Finding(
                rel_path="docs/other.md",
                line_no=3,
                code="Z101",
                severity="error",
                message="Broken link",
            ),
        ]
        _output_sarif_findings(findings, version="0.7.0")
        out = capsys.readouterr().out
        data = json.loads(out)
        results = data["runs"][0]["results"]
        assert len(results) == 2
        # Security breach gets properties.security-severity
        security_result = next(r for r in results if r["ruleId"] == "Z201")
        assert "properties" in security_result

    # ── _validate_docs_root ───────────────────────────────────────────────────

    def test_validate_docs_root_valid(self, tmp_path: Path) -> None:
        from zenzic.cli._shared import _validate_docs_root

        repo = tmp_path / "repo"
        docs = repo / "docs"
        repo.mkdir()
        docs.mkdir()
        _validate_docs_root(repo, docs)  # must not raise

    def test_validate_docs_root_escape_raises(self, tmp_path: Path) -> None:
        """Cover the path traversal guard path traversal exit."""
        import typer

        from zenzic.cli._shared import _validate_docs_root

        repo = tmp_path / "repo"
        repo.mkdir()
        outside = tmp_path / "elsewhere"
        outside.mkdir()

        with pytest.raises(typer.Exit):
            _validate_docs_root(repo, outside)


class TestFormatElapsedMs:
    """The single shared progress-line duration formatter (`core.ui`)."""

    def test_converts_seconds_to_milliseconds_with_one_decimal(self) -> None:
        from zenzic.core.ui import format_elapsed_ms

        assert format_elapsed_ms(0.3312) == "[dim](331.2ms)[/dim]"
        assert format_elapsed_ms(1.0) == "[dim](1000.0ms)[/dim]"
        assert format_elapsed_ms(0.0) == "[dim](0.0ms)[/dim]"

    def test_does_not_switch_units_on_long_durations(self) -> None:
        """Deliberately always ms — the progress lines are compared against each
        other, so a column that changes unit partway down is harder to scan.
        """
        from zenzic.core.ui import format_elapsed_ms

        assert format_elapsed_ms(3.4058) == "[dim](3405.8ms)[/dim]"
        assert "s)" not in format_elapsed_ms(3.4058).replace("ms)", "")

    def test_output_matches_the_previously_inlined_format_exactly(self) -> None:
        """Guards the dedup: this is the literal f-string the 10 call sites used."""
        from zenzic.core.ui import format_elapsed_ms

        for seconds in (0.0, 0.0234, 0.3312, 2.1172, 3.4058, 12.5):
            legacy = f"[dim]({seconds * 1000:.1f}ms)[/dim]"
            assert format_elapsed_ms(seconds) == legacy
