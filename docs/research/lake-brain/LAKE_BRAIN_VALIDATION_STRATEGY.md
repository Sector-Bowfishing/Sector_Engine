# Lake Brain — validation without 621 field trips

Status: research (2026-10-13). Nothing here changes `/validation/lake-brain` (still `NOT_VALIDATED`), the lifecycle, or the rubric.
Evidence run: `research/lake-brain/holdout_validation.py` (pre-registered, committed before it ran), binding review `binding-review-v1`
(`LAKE_BRAIN_BINDING_RESEARCH.md`), species cross-checks (`LAKE_BRAIN_SPECIES_PRESENCE_RESEARCH.md`).

## 1. Why it matters, and what the rubric can and cannot see
`validation` is 15 % of the Lake score **and** a gate: `NOT_VALIDATED` caps the score at **5.0** regardless of anything else
(`LAKE_BRAIN_AUDIT.md` §3). With coverage and quality evidence in hand, the displayed research score is pinned at 5.0 until this
changes (`data/score_marginals_final.json`: strict research scenario 5.0 → 7.4 at PARTIAL → 8.1 at VALIDATED).
The rubric knows only a fleet-wide ternary. The evidence does not arrive that way, so this document validates **per dimension**
and then says honestly what a single status can and cannot claim.

## 2. Dimension-specific validation matrix

| # | Dimension / claim | Tier | Independent truth used | Result today | Verdict |
|---|---|---|---|---|---|
| V-A | **Lake → level-source binding is the right water** | B (independent agreement) + D (operator metadata, NID, geometry) | NID dam ids, station names, polygon distance, directory full pool, a second origin for the same lake | binding-review-v1 R1–R9 machine pass on 258 core / 315 incl. flagged; 122 of 123 independent pairs within 2 ft (median gap 0.01 ft); 57-binding manual adjudication 0 wrong, 10 of 10 two-origin agree, 0 of 15 operator-level checks contradicted; my own seeded 16-lake audit found none implausible | **Validated by agreement, conditional on human acceptance** (§4). 95 % upper error bound ≈ 5 % (rule of three) — not a measured 0 % |
| V-B | **Current level is accurate** (value, datum, timeliness) | B | same-lake, different origin (CWMS vs USGS Hartwell 0.03 ft; HADS vs TVA 0.00 ft; A2W vs CWMS/USGS pairs) | agreement tight where two origins exist (125 pairs, 120 within 0.5 ft); 4 early A2W tailwater errors were caught by R9 and rejected | **Validated where checkable** (≈ 70 lakes with two origins); single-origin lakes rely on V-A |
| V-C | **History is complete and continuous** | A/B | the provider's own record + reconciliation vs a second feed | TVA pilot composite 16–18 complete years, MAE 0.001–0.003 ft vs the Lake Brain history over 647 days | **Validated** for the TVA pilots; recount rule is mechanical (≥ 329 days/yr) |
| V-D | **Seasonal band (p10/p50/p90, p02/p98) is calibrated** | C (temporal hold-out) | the lake's own later years | 154 lakes, 10-y training: median coverage p10–p90 = 0.84 (nominal 0.80), p02–p98 = 0.973, tail rate 2.7 % (nominal 4 %); but only **32.5 % of lakes** meet the per-lake pre-registered tolerance; with the rubric's 5-y training 237 lakes: tail rate median **5.9 %** (101 lakes > 8 %) | **Not validated** per-lake; fleet-level calibration reasonable at ≥ 10 y; **5 years is overconfident in the tails** |
| V-E | **Rapid-change flag (|Δ24 h| > seasonal p95)** | C | later years | 80 % (10-y) / 85 % (5-y) of lakes have a realised rate within [2 %, 9 %] (nominal 5 %) | **Passes** the pre-registered 70 % bar for this family alone |
| V-F | **STABLE rule** (`max(0.10 ft, seasonal p50)`) | C + analytic | day-level distribution | baselines thread: calls 51–58 % of days STABLE by construction; 6–18 % of STABLE days sit inside a ≥ 0.5 ft 3-day move | **Fails** — replace before validating (`LAKE_BRAIN_BASELINE_RESEARCH.md` §2.5) |
| V-G | **levelState vs operator zone** (IN_ZONE / ABOVE / BELOW / FLOOD_POOL) | tautology | – | a comparison against the operator's own published levels; correctness = correct binding + correct datum (V-A/V-B) + correct level semantics | Validate the *levels' meaning* (e.g. CWMS "Top of Conservation" is the flood-pool bottom), not the comparison. Operator-level checks: 0 of 15 contradicted |
| V-H | **Flood-pool state** | A | operator-published flood-pool bottom | applies only where the operator publishes it (~30 % of bound lakes) | Not applicable elsewhere — must stay `UNKNOWN`, not scored as a gap |
| V-I | **Lake geometry (boundary)** | B | NID surface area, USACE pool polygon, OSM, JRC occurrence | 351 HIGH / 195 MEDIUM / 53 LOW / 22 MISSING (`LAKE_BRAIN_GEOMETRY_RESEARCH.md`) | Validated against independent sources; does not enter the rubric |
| V-J | **Species presence** | B + hold-out | independent in-waterbody records (NAS, GBIF, agencies) | recall 84–100 % carp, 63–77 % gar/buffalo; 408 of 525 private positives corroborated; independence limited | Partial, aggregate only; does not enter the rubric |
| V-K | **Pilot → fleet transfer** | E | leave-one-class-out | calibration quality is the same in every class that has ≥ 10 lakes (pass rates 28–34 % for R2/R3/R4); pilots cover only 2 of 9 lake classes | Transfer **not** demonstrated by the pilots; use class-stratified onboarding (`LAKE_BRAIN_FLEET_SCALING.md`) |

## 3. Tiers (applied)

| Tier | Meaning | Used for |
|---|---|---|
| A | direct authoritative observation of the quantity | operator levels, flood-pool bottom, TVA vs HADS |
| B | ≥ 2 independent authoritative sources agree | binding identity and level accuracy (122/123 pairs) |
| C | historical comparison / temporal hold-out | baseline bands, rapid-change calibration |
| D | operator metadata + spatial/source validation | review criteria R1–R8, NID, geometry |
| E | transfer validation from representative classes | pilot-to-fleet |

## 4. Binding acceptance without reviewing 315 rows by hand
The machine review (`binding-review-v1`) is deterministic: R1 station ≤ 1.5 km of the polygon; R2 name similarity ≥ 0.5 or inside the
polygon; R3 not a tailwater/river/piezometer series; R4 state match; R5 no other lake claims the series better; R6 last observation < 72 h
(192 h daily); R7 30-day median within −25…+8 ft of the directory full pool (a flagged "drawdown" class down to −220 ft needs strong identity);
R8 datum identified; R9 independent sources agree within 2 ft. It reproduces all 5 hand-reviewed pilots.
The rubric counts only **reviewed** bindings, so a human (or a human-approved procedure) must accept the rows. **Acceptance sampling**
turns that into ~one hour of work instead of 315 row reviews: draw a stratified random sample (provider × capability × flagged), review each
against the station page, and apply:

| Sample | 0 errors | 1 error | 2 errors | 3 errors |
|---|---|---|---|---|
| n = 40 | 95 % upper bound 7.2 % | 11.3 % | 14.9 % | 18.3 % |
| n = 60 | **4.9 %** | 7.7 % | 10.1 % | 12.4 % |
| n = 80 | 3.7 % | 5.8 % | 7.7 % | 9.4 % |

Recommended rule: n = 60 stratified, accept the batch at ≤ 1 error (upper bound ≤ 7.7 %); on 2+ errors review the stratum in full. The 57 **flagged**
rows (deep drawdown or weak full-pool confidence, single origin) are the main residual risk and are reviewed in full, not sampled.

## 5. Hold-out calibration — method and result
`holdout_validation.py` re-implements `doy15-percentile-v1` exactly (±7 days, quantile grid, type-7) and walks forward: for each of the last five
complete years of each lake, train on the earlier complete years (most recent 30; ≥ 10 or ≥ 5 required), score the held-out year. Criteria were fixed
and committed (c7d8bf17) before the first run:

| Test | Criterion | Result (10-y training, 154 lakes) | Result (5-y training, 237 lakes) |
|---|---|---|---|
| V1 band | per lake, mean [p10,p90] coverage ∈ [0.70,0.90] **and** [p02,p98] ∈ [0.92,0.99] | 47 lakes too wide, 25 too narrow | |
| V2 tails | per lake, share outside [p02,p98] ≤ 0.08 | 34 fail | **101 fail** |
| V1∧V2 | fleet bar ≥ 70 % of lakes | **32.5 %** | **25.7 %** |
| V3 rapid | per lake realised rate ∈ [0.02,0.09], fleet bar ≥ 70 % | **79.9 %** | **85.2 %** |
| Fleet medians (nominal) | in80 (0.80) / in96 (0.96) / tail (0.04) / rapid (0.05) | 0.840 / 0.973 / 0.027 / 0.045 | 0.802 / 0.941 / 0.059 / 0.047 |
| Verdict | `ELIGIBLE_FOR_PARTIAL` needs V1∧V2 and V3 ≥ 70 % | **NOT_ELIGIBLE** | **NOT_ELIGIBLE** |

By provider and class (`data/holdout_validation_mt10.json`): no provider and no class passes V1∧V2 at 70 %; run-of-river pools score best (4 of 5) but n is tiny.

**What the numbers mean.** (1) With 5 years of training the baseline is overconfident in the tails: VERY_UNUSUAL fires on 5.9 % of days (nominal 4 %),
and on > 8 % for 101 of 237 lakes — an independent, 237-lake confirmation of the baselines thread's finding that the SUFFICIENT = 5 years rule is too lax.
(2) With ≥ 10 years the fleet is, if anything, conservative (tail 2.7 %), which is the safe direction for an advisory flag.
(3) Per-lake coverage varies far more than a simple binomial would predict because hydrology is autocorrelated and operations change (rule-curve
revisions, drought cycles): five held-out years are a handful of effectively independent seasons. **The pre-registered per-lake tolerance was probably too tight for that — but it is not
re-tuned after seeing the result.** Any PARTIAL claim must come from criteria that are pre-registered with year-block uncertainty and tested on
data not used to design them (§6).

## 6. What would honestly earn PARTIAL, and VALIDATED

Proposal for Michael's decision (this is a definition, not a status change): **PARTIAL** = (a) bindings accepted by acceptance sampling (§4) **and** (b) at
least one classification family (the rapid-change flag) calibrated on ≥ 100 lakes against a pre-registered criterion **and** (c) every family that fails its
criterion is withheld (`INSUFFICIENT_HISTORY`/`UNKNOWN`) rather than published. Today (a) awaits review, (b) is met for the rapid-change flag only on the exploratory run, and (c) requires the rule changes below.
**VALIDATED** additionally needs a **prospective** result: predictions logged from the day the fleet job runs and scored after 12 months (the only evidence that cannot be overfit to the history we have already seen).

Rule changes the evidence supports (implementation, not done): minimum 10 complete years for NORMAL/UNUSUAL and 15 for VERY_UNUSUAL (5–9 years → LIMITED, no VERY_UNUSUAL); use all years (no 30-year cap) for natural lakes and recency weighting for lakes whose operations changed;
STABLE = fixed floor (0.10 ft reservoirs, 0.05 ft natural) with a 72 h mean-rate label, RAPID = max(p95, 0.25 ft); keep both anomaly-vs-guide and vs-history fields.
After these changes, re-run `holdout_validation.py` with a **v2 pre-registration** and year-block bootstrap acceptance intervals.

## 7. Prospective validation protocol (low effort, high value)
1. Orchestrator `lake-brain` job (already scheduled when stale) appends each published classification to `gs://sector-lake-brain/predictions/{lake}/{yyyymm}.jsonl` (state kinds, band edges used, rate threshold) — no new compute.
2. A monthly scorer joins predictions to the realised level 1 d / 7 d / 30 d later and writes calibration tables per lake and class.
3. After 12 months, the v2 criteria are applied once. Publish pass/fail per dimension; never roll up silently.

## 8. What makes Lake Brain honestly trustworthy at scale (without visiting lakes)
Identity and source are verified by independent agreement and operator metadata (V-A, V-B); every classification that depends on history is published only when
the lake has enough years for that classification (V-D, V-F); the operator's own levels drive zone/flood states and stay `UNKNOWN` where the operator publishes nothing (V-G, V-H);
each family carries its own validation status in the state's `provenance` rather than a single fleet flag; and a prospective ledger keeps the claim honest as the fleet grows.
Field visits remain a premium confidence tier for chosen pilot lakes, not a prerequisite.
