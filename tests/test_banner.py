"""Brand intro is deterministic, optional and does not pollute machine CLI commands."""
from __future__ import annotations

from typer.testing import CliRunner

from prehnite.banner import TAGLINE, allow_ansi, banner, logo_lines
from prehnite.cli import app

runner = CliRunner()


def test_five_line_ascii_logo_is_complete_and_short():
    rows = logo_lines()
    assert len(rows) == 5
    assert all(line and len(line) <= 60 for line in rows)
    assert "####" in rows[0]
    assert TAGLINE in banner(color=False)
    assert "\x1b" not in banner(color=False)


def test_color_banner_uses_prehnite_coral_and_resets_terminal():
    text = banner(color=True)
    assert "\x1b[38;2;247;101;91m" in text
    assert text.count("\x1b[0m") == 2


def test_bare_prehnite_launch_has_logo_and_help():
    result = runner.invoke(app, [])
    assert result.exit_code == 0, result.output
    assert TAGLINE in result.output
    assert "prehnite init" in result.output
    assert "prehnite --help" in result.output


def test_machine_commands_and_help_do_not_print_logo(tmp_path):
    init = runner.invoke(app, ["init", "--destination", str(tmp_path / "sample")])
    help_ = runner.invoke(app, ["--help"])
    assert init.exit_code == 0, init.output
    assert help_.exit_code == 0, help_.output
    assert TAGLINE not in init.output
    assert TAGLINE not in help_.output
    assert "Created" in init.output


def test_opt_out_disables_ansi(monkeypatch):
    monkeypatch.setenv("PREHNITE_NO_BANNER", "1")
    assert allow_ansi() is False
