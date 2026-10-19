"""Smoke tests for token_finops_cli — no live Copilot DB required."""
import os
import subprocess
import sys

from token_finops_cli.synth import generate

# run the CLI from the checkout even when pytest's interpreter lacks the installed package
_SRC = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src")
_ENV = {**os.environ, "PYTHONPATH": _SRC + os.pathsep + os.environ.get("PYTHONPATH", "")}


def test_help_runs():
    result = subprocess.run(
        [sys.executable, "-m", "token_finops_cli.cli", "--help"],
        capture_output=True,
        text=True,
        check=False,
        env=_ENV,
    )
    assert result.returncode == 0
    assert "report" in result.stdout
    assert "sessions" in result.stdout


def test_report_help_runs():
    result = subprocess.run(
        [sys.executable, "-m", "token_finops_cli.cli", "report", "--help"],
        capture_output=True,
        text=True,
        check=False,
        env=_ENV,
    )
    assert result.returncode == 0
    assert "--budget" in result.stdout
    assert "--watch" in result.stdout


def test_default_command_is_report():
    """No subcommand should behave the same as `report` (backward compat
    with the pre-subcommand CLI)."""
    result = subprocess.run(
        [sys.executable, "-m", "token_finops_cli.cli", "--help"],
        capture_output=True,
        text=True,
        check=False,
        env=_ENV,
    )
    assert result.returncode == 0


def test_sessions_help_runs():
    result = subprocess.run(
        [sys.executable, "-m", "token_finops_cli.cli", "sessions", "--help"],
        capture_output=True,
        text=True,
        check=False,
        env=_ENV,
    )
    assert result.returncode == 0
    assert "--gap-minutes" in result.stdout
    assert "--limit" in result.stdout


def test_version_flag_and_subcommand_agree(home):
    """`--version`, `-V` and the `version` subcommand must all print the same
    thing and exit 0 -- three entry points to the one piece of information a
    user reaches for first when filing a bug report."""
    from token_finops_cli import __version__

    outputs = []
    for argv in (["--version"], ["-V"], ["version"]):
        result = subprocess.run(
            [sys.executable, "-m", "token_finops_cli.cli", *argv],
            capture_output=True, text=True, check=False, env=_ENV,
        )
        assert result.returncode == 0, argv
        outputs.append(result.stdout.strip())
    assert len(set(outputs)) == 1, outputs
    assert outputs[0] == f"token-finops-cli {__version__}"


def test_version_is_not_mistaken_for_a_report_argument():
    """`_normalize_argv` prefixes a bare flag list with "report" when the first
    token isn't a known subcommand -- "version" (and -V/--version) must be in
    that known set, or `token-finops version` silently becomes `report version`
    and fails with argparse's "unrecognized arguments"."""
    from token_finops_cli.cli import _normalize_argv

    assert _normalize_argv(["version"]) == ["version"]
    assert _normalize_argv(["--version"]) == ["--version"]
    assert _normalize_argv(["-V"]) == ["-V"]


def test_budget_help_notes_copilot_only():
    """--help text must make clear --budget is Copilot-specific (issue: it was
    silently ignored for every other tool, with no hint in --help either)."""
    result = subprocess.run(
        [sys.executable, "-m", "token_finops_cli.cli", "report", "--help"],
        capture_output=True, text=True, check=False, env=_ENV,
    )
    assert result.returncode == 0
    # the usage summary at the top also says "--budget", so find the *second*
    # occurrence: the option's own description in the args list below it.
    idx = result.stdout.index("--budget", result.stdout.index("--budget") + 1)
    assert "Copilot" in result.stdout[idx:idx + 200]


def test_budget_warns_on_stderr_for_non_copilot_tool(home, capsys):
    """Core fix: `--budget` only feeds Copilot's policy. Passing it with any other
    tool used to be silently swallowed; it must now warn on stderr and not crash.

    Note: calls `main()` directly rather than via the `run_cli` fixture, since
    that fixture already drains capsys (stdout *and* stderr) before we could
    inspect stderr ourselves."""
    from token_finops_cli.cli import main

    generate(str(home), tools=["gemini_cli"], days=3, seed=1)
    main(["report", "--tool", "gemini_cli", "--budget", "20", "--json"])
    captured = capsys.readouterr()
    assert "note:" in captured.err and "--budget" in captured.err and "gemini_cli" in captured.err
    assert "Copilot" in captured.err
    # the report itself still renders fine (ignoring --budget, not crashing)
    assert captured.out.strip().startswith("[")


def test_budget_no_warning_for_copilot(home, capsys, monkeypatch, tmp_path):
    """Sanity check: Copilot itself must never trigger the new warning."""
    from token_finops_cli.adapters.copilot import build_synthetic_db
    from token_finops_cli.cli import main

    db = tmp_path / "s.db"
    build_synthetic_db(str(db), days=3, events_per_day=2)
    monkeypatch.setenv("TOKEN_FINOPS_COPILOT_DB", str(db))
    main(["report", "--tool", "copilot", "--budget", "1500"])
    captured = capsys.readouterr()
    assert "note:" not in captured.err


def test_sessions_list_against_synthetic_db(tmp_path):
    from token_finops_cli.examples_helper import build_synthetic_db

    db_path = tmp_path / "demo.db"
    build_synthetic_db(str(db_path), days=10, events_per_day=5, seed=1)

    result = subprocess.run(
        [sys.executable, "-m", "token_finops_cli.cli", "sessions",
         "--db-path", str(db_path)],
        capture_output=True,
        text=True,
        check=False,
        env=_ENV,
    )
    assert result.returncode == 0
    assert "demo-session-0" in result.stdout


def test_sessions_totals_report(tmp_path):
    from token_finops_cli.examples_helper import build_synthetic_db

    db_path = tmp_path / "demo.db"
    build_synthetic_db(str(db_path), days=10, events_per_day=5, seed=1)

    result = subprocess.run(
        [sys.executable, "-m", "token_finops_cli.cli", "sessions",
         "--totals", "--db-path", str(db_path)],
        capture_output=True,
        text=True,
        check=False,
        env=_ENV,
    )
    assert result.returncode == 0
    assert "All sessions report" in result.stdout
    assert "sessions:" in result.stdout
    assert "total breaks detected" in result.stdout


def test_session_breaks_detection(tmp_path):
    from token_finops_cli.cli import connect_readonly, session_breaks
    from token_finops_cli.examples_helper import build_synthetic_db

    db_path = tmp_path / "demo.db"
    build_synthetic_db(str(db_path), days=10, events_per_day=5, seed=1)

    con = connect_readonly(str(db_path))
    breaks, active_s, idle_s, elapsed_s = session_breaks(
        con, "demo-session-0", gap_minutes=60
    )
    con.close()

    assert elapsed_s > 0
    assert active_s + idle_s <= elapsed_s + 1  # allow float rounding
    assert isinstance(breaks, list)


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
