# Stage 8 pre-registration: fresh NDCI confirmation and the continuous challenger

**Written:** 2026-09-28, before any fresh observation was sampled or extracted, and before the continuous model was fitted.

**Fixed from the previous stage:**
- the NDCI > 0.03 rule;
- the nine readiness gates;
- the Guntersville evaluation rows;
- the contamination labels.

**Nothing below is changed after results are seen.**

---

## Part A: fresh-data confirmation of NDCI > 0.03

### Pool

- **Source:** the WQP lake/reservoir Secchi extract (`q9/wqp/secchi.csv`, 397,798 rows, 2018–2026).
- **Keep:**
  - rows at sites that appear in **no** Stage 1 file (`national_sample`, `targeted_sample`, `targeted_capped`, `all_matchups`, `targeted_matchups`, `national_matchups`, `national_matchups_clean`): 253,265 rows;
  - Secchi 0.05–25 m, bottom not visible, dated 2018-06-01 to 2026-09-15.
- **Remove:**
  - Guntersville;
  - **the same lake-year:** any row whose site lies within 2 km of any Stage 1 site in the same calendar year.

### Draw

- **Random,** seed 20260928.
- **Per site:** one observation per site per calendar month, and at most 3 per site.
- **Per state:** no state above 12% of the draw.
- **Size:** 4,000 rows.

### Read-out

- **Extractor:** `stage6/extract.py`, the production gates imported read-only, on the Sentinel-2 C1 collection, ±1 day.
- **Direct read:** ≥ 5 valid 10 m pixels in the 60 m disk.
- **Pass choice:** closest pass, then most valid pixels.
- **NDCI:** from the median valid-pixel B05 and B04.

### Chlorophyll

- Fetched from WQP **after** extraction, for the matched sites only: same site, same day.
- Units as in Stage 7: µg/L, mg/m³, ppb, and mg/L × 1000. RFU, volts and blank units are excluded.

### Site type

From `q9/wqp/sites.csv`. A site is a reservoir if `site_type` names a reservoir or impoundment.

### Definitions (unchanged)

- **T1 (material overstatement):** champion visibility ≥ 1.5 × Secchi.
- **Flag:** NDCI > 0.03.

### CONFIRMED requires all of these on the fresh set F

| # | Criterion |
|---|---|
| 1 | Spearman(NDCI, chlorophyll) ≥ 0.5, with n ≥ 50. |
| 2 | T1 relative risk (flagged / unflagged) ≥ 2, with the lower bound of the site-clustered bootstrap 95% CI > 1. |
| 3 | The Guntersville criterion. See the note below. |
| 4 | Sensitivity for T1 ≥ 0.5 in F, and in F-reservoirs. |
| 5 | ≤ 20% of matches with chlorophyll < 5 µg/L are flagged. |
| 6 | Stability: flagged overstatement rate > unflagged in every year with ≥ 3 flagged and ≥ 3 unflagged; in the majority of states with ≥ 3 flagged and ≥ 3 unflagged; and in reservoirs and natural lakes separately. |
| 7 | Positive predictive value ≥ 0.40. |

**Criterion 3 in detail.** There are no fresh Guntersville direct reads unless ≥ 15 exist after 2025-11-03; that is checked and reported. Otherwise criterion 3 is tested on the **fresh reservoir subset** (Guntersville-like water): relative risk ≥ 2, with the CI lower bound > 1.

**Anything else is NOT CONFIRMED.** The threshold is not revisited.

**Also reported:** a Guntersville 2026 WQP check, and the count of bowfisher clarity reports on record. Neither is decisive.

---

## Part B: continuous optical-regime challenger (C6)

### Form

**log10 Secchi_ft = a + b·log10 R + c·NDCI + d·NDCI·log10 R**

- R = median valid-pixel B04 reflectance, floored at 0.001.
- NDCI as above.
- **No other features.** No other challenger is fitted.

### Partial pooling of Guntersville

**Standardisation.** The three features are standardised with the training rows' means and SDs.

**Objective.** One set of coefficients β is fitted on all training rows (national plus Guntersville). Guntersville rows also get their own deviation δ, penalised by λ:

  minimise Σ_all (y − Xβ − g·Xδ)² + λ·‖δ‖², where g = 1 for Guntersville rows.

**Why this approach:**
- This is a hierarchical model with a Gaussian prior on Guntersville's deviation from the shared relationship.
- Guntersville departs from the shared relationship only as far as its own held-out data supports.
- A **small λ** lets Guntersville behave differently, so the national rows cannot swamp it.
- A **large λ** shrinks it back to the shared fit, so it cannot overfit about 65 rows.
- Up-weighting Guntersville would be a special case, with no principled choice of weight.

**Choosing λ:**
- The grid is {0.3, 1, 3, 10, 30, 100, 300, 1000, ∞}; ∞ equals the pooled fit.
- λ is chosen **inside each training fold only**, by an inner cross-validation over that fold's Guntersville rows:
  - under leave-one-year-out, the inner folds are its remaining years;
  - under leave-one-station-out, its remaining stations.
- The criterion is the minimum inner mean squared error of log10 Secchi.
- The held-out year or station is never used to choose λ.
- λ = 0 and λ = ∞ results are reported for context only. They are not candidates.

**National prediction.** Nationally only β is used: δ applies to Guntersville alone.

### Evaluation (unchanged from Stage 7)

- **Headline:** the 72 clean Guntersville rows.
- **Schemes:** leave-one-year-out and leave-one-station-out. Training in both is the Stage 1 national rows plus the training Guntersville rows.
- **National check:** lake-grouped 5-fold cross-validation on the Stage 1 national rows (the same folds), using β only. The fresh set F is also scored as an extra external check, not a gate.

### READY requires all nine Stage 7 gates, under both leave-one-year-out and leave-one-station-out

| # | Gate |
|---|---|
| 1 | Spearman ≥ 0.5 |
| 2 | Monotone calibration: ≥ 3 predicted bins with n ≥ 5, and no reversal > 0.5 ft |
| 3 | \|Station-balanced median signed error\| ≤ 0.75 ft |
| 4 | Stained 2–3 ft water: median signed error ≤ +1.0 ft |
| 5 | Clear channel: median signed error ≥ −1.5 ft |
| 6 | Clear-channel/stained-arm AUC ≥ 0.8 |
| 7 | 4-class accuracy ≥ the constant guess + 10 points |
| 8 | Beats the champion on MAE **and** median absolute error |
| 9 | National cross-validation median absolute error ≤ 1.1 × the champion's, and Alabama MAE ≤ 1.2 × the champion's |

**No gate is relaxed.**

### Reported diagnostics (not gates)

- **Stained water:** every held-out stained observation (Secchi 2–3 ft), showing:
  - measured Secchi;
  - champion, C3 and C6 predictions;
  - NDCI, red reflectance, chlorophyll;
  - station, date, arm/channel.
- **Clear channel:** measured on the clean rows, and again with the bottom-risk rows added. Bottom-risk rows are predicted by fold models trained without them.
- **Algal against sediment** subsets.
- **The 4-class confusion matrix.**
- **The same-day subset.**

**No correction is fitted to the failures.**
