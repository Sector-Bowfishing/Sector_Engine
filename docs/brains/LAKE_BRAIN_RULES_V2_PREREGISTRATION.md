# Lake Brain rules v2 — pre-registration

Committed **before** any v2 code exists and before any v2 test is run. Anything not written here may not be used to decide pass/fail later.
Thresholds below are fixed. They are **not** to be lowered, widened or reinterpreted after results are seen; a failed criterion is reported as failed.

Approved by Michael (2026-10-13 session decisions): STABLE floor 0.10 ft (reservoir) / 0.05 ft (natural); RAPID = max(p95 historical rate, 0.25 ft);
pre-register before testing; do not lower after validation. Lake Brain validation stays `NOT_VALIDATED`; nothing here changes lifecycle or claims PARTIAL.

Versions introduced: model `lake-level-rules-v2`, baseline method `doy15-percentile-v2`. (v1: `lake-level-rules-v1`, `doy15-percentile-v1`.)

## 1. Rules

### R1 — history tiers (what a lake's history may be used for)
Complete year = calendar year with ≥ 329 daily values (unchanged). Basis years: the most recent 30 complete years for lakes whose directory `poolBasis` is `fullPool` (regulated); **all** complete years (cap 60) for `naturalSurface` lakes.

| `historicalTier` | complete basis years | `historicalState` values that may be published |
|---|---|---|
| `NONE` | < 5 | `INSUFFICIENT_HISTORY` only |
| `PROVISIONAL` | 5–9 | `NORMAL`, `UNUSUAL` with quality flag `historicalProvisional`; **never** `VERY_UNUSUAL` (a value outside p02–p98 is reported `UNUSUAL`) |
| `STANDARD` | 10–14 | `NORMAL`, `UNUSUAL`; **never** `VERY_UNUSUAL` |
| `FULL` | ≥ 15 | `NORMAL`, `UNUSUAL`, `VERY_UNUSUAL` |

`baselineStatus` keeps its v1 meaning (`SUFFICIENT` ≥ 5, `LIMITED` 2–4, `INSUFFICIENT`, `NONE`), so the Lake score rubric facts are unchanged; `historicalTier` is a new, separate field. (Whether the rubric should demand 10 years is a rubric-v2 decision, not made here.)
Band edges unchanged: NORMAL inside p10–p90; UNUSUAL outside; VERY_UNUSUAL outside p02–p98. Window ±7 days, type-7 quantiles, quantile grid unchanged.
Recency weighting is **not** part of v2.0 (deferred to a later version).

### R2 — trend labels
`floor` = 0.10 ft if the lake is regulated (`poolBasis == fullPool`), 0.05 ft if `naturalSurface`.
- `rate24` = |level(t) − level(t−24 h)| (tolerances as v1).
- `mean72` = (level(t) − level(t−72 h)) / 3 days, ft/day (tolerance ±3 h). If unavailable, fall back to the 24 h change with flag `trend24hFallback`.
- `rapid` when `rate24 > max(seasonal p95 of |Δ24h|, 0.25 ft)` (seasonal p95 only when the rate baseline exists; otherwise the 0.25 ft floor alone, flag `rateBaselineLimited`).
- else `STABLE` when `|mean72| ≤ floor`; `RISING` when `mean72 > floor`; `FALLING` when `mean72 < −floor`.
- The v1 term `seasonal p50` is **removed**.
Existing fields stay: `differenceFromGuideFt`, `differenceFromNormalPoolFt`, `rateOfChangePercentile`, `rapidChangeThresholdFt` (now the effective RAPID threshold).

### R3 — what stays the same
`levelState` (operator zone first), `floodPoolState` (only where the operator publishes a flood-pool bottom), freshness envelope, readiness ladder, `NOT_VALIDATED` status, score rubric.

## 2. Pre-registered test protocol (hold-out, run after implementation, on data not used to set the rules above)
Implementation under test: the Swift rules, mirrored by `jobs/lake-brain/validation/holdout_v2.py` (the mirror is checked against the Swift rules on shared fixtures before it is used).
Data: daily series of the machine-verified strict bindings (`binding-review-v1`, waves w1 + w2-v1, minus the exclusions in the adoption kickoff) with complete-year counts from the research history tables. Test years: each lake's last 5 complete years; training for year Y = complete years before Y (basis rules per R1). No lake or year is dropped after the fact; lakes with fewer than the tier minimum years are simply not in that tier's test.

**H-A band calibration under exchangeability** (tiers `STANDARD` and `FULL`, training ≥ 10 y).
For lake L and held-out year Y compute c(L,Y) = share of days in Y inside [p10,p90]. The reference distribution C_L is the leave-one-year-out coverage of L's own training years (each training year scored with a baseline built from the other training years; needs ≥ 10 values). A lake-year *passes* if c(L,Y) lies within the 5th–95th percentile of C_L. A lake *passes* if ≥ 4 of its 5 test years pass.
*Criterion:* ≥ 80 % of tested lakes pass **and** pooled coverage across all lake-years ∈ [0.75, 0.85].

**H-B tail behaviour** (tier `FULL`, training ≥ 15 y): pooled share of days outside [p02,p98] ≤ 0.06 (nominal 0.04). `PROVISIONAL` lakes: pooled share of days that would have been flagged by the *v1* rule as VERY_UNUSUAL but are reported UNUSUAL under v2 is reported for information (no pass/fail).

**H-C rapid-change rate** (all lakes with a rate baseline, training ≥ 5 y): pooled share of days with `rate24 > max(p95, 0.25 ft)` ∈ [0.03, 0.08] **and** ≥ 70 % of lakes within [0.02, 0.09].

**H-D trend-label stability** (all lakes, training ≥ 5 y): (i) pooled share of consecutive-day pairs where the trend label changes ≤ 0.30; (ii) pooled share of `STABLE` days that sit inside a 3-day move of ≥ 0.5 ft ≤ 0.08.

**Reporting rules.** Each criterion is reported as PASS/FAIL with the numbers, per provider and per lake class, whichever way it falls. Failures are not re-tuned. A passing H-A..H-D result does **not** by itself change `/validation/lake-brain`: see `LAKE_BRAIN_PARTIAL_VALIDATION_DEFINITION.md`.

## 3. Out of scope for this pre-registration
Recency weighting; per-class thresholds; any change to the score rubric; any change to lifecycle or validation status; species presence.
