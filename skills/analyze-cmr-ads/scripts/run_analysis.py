#!/usr/bin/env python3
"""
run_analysis.py — One-command CMR ads analysis runner.

Creates a timestamped run folder under runs/ and orchestrates
fetch_ads.py + format_ads.py automatically.

Usage:
    python3 scripts/run_analysis.py --start-date 2026-04-04 --end-date 2026-04-10
    python3 scripts/run_analysis.py --last-7-days
    python3 scripts/run_analysis.py --last-30-days

Reads credentials from .env in the skill root directory.
Outputs to runs/YYYY-MM-DD_to_YYYY-MM-DD/
"""

import argparse
import calendar
import json
import os
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

# ── Resolve skill root (parent of scripts/) ───────────────────────────────────
SKILL_ROOT = Path(__file__).parent.parent.resolve()
SCRIPTS_DIR = SKILL_ROOT / "scripts"
RUNS_DIR = SKILL_ROOT / "runs"
ENV_FILE = SKILL_ROOT / ".env"


def load_env():
    """Load credentials from .env file in skill root."""
    env = {}
    if not ENV_FILE.exists():
        print(f"ERROR: .env file not found at {ENV_FILE}", file=sys.stderr)
        print(f"  Create it with:", file=sys.stderr)
        print(f"    FACEBOOK_ACCESS_TOKEN=your_token", file=sys.stderr)
        print(f"    CMR_AD_ACCOUNT_ID=act_xxxxx", file=sys.stderr)
        sys.exit(1)

    for line in ENV_FILE.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, val = line.partition("=")
            env[key.strip()] = val.strip().strip('"').strip("'")

    for required in ["FACEBOOK_ACCESS_TOKEN", "CMR_AD_ACCOUNT_ID"]:
        if required not in env:
            print(f"ERROR: {required} missing from .env", file=sys.stderr)
            sys.exit(1)

    return env


def compute_previous_period(start_date_str, end_date_str, full_prev_month=False):
    """
    Return (prev_start, prev_end) shifted one month back.

    full_prev_month=True  → return the complete previous calendar month (used with --this-month)
    full_prev_month=False → return the same day numbers in the previous month
    """
    from datetime import date as date_type
    start = datetime.strptime(start_date_str, "%Y-%m-%d").date()
    end   = datetime.strptime(end_date_str,   "%Y-%m-%d").date()

    prev_month = start.month - 1 if start.month > 1 else 12
    prev_year  = start.year      if start.month > 1 else start.year - 1

    if full_prev_month:
        prev_start = date_type(prev_year, prev_month, 1)
        prev_end   = date_type(prev_year, prev_month, calendar.monthrange(prev_year, prev_month)[1])
    else:
        max_start_day = calendar.monthrange(prev_year, prev_month)[1]
        prev_start = date_type(prev_year, prev_month, min(start.day, max_start_day))

        end_prev_month = end.month - 1 if end.month > 1 else 12
        end_prev_year  = end.year      if end.month > 1 else end.year - 1
        max_end_day = calendar.monthrange(end_prev_year, end_prev_month)[1]
        prev_end = date_type(end_prev_year, end_prev_month, min(end.day, max_end_day))

    return str(prev_start), str(prev_end)


def resolve_dates(args):
    today = datetime.now().date()
    yesterday = today - timedelta(days=1)

    if args.last_7_days:
        return str(today - timedelta(days=7)), str(yesterday)
    if args.last_30_days:
        return str(today - timedelta(days=30)), str(yesterday)
    if args.this_month:
        return str(today.replace(day=1)), str(yesterday)
    if args.start_date and args.end_date:
        return args.start_date, args.end_date

    # Default: last 7 days
    return str(today - timedelta(days=7)), str(yesterday)


def run(cmd, label):
    """Run a subprocess command, streaming output."""
    print(f"\n── {label} ──────────────────────────────")
    result = subprocess.run(cmd, capture_output=False, text=True)
    if result.returncode != 0:
        print(f"ERROR: {label} failed (exit {result.returncode})", file=sys.stderr)
        sys.exit(result.returncode)


def main():
    parser = argparse.ArgumentParser(description="Run CMR Facebook Ads analysis pipeline")
    date_group = parser.add_mutually_exclusive_group()
    date_group.add_argument("--last-7-days",  action="store_true", help="Last 7 days (default)")
    date_group.add_argument("--last-30-days", action="store_true", help="Last 30 days")
    date_group.add_argument("--this-month",   action="store_true", help="Current month to date")
    parser.add_argument("--start-date", help="Custom start date YYYY-MM-DD")
    parser.add_argument("--end-date",   help="Custom end date YYYY-MM-DD")
    args = parser.parse_args()

    env = load_env()
    token      = env["FACEBOOK_ACCESS_TOKEN"]
    account_id = env["CMR_AD_ACCOUNT_ID"]

    start_date, end_date = resolve_dates(args)

    # Previous period: same day range one month back; full prev month for --this-month
    is_full_month = bool(args.this_month)
    prev_start_date, prev_end_date = compute_previous_period(start_date, end_date, full_prev_month=is_full_month)

    # Create timestamped run folder
    run_name = f"{start_date}_to_{end_date}"
    run_dir  = RUNS_DIR / run_name
    run_dir.mkdir(parents=True, exist_ok=True)

    campaigns_file      = run_dir / "campaigns.json"
    ads_file            = run_dir / "ads.json"
    prev_campaigns_file = run_dir / "prev_campaigns.json"
    prev_ads_file       = run_dir / "prev_ads.json"
    processed_file      = run_dir / "processed.json"

    print(f"📁 Run folder:       {run_dir}")
    print(f"📅 Current period:   {start_date} → {end_date}")
    print(f"📅 Previous period:  {prev_start_date} → {prev_end_date}")

    fetch_script  = str(SCRIPTS_DIR / "fetch_ads.py")
    format_script = str(SCRIPTS_DIR / "format_ads.py")

    # Step 1: Current period — campaign-level fetch
    run([
        sys.executable, fetch_script,
        "--start-date",    start_date,
        "--end-date",      end_date,
        "--level",         "campaign",
        "--token",         token,
        "--ad-account-id", account_id,
        "--output",        str(campaigns_file),
    ], f"Fetching current campaign data ({start_date} → {end_date})")

    # Step 2: Current period — ad-level fetch
    run([
        sys.executable, fetch_script,
        "--start-date",    start_date,
        "--end-date",      end_date,
        "--level",         "ad",
        "--token",         token,
        "--ad-account-id", account_id,
        "--output",        str(ads_file),
    ], f"Fetching current ad data ({start_date} → {end_date})")

    # Step 3: Previous period — campaign-level fetch
    run([
        sys.executable, fetch_script,
        "--start-date",    prev_start_date,
        "--end-date",      prev_end_date,
        "--level",         "campaign",
        "--token",         token,
        "--ad-account-id", account_id,
        "--output",        str(prev_campaigns_file),
    ], f"Fetching previous campaign data ({prev_start_date} → {prev_end_date})")

    # Step 4: Previous period — ad-level fetch
    run([
        sys.executable, fetch_script,
        "--start-date",    prev_start_date,
        "--end-date",      prev_end_date,
        "--level",         "ad",
        "--token",         token,
        "--ad-account-id", account_id,
        "--output",        str(prev_ads_file),
    ], f"Fetching previous ad data ({prev_start_date} → {prev_end_date})")

    # Step 5: Pre-process
    format_cmd = [
        sys.executable, format_script,
        "--campaigns", str(campaigns_file),
        "--ads",       str(ads_file),
        "--prev-ads",  str(prev_ads_file),
        "--output",    str(processed_file),
    ]
    run(format_cmd, "Pre-processing & computing CPA")

    # Step 4: Print summary
    print(f"\n✅ Analysis complete → {processed_file}")
    with open(processed_file) as f:
        data = json.load(f)

    s = data.get("account_summary", {})
    seg = data.get("segments", {})
    print(f"\n{'─'*40}")
    print(f"  Spend:            ${s.get('total_spend', 0):,.2f}")
    print(f"  WA conversations: {s.get('total_wa_conversations', 0)}")
    print(f"  Calls (est. 60s): {s.get('total_calls_60s', 0)}")
    print(f"  Est. appointments:{s.get('total_est_appointments', 0):.1f}")
    if s.get("account_cpa_blended"):
        print(f"  Blended CPA:      ${s['account_cpa_blended']:,.2f}/appointment")
    print(f"  Winners:          {seg.get('winners_count', 0)}")
    print(f"  Losers:           {seg.get('losers_count', 0)}")
    print(f"  Fatigued:         {seg.get('fatigued_count', 0)}")
    print(f"{'─'*40}")
    print(f"\nPaste {processed_file} contents into Claude to get the full analysis.")


if __name__ == "__main__":
    main()
