"""token-finops-cli: read-only, local-first token usage and budget-runway tracker for
AI coding agents (Copilot CLI, Claude Code, Codex CLI, Gemini CLI, Hermes Agent, ...)."""

from .cli import __version__, main

__all__ = ["main", "__version__"]
