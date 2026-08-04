"""Smoke tests for token_finops_cli — no live Copilot DB required."""
import subprocess
import sys


def test_help_runs():
    result = subprocess.run(
        [sys.executable, "-m", "token_finops_cli.cli", "--help"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert "--budget" in result.stdout
    assert "--watch" in result.stdout


def test_progress_bar_bounds():
    from token_finops_cli.cli import progress_bar

    assert progress_bar(0.0).startswith("[")
    assert "100.0%" in progress_bar(1.5)  # clamps above 1
    assert "0.0%" in progress_bar(-0.5)  # clamps below 0


def test_format_tokens():
    from token_finops_cli.cli import format_tokens

    assert format_tokens(500) == "500"
    assert format_tokens(1_500) == "1.5k"
    assert format_tokens(2_000_000) == "2.0M"
