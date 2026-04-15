#!/usr/bin/env python3
"""
fetch_ads.py — Facebook Marketing API data fetcher for CMR clinic.

Uses the entity endpoints (/campaigns, /ads) with nested insights — more reliable
than the /insights endpoint which has stricter field validation.

Usage:
    python fetch_ads.py \
        --start-date 2026-04-04 \
        --end-date 2026-04-10 \
        --level campaign|ad \
        --token <access_token> \
        --ad-account-id <act_XXXXXXX> \
        --output runs/2026-04-04_to_2026-04-10/campaigns.json
"""

import argparse
import json
import sys
import time
from datetime import datetime

try:
    import requests
except ImportError:
    print("ERROR: 'requests' library not found. Run: pip install requests", file=sys.stderr)
    sys.exit(1)

API_VERSION = "v19.0"
BASE_URL = f"https://graph.facebook.com/{API_VERSION}"

# Metrics fetched via nested insights — all valid on entity endpoints
INSIGHT_METRICS = "spend,impressions,reach,clicks,ctr,cpc,cpm,frequency,actions,cost_per_action_type"

CMR_ACTION_TYPES = {
    # WhatsApp / Messenger
    "onsite_conversion.messaging_conversation_started_7d": "wa_conversations",
    "onsite_conversion.messaging_first_reply": "messaging_first_reply",
    "onsite_conversion.messaging_welcome_message_view": "wa_welcome_views",
    "onsite_conversion.total_messaging_connection": "total_messaging",
    # Calls — Facebook uses these action types for click-to-call campaigns
    "click_to_call_native_call_placed": "calls_total",
    "click_to_call_native_20s_call_connect": "calls_20s",
    "click_to_call_native_60s_call_connect": "calls_60s",
    "click_to_call_call_confirm": "calls_confirmed",
    # Other
    "lead": "form_leads",
    "onsite_conversion.lead_grouped": "form_leads_grouped",
    "link_click": "link_clicks",
    "page_engagement": "page_engagement",
    "post_engagement": "post_engagement",
    "video_view": "video_views",
}


def build_params(access_token, start_date, end_date, level):
    """
    Build params for the entity endpoint (/campaigns or /ads).
    Uses insights.time_range(){...} syntax for date-filtered nested insights.
    """
    time_range = json.dumps({"since": start_date, "until": end_date}, separators=(",", ":"))

    if level == "campaign":
        fields = f"id,name,objective,effective_status,insights.time_range({time_range}){{{INSIGHT_METRICS}}}"
    else:
        fields = f"id,name,effective_status,adset_id,adset{{name}},campaign_id,campaign{{name,objective}},insights.time_range({time_range}){{{INSIGHT_METRICS}}}"

    return {
        "access_token": access_token,
        "fields": fields,
        "limit": 100,
    }


def make_url(base_url, params):
    """
    Build URL manually to avoid requests percent-encoding curly braces in
    the fields parameter — Facebook's field parser requires them unencoded.
    """
    import urllib.parse
    # Encode everything except the fields value
    fields = params.pop("fields", "")
    encoded = urllib.parse.urlencode(params)
    params["fields"] = fields  # restore for potential reuse
    return f"{base_url}?{encoded}&fields={fields}"


def paginate(url, params, retries=3):
    results = []
    first = True
    current_url = None

    while True:
        if first:
            current_url = make_url(url, dict(params))
            first = False

        for attempt in range(retries):
            try:
                resp = requests.get(current_url, timeout=30)
                data = resp.json()
                break
            except Exception as e:
                if attempt == retries - 1:
                    print(f"ERROR: Request failed: {e}", file=sys.stderr)
                    sys.exit(1)
                time.sleep(2 ** attempt)

        if "error" in data:
            err = data["error"]
            print(f"ERROR: Facebook API error {err.get('code')}: {err.get('message')}", file=sys.stderr)
            if err.get("code") == 190:
                print("  → Token expired. Refresh FACEBOOK_ACCESS_TOKEN in .env", file=sys.stderr)
            sys.exit(1)

        results.extend(data.get("data", []))

        next_url = data.get("paging", {}).get("next")
        if not next_url:
            break

        current_url = next_url

    return results


def extract_actions(insights):
    extracted = {v: 0 for v in CMR_ACTION_TYPES.values()}
    actions = insights.get("actions") or []
    cost_per = insights.get("cost_per_action_type") or []

    action_costs = {item["action_type"]: float(item.get("value", 0)) for item in cost_per}

    for action in actions:
        atype = action.get("action_type", "")
        val = float(action.get("value", 0))
        if atype in CMR_ACTION_TYPES:
            key = CMR_ACTION_TYPES[atype]
            extracted[key] = extracted.get(key, 0) + val

    # calls_60s and calls_20s now come directly from Facebook action types
    # (click_to_call_native_60s_call_connect / click_to_call_native_20s_call_connect)
    # No heuristic needed — real values are already mapped above
    extracted["cost_per_wa_conversation"] = action_costs.get(
        "onsite_conversion.messaging_conversation_started_7d", 0)
    extracted["cost_per_call"] = action_costs.get("click_to_call_native_call_placed", 0)
    return extracted


def compute_cpa(spend, actions):
    wa = actions.get("wa_conversations", 0)
    calls_60s = actions.get("calls_60s", 0)
    cpa_via_wa    = (spend / wa / 0.08)        if wa > 0        else None
    cpa_via_calls = (spend / calls_60s / 0.16) if calls_60s > 0 else None
    wa_appts    = wa * 0.08
    call_appts  = calls_60s * 0.16
    total_appts = wa_appts + call_appts
    cpa_blended = (spend / total_appts) if total_appts > 0 else None
    return {
        "cpa_via_wa":             round(cpa_via_wa, 2)    if cpa_via_wa    else None,
        "cpa_via_calls":          round(cpa_via_calls, 2) if cpa_via_calls else None,
        "cpa_blended":            round(cpa_blended, 2)   if cpa_blended   else None,
        "est_appointments_wa":    round(wa_appts, 2),
        "est_appointments_calls": round(call_appts, 2),
        "est_appointments_total": round(total_appts, 2),
    }


def normalize_record(record, level):
    # Nested insights data
    insights_list = record.get("insights", {}).get("data", [])
    ins = insights_list[0] if insights_list else {}

    # Skip records with no spend in this period
    spend = float(ins.get("spend", 0) or 0)

    impressions = int(ins.get("impressions", 0) or 0)
    reach       = int(ins.get("reach", 0) or 0)
    clicks      = int(ins.get("clicks", 0) or 0)
    frequency   = float(ins.get("frequency", 0) or 0)
    ctr         = float(ins.get("ctr", 0) or 0)
    cpm         = float(ins.get("cpm", 0) or 0)
    cpc         = float(ins.get("cpc", 0) or 0)

    actions = extract_actions(ins)
    cpa     = compute_cpa(spend, actions)

    base = {
        "level":       level,
        "spend":       round(spend, 2),
        "impressions": impressions,
        "reach":       reach,
        "clicks":      clicks,
        "frequency":   round(frequency, 2),
        "ctr":         round(ctr, 4),
        "cpm":         round(cpm, 2),
        "cpc":         round(cpc, 2),
        "status":      record.get("effective_status", "UNKNOWN"),
        **actions,
        **cpa,
    }

    if level == "campaign":
        base["campaign_id"] = record.get("id", "")
        base["name"]        = record.get("name", "")
        base["objective"]   = record.get("objective", "")
    else:
        base["ad_id"]        = record.get("id", "")
        base["name"]         = record.get("name", "")
        base["adset_id"]     = record.get("adset_id", "")
        base["adset_name"]   = record.get("adset", {}).get("name", "")
        base["campaign_id"]  = record.get("campaign_id", "")
        base["campaign_name"]= record.get("campaign", {}).get("name", "")
        base["objective"]    = record.get("campaign", {}).get("objective", "")

    return base


def compute_account_summary(records):
    if not records:
        return {}
    active = [r for r in records if r["spend"] > 0]
    total_spend       = sum(r["spend"] for r in active)
    total_wa          = sum(r.get("wa_conversations", 0) for r in active)
    total_calls_60s   = sum(r.get("calls_60s", 0) for r in active)
    total_impressions = sum(r.get("impressions", 0) for r in active)
    total_clicks      = sum(r.get("clicks", 0) for r in active)
    total_est_appts   = sum(r.get("est_appointments_total", 0) for r in active)

    avg_ctr = (total_clicks / total_impressions * 100) if total_impressions > 0 else 0
    avg_cpm = (total_spend / total_impressions * 1000) if total_impressions > 0 else 0
    cpa_blended       = (total_spend / total_est_appts)   if total_est_appts > 0   else None
    cost_per_wa       = (total_spend / total_wa)          if total_wa > 0          else None
    cost_per_call_60s = (total_spend / total_calls_60s)   if total_calls_60s > 0   else None

    return {
        "total_spend":               round(total_spend, 2),
        "total_wa_conversations":    int(total_wa),
        "total_calls_60s":           int(total_calls_60s),
        "total_impressions":         total_impressions,
        "total_clicks":              total_clicks,
        "avg_ctr":                   round(avg_ctr, 4),
        "avg_cpm":                   round(avg_cpm, 2),
        "total_est_appointments":    round(total_est_appts, 2),
        "account_cpa_blended":       round(cpa_blended, 2)       if cpa_blended       else None,
        "account_cost_per_wa":       round(cost_per_wa, 2)       if cost_per_wa       else None,
        "account_cost_per_call_60s": round(cost_per_call_60s, 2) if cost_per_call_60s else None,
        "account_cpa_via_wa":        round(cost_per_wa / 0.08, 2)       if cost_per_wa       else None,
        "account_cpa_via_calls":     round(cost_per_call_60s / 0.16, 2) if cost_per_call_60s else None,
    }


def main():
    parser = argparse.ArgumentParser(description="Fetch Facebook Ads data for CMR")
    parser.add_argument("--start-date",    required=True)
    parser.add_argument("--end-date",      required=True)
    parser.add_argument("--level",         required=True, choices=["campaign", "ad"])
    parser.add_argument("--token",         required=True)
    parser.add_argument("--ad-account-id", required=True)
    parser.add_argument("--output",        required=True)
    args = parser.parse_args()

    try:
        datetime.strptime(args.start_date, "%Y-%m-%d")
        datetime.strptime(args.end_date,   "%Y-%m-%d")
    except ValueError as e:
        print(f"ERROR: Invalid date format: {e}", file=sys.stderr)
        sys.exit(1)

    print(f"Fetching {args.level}-level data {args.start_date} → {args.end_date}...")

    endpoint = "campaigns" if args.level == "campaign" else "ads"
    account_id = args.ad_account_id if args.ad_account_id.startswith("act_") else f"act_{args.ad_account_id}"
    url    = f"{BASE_URL}/{account_id}/{endpoint}"
    params = build_params(args.token, args.start_date, args.end_date, args.level)
    raw    = paginate(url, params)

    # Normalize and filter to records with spend in this period
    records = [normalize_record(r, args.level) for r in raw]
    records_with_spend = [r for r in records if r["spend"] > 0]

    summary = compute_account_summary(records)

    output = {
        "meta": {
            "fetched_at":    datetime.utcnow().isoformat() + "Z",
            "start_date":    args.start_date,
            "end_date":      args.end_date,
            "level":         args.level,
            "ad_account_id": args.ad_account_id,
            "total_fetched": len(records),
            "with_spend":    len(records_with_spend),
        },
        "summary": summary,
        "records": records_with_spend,
    }

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"✓ {len(records_with_spend)}/{len(records)} {args.level}(s) had spend → {args.output}")
    print(f"  Total spend:       ${summary.get('total_spend', 0):,.2f}")
    print(f"  WA conversations:  {summary.get('total_wa_conversations', 0)}")
    print(f"  Calls (est. 60s):  {summary.get('total_calls_60s', 0)}")
    print(f"  Est. appointments: {summary.get('total_est_appointments', 0):.1f}")
    if summary.get("account_cpa_blended"):
        print(f"  Blended CPA:       ${summary['account_cpa_blended']:,.2f}/appointment")


if __name__ == "__main__":
    main()
