---
name: google-maps-reviews
description: Manage Google My Business reviews for CMR locations. Check reviews weekly (Monday mornings), draft responses for approval, generate sentiment summaries, and alert on negative reviews immediately. Use when managing business reviews, customer feedback analysis, or reputation monitoring for Centro de Medicina Regenerativa.
---

# Google Maps Reviews Management

Automated review monitoring, response drafting, and sentiment analysis for CMR business locations.

## CMR Account & Locations

- **Account:** `accounts/113819797485493768273` (Soporte Centro de Medicina Regenerativa)
- **Bayamon:** `accounts/113819797485493768273/locations/12929992059614547382` (Calle Doctor Veve #51, Suite 1)
- **Caguas:** `accounts/113819797485493768273/locations/14162955965865191326` (Q2 Avenida Luis Munos Marin, Urbanizacion Mariolga)

## OAuth Credentials

Uses the gogcli OAuth client (GCP project `solid-league-487616-s0`):
- **Credentials:** `~/Agent/mateo/credentials/client_secret_158668894120-i9ua7d8lo408q3sbrmvivv328aiaq2ei.apps.googleusercontent.com.json`
- **Token:** `~/.openclaw/credentials/gmb_token.json`
- **Scope:** `https://www.googleapis.com/auth/business.manage`

## Quick Start

### List Recent Reviews

```bash
cd ~/Agent/mateo/profile/skills/google-maps-reviews

# Last 7 days (default)
python3 scripts/gmb_reviews.py list-reviews \
  --location accounts/113819797485493768273/locations/12929992059614547382

# Last 30 days, JSON output
python3 scripts/gmb_reviews.py list-reviews \
  --location accounts/113819797485493768273/locations/12929992059614547382 \
  --days 30 --json
```

### Weekly Summary

```bash
python3 scripts/gmb_reviews.py summary \
  --location accounts/113819797485493768273/locations/12929992059614547382 --days 7
```

### Reply to Review

```bash
python3 scripts/gmb_reviews.py reply \
  --review accounts/113819797485493768273/locations/12929992059614547382/reviews/REVIEW_ID \
  --reply-text "Gracias por su comentario..."
```

**Note:** Always draft replies for Diego's approval before posting, except for positive reviews which can be auto-replied.

## Commands Reference

```bash
# List accounts
python3 scripts/gmb_reviews.py list-accounts

# List locations for account
python3 scripts/gmb_reviews.py list-locations --account accounts/113819797485493768273

# List reviews (past N days)
python3 scripts/gmb_reviews.py list-reviews --location LOCATION --days 7

# Generate summary
python3 scripts/gmb_reviews.py summary --location LOCATION --days 7

# Reply to review
python3 scripts/gmb_reviews.py reply --review REVIEW_NAME --reply-text "Your reply"

# JSON output (any command)
python3 scripts/gmb_reviews.py list-reviews --location LOCATION --json
```

## Weekly Workflow (Monday Morning — Cron Job)

The cron job `f0d7ddf7` runs every Monday at 5am AST and does the following:

1. **Fetch reviews** for the past 7 days from both Bayamon and Caguas locations
2. **Generate summary** with sentiment breakdown (positive/neutral/negative)
3. **Auto-reply** to positive reviews (4-5 stars) that don't have a reply yet
4. **Draft replies** for negative/neutral reviews for Diego's approval
5. **Send WhatsApp report** to Diego with the weekly summary

### Response Guidelines

**General rules for all replies:**
- Always use the reviewer's first name if available (e.g. "¡Gracias, María!")
- Never use generic openers — reference something specific from their review
- Keep replies concise but personal

**Positive reviews (4-5 stars) — auto-reply:**
Reference a specific detail from the review (staff, treatment, results, facility, etc.) and thank them by name. End with a warm closing like "¡Bendiciones!" or "¡Le esperamos pronto!"

**Neutral reviews (3 stars) — draft for approval:**
Acknowledge the specific feedback by name, express commitment to improvement, and invite them to call at +1 787 780 7575 if there's anything specific to address.

**Negative reviews (1-2 stars) — draft for approval:**
Address the reviewer by name, acknowledge their specific concern, and invite them to email atencion@centrodemedicinaregenerativa.com so the team can take further action.

### Sentiment Classification
- **Positive:** 4-5 stars
- **Neutral:** 3 stars
- **Negative:** 1-2 stars

### Report Format

When Diego asks for a report, always use this exact structure:

```
Semana del [start date] al [end date] de [month] de [year]:

RESUMEN GENERAL:
Total reseñas: X | ✅ Positivas: Y (Z%) | ⚠️ Negativas: W (V%)

CAGUAS: ⭐⭐⭐⭐ (A/B positivas)
- Puntuación actual: X.X
- Las reseñas de esta semana:
- Reviewer Name — 10-15 word summary in Spanish
- Reviewer Name — 10-15 word summary in Spanish

BAYAMÓN: ⭐⭐⭐⭐⭐ (A/B positivas)
- Puntuación actual: X.X
- Las reseñas de esta semana:
- Reviewer Name — 10-15 word summary in Spanish
- Reviewer Name — 10-15 word summary in Spanish

⚠️ NEGATIVAS (requieren atención):
- Location - Reviewer — summary
  Respuesta propuesta: "..."

La semana próxima mandaré un reporte igual a este para ver cómo hemos progresado.
```

Rules:
- Header: "Semana del X al Y de [mes] de [año]" using the actual date range requested
- Star emojis = round overall rating to nearest whole number
- "A/B positivas" = positive / total for that location in the period
- Percentages in RESUMEN must add up correctly (positivas % based on total)
- One line per review: Name — 10-15 word summary in Spanish
- Omit "Puntuación actual" if rating API unavailable
- Omit ⚠️ NEGATIVAS section if none
- Always end with: "La semana próxima mandaré un reporte igual a este para ver cómo hemos progresado."

## Important Notes

**Never use the CLI `reply` command to post replies.** Shell argument parsing escapes `!` characters (e.g. `¡Gracias\!`), which get posted verbatim to Google. Always call the Python function directly via a heredoc script:

```python
python3 - <<'PYEOF'
import sys
sys.path.insert(0, '.')
from scripts.gmb_reviews import get_credentials, reply_to_review

creds = get_credentials()
reply_to_review(creds, "REVIEW_NAME", "¡Gracias! Texto aquí.")
PYEOF
```

## Troubleshooting

**"HTTP 403: Permission Denied"**
- Verify owner/manager access to the GMB account
- Check OAuth consent screen configuration

**"Invalid credentials" or "deleted_client"**
- Delete `~/.openclaw/credentials/gmb_token.json`
- Re-authenticate: `python3 scripts/gmb_reviews.py list-accounts`

**"No reviews found"**
- Verify location ID is correct
- Increase `--days` value
