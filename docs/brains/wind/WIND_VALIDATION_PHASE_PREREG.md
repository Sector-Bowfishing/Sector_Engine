# Wind validation + shadow-readiness phase — pre-registration (2026-10-13, before any result below was computed)

H2 (NBM inits ≥ 2026-10-07) stays sealed until 2027-01-01. Nothing here reads, summarises, copies or derives statistics from H2 forecast, analysis, observation or state VALUES. Allowed metadata for the live-reliability audit only: ingest-ledger status lines (product, cycle id, lake, status), run-summary counters/error strings, Cloud Run execution status/timestamps, and object modification times. No forecast/obs value content from those days is opened. Every skill statistic uses the CAL+H1 corpus (inits 2026-05-06 → 2026-10-06) that earlier campaigns already consumed; results are descriptive and tune nothing.

## M — matched per-bank validation (audited vs estimated)
Same points: every estimate is evaluated at the AUDITED bank standoff coordinates (not at independently sampled shoreline cells), 8 compass wind directions, 9-ray ±12° effective fetch, frozen CEM (6 h steady) at 12 mph; labels use the AUDITED facing for both sides unless stated.
- **M1 method match** (same NHD polygon, 7 lakes: Guntersville, Wheeler, Wilson, Pickwick, Aleknagik, Coventry, Salton Sea). Isolates raster/ray method.
- **M2 source match** (engine polygon, all lakes with both; ≤ 1,500 banks per lake by deterministic stride). The real ESTIMATED-tier test. Banks whose standoff point is not water in the estimated raster (after a 2-cell search) are UNKNOWN, never PROTECTED, and counted.
- **M2-C conservative policy** (frozen now): in the ESTIMATED tier a bank is PROTECTED only if it would still be PROTECTED with its estimated effective fetch multiplied by 1.5; otherwise CROSS (facing lee) or UNKNOWN. M2-C is the candidate product policy.
Metrics (per bank-direction cell; pooled by lake then median across lakes): 3-class label agreement (DIRECT/CROSS/PROTECTED, UNKNOWN excluded and counted); HIGH-FETCH precision and recall (audited chop class ≥ 4 as truth); per-direction Spearman of effective fetch across banks (median); lake dominant-exposure direction within 22.5°; facing-bearing error (estimated gradient vs audited anchor→standoff) median and share within 45°; **false-PROTECTED rate** = share of audited-exposed cells (audited chop class ≥ 3) that the estimate labels PROTECTED; plus the secondary rate vs audited labels DIRECT/CROSS.
Pass lines: M1 — label agreement ≥ 0.90, HIGH-FETCH precision and recall ≥ 0.85, Spearman median ≥ 0.90, false-PROTECTED ≤ 2%. M2 and M2-C — label agreement ≥ 0.85, HIGH-FETCH recall ≥ 0.80, Spearman median ≥ 0.80, dominant direction ≥ 80% of lakes, and for M2-C **false-PROTECTED ≤ 2%**. Failure keeps the tier ESTIMATED with customer exposure labels withheld.

## P — provider shadow comparison (CAL+H1 only)
Production proxy = HRRR 10 m wind from the archived U/V (Stage 3D.1 matched Open-Meteo Best Match to HRRR for ≤ 46 h). Candidate = NBM v5.0. Same station rows, same tonight rows as the research (init 12Z lead 12/18, 18Z lead 6/12). Observed truth = METAR at the 8 stations. Winner per row = smaller absolute speed error (tie within 0.5 mph); direction winner = smaller circular error when both ≥ 5 mph and observed ≥ 2.6 m/s. Report by lake, speed class, lead, direction sector, night/day. Where no observation exists the row is PROVIDER DISAGREEMENT, not accuracy. No pass line (decision input).

## S — strong-wind mechanisms (CAL+H1, frozen product rules, descriptive)
Evaluate as shipped: category-as-floor, P90 `ifItBlows`, `breezyRisk` (P90 ≥ 10 mph), confidence. Report for observed ≥ 10 and ≥ 15 mph nights: flagged share, miss rate, false-alarm rate, how often the product text would have been "light/calm with no risk" on a ≥ 10 mph night, by station/lake. Sensitivity of P90 thresholds 8/9/10/12 is reported for information only; the product threshold stays 10 (frozen in the H2 pre-registration). No numeric speed correction is applied or tested.

## F — fleet sampling (synthetic + real grid geometry, no network)
The fleet sampler must reproduce per-lake cut-out interpolation within 0.02 m/s and 1° on 621 real lake points over a real archived NBM grid (grid geometry only, taken from `grids/nbm`, no forecast values from H2), be deterministic, and run 621 lakes × 36 leads in under 5 s on a laptop.

## T — tonight scenarios
Unit-test fixtures A–E from the work order; all must pass.

## L — live reliability
A calendar day is VALID only if (a) ≥ 99% of the 24 expected hourly NBM cycles are archived with status `complete` for every live lake, (b) ≥ 95% of expected RTMA-RU quarter-hours archived, (c) METAR day object present and fresh, (d) the Brain state object was refreshed at least hourly and never > 90 min stale during the day, and (e) no job execution failed unrecovered. Otherwise it is INVALID with the reason recorded. Scheduler runs alone do not count.
