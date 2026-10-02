# Current Clarity Stage 19: Live-Causal Consensus Validation

**2026-10-02.** The Stage 18 physical-pass consensus was run the way a live product must run it: the current pass plus independent passes sensed **before** it, never after.

**What didn't change:**
- the C-gbm, which was not refit;
- the Stage 16 gate, which was not altered.

**What was never used:**
- field reports;
- Stage 14/15 certification truth;
- Stage 16 fresh truth.

**Method:** pre-registered before scoring (`PREREGISTRATION_STAGE19.md`, frozen 23:17 UTC), on whole-lake-held-out development only.

Production is unchanged, and nothing was deployed.

**The answer: only part of the Stage 18 gain survives live operation.**
- The best live window gives stained 0.606 against Stage 16's 0.571 (+0.034, CI +0.006 to +0.063).
- That gain is real, but below the 0.05 material bar, so causal consensus is not adopted.
- About a third of Stage 18's gain survives: 36% on stained, 38% on operational.
- The reason is evidence, not method. Without future scenes, two-thirds of current passes have no independent earlier pass within 5 days, and half have none within 10.

| | A: Stage 16 | B: Stage 18, two-sided | C: causal, past 5 days (selected) | C: past 10 days |
|---|---:|---:|---:|---:|
| Operational | 0.693 | 0.737 | **0.710** | 0.719 |
| Clear | 0.880 | 0.893 | **0.883** | 0.889 |
| Normal | 0.643 | 0.685 | **0.669** | 0.679 |
| Stained | 0.571 | 0.668 | **0.606** | 0.616 |
| Limited | 0.676 | 0.703 | **0.680** | 0.692 |
| Harmful | 10.6% | 11.6% | **11.4%** | 11.6% |
| Severe | 1.52% | 1.26% | **1.39%** | 1.20% |
| Exact-feet error (same 1,261 rows) | ×1.35 | ×1.32 | **×1.34** | — |
| Exact-feet capability | 7/10 | 8/10 | **8/10** | — |
| Unknown share | 12.8% | 6.7% | **10.1%** | 8.7% |
| Strong share / truth-in-answer | 11.3% / 96.8% | 22.9% / 94.7% | **11.0% / 92.9%** | 16.2% / 93.6% |

## 1. The frozen reference

**Stage 18 is unchanged and stays the two-sided development reference** (`stage18p/`). Preserved exactly:
- ACOLITE K4 and the C-gbm;
- the Stage 16 gate (0.70 / 0.70);
- tier-2 boundary-only, tier-3 Clear-only, the algal modifier and S2C at lower authority;
- the physical-pass identity: (platform, UTC sensing date);
- inverse-uncertainty weighting over at most 3 independent passes;
- the Stage 18 per-fold σ and κ;
- the posterior calibration architecture: Stage 16 posteriors for one scene, nested posteriors for 2 and for 3 or more.

## 2. The strictly causal dataset

**Read-outs.** Prior passes need Sen2Cor read-outs further back than Stage 11 collected, because anchors fall up to 2 days from their observation:
- the Stage 11 read-outs cover the observation date ±10 days;
- the same frozen extractor added the 11–17 days before every observation (4,416 read-outs, `readouts19.csv`);
- so a 15-day lookback is complete for every anchor.

**Eligible prior passes:**
- a different physical pass from the anchor's;
- sensed strictly before the anchor's sensing time;
- with a valid production-gated Sen2Cor disk.

**Selection:**
- one representative item per pass (the Stage 18 rule);
- the 3 most recent within 15 days;
- each window is a subset by age.

**Data volume.** 575 representatives were new and went through the frozen ACOLITE path. 7 had no L1C (a 9–11 August 2023 gap in the bucket) and contribute nothing.

**Asserted for every event:** every prior pass is sensed before the anchor, and no physical pass appears twice.

**Valid prior passes available (S2A/B/C, after ACOLITE validity):**

| Lookback | None | 1 | 2 | 3 |
|---|---:|---:|---:|---:|
| Previous 3 days | 88.9% | 10.6% | 0.4% | 0.0% |
| Previous 5 days | 66.8% | 29.2% | 3.9% | 0.2% |
| Previous 7 days | 64.7% | 28.6% | 5.6% | 1.1% |
| Previous 10 days | 51.9% | 30.8% | 12.5% | 4.7% |
| Previous 15 days (diagnostic) | 41.1% | 31.4% | 16.4% | 11.1% |

The two-sided Stage 18 set had at least one independent neighbour for 65% of events (1,035 of 1,582).

**Hydrology: none used.** The Stage 17 rain rule would have excluded 76 of the 576 contributing prior scenes that have a rain record (13%). It is context only.

## 3. The causal consensus

**The method:** inverse-uncertainty weighting only. No other method was searched.

**The weighting:**
- The current pass is age 0, the newest evidence.
- Prior scenes are weighted by Stage 18's uncertainty model: σ²_tier + κ·age, with the Stage 18 per-fold values.

**What was re-estimated: posterior calibration only.** The n = 2 and n ≥ 3 posteriors were refit per fold on inner-fold causal consensus predictions.
- At 5 days that leaves about 330 rows for n = 2 and 41–49 for n ≥ 3, just above the 40-row minimum.
- This is calibration, not clarity-model fitting. Every scene's visibility prediction is the frozen C-gbm fold prediction.

## 4. Does the gain survive? Stained water (227 events)

| Stained | A: Stage 16 | B: Stage 18 | C: past 5 days | C: past 10 days |
|---|---:|---:|---:|---:|
| Operational | 0.571 | 0.668 | 0.606 | 0.616 |
| Gain over Stage 16 (95% CI) | — | +0.097 (+0.055 to +0.141) | **+0.034 (+0.006 to +0.063)** | +0.045 (+0.012 to +0.079) |
| Truth-in-answer | 71.9% | 78.9% | 74.5% | 74.5% |
| Harmful | 22.0% | 18.9% | 21.1% | 22.0% |
| Severe | 4.0% | 3.5% | 4.0% | 3.1% |
| Exact-feet error (same 174 rows) | ×1.42 | ×1.39 | ×1.41 | — |
| Posterior confidence | 0.791 | 0.802 | 0.798 | 0.799 |
| Unknown | 19.8% | 9.3% | 15.9% | 12.8% |

**The stained improvement is statistically supported but not material.** At every window from 5 to 10 days, the CI excludes zero. But the gain stays under the 0.05 bar: 36% of Stage 18's gain at 5 days, 46% at 10.

**Past-only consensus is clearly worse than two-sided.** Against Stage 18, stained is −0.062 at 5 days (CI −0.104 to −0.017). Harmful rises about 0.8 point over Stage 16 at 5 days (CI +0.1 to +1.7).

## 5. Lookback windows

| Past window | Operational | Stained (gain over Stage 16) | Harmful | Severe | Freeze bars |
|---|---:|---:|---:|---:|---|
| 3 days | 0.693 | 0.575 (+0.004, CI reaching 0) | 11.3% | 1.45% | no (stained) |
| 5 days | 0.710 | 0.606 (+0.034) | 11.4% | 1.39% | yes |
| 7 days | 0.708 | 0.610 (+0.038) | 11.5% | 1.33% | yes |
| **10 days** (highest) | 0.719 | 0.616 (+0.045) | 11.6% | 1.20% | yes |
| 15 days (diagnostic) | 0.728 | 0.644 (+0.073, CI +0.036 to +0.112) | 12.3% | 1.33% | yes |

**Ten days scores highest, but 5 days is statistically equivalent to it,** on both operational and stained:
- operational −0.009, CI −0.021 to +0.002;
- stained −0.011, CI −0.042 to +0.024.

The pre-registered rule takes the smallest equivalent window, so **5 days** is the best live lookback.

**The 15-day diagnostic is the only window whose stained gain clears 0.05.** It was pre-registered as diagnostic only, so it cannot be selected here. It also carries the highest harmful rate, 12.3%.

**Longer lookbacks keep helping** because live operation is short of scenes. Within ±10 days, a pass's age barely matters (Stage 18: κ ≈ 0.00012 a day).

## 6. Strong evidence, causal

| Past window | Strong share | Truth-in-answer | Median age of supporting prior passes | Supported by 2 passes / by 3+ |
|---|---:|---:|---:|---|
| 3 days | 4.0% | 96.4% | 3 days | 100% / 0% |
| 5 days | 11.0% | 92.9% | 5 days | 84% / 16% |
| 10 days | 16.2% | 93.6% | 5 days | 69% / 31% |
| 15 days (diagnostic) | 20.6% | 94.7% | 8 days | 59% / 41% |

**Accuracy holds; the share is small.** Strong stays above the 90% accuracy target at every window. But it covers only 11–16% of usable answers, against Stage 18's 23% and the 50% target.

**For Sector Intelligence:** recent agreement is reliable when it happens, but it happens too rarely to feed Clarity strongly. Clarity should stay a moderate-weight input.

## 7. Current-pass priority

**The population:** 429 events at 5 days (633 at 10 days) whose current pass is a full-authority S2A/B scene and whose consensus uses an earlier scene.

| Diagnostic | Past 5 days | Past 10 days |
|---|---|---|
| Consensus state non-adjacent to the current state | 0 | 0 |
| Consensus state disjoint from the current state | 0 | 0 |
| Consensus moves the hard class by more than 1 | 1 (consensus right, current right) | 2 (consensus right 2/2, current 1/2) |
| Consensus visibility ×1.5 or more from the current scene | 18: consensus right 83% vs current 78%; harmful 17% vs 22%; closer to truth in 18/18 | 43: right 79% vs 74%; harmful 19% vs 26%; closer in 70% |

**No older scene overpowers an obviously different current observation.** When consensus does move the number materially, it is more often right than the current scene alone. The pre-registered problem trigger did not fire, so no age or current-scene guard was added.

## 8. Sentinel-2C (diagnostic only; not recalibrated, not upgraded)

| | Count |
|---|---:|
| Development anchors that are S2C | 41 |
| With prior S2A/B scenes within 10 days | 21 |
| With both states | 15 |

**Agreement with the prior S2A/B consensus:**
- 100% share a class;
- 80% contain the consensus state.

**Offset:** the S2C anchor's prediction sits a median **0.059 log10 lower** than the prior S2A/B consensus, about 13% less visibility (IQR −0.116 to +0.010). This matches earlier stages, where S2C read clearer water as murkier.

**For the S2C stage:** the sample is small. The S2C stage needs more 2025–26 S2C scenes with truth.

## 9. Decision

| Adoption requirement | Causal, past 5 days |
|---|---|
| Every Stage 16 freeze bar | **Pass:** 7/10 (0.710), weakest class 0.606, harmful 11.4%, severe 1.39% |
| Stained materially better than Stage 16, CI above 0 | **Fail:** +0.034, CI +0.006 to +0.063, below the 0.05 bar |
| Physically independent passes | **Pass:** asserted |
| No future scene anywhere | **Pass:** asserted, and the anchor is always the newest |
| Strong truth-in-answer ≥ 90% | **Pass:** 92.9% |

**Causal consensus is not adopted.**
- Stage 18 stays the two-sided development reference, and it cannot run live.
- The live candidate stays the Stage 16 single-scene engine.
- **The shadow is not changed.** The pre-registration allowed an update only on adoption.
- **The shadow's challenger is now known to be wrong.** It still shows the item-based Stage 17 rule, which Stage 18 showed can count one pass twice. It should be read as legacy.

**The true 9/10 development bar fails** for every system:
- the best live system is at operational 0.710 against 0.85;
- weakest class 0.606 against 0.80;
- harmful 11.4% against 5%;
- severe 1.39% against 0.5%;
- Strong 11.0% against 50%.

**Three capabilities, kept separate:**
- **Development:** 7/10.
  - The two-sided Stage 18 reference: 0.737.
  - The best system that can run live: 0.710, causal at 5 days. It is not adopted, so the live candidate is Stage 16 at 0.693, also 7/10.
- **Certified:** none.
  - The only blind certification run, Stage 14, did not pass (2 of 6).
  - No unseen pool exists.
- **Deployed production:** 2/10. Production is `secchi-power-v1`, as scored in Stage 14.

## 10. What would make live consensus work

The gain is limited by how many independent views exist before today, not by the method. Two levers:
1. **Sentinel-2C at full authority.** S2C is a third satellite and a third to a half of 2025–26 passes, but it is excluded from consensus by rule. A dedicated S2C stage could roughly double the prior-pass supply. The S2C data here (agreement 100%, offset −0.06 log10) point that way, but the sample is too small.
2. **A longer lookback.** The pre-registered 15-day diagnostic recovers +0.073 on stained. It needs its own pre-registered test, which choosing it now would not be.

## Files

All in `research/clarity-candidate/stage19/`:

| File | Contents |
|---|---|
| `in19.csv`, `readouts19.csv` | Read-outs for 11–17 days before each observation |
| `passes19.py`, `neighbors19.json`, `passes19.json`, `tasks_nb19.json`, `elevations19.json`, `res_nb19/` | The causal selection and the 575 ACOLITE samples |
| `PREREGISTRATION_STAGE19.md`, `FREEZE_STAGE19.json` | The pre-registration and its hashes |
| `dev19.py`, `dev19.json`, `dev19_rows.json` | Scoring |

FUTURE SCENES USED: NO

BEST LIVE LOOKBACK WINDOW: previous 5 days (statistically equivalent to the highest-scoring 10 days)

CAUSAL CONSENSUS USEFUL: NO

STAGE 18 GAIN SURVIVES LIVE OPERATION: PARTIAL (36% of the stained gain and 38% of the operational gain at 5 days; 46% / 58% at 10 days)

STAINED SCORE: 0.606 (Stage 16 0.571; gain +0.034, CI +0.006 to +0.063; Stage 18 two-sided 0.668)

LIMITED SCORE: 0.680 (Stage 16 0.676)

NORMAL SCORE: 0.669 (Stage 16 0.643)

CLEAR SCORE: 0.883 (Stage 16 0.880)

OPERATIONAL SCORE: 0.710 — 7/10 (Stage 16 0.693; Stage 18 two-sided 0.737)

HARMFUL RATE: 11.4% (Stage 16 10.6%)

SEVERE RATE: 1.39% (Stage 16 1.52%)

EXACT-FEET CAPABILITY: 8/10 (Stage 16 7/10)

STRONG EVIDENCE SHARE / ACCURACY: 11.0% of usable answers / 92.9%

S2C AGREEMENT FINDING: on 15 S2C current passes with a prior S2A/B consensus, the states always shared a class (100%) and contained it 80% of the time; S2C read 0.059 log10 lower, about 13% less visibility (IQR −0.116 to +0.010); the sample is small

STAGE 16 FREEZE BARS PASSED: YES (causal 5-day; adoption failed only on the material stained gain)

TRUE 9/10 DEVELOPMENT BAR PASSED: NO

CURRENT CLARITY SCORE RECOMMENDATION: 7/10 development (uncertified); certified none; deployed production 2/10

READY FOR DEDICATED S2C STAGE: NO (pre-registered as conditional on adopting the causal candidate)

READY TO FREEZE CLARITY AFTER S2C: NO

NEXT BLOCKER: Too few independent earlier passes for live consensus. 67% of current passes have no valid earlier S2A/B pass within 5 days, and 52% within 10. The main lever is Sentinel-2C, a third to a half of 2025–26 passes, which is excluded by rule. After that comes the unseen certification pool.
