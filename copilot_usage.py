#!/usr/bin/env python3
"""Copilot CLI usage/efficiency summary.

Reads directly from the local session store's assistant_usage_events
table (~/.copilot/session-store.db) - this is the CLI's own local
telemetry, no external logs/network calls involved. Read-only (opened
in immutable/read-only mode to avoid any risk of corrupting the CLI's
live database while it's in use).

Also estimates a "runway" (days until a self-defined monthly AI-token
budget would run out at the current burn rate), based on the
`total_nano_aiu` column - GitHub's own cost/usage unit for a mixed
included-quota + pay-per-use Copilot plan (divide by 1e9 to get "AI
units" matching what's shown on the Copilot billing page). The budget
number itself is NOT fetched automatically (no API/scrape of the
billing page - that would need an authenticated browser session we
deliberately don't wire up here); it's a value you tell the script
yourself via --budget, defaulting to what you've told the agent
(50,000), and the cycle is assumed to reset monthly on --cycle-day
(default 1st) unless your actual billing cycle differs.

Usage:
    python3 copilot_usage.py [--since 1d|7d|30d|all] [--session <id>]
                              [--budget 50000] [--cycle-day 1]
"""
import argparse
import os
import sqlite3
from datetime import datetime, timedelta, timezone

DB_PATH = os.path.expanduser("~/.copilot/session-store.db")
DEFAULT_BUDGET_AIU = 50_000

SINCE_MAP = {
    "1d": timedelta(days=1),
    "7d": timedelta(days=7),
    "30d": timedelta(days=30),
    "all": None,
}


def connect_readonly(path):
    # Open read-only via URI so we never risk writing to the CLI's live DB.
    uri = f"file:{path}?mode=ro"
    return sqlite3.connect(uri, uri=True)


def fetch_stats(con, since_delta, session_id=None):
    where = []
    params = []
    if since_delta is not None:
        cutoff = (datetime.now(timezone.utc) - since_delta).isoformat()
        where.append("created_at >= ?")
        params.append(cutoff)
    if session_id:
        where.append("session_id = ?")
        params.append(session_id)
    where_clause = f"WHERE {' AND '.join(where)}" if where else ""

    query = f"""
        SELECT
            COUNT(*) AS requests,
            COALESCE(SUM(input_tokens), 0) AS total_input,
            COALESCE(SUM(output_tokens), 0) AS total_output,
            COALESCE(SUM(reasoning_tokens), 0) AS total_reasoning,
            COALESCE(AVG(duration_ms), 0) AS avg_duration_ms,
            COUNT(DISTINCT session_id) AS sessions
        FROM assistant_usage_events
        {where_clause}
    """
    cur = con.cursor()
    cur.execute(query, params)
    row = cur.fetchone()
    return {
        "requests": row[0],
        "total_input": row[1],
        "total_output": row[2],
        "total_reasoning": row[3],
        "avg_duration_ms": row[4],
        "sessions": row[5],
    }


def format_tokens(n):
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}k"
    return str(n)


def current_cycle_start(cycle_day, now=None):
    """First moment of the current billing cycle (assumed monthly, resetting
    on `cycle_day` of each month). If today's day-of-month is before
    cycle_day, the cycle started last month instead."""
    now = now or datetime.now(timezone.utc)
    year, month = now.year, now.month
    if now.day < cycle_day:
        month -= 1
        if month == 0:
            month, year = 12, year - 1
    return datetime(year, month, cycle_day, tzinfo=timezone.utc)


def fetch_cycle_aiu(con, cycle_start):
    cur = con.cursor()
    cur.execute(
        """
        SELECT COALESCE(SUM(total_nano_aiu), 0), COUNT(*)
        FROM assistant_usage_events
        WHERE created_at >= ?
        """,
        (cycle_start.isoformat(),),
    )
    total_nano, requests = cur.fetchone()
    return total_nano / 1e9, requests


def runway_report(con, budget, cycle_day):
    now = datetime.now(timezone.utc)
    cycle_start = current_cycle_start(cycle_day, now)
    used_aiu, requests = fetch_cycle_aiu(con, cycle_start)

    elapsed_days = max((now - cycle_start).total_seconds() / 86400, 1e-6)
    daily_rate = used_aiu / elapsed_days
    remaining_aiu = budget - used_aiu

    # Days left until the cycle itself resets (next reset date).
    next_reset_month = cycle_start.month + 1
    next_reset_year = cycle_start.year
    if next_reset_month == 13:
        next_reset_month, next_reset_year = 1, next_reset_year + 1
    next_reset = datetime(next_reset_year, next_reset_month, cycle_start.day, tzinfo=timezone.utc)
    days_left_in_cycle = (next_reset - now).total_seconds() / 86400

    if daily_rate > 0:
        runway_days = remaining_aiu / daily_rate
    else:
        runway_days = float("inf")

    cycle_length_days = max((next_reset - cycle_start).total_seconds() / 86400, 1e-6)
    cycle_fraction = 1 - (days_left_in_cycle / cycle_length_days)

    return {
        "cycle_start": cycle_start,
        "next_reset": next_reset,
        "used_aiu": used_aiu,
        "requests": requests,
        "daily_rate": daily_rate,
        "remaining_aiu": remaining_aiu,
        "runway_days": runway_days,
        "days_left_in_cycle": days_left_in_cycle,
        "cycle_fraction": cycle_fraction,
    }


def progress_bar(fraction, width=30):
    """Render a plain-ASCII progress bar (fraction clamped to [0, 1]).

    Deliberately uses only '#'/'-' rather than Unicode block characters
    (U+2588/U+2591) - some terminal fonts don't have glyphs for those and
    render them as blank space, making the bar invisible even though the
    rest of the line displays fine.
    """
    fraction = max(0.0, min(1.0, fraction))
    filled = int(round(width * fraction))
    bar = "#" * filled + "-" * (width - filled)
    return f"[{bar}] {fraction * 100:5.1f}%"


def render(args):
    con = connect_readonly(DB_PATH)
    stats = fetch_stats(con, SINCE_MAP[args.since], args.session)
    runway = runway_report(con, args.budget, args.cycle_day)
    con.close()

    total_tokens = stats["total_input"] + stats["total_output"]
    tok_per_req = total_tokens / stats["requests"] if stats["requests"] else 0
    out_in_ratio = (
        stats["total_output"] / stats["total_input"] if stats["total_input"] else 0
    )

    lines = []
    label = "all time" if args.since == "all" else f"last {args.since}"
    lines.append(f"Copilot CLI usage ({label}):")
    lines.append(f"  requests:        {stats['requests']}")
    lines.append(f"  sessions:        {stats['sessions']}")
    lines.append(f"  input tokens:    {format_tokens(stats['total_input'])}")
    lines.append(f"  output tokens:   {format_tokens(stats['total_output'])}")
    lines.append(f"  reasoning tokens:{format_tokens(stats['total_reasoning'])}")
    lines.append(f"  tokens/request:  {format_tokens(int(tok_per_req))}")
    lines.append(f"  output/input:    {out_in_ratio:.2f}")
    lines.append(f"  avg duration:    {stats['avg_duration_ms']/1000:.1f}s")

    # Compact status-bar style one-liner
    lines.append("")
    lines.append(
        f"\U0001F916 {stats['requests']} req  "
        f"\U0001FA99 {format_tokens(total_tokens)} tok  "
        f"\U0001F4C8 {format_tokens(int(tok_per_req))} tok/req  "
        f"\u23F1\uFE0F {stats['avg_duration_ms']/1000:.1f}s avg"
    )

    lines.append("")
    lines.append(f"Budget runway (cycle since {runway['cycle_start'].date()}, "
                  f"resets {runway['next_reset'].date()}):")
    used_fraction = runway["used_aiu"] / args.budget if args.budget else 0
    lines.append(f"  budget:  {progress_bar(used_fraction)}")
    lines.append(f"  used:            {runway['used_aiu']:.1f} / {args.budget:.0f} AI units"
                  f" ({runway['requests']} requests this cycle)")
    lines.append(f"  burn rate:       {runway['daily_rate']:.1f} AI units/day")
    if runway["runway_days"] == float("inf"):
        lines.append("  runway:          no usage yet this cycle, can't estimate")
    else:
        lines.append(f"  runway:          {runway['runway_days']:.1f} days at this rate")
        status = "OK" if runway["runway_days"] >= runway["days_left_in_cycle"] else "WILL RUN OUT EARLY"
        lines.append(f"  vs. {runway['days_left_in_cycle']:.1f} days left in cycle -> {status}")
        lines.append(f"  cycle time:  {progress_bar(runway['cycle_fraction'])}")

    if runway["runway_days"] != float("inf"):
        lines.append(f"\U0001F6E3\uFE0F  runway: {runway['runway_days']:.0f}d")

    return "\n".join(lines)


def render_compact(args):
    """Minimal 2-line render: just the budget progress bar and a one-line
    runway summary. Meant for tiny terminal panes (e.g. a 3-line split)
    where the full report would scroll/clip."""
    con = connect_readonly(DB_PATH)
    runway = runway_report(con, args.budget, args.cycle_day)
    con.close()

    used_fraction = runway["used_aiu"] / args.budget if args.budget else 0
    lines = [
        f"AI budget {progress_bar(used_fraction)} "
        f"{runway['used_aiu']:.0f}/{args.budget:.0f}",
    ]
    if runway["runway_days"] == float("inf"):
        lines.append("runway: no usage yet this cycle")
    else:
        status = "OK" if runway["runway_days"] >= runway["days_left_in_cycle"] else "RUNNING OUT EARLY"
        lines.append(
            f"\U0001F6E3\uFE0F  {runway['runway_days']:.0f}d runway "
            f"({runway['days_left_in_cycle']:.0f}d left in cycle) - {status}"
        )
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--since", choices=SINCE_MAP.keys(), default="7d")
    parser.add_argument("--session", default=None, help="Filter to one session_id")
    parser.add_argument(
        "--budget", type=float, default=DEFAULT_BUDGET_AIU,
        help=f"Monthly AI-unit budget for the runway estimate (default {DEFAULT_BUDGET_AIU})",
    )
    parser.add_argument(
        "--cycle-day", type=int, default=1,
        help="Day of month your billing cycle resets on (default 1st)",
    )
    parser.add_argument(
        "--watch", type=float, default=None, metavar="SECONDS",
        help="Keep running, redrawing the report every SECONDS (e.g. --watch 30). "
             "Meant for a spare terminal pane/tmux split, not the Copilot session itself.",
    )
    parser.add_argument(
        "--compact", "-c", action="store_true",
        help="Print only the budget progress bar + one-line runway summary "
             "(2 lines total) instead of the full report. Good for tiny "
             "terminal panes/splits.",
    )
    parser.add_argument(
        "--verbose", "-vv", action="store_true",
        help="Explicitly request the full report (this is the default; "
             "provided as the counterpart to --compact/-c).",
    )
    args = parser.parse_args()

    renderer = render_compact if (args.compact and not args.verbose) else render

    if args.watch is None:
        print(renderer(args))
        return

    import time
    try:
        while True:
            # Clear screen + move cursor home (ANSI), then redraw in place.
            print("\033[2J\033[H", end="")
            print(renderer(args))
            print(f"\n(refreshing every {args.watch:.0f}s, Ctrl+C to stop)")
            time.sleep(args.watch)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
