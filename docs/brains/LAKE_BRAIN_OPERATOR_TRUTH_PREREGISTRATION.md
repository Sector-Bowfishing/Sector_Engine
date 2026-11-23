# Lake Brain: operator-truth validation v1 (`lake-operator-truth-v1`): pre-registration

Committed **before any water-level value is fetched** for this test, and before the runner exists. Anything not written here may not be used to decide
pass or fail later. Thresholds are fixed: they are not to be lowered, widened or reinterpreted after results are seen. A failed criterion is reported as
failed. A harness bug found after the run is fixed and the run is repeated once on the same frozen sample and window, with the bug and both results
reported (RS-30); nothing else is re-run.

`/validation/lake-brain` stays `NOT_VALIDATED`. This document, the runner and its result change no status, score, rubric, binding or live build.
Publishing a result is a separate owner decision (section 8).

## 1. What the rubric asks, and what it does not say

- Rubric `docs/brains/scoring/lake-brain-score-v1.json`: dimension `validation` (weight 15) reads `/validation/lake-brain.status` only
  (`NOT_VALIDATED` 0, `PARTIAL` 5, `VALIDATED` 10). Gate `validation` caps the score at 5.0 while the status is `NOT_VALIDATED` (or absent).
  The scorer is `score_lake` in `jobs/brain_platform/sector_brain_platform/scoring.py`; it reads only `status`. `PARTIAL` lifts the gate.
- `score_improvements_v1.json` names the work: "Run a validation against operator truth (lifts the 5.0 cap)".
- **The rubric defines no truth source, sample size, metric or pass mark.** Those are defined here, before data.
- The node is written by every Lake run: `LakeBrainRunner.validationSummary` (`brains/lake/runtime/LakeBrain/LakeBrainRunner.swift`) hard-codes
  `status: NOT_VALIDATED`. A hand write to RTDB would be overwritten by the next run, so publication is a code change (section 8).
- `LAKE_BRAIN_PARTIAL_VALIDATION_DEFINITION.md` holds a proposed (not adopted) `PARTIAL` definition built on other evidence (binding sample review,
  hold-out H-A..H-D, ledger). This test does not satisfy that proposal; whether operator-truth agreement is enough for `PARTIAL` is an owner decision.

## 2. What is validated

The Lake Brain's **current observed level** (capability LB-04): the number the Brain publishes as `currentElevationFt` for a lake at night.
Not validated here: history bands, trend labels, operating zones, flood state, outlooks (LB-05..LB-20).

## 3. Lakes, value series and truth series

### 3.1 Frame and the Brain's value
Frame: the 289 accepted lakes (`jobs/lake-brain/data/accepted_batch.json` 187 + `accepted_batch2.json` 102), with the runtime binding records the Lake
Brain runs on (`brains/lake/runtime/LakeBrain/LakeSourceBindingsGenerated.swift`, table fingerprint `954ad1890cf2`). The 5 hand-written pilot
bindings are not in the frame.

The Brain's value series is the lake's **primary** live series (`live[0]`). Its value for a night is reconstructed from that series' public record,
as the Brain reads it:
- `cwms`: CWMS Data API `timeseries` (office, tsid). `a2w`: Access2Water is a front end of CWMS and keeps no history, so the same office and tsid are
  read from the CWMS Data API (assumption A1).
- `usgs`: WaterServices `iv` for the bound site and parameter. `nwps`: NWPS `stageflow/observed` (about 30 days, pe prefix checked as the Brain does).
- `rise`: RISE `result` for the item (daily; 0.0 placeholders and non-`observed` results dropped, as the Brain does).
- `tva`: **not reconstructible** (the public feed covers only the last 48 h); the 11 TVA-primary lakes are excluded and listed.

Value at night `M`: the latest primary reading at or before `M` that the Brain would still select (`M − t ≤ lagMin + 3 × cadenceMin` minutes,
`LakeLevelClassifier.select`), plus the binding's `datumOffsetFt`, rounded to 0.01 ft. No reading in that window: the night has no Brain value.
The Brain's spike/validity filter (`LakeLevelValidity`) is not reproduced (limitation L2).

### 3.2 Truth: the operator's own publication, never the Brain's value series
Candidates are the lake's other bound series: live fallbacks (`live[1…]`) and history series (`history[]`). No unbound series is used, because finding
one needs lookups that would be made after registration (limitation L1). Each candidate is classed against the value series:

| Class | Rule | Tier |
|---|---|---|
| `SAME_SERIES` | same series identity (a2w ≡ cwms for the same office + tsid); any USGS series at the same USGS site (another parameter is a datum conversion, `dv` is derived); NWPS / HADS at the same NWS id | excluded |
| `OPERATOR_OTHER_SERIES` | published by the dam operator's agency (USACE → CWMS/a2w, TVA → TVA, USBR → RISE; from the binding's NID operator), a different series | 1 |
| `AGENCY_OTHER_SERIES` | same agency as the value series, a different series, and that agency is not the dam operator | 2 |
| `CROSS_AGENCY` | another agency among CWMS, USGS, USBR, TVA | 2 |
| `NWS_REDISTRIBUTION` | NWPS or HADS (the NWS redistributes agency DCP data; independence unknown) | 3 |

Truth choice per lake: the lowest tier; then a series with recorded offset 0 before a calibrated one (an offset fitted against live cannot reveal a
constant datum error); then sub-daily before daily; then binding order. The recorded offset of the chosen truth (`datumOffsetFt` for a live entry,
`offsetFt` for history; ADDED to readings, `LakeHistoryOffsets.swift`) is applied. Classes may share a physical sensor (raw vs revised series):
the class is reported per lake, and the result is broken down by class.

Lakes whose best truth is tier 1 or 2 are **verdict-eligible**; tier 3 lakes are **report-only**; the rest are excluded with the reason.

## 4. Sample (frozen)

Strata: primary provider. Verdict sample n = 60: strata with ≤ 10 eligible lakes taken whole; the remainder split over larger strata in proportion to
size (largest remainder), at least 6 each. Within a stratum, lakes in ascending `sha256("sector-lake-operator-truth-v1|" + lakeId)`.
Report-only sample: up to 5 tier-3 lakes per stratum, same order. No replacement after data are fetched.

Built by `jobs/lake-brain/validation/operator_truth/build_sample.py` from committed metadata only; frozen file
`jobs/lake-brain/validation/operator_truth/sample_v1.json`, **sha256 `b6fe824b9f5aa9d0959014ed757c32110e53339db1e10d5806df22c39038684d`**.

| Primary provider | Frame | Verdict-eligible | Verdict sample | Report-only eligible | Excluded (reason) |
|---|---|---|---|---|---|
| a2w | 97 | 81 | 29 | 11 | 5 (2 same series only, 3 no second series) |
| cwms | 58 | 29 | 11 | 17 | 12 (10 same series only, 2 no second series) |
| nwps | 35 | 7 | 7 | 0 | 28 (25 same series only, 3 no second series) |
| rise | 28 | 9 | 9 | 9 | 10 same series only |
| usgs | 60 | 4 | 4 | 16 | 40 (38 same series only, 2 no second series) |
| tva | 11 | 0 | 0 | 0 | 11 value not reconstructible |
| **Total** | **289** | **130** | **60** | **53** | **106** |

Verdict-sample truth classes: 32 `OPERATOR_OTHER_SERIES`, 20 `CROSS_AGENCY`, 8 `AGENCY_OTHER_SERIES`. No CDEC or CO-OPS series is bound to any
accepted lake, so those providers are not in the test.

## 5. Window (past nights only)

21 nights: the instants `M` = 00:00 lake-local (binding `timeZone`) on 2026-11-03 through 2026-11-23. Fetch range per lake: from 6 days before the
first `M` (covers the RISE selection window) to 1 day after the last. The run must start after 2026-11-24T00:00Z and finish by 2026-11-30T23:59Z
(NWPS keeps about 30 days); a run outside that is void and needs a new pre-registration. Operators may revise values; values are as published at run
time, and the run records its fetch times.

## 6. Matching and metric

For each lake and night with a Brain value `B` observed at `t_B`: the truth reading nearest to `t_B` (earlier on a tie), accepted if
`|Δt| ≤ 90 min` for a sub-daily truth series, or `|Δt| ≤ 13 h` for a daily one. Daily timestamps: as published (CWMS, RISE); USGS `dv` at 12:00
lake-local of its date; TVA guide `CurYrElev` at 00:00 lake-local. Error `e = B − T` (ft). A night without `B` or without a matched `T` is unmatched.

Per lake: `n` matched nights (of 21), MedAE = median `|e|`, share of nights with `|e| ≤ 0.50 ft` (the 0.5 ft agreement rule of the batch checks),
mean `e` (bias, information), max `|e|`.
- **PASS**: `n ≥ 14` and share `≥ 0.90` and MedAE `≤ 0.25 ft`.
- **FAIL**: `n ≥ 14` and not PASS.
- **INSUFFICIENT**: `n < 14` (reason recorded: no Brain value, no truth match, fetch error). Not replaced.

## 7. Fleet verdict (verdict sample only)

- **V1 enough evidence**: ≥ 45 scored (PASS + FAIL) lakes, and ≥ 3 strata with ≥ 5 scored lakes.
- **V2 lakes**: ≥ 90 % of scored lakes PASS.
- **V3 nights**: pooled share of matched lake-nights with `|e| ≤ 0.50 ft` ≥ 0.95.
- **V4 strata**: every stratum with ≥ 5 scored lakes has ≥ 75 % PASS.

Verdict: `PASS` when V1–V4 all hold; `INCONCLUSIVE` when V1 fails; otherwise `FAIL`. Every FAIL lake is listed with its numbers, truth class and
series, and the result is broken down by stratum, truth class and truth cadence, whichever way it falls. The report-only sample is reported the same
way and never enters the verdict.

## 8. Reporting and publication (owner decision)

The runner writes a result JSON and a per-lake CSV into the Lake research folder (`lake-brain/validation/`) and prints a summary for Sector_Ops #51.
It also prints the **proposed** `/validation/lake-brain` value, in exactly the shape `LakeBrainRunner.ValidationSummary` writes:
- verdict `PASS` → proposed `status: "PARTIAL"` (scope: current observed level vs operator truth; never `VALIDATED`, which needs prospective evidence);
- `FAIL` or `INCONCLUSIVE` → no change proposed (`NOT_VALIDATED`).

Publishing needs Michael's approval and then: the result committed as a Lake runtime evidence file; `validationSummary` changed to read it (fails
closed to `NOT_VALIDATED` when the file is missing, unapproved or its hash differs); LakeBrainJob rebuilt on Pulse. The scorer then reads the new
status on its next run. None of this is done by the runner.

## 9. Assumptions and limitations

- A1: Access2Water values equal the CWMS Data API values for the same office and tsid (Access2Water reads CWMS). A lake where this fails shows as no
  Brain value, not as agreement.
- L1: every truth series is bound to the lake in some role (fallback or history), because only committed metadata may choose it. Lakes whose only
  other series is the same series are excluded, not guessed. That excludes 38 of 60 USGS-primary and 25 of 35 NWPS-primary lakes.
- L2: the reconstruction does not apply the Brain's validity filter, so a spike the Brain would reject can show as an error (conservative).
- L3: "operator other series" can share the sensor with the value series (raw vs revised). It tests the Brain's series choice, units, datum offset
  and timing against the operator's own publication; it is not an independent instrument. `CROSS_AGENCY` truth is the stronger evidence; both are
  reported separately.
- L4: neighbouring nights and lakes on one river are correlated; the shares are descriptive.
