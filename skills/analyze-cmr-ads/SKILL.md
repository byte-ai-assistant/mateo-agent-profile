---
name: analyze-cmr-ads
description: Analyze Facebook Ads campaign performance for CMR clinic and deliver expert-level, actionable insights in Spanish. Use this skill whenever the user asks to analyze, review, check, or report on CMR Facebook ads, campaign performance, ad spend, leads, WhatsApp connections, calls, CPA, or any ad-related metric — even if they phrase it casually like "how are the ads doing?" or "run the weekly report".
version: 3.0.0
allowed-tools: Bash, Read, Write
---

# Analyze CMR Ads

Expert Facebook Ads analysis for Centro de Medicina Regenerativa.

CMR always runs two campaign types in parallel:
- **LEAD_CALL_[MES]_[AÑO]** — optimized for phone calls
- **LEAD_WHATSAPP_[MES]_[AÑO]** — optimized for WhatsApp/Messenger conversations

These are analyzed SEPARATELY. Never compare calls vs messages. Each channel has its own KPIs and its own month-over-month benchmark.

---

## Directory Structure

```
analyze-cmr-ads-skill/
├── .env                  ← FACEBOOK_ACCESS_TOKEN, CMR_AD_ACCOUNT_ID
├── SKILL.md
├── scripts/
│   ├── run_analysis.py   ← ONE-COMMAND runner
│   ├── fetch_ads.py      ← Facebook API fetcher
│   └── format_ads.py     ← Channel-aware pre-processor
├── references/
│   ├── analysis-framework.md  ← Expert analysis rules
│   ├── benchmarks.md          ← Channel-specific benchmarks
│   └── report-template.md     ← Spanish report template
└── runs/
    └── YYYY-MM-DD_to_YYYY-MM-DD/
        ├── campaigns.json
        ├── ads.json
        └── processed.json
```

---

## Prerequisites

- Python 3.8+, `requests` (`pip install requests`)
- `.env` in skill root:
  ```
  FACEBOOK_ACCESS_TOKEN=your_token
  CMR_AD_ACCOUNT_ID=act_1190857712929052
  ```

---

## Workflow

### Step 1 — Determine Date Range

| User says | Flag |
|---|---|
| "last 7 days" / "esta semana" / no date | `--last-7-days` |
| "last 30 days" / "este mes" | `--last-30-days` |
| "this month" | `--this-month` |
| Explicit dates | `--start-date ... --end-date ...` |

**Important:** To get month-over-month comparison, the date range must cover both the current AND previous month campaigns. If the user asks for "this week" but the previous month's campaign is still running (common in early month), the processed.json will detect both automatically from campaign names.

### Step 2 — Run Pipeline

```bash
cd /path/to/analyze-cmr-ads-skill
python3 scripts/run_analysis.py --last-7-days
```

Output → `runs/YYYY-MM-DD_to_YYYY-MM-DD/processed.json`

### Step 3 — Read and Analyze

```bash
Read {run_dir}/processed.json
```

Then load references:
- Read `{baseDir}/references/analysis-framework.md`
- Read `{baseDir}/references/benchmarks.md`

Apply the framework channel by channel. Use `processed.json` fields:
- `call_campaigns.current_month` + `call_campaigns.previous_month` → MoM LLAMADAS
- `whatsapp_campaigns.current_month` + `whatsapp_campaigns.previous_month` → MoM MENSAJERÍA
- `call_campaigns.bad_performers` → losers en LLAMADAS
- `whatsapp_campaigns.bad_performers` → losers en MENSAJERÍA
- `call_campaigns.top_performers` → ganadores en LLAMADAS
- `whatsapp_campaigns.top_performers` → ganadores en MENSAJERÍA
- `call_campaigns.zero_call_diagnosis` → if present, ALWAYS report this prominently
- `fatigued_ads` → fatigue section

### Step 4 — Deliver Report

Follow `{baseDir}/references/report-template.md`. Write entirely in Spanish.

---

## Critical Rules

1. **Never mix LLAMADAS and MENSAJERÍA metrics** in the same table or comparison
2. **Primary benchmark = month-over-month within same channel type**, dollar-adjusted
3. KPI for LLAMADAS = # llamadas 60s+, costo/llamada 60s+
4. KPI for MENSAJERÍA = # conversaciones, costo/conversación
5. **Budget is managed at campaign level (CBO). Never recommend changing spend on a specific ad.**
   - To help a winning ad: pause the losers in the same campaign
   - To scale a channel: increase the campaign's daily budget
6. Keep the report brief — readable in 2 minutes. Cut anything not actionable.
7. Verdicts must be concrete: "Elimínalo" not "considera pausarlo"
8. Every number must come from the processed JSON, not estimated

---

## Error Handling

| Error | Action |
|---|---|
| `.env` not found | Show path and required variables |
| Token expired (error 190) | Remind user to refresh token |
| No data for period | Inform user, do not fabricate |
| Campaign type undetected | Flag as UNKNOWN in report, ask user to clarify naming |
