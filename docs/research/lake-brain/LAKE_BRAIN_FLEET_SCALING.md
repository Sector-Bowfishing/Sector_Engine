# Lake Brain — from 5 pilots to 621 lakes

Research (2026-10-13). Uses Engine vocabulary: readiness `DISCOVERED → PROFILED → CALIBRATION → BETA → VALIDATED → PRODUCTION` (+`DEGRADED`/`BLOCKED`),
binding status `CANDIDATE`/`REVIEWED`, source capability `DIRECT_OPERATOR_POOL | DIRECT_LAKE_GAUGE | NEARBY_GAUGE_PROXY | HISTORICAL_ONLY | NO_SOURCE`.

## 1. What the 621-lake directory looks like to the Lake Brain
| Fact | Count |
|---|---|
| Directory lakes | 621 (50 states; 16 duplicated names covering 41 ids) |
| Operator families | USACE 198 · USBR 61 · TVA 18 · natural/none 101 · other operators/utilities/states 243 |
| Machine-verified level binding (binding-review-v1) | **258 core** (203 operator pool, 55 own gauge) + 57 flagged = 315 (50.7 %); 33 stage-only not counted |
| …with ≥ 5 complete years of daily history | 203 core (181 + 22) · 244 of 315; TVA pilots 16–18 y via the NWS/HADS composite |
| …with operator plan evidence (guide curve or zone) | ≈ 51 core under the conservative rule (117 bound lakes have any operator level text) |
| …with an operator flood-pool bottom | ≈ 78 core |
| Unbound | 274: 171 no candidate, 96 candidates rejected (0 of 12 AK, 12 CT, 9 HI, 12 NH; Duke 0 of 8) |
| Canonical shoreline (NHD HR) | 606 of 621 matched; polygons: 351 HIGH / 195 MEDIUM / 53 LOW / 22 MISSING |
| Classification coverage | 615 of 621 classifiable; 577 lakes get run-of-river vs storage |

## 2. Why pilots do not scale by themselves
The five pilots reach **2 of 9 lake classes and one region** (Southeast); 17 % of the fleet is within a "similar lake" distance of a pilot (25 % at a looser threshold). The four TVA lakes are one hydraulic system
(predicted outflow equals the next pool's inflow within 0.3–4 %), so the **effective pilot count is 2**. Ten deliberately chosen additional lakes lift similarity coverage to 62 % (82 % looser) versus 50 % for ten random lakes.

## 3. Lake classes and transfer slots (`LAKE_BRAIN_CONTEXT_RESEARCH.md`)
Retained features (11): regime, residence time, reference area, mean depth, shoreline development index + narrow-water fraction, shore-band share, operator family + release feed, region, shoreline slope index, chain position, measured grassPct.
Classes (621): R1 run-of-river 46 · R2 flow-through 85 · R3 dendritic storage 91 · R4 open-basin storage 146 · R5 small impoundment 25 · N1a natural deep 56 · N1b natural shallow 34 · N2 regulated natural 99 · N3 small pond 15 · very large 18 · no data 6.
Class explains 10 % of the rank variance of Water Clarity turbidity, region 25 %, both 31 % (vegetation: 1 % / 11 % / 12 %). **Region must be a stratifier; vegetation must be measured, not inferred.**

Pilot expansion slots (two named candidates each; first pick has the best public data): S01 run-of-river TVA pool (covered by pilots) · S02 non-TVA run-of-river (Wateree SC / Jordan AL) · S03 deep dendritic storage (covered) · S04 Ozark/highland dendritic (Stockton MO / Broken Bow OK) · S05 Great Plains flood-control (Sardis OK / Darling ND) · S06 western drawdown (Starvation UT / Heron NM) · S07 flow-through (Allatoona GA / Millwood AR) · S08 dam-raised glacial (Massabesic / Sunapee NH) · S09 regulated headwaters (Mendota WI / Houghton MI) · S10 natural deep (Yellowstone WY / Clear CA) · S11 natural shallow vegetated (Eagle MS / Crescent FL) · S12 small pond (Highland / Mansfield Hollow CT). Slots S08–S12 have **no machine-readable level source** for most candidates — they are exactly where transfer cannot be tested with level data, and where onboarding should stop at `PROFILED`.

## 4. The repeatable onboarding path (Engine terms)
```
DISCOVERED (directory lake)
  └─ candidate match (automatic: spatial + name + operator + NID, scored)                         ─ machine, nightly
      └─ binding-review-v1 R1–R9 probe (live age, datum, level-vs-full-pool, 2nd-origin agreement) ─ machine
          └─ PROFILED/REVIEWED binding row (acceptance sampling, §5)                                ─ human, sampled
              └─ CALIBRATION: live OBSERVED state; history < 5 y or no guide                        ─ automatic
                  └─ BETA: observed + operator plan + ≥ 10 y history (rule change) + baseline SUFFICIENT
                      └─ VALIDATED: prospective hold-out passed per dimension (VALIDATION_STRATEGY §6–7)
                          └─ PRODUCTION: policy gate (overall ≥ 8.0, every critical condition ≥ 7.5) — Michael only
```
Stage gates are data-driven; the human touch is the sampled review and the policy gate. `NO_SOURCE` reviews stop at `PROFILED` and are **never** counted toward coverage in the research score.

## 5. Candidate → binding automation (what the pipeline already does)
`research/lake-brain/binding_pipeline.py` (+ `binding/`): Access2Water (one GET per USACE district; carries NID ids and operator levels; the only route for districts whose CWMS API is empty), CWMS Data API (long daily history), USGS (88 lakes, 20 only via USGS), USBR RISE (48), TVA (22), NWS NWPS (223 lakes, live check/short history only), NID hosted layer (368 of 401 dam lakes by name+geometry, 17 geometry-only, agrees with A2W on 144 of 144). Gotchas recorded in the ledger: CWMS metric default, TVA needs a browser User-Agent, CWMS catalog "latest" is frozen so liveness needs a data query.
Productionising this is the single highest-leverage implementation step (`LAKE_BRAIN_NEXT_IMPLEMENTATION_PLAN.md`): a `bindings.json` table generated by the pipeline and reviewed, replacing the 5 hand-written Swift rows, with provider adapters for A2W, RISE and NWPS (the Engine reads only TVA, CWMS and USGS today).

## 6. Provider readiness (what the Engine can read today vs what research verified)
| Provider | Lakes verified | Engine adapter today | Needs |
|---|---|---|---|
| TVA | 16 (22 reached) | yes | HADS/RVD history sources (`nwsHadsDcp`, `nwsRvdhunArchive`) |
| USACE CWMS | 58 | yes | tsid selection, unit handling (metric default) |
| USGS | 18 (88 reached) | yes | 62614/62615/00062 parameter handling, datum |
| USACE Access2Water | 96 | **no** | new adapter (REST, per district) |
| USBR RISE | 33 | **no** | new adapter; daily feed (≈ 48 h latency), zero placeholders |
| NWS NWPS | 36 | **no** | adapter; ~30 d history — needs HADS/RVD archive for baselines |
| TWDB, CO-OPS | 4 | no | small; optional |
Using only what the Engine reads today, 92 lakes (14.8 %) are bindable (`fleet_score.py --providers tva,cwms,usgs`): that alone lifts the coverage gate.

## 7. Where the fleet cannot be scored honestly (accept it, publish `UNKNOWN`)
- Natural lakes with no gauge (AK, HI, NH, much of New England and the northern Midwest) — satellite or altimetry level would be a `MODELED`/proxy source, which the rubric does not count and v1 does not publish.
- Lakes with no operator flood pool (run-of-river, natural): flood state stays `UNKNOWN` by design; the rubric's non-applicability-aware share penalises this (`LAKE_BRAIN_AUDIT.md` §4).
- Duke and most utility reservoirs: no machine-readable public level feed was found (dead end in the ledger).

## 8. Operating cost at fleet scale
The orchestrator already starts `lake-brain` only when stale, and per-lake `nextCheckAt` lets the job skip current lakes (`plan()`); no always-on compute is needed.
Measured artifact sizes (2026-10-13, `gs://sector-lake-brain`): a baseline artifact is ≈ 50 KB (Hartwell, 60 years, 122 KB); a daily history CSV is ≈ 70 bytes/day (Hartwell 23,656 days = 1.7 MB; a 20-year series ≈ 0.5 MB).
At 315 lakes: history ≈ 150 MB once (backfill), baselines ≈ 16 MB per full recompute.
**Implementation hazard:** `baselineVersion = method@historyEnd#fingerprint` changes whenever `historyEnd` advances, and artifacts are immutable and never pruned — at 315 lakes that is ≈ 16 MB and 315 new objects per day (≈ 5.7 GB and 115k objects per year). Storage cost is negligible, but the object count and listing time are not: recompute weekly (history still appends daily), or key baselines by content fingerprint only, and add a bucket lifecycle rule (keep latest + 30 days).
