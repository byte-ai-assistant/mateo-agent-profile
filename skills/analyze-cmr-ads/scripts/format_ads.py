#!/usr/bin/env python3
"""
format_ads.py — Pre-processor for CMR Facebook Ads analysis.

Detects campaign types (CALL vs WHATSAPP) from campaign names,
groups by type and month, computes channel-specific KPIs,
and flags bad performers within each channel independently.

Usage:
    python format_ads.py \
        --campaigns /tmp/cmr_campaigns.json \
        --ads /tmp/cmr_ads.json \
        --output /tmp/cmr_processed.json
"""

import argparse
import json
import re
import sys
from datetime import datetime
from typing import Optional

# ── Month name mapping (Spanish and English) ─────────────────────────────────

MONTH_ORDER = {
    "enero": 1, "january": 1, "jan": 1,
    "febrero": 2, "february": 2, "feb": 2,
    "marzo": 3, "march": 3, "mar": 3,
    "abril": 4, "april": 4, "apr": 4,
    "mayo": 5, "may": 5,
    "junio": 6, "june": 6, "jun": 6,
    "julio": 7, "july": 7, "jul": 7,
    "agosto": 8, "august": 8, "aug": 8,
    "septiembre": 9, "september": 9, "sep": 9, "sept": 9,
    "octubre": 10, "october": 10, "oct": 10,
    "noviembre": 11, "november": 11, "nov": 11,
    "diciembre": 12, "december": 12, "dec": 12,
}

# ── Campaign type detection ───────────────────────────────────────────────────

def detect_campaign_type(campaign_name: str) -> str:
    """Detect CALL or WHATSAPP from campaign name."""
    name = campaign_name.upper()
    if "_CALL_" in name or "LLAMADA" in name or "CALL" in name:
        return "CALL"
    if "_WHATSAPP_" in name or "WHATSAPP" in name or "_WA_" in name or "MENSAJ" in name:
        return "WHATSAPP"
    return "UNKNOWN"


def detect_campaign_month(campaign_name: str) -> tuple[str, int, int]:
    """
    Parse month and year from campaign name.
    Returns (month_label, month_number, year)
    e.g. 'LEAD_CALL_ABRIL_2026' → ('ABRIL_2026', 4, 2026)
    """
    name_lower = campaign_name.lower()
    for month_str, month_num in MONTH_ORDER.items():
        if month_str in name_lower:
            # Try to extract year
            year_match = re.search(r'20\d{2}', campaign_name)
            year = int(year_match.group()) if year_match else 0
            return (f"{month_str.upper()}_{year}", month_num, year)
    return ("UNKNOWN", 0, 0)


# ── Benchmarks ───────────────────────────────────────────────────────────────

BENCHMARKS = {
    "CALL": {
        "cost_per_call_exceptional": 8.0,
        "cost_per_call_good": 15.0,
        "cost_per_call_acceptable": 25.0,
        "cost_per_call_60s_exceptional": 25.0,
        "cost_per_call_60s_good": 50.0,
        "ctr_good": 2.0,
        "ctr_exceptional": 3.5,
        "frequency_warning": 3.5,
        "frequency_critical": 4.0,
        "min_spend_significant": 50.0,
        "min_spend_loser": 100.0,
        "loser_multiplier": 2.0,
    },
    "WHATSAPP": {
        "cost_per_wa_exceptional": 8.0,
        "cost_per_wa_good": 12.0,
        "cost_per_wa_acceptable": 18.0,
        "ctr_good": 2.0,
        "ctr_exceptional": 3.5,
        "frequency_warning": 3.5,
        "frequency_critical": 4.0,
        "min_spend_significant": 30.0,
        "min_spend_loser": 50.0,
        "loser_multiplier": 2.0,
    },
}


# ── Per-record KPI computation ────────────────────────────────────────────────

def compute_call_kpis(record: dict) -> dict:
    spend = record.get("spend", 0)
    calls_total = record.get("calls_total", 0)
    calls_60s = record.get("calls_60s", 0)

    cost_per_call = (spend / calls_total) if calls_total > 0 else None
    cost_per_call_60s = (spend / calls_60s) if calls_60s > 0 else None

    # Appointment estimate (reference only, not primary KPI)
    est_appts = calls_60s * 0.16

    return {
        "primary_kpi": "calls",
        "calls_total": calls_total,
        "calls_60s": calls_60s,
        "cost_per_call": round(cost_per_call, 2) if cost_per_call else None,
        "cost_per_call_60s": round(cost_per_call_60s, 2) if cost_per_call_60s else None,
        "est_appointments": round(est_appts, 2),
        "has_conversions": calls_total > 0,
    }


def compute_whatsapp_kpis(record: dict) -> dict:
    spend = record.get("spend", 0)
    wa_conv = record.get("wa_conversations", 0)
    first_reply = record.get("messaging_first_reply", 0)

    cost_per_wa = (spend / wa_conv) if wa_conv > 0 else None
    reply_rate = (first_reply / wa_conv) if wa_conv > 0 else None

    # Appointment estimate (reference only, not primary KPI)
    est_appts = wa_conv * 0.08

    return {
        "primary_kpi": "wa_conversations",
        "wa_conversations": wa_conv,
        "messaging_first_reply": first_reply,
        "cost_per_wa_conversation": round(cost_per_wa, 2) if cost_per_wa else None,
        "reply_rate": round(reply_rate, 3) if reply_rate else None,
        "est_appointments": round(est_appts, 2),
        "has_conversions": wa_conv > 0,
    }


def rate_call_ad(record: dict, campaign_avg_cost_per_call: Optional[float]) -> dict:
    bench = BENCHMARKS["CALL"]
    spend = record.get("spend", 0)
    calls = record.get("calls_total", 0)
    calls_60s = record.get("calls_60s", 0)
    ctr = record.get("ctr", 0) * 100  # stored as fraction
    freq = record.get("frequency", 0)
    cost_per_call = record.get("cost_per_call")

    is_significant = spend >= bench["min_spend_significant"]

    # Flag as bad performer
    is_bad = False
    bad_reason = ""

    if spend >= bench["min_spend_loser"] and calls == 0:
        is_bad = True
        bad_reason = "gasto_sin_llamadas"
    elif campaign_avg_cost_per_call and cost_per_call and cost_per_call > campaign_avg_cost_per_call * bench["loser_multiplier"]:
        is_bad = True
        bad_reason = "costo_por_llamada_muy_alto"
    elif freq >= bench["frequency_critical"]:
        is_bad = True
        bad_reason = "fatiga_creativa"

    # Flag as top performer
    is_top = (
        is_significant and
        not is_bad and
        calls > 0 and
        (campaign_avg_cost_per_call is None or (cost_per_call and cost_per_call < campaign_avg_cost_per_call)) and
        freq < bench["frequency_warning"]
    )

    return {
        "is_significant": is_significant,
        "is_bad_performer": is_bad,
        "bad_reason": bad_reason,
        "is_top_performer": is_top,
        "frequency_status": (
            "fatiga_critica" if freq >= bench["frequency_critical"]
            else "fatiga_warning" if freq >= bench["frequency_warning"]
            else "ok"
        ),
    }


def rate_whatsapp_ad(record: dict, campaign_avg_cost_per_wa: Optional[float]) -> dict:
    bench = BENCHMARKS["WHATSAPP"]
    spend = record.get("spend", 0)
    wa = record.get("wa_conversations", 0)
    ctr = record.get("ctr", 0) * 100
    freq = record.get("frequency", 0)
    cost_per_wa = record.get("cost_per_wa_conversation")

    is_significant = spend >= bench["min_spend_significant"]

    is_bad = False
    bad_reason = ""

    if spend >= bench["min_spend_loser"] and wa == 0:
        is_bad = True
        bad_reason = "gasto_sin_conversaciones"
    elif campaign_avg_cost_per_wa and cost_per_wa and cost_per_wa > campaign_avg_cost_per_wa * bench["loser_multiplier"]:
        is_bad = True
        bad_reason = "costo_por_conversacion_muy_alto"
    elif freq >= bench["frequency_critical"]:
        is_bad = True
        bad_reason = "fatiga_creativa"

    is_top = (
        is_significant and
        not is_bad and
        wa > 0 and
        (campaign_avg_cost_per_wa is None or (cost_per_wa and cost_per_wa < campaign_avg_cost_per_wa)) and
        freq < bench["frequency_warning"]
    )

    return {
        "is_significant": is_significant,
        "is_bad_performer": is_bad,
        "bad_reason": bad_reason,
        "is_top_performer": is_top,
        "frequency_status": (
            "fatiga_critica" if freq >= bench["frequency_critical"]
            else "fatiga_warning" if freq >= bench["frequency_warning"]
            else "ok"
        ),
    }


# ── Group-level aggregation ───────────────────────────────────────────────────

def aggregate_campaign_group(ads: list[dict], campaign_type: str) -> dict:
    """Aggregate KPIs for a group of ads within the same campaign type+month."""
    total_spend = sum(a["spend"] for a in ads)

    if campaign_type == "CALL":
        total_calls = sum(a.get("calls_total", 0) for a in ads)
        total_calls_60s = sum(a.get("calls_60s", 0) for a in ads)
        cost_per_call = (total_spend / total_calls) if total_calls > 0 else None
        cost_per_call_60s = (total_spend / total_calls_60s) if total_calls_60s > 0 else None
        return {
            "spend": round(total_spend, 2),
            "calls_total": int(total_calls),
            "calls_60s": int(total_calls_60s),
            "cost_per_call": round(cost_per_call, 2) if cost_per_call else None,
            "cost_per_call_60s": round(cost_per_call_60s, 2) if cost_per_call_60s else None,
            "est_appointments": round(total_calls_60s * 0.16, 2),
        }
    else:  # WHATSAPP
        total_wa = sum(a.get("wa_conversations", 0) for a in ads)
        total_replies = sum(a.get("messaging_first_reply", 0) for a in ads)
        cost_per_wa = (total_spend / total_wa) if total_wa > 0 else None
        reply_rate = (total_replies / total_wa) if total_wa > 0 else None
        return {
            "spend": round(total_spend, 2),
            "wa_conversations": int(total_wa),
            "messaging_first_reply": int(total_replies),
            "cost_per_wa_conversation": round(cost_per_wa, 2) if cost_per_wa else None,
            "reply_rate": round(reply_rate, 3) if reply_rate else None,
            "est_appointments": round(total_wa * 0.08, 2),
        }


def compute_month_over_month(current: dict, previous: dict, campaign_type: str) -> dict:
    """Compute dollar-adjusted month-over-month comparison."""
    if not current or not previous:
        return {}

    if campaign_type == "CALL":
        cpl_curr = current.get("cost_per_call")
        cpl_prev = previous.get("cost_per_call")
        metric_label = "cost_per_call"
        volume_curr = current.get("calls_total", 0)
        volume_prev = previous.get("calls_total", 0)
        volume_label = "calls_total"
    else:
        cpl_curr = current.get("cost_per_wa_conversation")
        cpl_prev = previous.get("cost_per_wa_conversation")
        metric_label = "cost_per_wa_conversation"
        volume_curr = current.get("wa_conversations", 0)
        volume_prev = previous.get("wa_conversations", 0)
        volume_label = "wa_conversations"

    if not cpl_curr or not cpl_prev:
        return {"comparison_available": False, "reason": "insufficient_data"}

    delta_pct = (cpl_prev - cpl_curr) / cpl_prev * 100  # positive = improvement
    projected_volume = current["spend"] / cpl_prev  # what previous month's CPL would yield with current spend

    return {
        "comparison_available": True,
        "current_spend": current["spend"],
        "previous_spend": previous["spend"],
        f"current_{metric_label}": cpl_curr,
        f"previous_{metric_label}": cpl_prev,
        f"current_{volume_label}": volume_curr,
        f"previous_{volume_label}": volume_prev,
        "delta_pct": round(delta_pct, 1),
        "direction": "mejora" if delta_pct > 0 else "empeora",
        f"projected_{volume_label}_at_current_spend": round(projected_volume, 1),
        "actual_vs_projected": round(volume_curr - projected_volume, 1),
    }


# ── Main ──────────────────────────────────────────────────────────────────────

def load_json(path: str) -> dict:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"ERROR: File not found: {path}", file=sys.stderr)
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"ERROR: Invalid JSON in {path}: {e}", file=sys.stderr)
        sys.exit(1)


def tag_and_group_ads(ad_records):
    """Tag each ad with campaign type/month and group by (type, month_label)."""
    for ad in ad_records:
        cname = ad.get("campaign_name", "")
        ad["campaign_type"] = detect_campaign_type(cname)
        label, month_num, year = detect_campaign_month(cname)
        ad["campaign_month_label"] = label
        ad["campaign_month_num"] = month_num
        ad["campaign_year"] = year

    groups: dict = {}
    for ad in ad_records:
        key = f"{ad['campaign_type']}|{ad['campaign_month_label']}"
        if key not in groups:
            groups[key] = {
                "campaign_type": ad["campaign_type"],
                "month_label": ad["campaign_month_label"],
                "month_num": ad["campaign_month_num"],
                "year": ad["campaign_year"],
                "campaign_name": ad.get("campaign_name", ""),
                "ads": [],
            }
        groups[key]["ads"].append(ad)

    for group in groups.values():
        group["summary"] = aggregate_campaign_group(group["ads"], group["campaign_type"])

    return groups


def top_group(groups, campaign_type):
    """Return the most recent group for the given campaign type."""
    matching = sorted(
        [g for g in groups.values() if g["campaign_type"] == campaign_type],
        key=lambda g: (g["year"], g["month_num"]), reverse=True
    )
    return matching[0] if matching else None


def main():
    parser = argparse.ArgumentParser(description="Pre-process CMR ads data")
    parser.add_argument("--campaigns", required=True)
    parser.add_argument("--ads", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--prev-ads", help="Previous period ad-level JSON (correct date range for MoM comparison)")
    args = parser.parse_args()

    campaigns_data = load_json(args.campaigns)
    ads_data = load_json(args.ads)
    ad_records = ads_data.get("records", [])

    # ── Step 1-3: Tag and group current ads ───────────────────────────────────
    groups = tag_and_group_ads(ad_records)

    # ── Step 4: Identify current and previous month per type ──────────────────
    if args.prev_ads:
        # Previous period fetched separately with the correct date range
        prev_ad_records = load_json(args.prev_ads).get("records", [])
        prev_groups = tag_and_group_ads(prev_ad_records)

        current_call  = top_group(groups, "CALL")
        current_wa    = top_group(groups, "WHATSAPP")
        previous_call = top_group(prev_groups, "CALL")
        previous_wa   = top_group(prev_groups, "WHATSAPP")
    else:
        # Fallback: detect both months from current data (old behaviour)
        call_groups = sorted(
            [g for g in groups.values() if g["campaign_type"] == "CALL"],
            key=lambda g: (g["year"], g["month_num"]), reverse=True
        )
        wa_groups = sorted(
            [g for g in groups.values() if g["campaign_type"] == "WHATSAPP"],
            key=lambda g: (g["year"], g["month_num"]), reverse=True
        )
        current_call  = call_groups[0] if call_groups else None
        previous_call = call_groups[1] if len(call_groups) > 1 else None
        current_wa    = wa_groups[0] if wa_groups else None
        previous_wa   = wa_groups[1] if len(wa_groups) > 1 else None

    # ── Step 5: Month-over-month comparisons ─────────────────────────────────
    mom_call = compute_month_over_month(
        current_call["summary"] if current_call else {},
        previous_call["summary"] if previous_call else {},
        "CALL"
    )
    mom_wa = compute_month_over_month(
        current_wa["summary"] if current_wa else {},
        previous_wa["summary"] if previous_wa else {},
        "WHATSAPP"
    )

    # ── Step 6: Compute campaign-level averages for ad rating ─────────────────
    def get_avg_cost(group, campaign_type):
        if not group:
            return None
        s = group["summary"]
        if campaign_type == "CALL":
            return s.get("cost_per_call")
        return s.get("cost_per_wa_conversation")

    avg_cost_call = get_avg_cost(current_call, "CALL")
    avg_cost_wa = get_avg_cost(current_wa, "WHATSAPP")

    # ── Step 7: Enrich each ad with channel-specific KPIs and ratings ─────────
    enriched_ads = []
    for ad in ad_records:
        ctype = ad.get("campaign_type", "UNKNOWN")
        enriched = dict(ad)

        if ctype == "CALL":
            enriched.update(compute_call_kpis(ad))
            enriched.update(rate_call_ad(ad, avg_cost_call))
        elif ctype == "WHATSAPP":
            enriched.update(compute_whatsapp_kpis(ad))
            enriched.update(rate_whatsapp_ad(ad, avg_cost_wa))
        else:
            enriched["primary_kpi"] = "unknown"
            enriched["is_bad_performer"] = False
            enriched["is_top_performer"] = False

        enriched_ads.append(enriched)

    # ── Step 8: Segment bad/top performers by type ────────────────────────────
    call_ads = [a for a in enriched_ads if a.get("campaign_type") == "CALL"]
    wa_ads = [a for a in enriched_ads if a.get("campaign_type") == "WHATSAPP"]

    call_bad = sorted(
        [a for a in call_ads if a.get("is_bad_performer")],
        key=lambda a: -(a.get("spend", 0))
    )
    call_top = sorted(
        [a for a in call_ads if a.get("is_top_performer")],
        key=lambda a: (a.get("cost_per_call") or float("inf"))
    )
    wa_bad = sorted(
        [a for a in wa_ads if a.get("is_bad_performer")],
        key=lambda a: -(a.get("spend", 0))
    )
    wa_top = sorted(
        [a for a in wa_ads if a.get("is_top_performer")],
        key=lambda a: (a.get("cost_per_wa_conversation") or float("inf"))
    )
    fatigued = [a for a in enriched_ads if a.get("frequency_status") != "ok"]

    # ── Diagnostic: zero calls in call campaigns ──────────────────────────────
    zero_call_diagnosis = None
    if current_call:
        total_calls = current_call["summary"].get("calls_total", 0)
        total_spend = current_call["summary"].get("spend", 0)
        if total_spend > 100 and total_calls == 0:
            # Gather clues from the ads
            sample_ads = current_call["ads"][:3]
            avg_ctr = sum(a.get("ctr", 0) for a in sample_ads) / len(sample_ads) if sample_ads else 0
            total_link_clicks = sum(a.get("link_clicks", 0) for a in sample_ads)
            zero_call_diagnosis = {
                "alert": "CAMPAÑA_LLAMADAS_SIN_LLAMADAS",
                "spend": round(total_spend, 2),
                "avg_ctr_sample": round(avg_ctr * 100, 2),
                "link_clicks_sample": int(total_link_clicks),
                "hypothesis": (
                    "CTR razonable pero cero llamadas sugiere problema operacional: "
                    "verificar número de teléfono, configuración del botón CTA, "
                    "y que Facebook esté registrando el evento click_to_call correctamente."
                    if avg_ctr > 0.01 else
                    "CTR bajo y cero llamadas — posible problema combinado de creativo y configuración."
                ),
            }

    # ── Build output ──────────────────────────────────────────────────────────
    output = {
        "meta": {
            "processed_at": datetime.utcnow().isoformat() + "Z",
            "start_date": campaigns_data["meta"]["start_date"],
            "end_date": campaigns_data["meta"]["end_date"],
            "ad_account_id": campaigns_data["meta"]["ad_account_id"],
            "total_ads_analyzed": len(ad_records),
        },

        # Channel-separated summaries
        "call_campaigns": {
            "current_month": {
                "label": current_call["month_label"] if current_call else None,
                "campaign_name": current_call["campaign_name"] if current_call else None,
                "summary": current_call["summary"] if current_call else {},
            },
            "previous_month": {
                "label": previous_call["month_label"] if previous_call else None,
                "campaign_name": previous_call["campaign_name"] if previous_call else None,
                "summary": previous_call["summary"] if previous_call else {},
            },
            "month_over_month": mom_call,
            "avg_cost_per_call": avg_cost_call,
            "zero_call_diagnosis": zero_call_diagnosis,
            "top_performers": call_top,
            "bad_performers": call_bad,
            "all_ads": call_ads,
        },

        "whatsapp_campaigns": {
            "current_month": {
                "label": current_wa["month_label"] if current_wa else None,
                "campaign_name": current_wa["campaign_name"] if current_wa else None,
                "summary": current_wa["summary"] if current_wa else {},
            },
            "previous_month": {
                "label": previous_wa["month_label"] if previous_wa else None,
                "campaign_name": previous_wa["campaign_name"] if previous_wa else None,
                "summary": previous_wa["summary"] if previous_wa else {},
            },
            "month_over_month": mom_wa,
            "avg_cost_per_wa_conversation": avg_cost_wa,
            "top_performers": wa_top,
            "bad_performers": wa_bad,
            "all_ads": wa_ads,
        },

        "fatigued_ads": fatigued,

        "benchmarks": BENCHMARKS,

        "all_ads": enriched_ads,
    }

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    # Print summary
    print(f"✓ Processed data written to {args.output}")
    print(f"\n── LLAMADAS ({current_call['month_label'] if current_call else 'N/A'}) ──")
    if current_call:
        s = current_call["summary"]
        print(f"  Gasto:          ${s.get('spend', 0):,.2f}")
        print(f"  Llamadas:       {s.get('calls_total', 0)}")
        print(f"  Llamadas 60s+:  {s.get('calls_60s', 0)}")
        print(f"  Costo/llamada:  ${s.get('cost_per_call') or 'N/A'}")
        if mom_call.get("comparison_available"):
            print(f"  vs mes anterior: {mom_call['delta_pct']:+.1f}% ({mom_call['direction']})")
    if zero_call_diagnosis:
        print(f"  ⚠️  ALERTA: {zero_call_diagnosis['alert']}")
    print(f"  Bad performers: {len(call_bad)} | Top: {len(call_top)}")

    print(f"\n── MENSAJERÍA ({current_wa['month_label'] if current_wa else 'N/A'}) ──")
    if current_wa:
        s = current_wa["summary"]
        print(f"  Gasto:             ${s.get('spend', 0):,.2f}")
        print(f"  Conversaciones WA: {s.get('wa_conversations', 0)}")
        print(f"  Costo/conversación:${s.get('cost_per_wa_conversation') or 'N/A'}")
        if mom_wa.get("comparison_available"):
            print(f"  vs mes anterior:   {mom_wa['delta_pct']:+.1f}% ({mom_wa['direction']})")
    print(f"  Bad performers: {len(wa_bad)} | Top: {len(wa_top)}")
    print(f"\n  Fatigued ads: {len(fatigued)}")


if __name__ == "__main__":
    main()
