# Current Clarity Stage 17: Multi-Scene Consensus

**Development only.**
- The single-scene engine is unchanged: C-gbm and its scene predictions are not refitted, and fold models are used
  exactly as in Stages 14–16.
- No field report, Stage 16 fresh row or Stage 14/15 certification row was used.
- Production is unchanged, and nothing was deployed.
- Water Temperature is not started.

| Step | UTC | What was fixed |
|---|---|---|
| Pre-registration | 2026-10-01T18:19:29Z | Windows, the 3-nearest cap, rainfall compatibility, 4 methods, S2C variants, the Strong agreement rule, selection, bars (`PREREGISTRATION_STAGE17.md`, `a058f476…`) |
| Inputs | 2026-10-01T23:54:18Z | 2,072 neighbour-scene ACOLITE results, ERA5 rainfall, the neighbour list (`scenes/`) |

## The answer

**Combining neighbouring satellite views does help, but under the rule I froze it is not adopted.**
- **What combining gains.** Weighting each frozen scene prediction by its uncertainty, over ±10 days (M-iuw), raises
  stained water from **0.571 to 0.667** (+0.096, CI +0.054 to +0.143) and the operational score from 0.693 to 0.743.
- **The Stage 16 freeze bars.** With it, every core class clears 0.60, so it
  **meets the Stage 16 freeze bars on development** for the first time.
- **What else it improves.**
  - Stained answers are right more often: 79%, from 72%.
  - Stained harm falls from 22% to 18.5%.
  - Exact feet tighten from ×1.36 to ×1.33.
- **The cost.** It answers about 100 rows that Stage 16 left Unknown, and some of those answers are wrong. The overall
  harmful rate rises **from 10.6% to 11.6%**. The CI of that change (−0.2 to +2.1 points) includes zero.
- **The frozen rule.** It admitted only variants that do not raise the harmful rate at all. That leaves only
  agreement-only variants, which keep every Stage 16 answer, so **MULTI-SCENE CONSENSUS USEFUL is NO**.

**Two pre-registered ideas do not hold up:**
- **The rainfall rule makes every method worse.** ERA5 point rainfall discards scenes that were in fact still
  informative.
- **Strong evidence reaches at most 24%,** at 95% right. That is far from the 50% target.

**Sentinel-2C cannot be tested on development:** only 49 of the 2,072 neighbour scenes are S2C.

**Bars.** The true 9/10 bar is far away. Readiness to move to Water Temperature is **NO**.

**The decision this leaves you.** Accepting about one extra harmful answer per hundred, a change that is not
statistically significant, would buy a material stained-water gain. That needs a new, unseen certification pool either
way.

## 1. How the consensus was built

**Which scenes.** Each development event gets up to its **3 nearest valid neighbouring passes** within ±10 days. These
are the Stage 11 production-gated passes with ≥ 5 valid water pixels, excluding the matched pass.
- **The run.** 2,487 neighbour scenes for 1,215 events, run through the unchanged K4 ACOLITE path: 2,072 L1C items, 15
  failures (6 had no L1C).
- **The predictor.** Each scene is predicted by the fold C-gbm trained without its lake.

| Window | Events with ≥ 1 valid neighbour (Stage 11 production gates) |
|---|---:|
| ±3 days | 623 of 1,582 (39%) |
| ±5 days | 919 (58%) |
| ±7 days | 1,064 (67%) |
| ±10 days | 1,215 (77%) |

**How each scene is weighted.** Each scene carries its prediction, tier, platform and Δt. Its variance is
σ²_tier + κ·|Δt|, fitted on training lakes:
- σ ≈ 0.19 (tier 1) and 0.17–0.20 (tier 2);
- κ ≈ 0.0015–0.0020 per day.

That growth is small: a scene 10 days away is only about 20% noisier than the matched one.

**Calibration.** Posteriors are re-calibrated (nested) by the number of contributing scenes, and the frozen Stage 16
gate (0.70 / 0.70) issues the state.

## 2. The four methods (±10 days, no rain rule, S2C off)

| Development (whole-lake held out) | Operational | Harmful | Severe | Clear | Normal | Stained | Limited | Strong share / right |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| **Stage 16 (anchor scene only)** | 0.693 | 10.6% | 1.5% | 0.880 | 0.643 | 0.571 | 0.676 | 11% / 97% |
| M-agree (±10 d, no rain rule, S2C off) | 0.693 | 10.6% | 1.5% | 0.880 | 0.643 | 0.571 | 0.676 | 21% / 95% |
| M-iuw (±10 d, no rain rule, S2C off) | 0.743 | 11.6% | 1.3% | 0.893 | 0.701 | 0.667 | 0.710 | 23% / 95% |
| M-robust (±10 d, no rain rule, S2C off) | 0.743 | 11.6% | 1.3% | 0.892 | 0.701 | 0.667 | 0.710 | 23% / 95% |
| M-bayes (±10 d, no rain rule, S2C off) | 0.745 | 11.4% | 1.3% | 0.893 | 0.703 | 0.671 | 0.711 | 23% / 95% |
| M-bayes (±10 d, no rain rule, S2C agree) | 0.745 | 11.3% | 1.4% | 0.891 | 0.704 | 0.675 | 0.709 | 24% / 95% |

- **Combining matters, the method does not.** The three combining methods are within 0.003 of one another. Down-weighting
  outliers (M-robust) and a population prior (M-bayes) add nothing over plain inverse-uncertainty weighting.
- **The lesson of Stage 11 holds.** Combining helps because it averages several independent errors. It does not help
  by discarding the matched scene.

## 3. Windows and hydrology

| M-iuw, S2C off | ±3 d | ±5 d | ±7 d | ±10 d |
|---|---:|---:|---:|---:|
| Operational (no rain rule) | 0.696 | 0.714 | 0.722 | 0.743 |
| Stained (no rain rule) | 0.545 | 0.590 | 0.611 | 0.667 |
| Harmful (no rain rule) | 11.4% | 12.1% | 12.3% | 11.6% |
| Operational (rain rule) | 0.696 | 0.707 | 0.715 | 0.726 |
| Stained (rain rule) | 0.548 | 0.580 | 0.603 | 0.634 |
| Harmful (rain rule) | 11.4% | 12.5% | 12.5% | 12.3% |

- **The widest window is best.** Most events have a valid neighbour only beyond ±3 days.
- **The rainfall rule (≥ 20 mm, or a day ≥ 12.7 mm) lowers the score at every window.** At the scale of an ERA5 cell,
  rain is a poor proxy for whether a lake's clarity changed. Hydrology may still decide compatibility, but this rule
  does not earn its place.

## 4. Stained water, the primary question

| Stained water (development) | Stage 16 | Selected (agreement-only) | M-iuw ±10 d (not adopted) |
|---|---:|---:|---:|
| Operational score | 0.571 | 0.571 | **0.667** |
| Answer right (full-authority answers) | 72% | 72% | **79%** |
| Harmful (stained rows) | 22.0% | 22.0% | **18.5%** |
| Mean posterior of issued states (all) | 0.805 | 0.805 | **0.830** |
| Exact-feet error, rows with a consensus | ×1.36 | ×1.36 | **×1.33** |

| M-iuw ±10 d against Stage 16 (lake bootstrap, 2,000, seed 17) | Difference | 95% CI |
|---|---:|---|
| Stained score | +0.096 | +0.054 to +0.143 |
| Class-balanced operational | +0.050 | +0.035 to +0.066 |
| Harmful rate | +0.95 pts | -0.19 to +2.08 pts |

- **For stained water, every measure improves.** That includes the stained harmful rate, which falls.
- **Where the overall harm increase comes from.** About 100 former Unknowns now get answers (Unknown falls from 13% to
  6%), and a few of those are wrong.

## 5. Strong evidence

| Agreement-only (M-agree, S2C off), Strong share / right | ±3 d | ±5 d | ±7 d | ±10 d |
|---|---|---|---|---|
| rain rule | 11% / 94% | 15% / 95% | 17% / 95% | 19% / 95% |
| no rain rule | 11% / 94% | 17% / 95% | 19% / 95% | 21% / 95% |

| Evidence level (share of all answers) | Stage 16 | Selected (agreement-only) | M-iuw ±10 d |
|---|---:|---:|---:|
| Strong | 10% | 9% | 22% |
| Moderate | 70% | 71% | 68% |
| Weak | 7% | 7% | 4% |
| Unavailable | 13% | 13% | 6% |
| Strong right | 97% | 94% | 95% |

**What agreement buys.**
- **The rule:** at least 2 compatible full-authority scenes whose states contain the answer, no disagreeing scene, and a
  posterior ≥ 0.90.
- **What it gives:** at ±10 days, Strong rises from Stage 16's 11% to 21–24% of usable answers, at 95% right. With only
  ±3 days (the selected variant) it stays at 11%.
- **The target is out of reach.** It is not close to 50%: half of events have at most one valid neighbour (23% have
  none), and agreement often still leaves the posterior below 0.90.
- **Why not loosen it.** Lowering the bar to hit 50% would trade accuracy for coverage, which the pre-registration
  forbids.

## 6. Sentinel-2C

**S2C AGREEMENT CAN UPGRADE AUTHORITY: NO.**
- **The test.** S-agree against S-off, at the selected variant.
- **The result.** S2C raised **0** answers' evidence level, against the 30 required.
  Development contains almost no S2C: 49 of 2,072 neighbour scenes, and 38 anchors.
- **What it would take.** Adding agreeing S2C scenes changes the consensus very little (M-bayes S2C-agree against S2C-off:
  0.745 against 0.745). The question can only be answered on 2025–2026 data, where S2C is a third of scenes.
- **No S2C scene regains authority alone,** and no S2C bias correction was fitted.

## 7. What the user would see (logic first)

| Underlying evidence | Display |
|---|---|
| Strong: ≥ 2 compatible full-authority views agree, posterior ≥ 0.90 | **2.7 ft · Normal-to-Stained** · High confidence — recent satellite views agree |
| Moderate: one view, or views that do not all agree but none disagree | **2.7 ft · Normal-to-Stained** |
| A compatible full-authority view disagrees | **~2.7 ft · Normal-to-Stained** · Lower confidence — recent views disagree |
| Weak (Sentinel-2C only, or tier 3) | **~2.7 ft · Normal-to-Stained** · Lower confidence |
| Unknown | Visibility unknown — no reliable recent view |

- **No scene counts.** The confidence line already says what the count would.
- **The algal warning** stays a separate line.

## 8. Bars

| Bar | Selected (agreement-only) | M-iuw ±10 d (not adopted) | Required |
|---|---|---|---|
| Operational | 0.693 | 0.743 | 9/10: ≥ 0.85; Stage 16: ≥ 7/10 |
| Weakest core class | 0.571 (stained) | 0.667 (stained) | 9/10: ≥ 0.80; Stage 16: ≥ 0.60 |
| Harmful | 10.6% | 11.6% | 9/10: ≤ 5%; Stage 16: ≤ 15% |
| Severe | 1.5% | 1.3% | 9/10: ≤ 0.5%; Stage 16: ≤ 2% |
| Strong share / right | 11% / 94% | 23% / 95% | 9/10: ≥ 50% / ≥ 90% |
| **Stage 16 freeze bars** | **no** (stained 0.571) | **yes, on development** | |
| **True 9/10** | **no** | **no** | |

- **The selected variant is Stage 16's answers with better evidence labels.** It meets neither bar.
- **The combining method meets the Stage 16 freeze bars on development, but not the 9/10 bar.** Stained (0.67) is still
  far from 0.80, harmful far above 5%, and Strong far below 50%.

## 9. Certification (none here)

**What exists.** Stage 16's 108 fresh rows are historical context only: 7/10 operational, insufficient. They were not
used.

**What a Stage 17 design needs.** A completely unseen pool. The immediate sources for US stained and limited reservoir
Secchi are:
1. **Oklahoma Water Resources Board, Beneficial Use Monitoring Program.** About 130 reservoirs sampled quarterly on a
   five-year rotation, many of them turbid. Data are served through the University of Oklahoma OKH2O water-quality
   portal (OWRB BUMP: `oklahoma.gov/owrb/data-and-maps/beneficial-use-monitoring-program.html`,
   OU portal: `ou.edu/okh2o/monitoring/data-portal/water-quality-data.html`).
2. **Texas TCEQ SWQMIS.** Reservoir Secchi from TCEQ and the river authorities, downloadable directly from TCEQ ahead of
   WQP's lag (TCEQ SWQM data: `www.tceq.texas.gov/waterquality/data-management/swqm_data.html`).
3. **TVA reservoir monitoring and USACE district water-quality programs:** a direct records request. There is no public
   bulk download.
4. **A WQP re-pull around April 2027** for the 2026 state uploads.

**Before anything is retrieved,** each needs the Stage 16 protocol: sites in no earlier file, a value-blind index, and
frozen minima.

---

MULTI-SCENE CONSENSUS USEFUL: NO (by the frozen rule. Every combining method raised the harmful rate and was excluded; the selected agreement-only variant keeps Stage 16's answers, so stained is unchanged. The best combining method, inverse-uncertainty weighting over ±10 days, raised stained by +0.096 (CI +0.054 to +0.143) and operational by +0.050 (CI +0.035 to +0.066), with harmful +0.95 points (CI −0.19 to +2.08): useful on the evidence, but not adopted)
BEST CONSENSUS METHOD: Agreement-only evidence upgrade (±3 days, rainfall rule on, S2C off), the simplest pre-registered variant that does not raise harm. If a ~1-point harmful increase is accepted: inverse-uncertainty weighting of frozen scene predictions over ±10 days without the rainfall rule (M-robust and M-bayes add nothing over it)
STAINED SCORE: 0.571 selected (unchanged from Stage 16); 0.667 with inverse-uncertainty weighting ±10 d (not adopted)
LIMITED SCORE: 0.676 selected; 0.710 with weighting ±10 d
OPERATIONAL SCORE: 0.693 (7/10) selected; 0.743 (7/10) with weighting ±10 d
HARMFUL RATE: 10.6% selected; 11.6% with weighting ±10 d
SEVERE RATE: 1.5% selected; 1.3% with weighting ±10 d
STRONG EVIDENCE SHARE: 11% of usable answers selected; at most 24% for any variant (Stage 16: 11%); the 50% target is not met
STRONG EVIDENCE ACCURACY: 94% selected; 95% with weighting ±10 d
S2C AGREEMENT CAN UPGRADE AUTHORITY: NO (development holds almost no Sentinel-2C: 0 upgraded answers against the 30 needed; testable only on 2025–2026 data)
DEVELOPMENT CAPABILITY: 7/10
TRUE 9/10 DEVELOPMENT BAR PASSED: NO
NEXT UNSEEN CERTIFICATION SOURCE: Oklahoma OWRB Beneficial Use Monitoring Program reservoirs (OU OKH2O portal) and Texas TCEQ SWQMIS reservoir Secchi, retrieved directly for sites in no earlier file under the Stage 16 protocol. Then a TVA/USACE records request and a WQP re-pull around April 2027
READY TO MOVE TO WATER TEMPERATURE: NO (the 9/10 bar is not passed; the selected variant misses the Stage 16 bars (stained 0.571); the combining method meets them on development, but no unseen certification pool exists yet)
