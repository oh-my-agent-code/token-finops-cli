# token-finops-cli

A small, read-only CLI to keep an eye on your **GitHub Copilot CLI** token
usage and estimate a "runway" — how many days your monthly AI-unit budget
will last at your current burn rate.

It reads directly from the Copilot CLI's own local telemetry database
(`~/.copilot/session-store.db`, table `assistant_usage_events`) — no
external API calls, no scraping, nothing leaves your machine. The database
is opened in immutable/read-only mode so it can never interfere with a
live Copilot CLI session.

## Why

GitHub's Copilot usage-metrics REST API is enterprise-admin-only (requires
`manage_billing:copilot` / `read:enterprise` scopes) — there's no
individual-seat endpoint to query your own quota. This tool works around
that by reading the CLI's own local usage log and letting you supply your
own monthly budget number (from the Copilot billing page) so it can project
a runway estimate.

## Usage

```bash
python3 copilot_usage.py                      # full report, last 7 days
python3 copilot_usage.py --since 30d          # last 30 days
python3 copilot_usage.py --since all          # all-time
python3 copilot_usage.py --session <id>       # filter to one session

# Budget / runway
python3 copilot_usage.py --budget 50000 --cycle-day 1
python3 copilot_usage.py --compact            # 2-line minimal output
python3 copilot_usage.py --watch 5            # live-refreshing view every 5s
```

### Options

| Flag | Description |
|---|---|
| `--since {1d,7d,30d,all}` | Time window for the usage summary |
| `--session ID` | Filter to a single session |
| `--budget N` | Monthly AI-unit budget (default `50000`) — get this from your Copilot billing page |
| `--cycle-day N` | Day of month your billing cycle resets on (default `1`) |
| `--watch SECONDS` | Live-refreshing view, redraws every N seconds |
| `--compact` / `-c` | 2-line minimal output (budget bar + runway status) |
| `--verbose` / `-vv` | Full report (overrides `--compact`) |

## What it measures

The "AI unit" is GitHub's own cost/usage unit for a mixed
included-quota + pay-per-use Copilot plan, taken from the
`total_nano_aiu` column (divided by `1e9`) — this matches what's shown on
the Copilot billing page. It is **not** raw token counts.

## Requirements

- Python 3 (standard library only — no dependencies)
- GitHub Copilot CLI installed and used at least once (so
  `~/.copilot/session-store.db` exists)

## Optional: use as a Copilot CLI skill

You can drop a `SKILL.md` into `~/.copilot/skills/token-finops-cli/` so any
Copilot CLI session can answer "what's my usage/runway?" on demand by
invoking this script. See the CLI's skills documentation for the expected
format.

## License

AGPL-3.0 — see [LICENSE](LICENSE).
