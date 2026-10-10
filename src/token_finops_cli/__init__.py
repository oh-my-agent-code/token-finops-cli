"""token-finops-cli: read-only, local-first token usage and budget-runway tracker for
AI coding agents (Copilot CLI, Claude Code, Codex CLI, Gemini CLI, Hermes Agent, ...)."""

from importlib.metadata import PackageNotFoundError, version as _pkg_version

from .cli import main

try:
    __version__ = _pkg_version("token-finops-cli")
except PackageNotFoundError:
    # Not installed (e.g. running straight from a source checkout) -- keep this in
    # sync with pyproject.toml's [project].version by hand in that case only.
    __version__ = "0.4.0"
__all__ = ["main"]
