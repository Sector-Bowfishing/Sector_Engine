# Session record: Depth datum verification (waves 0-1)

Standards: Rehtac Cortex 3.1.2 @ ecaef70, pack sector/engine. Date: 2026-11-22. Branch: `feat/depth-datum-verification-2026-11-22` (off main 669d4928). Cloud session.

## Scope
Depth datum plan (2026-11-22) waves 0 and 1: Toledo Bend's NGVD29/NAVD88 conversion, then the 14 CWMS/A2W lakes blocked only by `DATUM_UNKNOWN`. Two research passes per lake at most. No change to the reference/contract semantics, no GLOBathy, no estimates, no knowledge-release rebuild, no publication.

## Done
- `brains/depth/research/tools/depth_research/records/datum_verification.json` (`depth-datum-verification-v1`): 15 per-lake records, level and reference sides, cited evidence, VDatum checks, pass counts.
- `candidates.py`: `load_datum_verification`, `verification_problems` (the plan's two-source rule, 0.10 ft VDatum tolerance, 0.25 ft conflict bound, two-pass stop rule) and `verified_conversion`. `assess_candidate` converts a NGVD29/NAVD88 pair only for a VERIFIED CONVERTED record whose datums match the manifest's verified datums; nothing else changes.
- Tests: `research/tools/tests/test_datum_verification.py`. Research README documents the file.

## Findings
| Result | Lakes |
|---|---|
| VERIFIED (conversion enabled at next rebuild) | Toledo Bend: NAVD88 level (USGS 312914093422701, 62615) vs NGVD29 pool 172.00 (TWDB, USGS 08025350, NWPS BKLT2); offset -0.2 ft vs VDatum -0.285 ±0.167 (0.085 ft); two-gauge check n=9, mean -0.18 ft |
| CONFLICT | Cross Lake: 171.1 ft pool frame is NAVD88 per NWPS, the crest 171.19 ft is NGVD 29 per USGS |
| SINGLE_SOURCE | Ross Barnett, Lake Tahoe (pool on USBR project datum), Mark Twain, Percy Priest, Jordan, Lay, Bistineau, Eagle, Palisades, Jackson, Anderson Ranch, Coeur d'Alene |
| NONE | Lake Chelan |

Level sides two-source verified without a usable pair: Cross Lake (NAVD88: CDA, USGS, NWPS), Ross Barnett (NGVD29: CDA, USGS). Ross Barnett's CDA offset (-0.198, estimate) is 0.31 ft from VDatum (+0.108): recorded, not used.

Fetch refusals: CDA `catalog` (robots), CDA `locations` for NWW/NWS, CDA `levels` for MVS, USGS OGC API (robots), web.archive.org (blocked), one USGS WDR PDF.

## Verification
Depth tests at merge of #223: 289 passed, 9 skipped (research-data tests). Cortex `research-check --repo .` and `data-check` report nothing in the touched files.

## Owner decisions (Michael, chat 2026-11-22 07:14Z, recorded on Sector_Ops #51 and PR #223)
- Toledo Bend: level datum accepted on USGS's parameter definition plus the two-gauge check; recorded as `basisDecision`.
- Percy Priest: reference is the CWMS JPHT1 seasonal level (summer 490.5 ft), so pool and level are same-source. New record status `SAME_SOURCE` with a `sameRecord` block; the builder uses 490.5 ft as the reference pool.
- Ross Barnett: stays unconverted.

## Not done
`candidates.json` is not rebuilt: `refresh` needs `DEPTH_RESEARCH_DATA`, and a rebuild needs a new release id. Release approval stays Michael's (DEPTH-REL-001).

## Review fixes (follow-up PR, branch `feat/depth-datum-review-fixes-2026-11-22`)
Independent review of #223 was clean; these findings are fixed before the next candidates rebuild.
- M1: Percy Priest's 490.5 ft reference differs from the 490 ft Lake Brain uses for `differenceFromNormalPoolFt`. Lake is unchanged. The record carries `lakeBrainPoolFt: 490`, the manifest reference carries it, and `shift.compute_shift` re-bases Lake's delta by (reference - lakeBrainPoolFt) before the 0.15 ft cross-check. Chosen over skipping the check because the check still catches a wrong binding or frame.
- M2: a SAME_SOURCE record pins Lake's reviewed live binding (`liveSourceIds`, reviewed-lake-bindings-v1). The builder refuses SAME_SOURCE if the ids change or any id's base location/office is not LRN/JPHT1 (exact match, so JPHT1X does not pass).
- M3: every evidence item may name `derivedFrom`; VERIFIED needs two distinct roots. Toledo Bend's reference evidence (TWDB, USGS, NWPS) all derive from USGS 08025350, so **Toledo Bend no longer verifies: it is SINGLE_SOURCE and the conversion is not enabled**. Cross Lake's and Ross Barnett's level sides drop to SINGLE_SOURCE for the same reason.
- LOWs: the 0.25 ft conflict bound is enforced (a side offset that far from VDatum must be recorded as `offsetConflict` and blocks VERIFIED); a record above NONE needs an http evidence item; carried-forward candidates.json pointers are `notEvidence`, which moves Palisades, Jackson, Anderson Ranch and Coeur d'Alene to NONE; a reversed-datums test is added.
- Counts now: SAME_SOURCE 1 (Percy Priest), CONFLICT 1 (Cross Lake), SINGLE_SOURCE 8, NONE 5, VERIFIED 0. Depth tests 298 passed, 9 skipped.
