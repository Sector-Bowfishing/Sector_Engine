# Lake Brain: operator-truth validation v2 (`lake-operator-truth-v2`): pre-registration

Committed **before any water-level value is fetched** for this test. It supersedes v1 (`lake-operator-truth-v1`, pre-registered in commit
469a15f, protocol sha256 `7bc8d1df9f2b…`, never run), after the independent review of Sector_Engine PR #243 found that the v1 design would mostly
measure its own selection. v1's protocol, rule and sample stay in the repository for the record (marked superseded); v1's runner is in commit 38272fc.

Anything not written here may not be used to decide pass or fail. Thresholds are fixed and are not lowered, widened or reinterpreted after results are
seen; a failed criterion is reported as failed. A harness bug found after the run is fixed and the run repeated once on the same frozen set and window,
with the bug and both results reported (RS-30).

`/validation/lake-brain` stays `NOT_VALIDATED`. This document, the runner and its result change no status, score, rubric, binding or live build.

**Stated before any data: under v2 a fleet verdict is not reachable.** Only 7 lakes are verdict-eligible (4 with independent cross-agency truth),
below the V1 minimum of 45, so the pre-registered verdict is `INCONCLUSIVE` whatever the data show, and the gate cannot be lifted by this run. The run
still yields per-lake operator-truth evidence for those 7 lakes and for the report-only set. What would make a fleet verdict reachable is in section 9.

## 1. What the rubric asks

As v1 §1: the scorer reads only `/validation/lake-brain.status` (`PARTIAL` lifts the 5.0 cap); the rubric defines no truth source, sample size, metric
or pass mark; every Lake run rewrites the node from `LakeBrainRunner.validationSummary` (hard-coded `NOT_VALIDATED`), so publication is an approved
code change. `LAKE_BRAIN_PARTIAL_VALIDATION_DEFINITION.md` holds a different, unadopted `PARTIAL` proposal.

## 2. What is validated

The accuracy of the Lake Brain's **fresh** current observed level (LB-04) at night, against an operator or other-agency record. Not validated: history
bands, trend labels, operating zones, flood state, outlooks.

## 3. Lakes, value series and truth series

### 3.1 Frame and the Brain's value
Frame: the 289 accepted lakes (`accepted_batch.json` 187 + `accepted_batch2.json` 102) with their runtime binding records
(`LakeSourceBindingsGenerated.swift`, fingerprint `954ad1890cf2`) and the reviewed contract's datum. The Brain's value series is `live[0]`,
reconstructed from its public record as the Brain reads it (CWMS Data API; USGS `iv`; NWPS; RISE). TVA-primary lakes (11) are excluded: the public
feed covers only 48 h.

**Access2Water (assumption A1, now checked).** An a2w series is read from the CWMS Data API only under an office evidenced in committed metadata: a
`cwms` or `cwmsDaily` entry of the same lake with the identical tsid (district or division office as recorded there). Without that evidence the series
is not evaluable: 32 a2w-primary lakes are excluded for this reason (`EXCLUDED_A1_UNVERIFIED`).

Value at night `M` (00:00 lake-local): the latest primary reading at or before `M` within the Brain's selection window (`lagMin + 3 × cadenceMin`),
plus `datumOffsetFt`, rounded to 0.01 ft. **Freshness gate:** the night is scored only when its age `M − t_B` ≤ `cadenceMin + lagMin` (the Brain's
own staleness limit; a staler value is published as stale). Older values are counted `STALE_BRAIN_VALUE` and every night's age is reported.

### 3.2 Independence classes (rules applied in this order)
Candidates are the lake's other bound series (`live[1…]`, `history[]`). CWMS tsids are split into location, parameter, version; a location's trailing
`-Lake` / `-Reservoir` is ignored when comparing (Kinzua-Lake ≈ Kinzua).

| Class | Rule |
|---|---|
| `SAME_SERIES` | identical series; CWMS same location + parameter **across offices** (NWO:CHCR ≡ NWDM:CHCR, NWP:FRN ≡ NWDP:FRN, NWS:KER ≡ NWDP:KER, NWK vs NWDM KANS/MILD/POMA/SMIE); CWMS same office, location, parameter whose versions differ only by `-raw`/`-rev` (Barren, Bull Shoals, Clearwater, CM Harden, Monroe, Norfork); any USGS series at the same USGS site; NWPS/HADS at the same NWS id |
| `SAME_SENSOR_SUSPECTED` | CWMS same office, location, parameter with another version, interval or type (OBS vs RESOPS, 1Hour vs ~1Day, Inst vs Ave); a CWMS series whose version names USGS (`…USGS-raw`) or whose location is an NWS id (e.g. PSMT2, TRNT2) against a USGS series (SAW:CFR BEJ vs 02098197, SAW:ROA PLP vs 02071900); **any** truth for an NWPS-primary lake (the NWS operates no lake gauge; it redistributes the operator's or USGS's DCP, e.g. DIXK2, INDN6, PSLI1, TOPN2, UTEN5) |
| `NWS_REDISTRIBUTION` | NWPS / HADS truth |
| `OPERATOR_OTHER_SERIES` | the dam operator's agency (USACE → CWMS, TVA, USBR → RISE), another series |
| `AGENCY_OTHER_SERIES` | the value series' agency, another series, agency not the operator |
| `CROSS_AGENCY` | another agency among CWMS, USGS, USBR, TVA |

### 3.3 Verdict eligibility of a truth
A truth of class `OPERATOR_OTHER_SERIES`, `AGENCY_OTHER_SERIES` or `CROSS_AGENCY` may enter the verdict only when all hold:
1. **It is a history series, not a fallback live series.** The frame was filtered by the dry-run check (b) (Mac mini, 2026-11-21 and 2026-11-22:
   where a fallback live series was reachable, it had to agree with the primary within 0.5 ft at the latest readings; lakes that failed were held). Those readings
   fall inside this test's window, and a lake whose fallback disagreed was removed from the frame, so a fallback truth would partly re-measure the
   filter that selected it. All fallback live truths are excluded from the verdict (47 candidates on non-verdict lakes).
2. **Its recorded offset is 0.** An offset fitted against the value series (Lake Washington +0.36, Red Lake +1100.25, Toledo Bend −0.18; Priest Lake
   +2434.40 and Topaz Lake +4899.97 are history truths of NWPS-primary lakes, already `SAME_SENSOR_SUSPECTED`) hides exactly the constant error the test must see.
3. **No known datum mismatch** (USGS 62614 = NGVD29, 62615 = NAVD88, against the value series' recorded datum). Toledo Bend's 08025350 truth is
   NGVD29 against a NAVD88 value series; it is also a fallback and offset-fitted, and is recorded here.
4. An a2w truth needs the A1 evidence of §3.1.

History series were checked earlier only loosely (dry-run (c): within 5 ft of a 7-day median; the batch "15 ft" series rule); that is disclosed, not
treated as selection on agreement at 0.5 ft.

### 3.4 Truth choice and sets
Per lake: among verdict-eligible truths, `CROSS_AGENCY` first, then operator/agency other series; then offset 0; then sub-daily before daily; then
binding order. A lake with one is in the **verdict set**; its truth is **independent** when it is `CROSS_AGENCY`.
Lakes with none but with a reportable candidate (any class except `SAME_SERIES`) are report-only; up to 5 per primary provider in ascending
`sha256("sector-lake-operator-truth-v2|" + lakeId)` are run. Report-only results never enter the verdict.

## 4. The frozen set

Built by `build_sample_v2.py` from committed metadata only. **The verdict set is a census** of every verdict-eligible lake (no sampling).

| Primary provider | Frame | Verdict (independent) | Report-only eligible (run) | Excluded |
|---|---|---|---|---|
| a2w | 97 | 2 (2) | 56 (5) | 39 (32 A1 unverified, 7 same series only) |
| cwms | 58 | 5 (2) | 41 (5) | 12 (10 same series only, 2 no second series) |
| nwps | 35 | 0 | 7 (5) | 28 (25 same series only, 3 no second series) |
| rise | 28 | 0 | 18 (5) | 10 same series only |
| usgs | 60 | 0 | 20 (5) | 40 (38 same series only, 2 no second series) |
| tva | 11 | 0 | 0 | 11 value not reconstructible |
| **Total** | **289** | **7 (4)** | **142 (25)** | **140** |

Verdict set: Fern Ridge Reservoir|OR, Flathead Lake|MT, Lake Milton|OH, Moses Lake|WA (CROSS_AGENCY, USGS daily history); Pueblo Reservoir|CO
(OPERATOR_OTHER_SERIES, RISE daily); Catahoula Lake|LA, Kissimmee|FL (AGENCY_OTHER_SERIES, CWMS daily history at another location of the lake).

## 5. Window

As v1: 21 nights, `M` = 00:00 lake-local on 2026-11-03 … 2026-11-23; fetch from 6 days before the first `M` to 1 day after the last; the run must
start after 2026-11-24T00:00Z and finish by 2026-11-30T23:59Z. Values as published at run time.

## 6. Matching and per-lake metric

Unchanged from v1: truth reading nearest to `t_B` (earlier on a tie) within 90 min (sub-daily) or 13 h (daily; USGS `dv` at 12:00 lake-local of its
date). `e = B − T`. Per lake: `n` scored nights, MedAE, share `|e| ≤ 0.50 ft`, mean `e`, max `|e|`, median and max age.
PASS: `n ≥ 14`, share ≥ 0.90, MedAE ≤ 0.25 ft. FAIL: `n ≥ 14`, not PASS. INSUFFICIENT: `n < 14` (reason recorded).

## 7. Fleet verdict

Criteria (as v1): V1 ≥ 45 scored lakes and ≥ 3 strata with ≥ 5 scored; V2 ≥ 90 % of scored lakes PASS; V3 ≥ 95 % of scored lake-nights within 0.5 ft;
V4 every stratum with ≥ 5 scored lakes ≥ 75 % PASS.
They are evaluated **twice: on the whole verdict set, and on the independent (CROSS_AGENCY) subset on its own.** `PASS` needs all eight; if V1 fails on
either, the verdict is `INCONCLUSIVE`; otherwise `FAIL`. With the frozen set above, the verdict is `INCONCLUSIVE`.

## 8. Reporting and publication

The runner writes a result JSON, a per-lake CSV and a summary into the Lake research folder and records its own sha256, the commit it ran from and the
Python version. Only on `PASS` would it propose `status: "PARTIAL"` (scope: fresh current level) in `ValidationSummary`'s exact shape; otherwise no
change. Publishing needs Michael's approval, then: the result committed as Lake runtime evidence, `validationSummary` changed to read it (fails closed),
LakeBrainJob rebuilt on Pulse.

## 9. Limitations, and what would make a verdict reachable

- Truth comes only from series already bound to the lake, chosen from committed metadata. After v2's rules almost every bound alternative is the same
  series, a suspected same sensor, a fallback filtered by check (b), or offset-fitted.
- "Operator / agency other series" at another location of the same lake (Catahoula, Kissimmee) may share an upstream processing chain.
- The spike filter (`LakeLevelValidity`) is not reproduced (conservative). Neighbouring nights and lakes on one river are correlated.
- **Reachable next step (a new pre-registration, not this one):** discover unbound truth first (each USACE/USBR/TVA/state operator's own published pool
  report or a USGS gauge at another site on the lake, located and identity-checked without reading values), freeze that list, then run. Separately,
  record the A1 office for the 32 a2w lakes in the bindings.

## Pins

`PREREGISTRATION_v2.sha256` holds this file's sha256. The runner refuses unless every file below matches.

<!-- pins:begin -->
`sample_v2.json` 9c1cbb271771ff50a8f0a6cb105a73d04bf8945b2c408ba62647f74889309aa7
`build_sample_v2.py` eea57172e2dfa8b55bf6aa34de20fbc317c5165e48088d1e95a95c21d805f832
`run_operator_truth_v2.py` 74339b18994e75da05230e33d096b9a4e8b6b9bf56075f33993d9671ec7f973e
<!-- pins:end -->
