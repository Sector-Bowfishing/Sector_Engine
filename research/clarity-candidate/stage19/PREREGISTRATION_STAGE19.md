# Stage 19 pre-registration: live-causal consensus validation

**Timing.** Written 2026-10-02, before any past-only consensus prediction or score existed. Its sha256 goes into
`FREEZE_STAGE19.json` before scoring.

**What is not used:**
- future scenes;
- field reports;
- Stage 14/15 certification truth;
- Stage 16 fresh truth.

**What is not changed:**
- the C-gbm;
- the Stage 16 reliability gate;
- production.

## 1. The reference (frozen, unchanged)

**Stage 18 two-sided physical-pass consensus.** Its development rows are `stage18p/dev18p_rows.json`, and its
parameters are `stage18p/engine/candidate18p.json`. It keeps:
- ACOLITE K4 and the C-gbm;
- the Stage 16 posterior gate (0.70 / 0.70);
- tier-2 boundary-only and tier-3 Clear-only;
- the algal modifier and S2C at lower authority;
- the physical-pass identity: (platform, UTC sensing date);
- inverse-uncertainty weighting over at most 3 independent neighbour passes;
- the Stage 18 uncertainty parameters and its posterior calibration architecture.

**The baseline is Stage 16**, the single scene (`stage16/analysis/dev16_rows.json`).

## 2. The causal dataset

**The anchor:** the matched pass, as in Stages 16–18.

**Prior passes** come from the Sen2Cor read-outs of the frozen Stage 6 extractor:
- the Stage 11 read-outs (observation date ±10 days);
- new read-outs for 11–17 days before the observation (`readouts19.csv`, same extractor, same disk).

So a 15-day lookback is complete for every anchor, since anchors fall within 2 days of their observation.

**A prior pass is eligible only if:**
- it is a different physical pass from the anchor's;
- it was sensed strictly before the anchor's sensing time;
- it has a valid production-gated Sen2Cor disk (n_valid ≥ 5).

**Selection:**
- **One item per pass:** the representative is the item with the most valid pixels, then the lowest scene cloud, then
  the item id (the Stage 18 rule).
- **Which passes:** the 3 most recent within 15 days, by age, then scene cloud, then pass key.
- **Windows:** each lookback window is the subset whose age (anchor date minus pass date, in days) is ≤ W.
- **No future scene anywhere.** Selection, calibration, features and authority all use current-or-past scenes only.
  This is asserted for every event (sensing time < anchor sensing time), and so is pass independence.

**Windows:**
- Previous 3, 5, 7 and 10 days are primary.
- Previous 15 days is a diagnostic, never eligible for selection.

**Hydrology:** not used. The share of contributing prior scenes the Stage 17 rain rule would have excluded is reported
as context only.

## 3. The causal consensus (inverse-uncertainty weighting only)

**The anchor counts as the newest evidence:** age 0.

**Scene variance** is σ²_tier + κ·age. σ and κ are the Stage 18 per-fold values in development evaluation
(`dev18p.json` params), and `candidate18p.json` for production, unchanged.

**Posterior calibration is the only thing re-estimated:**
- n = 1 keeps the Stage 16 posteriors.
- n = 2 and n ≥ 3 use nested posteriors, fitted per fold on the inner folds' causal consensus predictions (at least
  40 rows, otherwise the Stage 16 posteriors), as in Stage 18.
- These are new **posterior calibration**, not new clarity-model fitting. The prediction of every scene is the frozen
  C-gbm fold prediction.

**Unchanged from Stage 18:**
- the gate (0.70 / 0.70);
- boundary-only when every contributing scene is tier 2;
- S2C never contributing;
- the fallback to Stage 16 when no full-authority scene contributes.

## 4. Comparisons and metrics

**The three systems compared:**
- A, Stage 16;
- B, Stage 18 two-sided;
- C, Stage 19 causal, at every window.

**Metrics:**
- operational, class-balanced and per class: clear, normal, stained, limited;
- harmful and severe rates;
- the Unknown share;
- exact-feet error (median |log10 error| on the same rows) and the Stage 12 exact-feet capability;
- Strong share and truth-in-answer.

**Stained only:** operational, truth-in-answer, harmful, severe, exact-feet error, mean posterior confidence and
Unknown share.

**Bootstrap:** C − A and C − B differences by whole-lake bootstrap (2,000 resamples, seed 19).

**The prior-pass count:** the share of events with 0, 1, 2 or 3 valid prior passes (S2A/B and S2C), per window.

## 5. Window selection

**The candidates:** primary windows meeting every Stage 16 freeze bar:
- round(10 × class-balanced) ≥ 7;
- every core class ≥ 0.60;
- harmful ≤ 15%;
- severe ≤ 2%.

**The best:** the candidate with the highest class-balanced score.

**Equivalent to the best:** a candidate is equivalent when the bootstrap 95% CI of (candidate − best) includes 0 for
both the class-balanced and the stained score.

**The pick:** the smallest equivalent window. If no window clears the bars, nothing is adopted.

## 6. Strong evidence (causal)

**The rule, unchanged:**
- at least 2 compatible full-authority scenes from different physical passes, all current-or-past, whose states
  contain the answer;
- no disjoint state;
- posterior ≥ 0.90.

**Reported:**
- the share and truth-in-answer;
- the median age of the supporting prior passes;
- the share of Strong answers supported by exactly 2 passes vs 3 or more.

## 7. Current-pass priority

**The population:** events whose anchor is a full-authority S2A/B tier-1/2 scene, and whose consensus uses at least
one prior scene.

**Three diagnostics:**
- **D1, state non-adjacent:** the consensus state and the anchor's Stage 16 state share no class and are at least 2
  classes apart. Disjoint states (no shared class) are also reported.
- **D2, a class jump:** the consensus prediction's hard class moves at least 2 classes from the anchor prediction's.
- **D3, numeric:** |consensus − anchor| ≥ 0.176 log10 (×1.5).

For each: the count, the truth-in-answer of consensus vs anchor, and the harmful rates.

**The problem trigger:** D1, D2 or D3 has at least 20 events in which the consensus is right less often, or harmful
more often, than the anchor.

**Guard G1 (tested only if triggered):**
- **The rule:** where a full-authority S2A/B anchor's own gate state is disjoint from the gate state of the prior-only
  consensus (the anchor excluded), the answer is the Stage 16 anchor product.
- **Adopted only if** it raises the class-balanced score or lowers the harmful rate, does not lower stained by more than
  0.01, and every bar still passes.

## 8. Sentinel-2C (diagnostic only; no recalibration, no upgrade)

**For S2C anchors:**
- their count;
- the number with prior S2A/B scenes within 10 days;
- agreement of the S2C anchor's own gate state with the prior S2A/B consensus state (a shared class, or containing
  it);
- the signed difference of the anchor's prediction from that consensus (log10 ft), as a median and IQR.

## 9. Decisions

**CAUSAL CONSENSUS USEFUL: YES** (it replaces Stage 18 as the development and shadow candidate) only if the selected
window:
- passes every Stage 16 freeze bar;
- improves stained over Stage 16 by ≥ 0.05, with the CI above 0;
- uses physically independent passes and no future scene (both asserted);
- keeps Strong truth-in-answer ≥ 90%.

**STAGE 18 GAIN SURVIVES LIVE OPERATION,** at the selected window, or at 10 days if none is selected:

| Answer | When |
|---|---|
| YES | The stained gain over Stage 16 is ≥ 0.05 with the CI above 0 |
| PARTIAL | The CI is above 0 but the gain is < 0.05, or the gain is ≥ 0.05 but the CI reaches 0 |
| NO | Otherwise |

The share of Stage 18's stained (+0.097) and operational (+0.045) gains retained is reported.

**BEST LIVE LOOKBACK WINDOW:** the window selected in section 5.

**TRUE 9/10 DEVELOPMENT BAR:** all of these:
- operational ≥ 0.85;
- weakest class ≥ 0.80;
- harmful ≤ 5%;
- severe ≤ 0.5%;
- Strong ≥ 50% at ≥ 90%.

**Capability (three distinct scores):**
- **Development:** round(10 × class-balanced) of the adopted engine, or Stage 18 if causal is not adopted.
- **Certified:** none. No certification has been passed, and no unseen pool exists.
- **Deployed production:** production's `secchi-power-v1`, whose readiness was scored 2/10 in Stage 14.

**READY FOR DEDICATED S2C STAGE: YES** if causal consensus is adopted, so the S2C stage has a fixed live candidate.

**READY TO FREEZE CLARITY AFTER S2C: YES** only if causal consensus is adopted, passes every Stage 16 bar, and keeps
Strong ≥ 90%. Freezing means a frozen certification candidate; certification still needs an unseen pool.

**Never lowered:** none of these bars.

## 10. Shadow (only if adopted)

**The update:** the shadow job runs the causal candidate — the current pass plus up to 3 prior independent passes
within the adopted window.

**Its parameters** are in `candidate19.json`:
- σ and κ from `candidate18p.json`;
- the n = 2 / n ≥ 3 posteriors pooled from the development outer-fold causal consensus, as Stage 18 did.

**Checked first:** the port is checked against fixtures from this frozen code.

**Recorded:** full provenance.

**Not touched:** production.
