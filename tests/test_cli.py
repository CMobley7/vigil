"""Tests for the vigil CLI entry point."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from vigil.cli import app

runner = CliRunner()


class TestBriefCommand:
    """Tests for the 'vigil brief' subcommand."""

    @patch("vigil.cli.writer_main")
    def test_brief_calls_writer_main(self, mock_writer: MagicMock) -> None:
        result = runner.invoke(app, ["brief"])
        assert result.exit_code == 0
        mock_writer.assert_called_once()

    @patch("vigil.cli.writer_main", side_effect=SystemExit(1))
    def test_brief_propagates_exit_code(self, mock_writer: MagicMock) -> None:
        result = runner.invoke(app, ["brief"])
        assert result.exit_code == 1


class TestMonitorCommand:
    """Tests for the 'vigil monitor' subcommand."""

    @patch("vigil.cli.monitor_main")
    def test_monitor_calls_monitor_main(self, mock_monitor: MagicMock) -> None:
        result = runner.invoke(app, ["monitor"])
        assert result.exit_code == 0
        mock_monitor.assert_called_once()


class TestAppHelp:
    """Tests for the top-level CLI help."""

    def test_help_shows_app_description(self) -> None:
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "Vigilant Integrated Guidance" in result.stdout

    def test_help_lists_brief_command(self) -> None:
        result = runner.invoke(app, ["--help"])
        assert "brief" in result.stdout

    def test_help_lists_monitor_command(self) -> None:
        result = runner.invoke(app, ["--help"])
        assert "monitor" in result.stdout
