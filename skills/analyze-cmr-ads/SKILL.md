# analyze-cmr-ads

Analyze Facebook Ads performance data for CMR clinic with expert-level, actionable insights.

## Description

This skill fetches comprehensive Facebook Ads data for CMR clinic and provides expert-level performance analysis. Think like a seasoned Facebook Ads manager — not just reporting numbers, but telling Diego exactly what's working, what's bleeding money, what to kill, what to scale, and what to test next.

**All reports must be written in Spanish.**

## Usage

When the user asks to analyze CMR ads (or when triggered by weekly cron), follow these steps:

1. **Determine the date range**: Parse the request or default to last 7 days (for weekly report)
2. **Fetch the data**: Run the fetch script
3. **Deep-analyze**: Apply the expert framework below
4. **Send report**: Deliver via email + chat with clear verdicts and actions

## Fetching Data

Use the fetch script located at: `/Users/byte/src/cmr-facebook-ads/fetch_facebook_ads.py`

Load credentials from: `/Users/byte/src/cmr-facebook-ads/.env`

**Command template**:
```bash
source ~/src/cmr-facebook-ads/.env && \
python3 ~/src/cmr-facebook-ads/fetch_facebook_ads.py \
  --start-date YYYY-MM-DD \
  --end-date YYYY-MM-DD \
  --token "$FACEBOOK_ACCESS_TOKEN" \
  --ad-account-id "$CMR_AD_ACCOUNT_ID" \
  --output ~/src/cmr-facebook-ads/data_YYYY-MM-DD_to_YYYY-MM-DD.json
```

---

## Expert Analysis Framework

You are a senior Facebook Ads strategist for a medical clinic. Your job is not to summarize numbers — it's to make decisions. Apply this framework rigorously.

---

### RULE #1: The True North Metric — Cost Per Appointment (CPA)

CMR is a clinic. The only thing that matters at the end of the day is booked appointments. Everything must be evaluated through this lens:

**Conversion rates (clinic-specific, use these always):**
- WhatsApp/Messenger connections → appointment: **8% conversion rate**
- Phone calls 60s+ → appointment: **16% conversion rate**

**Formula:**
- Cost per Appointment via WhatsApp = (spend / WA connections) / 0.08
- Cost per Appointment via Calls = (spend / calls_60s) / 0.16

This means: a call lead is worth 2× a WhatsApp connection in appointment potential — but only if the cost per call is competitive. Always calculate and show BOTH the raw cost-per-lead AND the true cost-per-appointment. Do not assume one channel is better than the other — let the math decide.

**Example:**
- Ad A: $5/WA → $5/0.08 = **$62.50/appointment**
- Ad B: $22/call → $22/0.16 = **$137.50/appointment**
- Ad A wins on CPA even though calls convert better

---

### RULE #2: Channel Priority Order

1. **Phone calls 60s+** — highest intent, 16% → appointment
2. **WhatsApp/Messenger connections** — high intent, 8% → appointment
3. **Phone calls 20s+** — secondary signal, use to diagnose call quality
4. Form leads — ignore, low priority for CMR

---

### Analysis Sections

#### 1. RESUMEN DE LA SEMANA (Weekly Snapshot)
- Gasto total del período
- WhatsApp connections totales + costo por conexión + **costo por cita estimado**
- Llamadas 60s+ totales + costo por llamada + **costo por cita estimado**
- Comparar vs período anterior si hay datos en memoria
- ¿Esta semana fue mejor o peor? ¿En cuánto?

#### 2. GANADORES — Escalar Ahora
Identify ads meeting ALL:
- Cost per APPOINTMENT < $120 (exceptional: < $80)
- CTR > 2%
- Frequency < 3.5
- Spent at least $30 (statistically meaningful)

For each winner:
- **Qué es** (nombre del anuncio, tipo de creativo)
- **Por qué está ganando** (métrica específica, costo por cita)
- **Acción**: "Aumentar presupuesto 25-30%" o "Duplicar a nueva audiencia"

#### 3. PERDEDORES — Cortar o Reparar
Identify ads with:
- Cost per appointment > 2× the account average CPA
- CTR < 1% with spend > $20
- Frequency > 4.0 with declining performance
- Spent > $50 with zero conversions (any channel)

For each loser:
- **Qué es**
- **Por qué está fallando** (CPC alto, CTR bajo, cero conversiones a pesar del gasto)
- **Veredicto**: "ELIMINAR" o "Pausar y renovar creativo" o "Cambiar objetivo de campaña"

#### 4. AUDITORÍA DE OBJETIVO DE CAMPAÑA
This is critical: the same creative can perform radically differently depending on whether it's running in a WhatsApp objective vs a Calls objective. Always check:
- Is any ad running in the wrong objective? (e.g., a video that gets great WA connections but poor calls — it should be in a WA campaign, not a calls campaign)
- Calculate CPA for both versions if the same creative runs in multiple campaigns
- Flag objective mismatches explicitly

#### 5. REVISIÓN DE FATIGA CREATIVA
- List any ads with frequency > 3.5
- If frequency is high AND CTR is declining: flag as fatigued
- Recommend type of new creative to test (video vs image, different hook, different offer angle)

#### 6. REASIGNACIÓN DE PRESUPUESTO
- Which campaign is consuming the most budget? Is it justified by CPA?
- Are high-CPA ads starving low-CPA ads of budget?
- Specific reallocation: "Mover $X/día de [perdedor] a [ganador]"

#### 7. LAS 3 ACCIONES DE ESTA SEMANA
End every report with exactly 3 concrete, prioritized actions Diego must take THIS WEEK:

Format:
```
ACCIÓN 1 [URGENTE]: ...
ACCIÓN 2 [ESCALAR]: ...
ACCIÓN 3 [PROBAR/REPARAR]: ...
```

---

### Tone & Format

- Write entirely in Spanish
- Be direct. Give verdicts. Say "Elimínalo" not "podrías considerar pausarlo..."
- Use concrete numbers always — especially cost per appointment
- Keep it scannable: headers, bold key numbers, verdict badges
- No fluff. Diego is busy. Every sentence must earn its place.
- Flag anything urgent clearly at the top

---

## Benchmark References (CMR)

### Raw Lead Benchmarks
- Buen costo por conexión WhatsApp: < $12 (excepcional: < $8)
- Buen costo por llamada 60s+: < $20 (excepcional: < $14)
- Buen CTR: > 2% (excepcional: > 3.5%)
- Frecuencia aceptable: < 3.5 (sobre 4 = fatiga creativa)
- CPM aceptable: < $15 (sobre $25 = problema de audiencia)

### Cost Per Appointment Benchmarks (THE REAL BENCHMARK)
- Excepcional: < $80/cita
- Bueno: < $120/cita
- Aceptable: < $160/cita
- Malo: > $200/cita → revisar o eliminar

### Historical Baselines (February 2026)
- $10.35/WhatsApp → $129/cita estimada
- $18.52/llamada 60s → $115.75/cita estimada
- Use these as reference when comparing weekly trends

---

## Date Range Helpers

- "last 7 days": today - 7 days to yesterday
- "last 30 days": today - 30 days to yesterday
- "this month": 1st of current month to today
- "last month": 1st to last day of previous month
- For weekly cron: always use last 7 days (Monday to Sunday)

---

## Output Format for Weekly Report (in Spanish)

```
## Reporte Semanal CMR Ads — [Rango de Fechas]

### Resumen de la Semana
[gasto, conexiones, llamadas, CPA estimado — vs semana anterior]

### Ganadores (Escalar)
...

### Perdedores (Cortar o Reparar)
...

### Auditoría de Objetivo de Campaña
...

### Fatiga Creativa
...

### Reasignación de Presupuesto
...

### Las 3 Acciones de Esta Semana
ACCIÓN 1 [URGENTE/ESCALAR/PROBAR]: ...
ACCIÓN 2 ...
ACCIÓN 3 ...
```

---

## Notes

- Data is saved to `~/src/cmr-facebook-ads/` with timestamped filenames
- Always check for API errors
- If no data for period, inform user
- Save key weekly CPA metrics to memory for trend comparison in future reports
