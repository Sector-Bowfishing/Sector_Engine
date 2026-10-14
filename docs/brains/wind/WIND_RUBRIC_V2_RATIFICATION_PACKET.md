# Wind Rubric v2 — ratification packet (DECISION ONLY; nothing applied; rubric v1 stays canonical)

Existing evidence only (`stage3a/evidence`, the file the canonical scorer already reads, plus the research branch's forecast-keyed direction table). No new evidence generated. **H2 untouched.** Scorer rerun 2026-10-14: canonical **3.3**, raw **3.29**, BWIS 5.4. Detail: `WIND_PRODUCT_RUBRIC_MISMATCH_PROPOSAL.md`.

## The one decision
Today each of Wind speed / Gust takes the **minimum** of its conditions, so one failed strong-event gate (land stations, NBM rarely forecasts ≥15 mph / ≥20 kt) erases credit for accuracy that already passes. Approve (or reject) replacing `min()` with **separately weighted components** for dimensions 1, 3 and a **forecast-keyed night slice** for dimension 2. Nothing else changes: weights total, caps, gates, H2, exposure/surface, reliability and coverage rules are as v1.

## Before / after
| Dimension | Current rule | Proposed rule | Current pts | Proposed pts | Why product-correct | Validation retained |
|---|---|---|---:|---:|---|---|
| 1 Wind speed (12) | credit = min(MAE, \|bias\|≤0.3, ≥15 mph POD≥0.5 & FAR≤0.5) | **A (8 pts):** min(MAE, \|bias\|) = provider accuracy. **B (4 pts):** the same all-or-nothing ≥15 mph POD/FAR gate, unchanged | 0.00 | **8.00** (A 8 × 1.0; B 4 × 0 = 0) | Provider speed is accurate (MAE 0.837, bias −0.042); the event gate measures a different capability. Split is 2:1 because v1 had two accuracy conditions and one event condition | Event gate keeps its full threshold and 4 points; still 0 |
| 2 Direction (8) | all-hours, both winds >= 2.6 m/s: within 22.5 deg 0.65->0.85 linear, circ MAE <= 20 | **night, FORECAST >= 5 mph** (forecast-keyed: what the customer is shown), same two conditions, pooled over leads 1-18 h (n = 4,004: within 22.5 deg 0.807, 16.0 deg) | 4.32 | **6.27** | The customer sees the forecast, not the observation; v1 and the observed-conditioned night slice both select hours where the observation was also windy, which flatters direction. Night is the bowfishing period; 5 mph is the product's existing label threshold | All-hours within-22.5 deg 0.758 stays reported; the same circ-MAE <= 20 pass/fail applies |
| 3 Gust (5) | credit = min(\|cond. bias\| 3→1 m/s, ≥20 kt POD≥0.6 & FAR≤0.6) | **A (2.5):** provider gust accuracy (\|cond. bias\| 3→1). **B (2.5):** ≥20 kt event gate, unchanged. **C gust→water impact: not scored here** (belongs to Surface, dimension 7) | 0.00 | **1.36** (A 2.5 × 0.544; B 0) | Gust is provider truth; impact on water is Sector-derived and already penalised in Surface (20 pts, 0) | Event skill stays visible and 0; impact stays in Surface |

## Score (exact: `research/rubric_v2_simulation.py` -> `data/rubric_v2_simulation.json`)
| | Current (v1) | Proposed (v2 primary) |
|---|---:|---:|
| Raw points / 100 | 32.92 | **44.23** (speed +8.00, gust +1.36, direction +1.95) |
| Raw (0-10) | 3.29 | **4.42** |
| Displayed (min of raw and caps 6.0 / 7.0, not binding) | 3.3 | **4.4** |
Sensitivity: speed split 6/6 -> raw 4.22 (4.2). Direction slice alternatives, same speed/gust split: all-hours (v1 rule) 4.23; night observed-conditioned 4.60 (NOT recommended: scores highest but conditions on the observation). **The recommended direction slice is the one that scores in the middle, chosen on product fit.**

## What remains penalised (no point inflation)
Strong-event detection 0 of 6.5 pts (speed B 4, gust B 2.5); exposure and surface 0 of 40 pts (field truth); reliability 1.6 of 8 (6/30 days; gate 2026-11-08); H2 sealed to 2027-01-01; 6.0 field-validation cap and 7.0 land-only cap unchanged. Production gate unchanged: overall ≥ 8.0 AND critical dimensions ≥ 7.5, so **v2 does not move Wind toward production**: exposure and surface (critical) stay at 0.

## Honest cautions for the reviewer
1. Direction: the forecast-keyed night slice is not the highest-scoring option (the observed-conditioned night slice would give 8.0 points); it is chosen because the customer sees the forecast. Its inputs come from the research branch's `bowfishing_validation.json` (descriptive restratification of the same corpus), so adopting it means freezing that table as scorer evidence. Land stations only; clustered weather days make the effective n smaller; one station (8A1) is poor (0.44).
2. The 8/4 and 2.5/2.5 weights are a judgement; I used the v1 condition counts to avoid choosing them for score. A stricter reviewer may prefer 6/6 (raw 4.40).
3. Any approved change must be applied by a new rubric id (`wind-certification-rubric-v2`), rescored from the same evidence, and published through the normal canonical path; v1 history is not rewritten.

## Confirmations
H2: not read, sampled, summarised or inspected. New evidence: none created (every number above is computed by `rubric_v2_simulation.py` from the scorer's evidence file and the research branch's existing direction table). Rubric: unchanged. Score: not published. Field packets: ready (below).

## Field readiness (Guntersville and Hartwell)
Packets ready: `field_packets/EXAMPLE-guntersville`, `EXAMPLE-hartwell`; 99 geometry-only candidate pairs; prereg `WIND_BANK_VALIDATION_V2_PREREG.freeze.json` + rules `WIND_EXPOSURE_RULES_V2.freeze.json` frozen and pinned; blinded observer sheet, one-minute record (`sector-wind-field-v2`). Targets: ≥40 pairs, ≥2 independent systems (Guntersville ~20, Hartwell 16-20, ≥8 mandatory). New this pass: every record carries `tripId` (shared-trip key) and the sealed key preserves `rulesVersion` + `rulesFingerprint` (predictions are never shown to the observer). Hartwell is the first physical test of the ESTIMATED tier. Access/safety unverified (tester checks ramps and permission). Anemometer: plan unchanged (≥30 sessions, 2-3 lakes, ≥10 with land wind ≥8 mph, ±0.3 m/s or 3%); nothing purchased.
