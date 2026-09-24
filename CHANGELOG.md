# Changelog

All notable changes to `token-finops-cli` are documented here, in the format of
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [0.4.0] — 2026-09-24

### Security

- **Fixed a credential-leak bug in `--online`'s OpenRouter key lookup.** `openrouter_key()`
  searched a Hermes config for generic `api_key`/`apiKey` aliases anywhere in the file. Since
  Hermes is bring-your-own-provider, a config like `{"providers": {"openai": {"api_key":
  "sk-..."}, "openrouter": {}}}` would match the OpenAI key and send it to openrouter.ai as an
  `Authorization: Bearer` header. The generic aliases are now only trusted inside a sub-object
  reached via an `openrouter`-named key; the provider-specific aliases (`openrouter_api_key`,
  `openrouterApiKey`) are unaffected. Found in external review before release.

### Added

- **`token-finops doctor`** — per-adapter found/empty/missing diagnosis with the exact paths
  probed and one actionable hint each.
- **`--online`** on `report`/`status` — opt-in live quota fetchers for GitHub Copilot, Claude
  Code, Gemini CLI and Hermes (OpenRouter), stdlib `urllib` only, cached >= 180 s in
  `~/.token-finops/online-cache.json` (mode `0600`), hard-fail closed to the offline path on
  any error. `status --online` now reuses a still-fresh cache that was itself built with
  `--online` instead of forcing a full local rescan on every poll.
- **Configurable budget policy** — `~/.token-finops/config.json` + `TOKEN_FINOPS_*` env vars
  override `warn_at`/`critical_at`, the Copilot `cycle_day`, per-tool `allowance`, rolling
  `window_hours`, and a `default_tool` (exempting `doctor`, whose purpose is diagnosing every
  adapter at once). Precedence: explicit CLI flag > env var > config.json > hardcoded default;
  a real provider-reported reset time or usage percentage always outranks a configured
  fallback. See `docs/CONFIG.md` in the main project repo.
- **`token-finops savings --co2`** — an opt-in green-IT block comparing local (measured, from
  the chosen power tariff) against cloud (an explicitly labelled order-of-magnitude estimate)
  gCO2e per 1M tokens, with `--cloud-region` (validated against `energy.json`'s known regions).
- **`savings --own-hardware`** reframed as Hosting vs. Licensing — once a box is bought, capex
  is sunk; the comparison that matters is ongoing cost (energy + a flat, labelled
  `--management-overhead` assumption, default 10%) against paying per token/plan.
- A MacBook Pro 16" M4 Max, 48 GB hardware profile.

### Fixed

- **`self-audit` across Claude Code context-compaction boundaries** — a compacted session used
  to silently report as two disconnected totals; transcript segments sharing a session id are
  now stitched and deduplicated, with `segments: N` in the header.
- Copilot synthetic-data scale rebalanced to match real plan sizes.
- `parse_anthropic`'s fraction/percentage heuristic no longer misreads a genuine
  `used_percentage: 1` (1%) as 100% used — field name now picks the convention, and the <= 1
  heuristic is reserved for the genuinely ambiguous bare `utilization` field.
- `__version__` now reads from installed package metadata instead of a hand-maintained
  constant that had drifted to `0.3.0`.

## [0.3.0] — 2026-09-05

First release under the `token-finops-cli` name: 9 adapters (Copilot, Claude Code, Codex CLI,
Gemini CLI, Hermes Agent, OpenCode, Cline/Roo/Kilo, Aider, Continue.dev), a shared runway
engine, `self-audit`, and the local-vs-cloud `savings`/`break-even` estimator, grown out of the
original single-file Copilot budget script.
