# CMR Facebook Ads — Expert Analysis Framework

Brief. Actionable. One page. Every sentence earns its place.

---

## Budget Model

CMR uses **Campaign Budget Optimization (CBO)**. Facebook decides how to distribute budget across ads within a campaign. This means:

- **Never recommend increasing/decreasing spend on a specific ad**
- All budget recommendations are at the **campaign level**
- To favor a winning ad: pause the losing ads in the same campaign so budget flows to the winner automatically
- To scale: increase the campaign's daily budget

---

## Two Campaign Types — Analyzed Separately, Never Compared

| Tipo | KPI principal | KPI secundario |
|---|---|---|
| LEAD_CALL_[MES] | # Llamadas 60s+ | Costo/llamada 60s+ |
| LEAD_WHATSAPP_[MES] | # Conversaciones WA | Costo/conversación |

---

## Primary Benchmark: Month-over-Month (Dollar-Adjusted)

**The only benchmark that matters is: did we get cheaper leads than last month?**

```
Δ costo/lead = (CPL_anterior - CPL_actual) / CPL_anterior × 100
Proyección   = Gasto_actual / CPL_anterior  →  compare vs actual
```

---

## Report Sections (Keep Each Brief)

### 1. MoM Tables (one per channel)
Show the 5-row table from the template. One verdict sentence each. Done.

### 2. Anuncios a Reemplazar
Flag ads that are clearly broken. Criteria:

**LLAMADAS** — flag if ANY of:
- Spend > $100, calls_60s = 0
- cost_per_call_60s > 2× campaign average
- frequency ≥ 4.0

**MENSAJERÍA** — flag if ANY of:
- Spend > $50, wa_conversations = 0
- cost_per_wa > 2× campaign average
- frequency ≥ 4.0

For each: name, campaign, one-line diagnosis, verdict (Pausar / Eliminar).
Limit to 5 ads maximum. If more qualify, pick the highest-spend ones.

Action on bad ads = **Pausar o Eliminar el anuncio** so CBO redistributes budget to remaining ads. Do NOT say "reduce budget on this ad."

### 3. Mejores Creativos
List the top 2-3 per channel by cost/lead. Name + metric only.
Purpose: inform creative decisions for next month's campaign.
No budget recommendations — CBO handles distribution.

### 4. 3 Acciones
Always campaign-level. Examples of valid actions:
- "Pausa los 3 anuncios perdedores de LEAD_CALL_ABRIL para que el presupuesto fluya a los ganadores"
- "Aumenta el presupuesto diario de LEAD_WHATSAPP_ABRIL_2026 de $X a $Y"
- "Crea nueva campaña LEAD_CALL_MAYO con creativos basados en [ganador]"

---

## Tone Rules
- Write in Spanish
- No fluff. No "podrías considerar." Say "Elimínalo."
- If something is good, say it's good and move on
- Total report should be readable in 2 minutes
