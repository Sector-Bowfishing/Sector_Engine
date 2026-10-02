# Stage 18 pre-registration: the physical-pass consensus rebuild

**Timing.** Written 2026-10-02. Before writing it, the only things computed were value-blind:
- the physical-pass identity and its validation;
- the Stage 17 contamination count;
- the rebuilt neighbour selection (`passes18.py`).

Nothing yet: no consensus prediction, no score, no rebuilt-neighbour Secchi comparison. This file's sha256 goes into
`FREEZE_STAGE18P.json`.

**What is never used:**
- field reports;
- Stage 14/15 certification truth;
- Stage 16 fresh truth.

**What is never changed:** the frozen production C-gbm (`frozen_gbm.pkl`) is not refit or touched. Development scenes are
predicted by the whole-lake-held-out fold models, exactly as in Stages 14–17.

## 1. Physical pass

**The identity.** A physical pass is (platform, UTC sensing date).
- A Sentinel-2 satellite images a site at most once a day.
- So every Earth Search item of one platform on one day is one observation: overlapping MGRS tiles, datastrip twins
  and duplicate representations alike.

**Validated before scoring** (`validation18.json`):
- **Against L1C datatakes.** On 6,544 pairs of items with a known L1C datatake, the key and the datatake agree 6,544
  times out of 6,544.
- **Sensing time.** Sensing times within one pass are at most 18.7 s apart. Two passes of one platform are at least 72
  h apart.
- **Manual review.** 20 duplicate groups were reviewed, across all three kinds. Every one is a single datatake (same
  satellite, datatake start and relative orbit).

**Stage 17 contamination:**
- 728 of its 2,487 neighbour observations (29.3%) disappear;
- 457 were the anchor's own pass (399 events);
- 271 repeated another neighbour (268 events).

## 2. Data

**Events.** The 1,582 Stage 16 development events (`dev16_rows.json`), with development truth only.

**The anchor** is the Stage 16 matched pass, unchanged: its tier, its outer-fold prediction, and its Stage 16 product
as the fallback.

**Neighbours** (`neighbors18.json`):
- **Eligible passes:** within ±10 days, with a valid production-gated Sen2Cor disk (n_valid ≥ 5), excluding the anchor's
  own pass.
- **One item per pass:** the representative is the item with the most valid pixels, then the lowest scene cloud, then
  the item id.
- **Which passes:** the 3 nearest by |dt|, then by cloud.
- **ACOLITE:** each representative goes through the frozen path. If it has no valid tier, the pass does not contribute,
  and no other item stands in for it (Stage 17's no-replacement rule).

**Windows:** ±3, ±5, ±7 and ±10 days, all subsets of the same selection.

**Hydrology:** none; the Stage 17 ERA5 rule is not used. The share of contributing neighbours that rule would have
excluded is reported as context only.

**No pass contributes twice.** This is asserted for every event: the pass keys among the contributing scenes, the
anchor's included, are distinct.

## 3. Methods (16 variants: 4 methods × 4 windows, S2C off)

The four methods are the Stage 17 methods, unchanged. Each scene's variance is σ²_tier + κ·|Δt|, with σ and κ refit
per fold on inner folds from independent passes.

| Method | What it does |
|---|---|
| M-agree | The prediction and state stay the anchor's (Stage 16); neighbours only change the evidence level |
| M-iuw | Inverse-uncertainty weighting |
| M-robust | Huber, c = 1.5 |
| M-bayes | Gaussian latent prior from the training lakes |

**Calibration.**
- n = 1 uses the Stage 16 posteriors.
- n = 2 and n ≥ 3 use nested posteriors from the inner-fold consensus predictions, needing at least 40 rows; otherwise
  the Stage 16 posteriors.
- The gate is 0.70 / 0.70.
- If every contributing scene is tier 2, the answer is boundary-only.
- With no full-authority scene, the event falls back to Stage 16.

**Robust and Bayesian count only if materially distinct.** That means their class-balanced operational score exceeds
M-iuw's at the same window by more than 0.01. Otherwise M-iuw stands for them.

## 4. Metrics

**Per variant and for Stage 16:**
- operational, class-balanced and per class: clear, normal, stained, limited;
- harmful and severe rates;
- the Unknown share;
- mean posterior confidence of answered rows;
- exact-feet error: the median |log10 error| of consensus predictions on answered rows, and the Stage 12 exact-feet
  capability;
- Strong share of usable answers, and Strong truth-in-answer.

**Stained only:** operational, truth-in-answer (full-authority answers), harmful rate, exact-feet error, mean
confidence and Unknown rate.

**S2C (descriptive, for Stage 19 only).** S2C stays lower authority and never contributes. Where an independent S2C
neighbour pass and an S2A/B consensus both exist, report how often the S2C scene's own state:
- shares a class with the consensus state;
- contains it.

## 5. Strong evidence

A Strong answer needs:
- full authority;
- posterior ≥ 0.90;
- at least 2 compatible full-authority scenes from different physical passes (the anchor counts as one) whose states
  contain the answer;
- no compatible full-authority scene with a state disjoint from it.

## 6. Selection

**The candidates:** variants meeting every Stage 16 freeze bar on development:
- round(10 × class-balanced) ≥ 7;
- every core class ≥ 0.60;
- harmful ≤ 15%;
- severe ≤ 2%.

**The winner:** among the candidates, the highest class-balanced operational score.

**Ties:** anything within 0.01 counts as tied, and the simplest wins. The order is M-agree < M-iuw < M-robust <
M-bayes, then the smaller window.

## 7. Decisions

**CONSENSUS ADOPTED: YES** only if the selected variant:
- passes every Stage 16 freeze bar;
- improves stained over Stage 16 by ≥ 0.05, with the lake-bootstrap 95% CI of the difference above 0 (2,000 resamples,
  seed 18);
- keeps severe ≤ 2% and harmful ≤ 15%;
- uses independent physical passes only.

**STAGE 17 GAIN SURVIVES** compares Stage 17's challenger variant (M-iuw ±10, S2C off), rebuilt, against Stage 16 on
stained:

| Answer | When |
|---|---|
| YES | Gain ≥ 0.05 and CI lower bound > 0 |
| PARTIAL | CI lower bound > 0 but gain < 0.05, or gain ≥ 0.05 but CI reaching 0 |
| NO | Otherwise |

The Stage 17 gain was +0.096.

**TRUE 9/10 DEVELOPMENT BAR:** all of these:
- operational ≥ 0.85;
- weakest core class ≥ 0.80;
- harmful ≤ 5%;
- severe ≤ 0.5%;
- Strong ≥ 50% of usable answers at ≥ 90% truth-in-answer.

**CURRENT CLARITY SCORE RECOMMENDATION:** round(10 × class-balanced operational) of the adopted engine, or Stage 16 if
none is adopted, on whole-lake-held-out development. It is a development capability, not a certified score.

**Never lowered:** none of these bars.
