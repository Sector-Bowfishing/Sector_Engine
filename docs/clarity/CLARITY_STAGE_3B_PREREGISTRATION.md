# Clarity Stage 3B: preregistration

Written 2026-09-28, **before any pre-2025 data was read**: no candidate list, satellite pass, rain file, NWM file or gauge record for 2020–2024 had been requested. The frozen artefacts are hashed in §9. After this document, the analysis code, the constants and the rules below do not change. Any later change is a deviation: it is logged in the hand-off, labelled exploratory, and kept out of the primary gate.

**Discovery set:** 2025-03 to 2026-09, used in Stages 2–3A. It is used only to set the constants in §5.
**Validation set:** 2021, 2022, 2023 and 2024, by the pass's calendar year (UTC). 2020 (Nov–Dec only, since MRMS Pass 2 begins in mid-October 2020) is reported separately and never enters the gate.

---

## 1. Hypotheses

- **H1 (primary): season.** In the cold season (Nov–Mar), zone observations in the storm window (§3) read murkier beyond noise more often than cold-season dry-week observations of the same class. Tested separately for **large-arm zones, medium-arm zones, small arms, and the main stem**.
  - The warm season (Apr–Oct) is reported with the same test as a contrast.
- **H2 (primary): relative NWM flow.** For arms whose flow is `modeledNWM`, zone observations with the model's own flow ≥ **3×** its baseline-pass median read murkier beyond noise more often than those below **1.5×**. Tested separately for large, medium and small.
  - NWM values are only ever compared with the same reach's own values, under the same model version (§2.4). No modeled value is compared with a measurement or across arms.
- **H3 (secondary): head vs mouth.** In cold-season storm-window events where the SAME arm on the SAME pass has ≥ 3 measurable zones, the anomaly decreases from head toward mouth (Spearman ρ between zone index and anomaly < 0). It is never tested across different passes or storms.

## 2. Data and pipeline (frozen)

### 2.1 Satellite
- **Candidates:** Earth Search `sentinel-2-c1-l2a`, `scripts/hydrology/pass_candidates.py`, a tile at or under 40% cloud. Window: 2020-10-15 → 2024-12-31.
- **Read:** `pass_history.py --cells` with the production gates in `jobs/lake-surface/derive_water_surface.py` exactly as hashed in §9: bank standoff, grass/vegetation, cloud and haze rules, speck and shadow drops, minimum patch. **Nothing is loosened.**
- **Statistics:** observed cells only (no fill) enter any FNU statistic.

### 2.2 Zones
- Stage 3A's `arm_zones.json` / `arm_positions.npz`, unchanged: equal-area bins of through-water distance from the head.
- **Classes:** large = 5-zone arms (13, including Town Creek, South Sauty and Browns); medium = 2–3-zone arms (13); small = one-zone arms; main stem = the main-stem cells as one unit.

### 2.3 Rain
- MRMS MultiSensor QPE Pass 2, basin means over each arm's drainage with the existing weights.
- **Daily:** 24 h totals valid 17Z (`rain_history.py`).
- **Hourly:** 01H products for the day before each pass, 17Z the day before → 16Z (`rain_pass_hours.py`).
- **Main stem:** the reservoir surface (`_lakeSurface`).

### 2.4 Flow
- **NWM:** the analysis-assimilation channel output at 16Z each day (`nwm_history.py`, public archive `gs://national-water-model`), recording each file's `NWM_version_number`. A ratio is formed only when the pass day and every baseline day carry the same version.
- **USGS:** instantaneous values for 03572900 and 03572690, the value nearest the pass within 1 h.

### 2.5 Year completeness
A validation year counts toward the gate only if:
- it has **≥ 40 read passes**; and
- it has **≥ 90% of daily MRMS days** present.

Otherwise it is reported and marked incomplete.

## 3. Event definitions

| Term | Definition |
|---|---|
| Storm day | A 17Z–17Z window with ≥ **1.0 in** of catchment-mean rain on the unit's drainage. The window ending at a pass is hourly, through 16Z. |
| Lag | Pass day minus the most recent storm day, within 10 days (0 = the window through 16Z on the pass day). |
| **Storm window** | Lag **0–3 days**. Secondary lags reported: 4–6 and 7–10. |
| Dry week | < **0.25 in** over the ~7 days before the pass. |
| Cold season | Nov, Dec, Jan, Feb, Mar (pass month). Warm = Apr–Oct. |
| Hydrologic episode | Lake-wide storm days (≥ 1.0 in on any tributary drainage) merged when ≤ **3 days** apart. A unit's episode is the one containing its triggering storm day (± 1 day). Independent storms = episodes. |
| Measurable | A zone with ≥ **30** observed cells and ≥ **30%** of its non-grass water observed. The main stem uses the same thresholds on its own cells. |
| Baseline | The median log10 FNU of the same unit's measurable passes in the prior **45 days** that followed a dry week; **≥ 2** are required. |
| Anomaly | log10(median observed FNU) − baseline. |
| Previous observation | The unit's most recent measurable observation within 45 days before the pass. |

## 4. Noise (frozen from discovery dry weeks, p10 / p90 of anomaly, log10)

| Position | p10 | p90 | Dry weeks (n) | Dry share above p90 |
|---|---|---|---|---|
| head | −0.1645 | +0.0823 | 185 | 0.103 |
| upper | −0.1645 | +0.1131 | 138 | 0.116 |
| middle | −0.1749 | +0.1543 | 252 | 0.103 |
| lower | −0.1749 | +0.1234 | 194 | 0.108 |
| mouth | −0.1646 | +0.1492 | 319 | 0.100 |
| whole (small arms) | −0.2777 | +0.1800 | 80 | 0.113 |
| main stem | −0.1749 | +0.1337 | pooled zone dry weeks* | 0.102 |

\*Discovery had fewer than 20 main-stem dry weeks, so the main stem takes the pooled zone band (flagged in the constants).

"Murkier beyond noise" = anomaly above the position's p90. Direction of change against the previous observation uses the same band: above p90 is murkier, below p10 clearer, else same.

## 5. Challengers and comparators (adjustments frozen from discovery)

For every validation unit with a baseline and a previous observation:
1. **Persistence:** the previous observation.
2. **Dry-baseline reversion:** the baseline.
3. **Season-only:** if cold season, storm window, and the storm day fell after the previous observation: baseline + δ_season(class). Otherwise persistence.
4. **Relative-flow:** if the NWM ratio is ≥ 3: baseline + δ_flow(class). Otherwise persistence.
5. **Combined:** evaluated **only** for a class where BOTH 3 and 4 are supported by the gate. If both conditions hold, baseline + δ_combined; if one, that one's rule; else persistence.

δ = the discovery median anomaly of the condition's units in that class, when ≥ 8 units support it; otherwise 0 (the challenger then equals persistence).

| Class | δ_season (n) | δ_flow (n) | δ_combined (n) |
|---|---|---|---|
| large | +0.1183 (131) | +0.0720 (139) | +0.0926 (50) |
| medium | +0.0412 (59) | +0.1311 (44) | +0.1337 (12) |
| small | +0.4319 (21) | 0 (1) | +0.2160 (1; the mean of the two) |
| main stem | 0 (4) | n/a | n/a |

**Consequence, stated now:** the main stem's season challenger is persistence, and the small class's flow challenger is persistence. Neither can pass G4 or G5, so only their hypothesis tests (H1, H2) are informative.

## 6. Metrics

All metrics are computed per class and challenger, pooled over the validation years and per year:
- MAE in log10 FNU;
- direction accuracy (the predicted and observed change against the previous observation, in the §4 bands);
- Peirce skill for "murkier";
- error by lag, by season and by class;
- calibration by the previous observation's coverage (30–50%, 50–75%, ≥ 75%).

H3 is reported as event counts, the share with ρ < 0 and a sign test.

**Uncertainty.** 95% intervals by cluster bootstrap (2,000 draws): condition units are clustered by independent storm (or by pass date when a unit has no episode), control and all-unit sets by pass date. The H1/H2 difference resamples condition and control clusters independently.

## 7. Evidence gate (per class × challenger; no lake-wide pass/fail)

A year **qualifies** for a class and challenger if it has ≥ 3 independent storms and ≥ 8 condition units in that class, and is complete (§2.5).

| | Criterion |
|---|---|
| **G1 independence and sample** | ≥ **15** independent storms pooled; ≥ **3** qualifying years; no single storm > **25%** of the condition units; and with the largest storm removed, the challenger's MAE advantage over persistence stays below 0 |
| **G2 hypothesis** | Pooled condition − control murkier share ≥ **0.10**, 95% interval lower bound > 0; the difference > 0 in ≥ 3 qualifying years and in ≥ 75% of them |
| **G3 effect larger than noise** | Median condition anomaly ≥ **+0.05** log10, 95% interval lower bound > 0 |
| **G4 beats persistence** | Pooled MAE (challenger − persistence) on condition units has its 95% interval entirely below 0; and in every qualifying year the challenger is no more than **0.02** worse |
| **G5 direction skill** | Pooled Peirce skill ≥ **0.15**, 95% interval lower bound > 0 |
| **G6 beats reversion** | Pooled condition MAE ≤ the dry-baseline reversion's |
| **G7 observation quality** | Enforced by the unit definition (measurable, a measurable previous observation, a baseline) |
| **G8 no harm overall** | Over all of the class's units, challenger MAE ≤ persistence + **0.005** |

**Decision per class × challenger:** *supported* if G1–G8 all hold; *insufficient evidence* if G1 fails; otherwise *unsupported*. Results are stated per class, e.g. "cold-season small arms supported; large embayment spatial runoff unsupported".

**Within-arm spatial structure (H3)** is supported only if all of these hold:
- ≥ 20 qualifying events, and the share with ρ < 0 is ≥ 0.60;
- the sign test gives p < 0.05;
- in ≥ 3 years with ≥ 5 events each, the share is > 0.5.

**Recommendation rule:**
- `PROCEED TO SPATIAL RUNOFF MODEL` only if at least one class × challenger is supported. The recommendation is scoped to those classes, and within-arm structure is included only if H3 passes.
- Otherwise `DO NOT PROCEED`.

## 8. Secondary and exploratory analyses (never in the gate)
- **Warm-season contrast** (H1 test in Apr–Oct).
- **By year, per class:** hypothesis shares and challenger errors.
- **Head coverage (item 11):**
  - cold-season storm events with a measurable head, and with both head and mouth;
  - per-arm head measurability with mean unreadable, grass and cloud fractions;
  - heads never measurable.
- **The Stage 2 per-arm state on untouched years:** `ClarityReplay` v3 (hourly rain, reconstructed fill distances), with its authority ladder and direction skill.
- **Measured flow (USGS) at Town Creek and South Sauty by zone.** Too few arms to gate.
- **Alternate sensor / method feasibility (item 12):** a tighter bank standoff on a few passes, measured separately; other sources; user reports. Never mixed into the primary result.
- **Wind:** collected and preserved only. It is not used.

## 9. Frozen artefacts (SHA-256)

Recorded in `CLARITY_STAGE_3B_PREREGISTRATION.sha256` beside this file, computed at the moment of writing, together with this document's own hash.
