# Lake Brain: scalable level-source binding research

Thread `binding`, Lake Brain deep-research campaign, 2026-10-13. Research only: GET-only against public APIs, no deploy, no write to any RTDB or bucket, no rubric edit.
Reproduce with `python research/lake-brain/binding_pipeline.py --list`. Bulk data lives outside Git in `Sector_Research_Data/lake-brain/binding/`.
Compact results committed here: `data/binding_summary.json`, `data/verified_bindings.csv`; ledger `ledger/binding.jsonl`.

## 1. Result in one table

The Lake Brain score is capped at 3.0 while only 5 of 621 lakes (0.8%) have a reviewed binding. The automated probe below reproduces the hand review for all 5 pilots and finds a machine-verified binding for 258 lakes (41.5%) at the strict tier, 315 (50.7%) if the single-origin flagged tier is accepted.
Machine-verified is evidence for a human reviewer. Per the rubric, only REVIEWED bindings count, so none of this lifts the score until reviewed (blocker B-binding-001, action M-B02).

| Tier | Definition | Lakes | % of 621 | Coverage-ladder points |
|---|---|---|---|---|
| Core | all hard checks pass and the level is inside the strong window, or the flagged level class is confirmed by an independent origin | **258** | 41.5% | 5 (>= 25%) |
| Flagged | hard checks pass, but the level is a deep drawdown or the directory full pool is low confidence, and only one origin exists | 57 | 9.2% | adds up to 7 (>= 50%) |
| Core + flagged | | 315 | 50.7% | 7 |
| Stage-only (not counted) | on-lake gauge with a local-datum gage height; no absolute level to test | 32 | 5.2% | 0 |
| No binding | | 274 | 44.1% | |

Core tier by source class and daily-history length (a complete year has >= 90% of days; the Lake Brain baseline rule, `LAKE_BRAIN_INTEGRATION.md` section 6):

| Class | >= 5 complete years | 2-4 years | none found | Total |
|---|---|---|---|---|
| `DIRECT_OPERATOR_POOL` (CWMS, Access2Water, RISE, TVA) | 181 | 4 | 18 | 203 |
| `DIRECT_LAKE_GAUGE` (USGS, NWPS, TWDB, CO-OPS) | 22 | 4 | 29 | 55 |
| **Core total** | **203 (32.7%)** | 8 | 47 | 258 |
| Flagged tier | 41 | 0 (2 with <2y) | 14 | 57 |
| Core + flagged, all classes | 244 | 8 | 61 | 315 |

Operator-plan evidence (operator conservation / flood levels or a guide curve) exists for 117 of the 315 bound lakes (Access2Water levels 94, TVA guide 17, CWMS guide series 6). 96 lakes have both >= 5 y history and plan evidence.

Directory cross-tab: 229 of 272 `apiLevel: dedicated` lakes bind, 73 of 184 `usgsOnly`, and 13 of 165 `none` (the production `apiLevel` hint is a decent but not exact predictor).

## 2. How the probe works (what replaced "probed and reviewed by hand")

1. **Catalog.** One normalised series table (`catalog.jsonl`, 36,785 series) from: USGS NWIS site+series catalog per state (siteType LK, plus ST/ES/SP/AT/OC with reservoir-elevation parameters 00062, 62614, 62615, 62616, 72020, 72022), USACE CWMS Data API (all 45 offices, `Elev*`/`Stage*`/`Stor*` series), USACE Access2Water reporting API, Reclamation RISE, TWDB, NWPS (`pedts` HP gauges), NOAA CO-OPS Great Lakes, TVA `/RestApi/locations`.
2. **Match.** For each of 621 lakes, candidate sites within 8 km of the polygon (12 km of the point when there is no polygon; up to 60 km when the name matches, for Great Lakes). Score 0-100 from polygon distance, token-set name similarity, siteType, parameter family (absolute elevation vs local-datum stage), state, operator agreement, and trap penalties (below/tailwater in the name, river-gauge name on an ST site, state mismatch). 488 of 621 lakes have at least one candidate.
3. **Probe.** The top 5 sites per lake with score >= 40 (1,392 candidates, 450 lakes) are queried for real: USGS `iv` (30 d), CWMS `timeseries?unit=EN` (30 d, up to 4 series per location), RISE `result`, TVA `observed-data-48-hours`, NWPS gauge detail, CO-OPS `datagetter`. The CWMS catalog's `latest-time` is frozen (about 2026-09-14 on every series), so liveness can only come from a data query.
4. **Review criteria** (pre-registered below), applied to every probed candidate.
5. **History.** For every candidate that passed, daily values are pulled (USGS `dv`, CWMS daily or aggregated sub-daily, RISE, TWDB; 706 candidate records) and complete years are computed. A right-lake series that is no longer live (`HISTORY_ONLY`) can supply the history leg, provided its level agrees with the live binding within 3 ft.
6. **Choose.** Per lake: best status, then operator pool over lake gauge, then match score.

### Pre-registered review criteria (`binding-review-v1`)

| ID | Check | Rule |
|---|---|---|
| R1 geo | position | within 1.5 km of the polygon; no-polygon lakes: within 3 km and name sim >= 0.5, or within 25 km and sim >= 0.6 |
| R2 identity | name or inside-lake | name similarity >= 0.5, or the site is inside the polygon (<= 150 m) and is an LK/reservoir site or uses a lake-elevation parameter |
| R3 not a trap | no tailwater/below/river-gauge name; CWMS role = pool/forebay/headwater (not Tail, Down, guide, forecast, statistic) | |
| R4 state | station state in the lake's states | |
| R5 unique | not claimed by a different-named lake with name sim 0.2 higher (same-name state siblings do not conflict) | |
| R6 live | last observation <= 72 h (sub-daily feeds) or <= 192 h (daily feeds), and not future-stamped | |
| R7 level | 30-day median minus directory `fullPoolFt`: strong -25..+8 ft (fullPool basis, high/med confidence); drawdown -220..-25 ft with level/fullPool >= 0.8 (needs strong identity); weak -60..+25 (needs strong identity); else fail | |
| R8 datum | datum identified (site metadata, CWMS vertical-datum-info, or a provider-fixed datum) | |
| R9 agreement | independent origins of one lake agree within 2 ft (min of 30-day-median and last-value gap); a flagged series that disagrees with a strong one is rejected; two strong ones that disagree become CONFLICT; relays (NWPS, TWDB) must agree with every origin | |

Strong identity = name sim >= 0.6 and within 500 m. Status: `VERIFIED` (R1-R6, R8 pass and R7 strong); `VERIFIED_FLAG` (R7 drawdown or weak with strong identity); `VERIFIED_CORROBORATED` (flagged, but an independent origin agrees); `STAGE_ONLY` (all hard checks, absolute level untestable; needs an LK or lake-named site with strong identity); `HISTORY_ONLY`; `CONFLICT`; `REJECT`.
Origins: USGS, USACE (CWMS and A2W count as one), USBR, TVA, NOAA. NWPS and TWDB are relays, so they never count as independent corroboration.

### Does it reproduce the hand review?

Yes, for all five pilots (`binding_summary.json` `pilotReproduction`):
- Guntersville, Wheeler, Wilson, Pickwick: TVA `GVDA1`, `WHLA1`, `WLSA1`, `PICT1` verified live; the neighbouring TVA dams on the same river are rejected by R7 (e.g. Guntersville's elevation 593.8 against Wheeler's full pool 556 is +37 ft).
- Hartwell: the CWMS/A2W pool series fails R6 (silent for 117 h, which is the C2 gap), USGS `02187010` parameter 00062 and NWPS `HWDS1` pass; the same 02187010 was the hand-reviewed fallback. History: CWMS `Hartwell.Elev-Pool…1Day…` gives 64 complete years (the CWMS leg is the history source, as in the hand review).
- TVA history is not repeatable here: TVA's operating guide holds 2 years and the hourly archive started 2026-10-06, so the four TVA pilots show history `NONE` from public sources.

## 3. Providers: where the leverage is

| Provider | Access | Lakes reachable (verified-class series) | Only reachable via this | History | Notes |
|---|---|---|---|---|---|
| **USACE Access2Water** `water.usace.army.mil/cda/reporting/providers/{district}/locations` | API, 1 GET per district | 110 chosen; 185 with CWMS | 30 (USACE family, with CWMS) | latest only | Includes NWK, NWO, NWP, NWS, NWW that the CWMS Data API serves empty; gives project geometry, NIDID alias, Top of Normal / Bottom of Flood levels; best single source for operatorPlan and floodDroughtContext |
| **USACE CWMS Data API** | API | 57 chosen | (above) | decades (daily 1950s+) | Use `unit=EN`; NWK/NWO/NWW data sit under offices NWDM and NWDP; the catalog extents are stale |
| **NWPS gauges** | API, 1 bulk call | 223 | 37 | about 30 d | Live-check relay only; some HP gauges are local stage (Catawba lakes read about 99 ft) and are caught by R7 |
| **USGS NWIS** (legacy) | API | 88 | 20 | decades | The only provider for many non-federal lakes; OGC replacement rate-limits anonymous callers |
| **USBR RISE** | API | 48 | 14 | decades daily | 233 daily elevation series; data lag up to 2 days |
| **TVA RestApi** | API (browser UA) | 22 | 6 | 2 y guide | 43 dams including the Cumberland system |
| **TWDB** | API | 15 | 0 | 1999+ | Relay; gives conservation-pool elevation |
| **CO-OPS** | API | 1 | 1 | decades | Great Lakes harbours only |

By operator group (bound / total): USACE 139 / 168, USBR 60 / 70, TVA 17 / 17, other operators 87 / 253 (Alabama Power 7 / 8 via CWMS SAM; Duke 0 / 8), natural or unknown 12 / 113.
Weakest states (bound / total): AK 0/12, CT 0/12, HI 0/9, NH 0/12, ME 1/14, WI 1/13, DE 1/12, RI 1/12.

Operator pages without an API were not probed beyond a web check (Alabama Power, Duke, Georgia Power, Santee Cooper, SRP, LCRA, Dominion, state DEPs); CDEC works but has no national station index; Colorado CDSS is reachable but not integrated. See ledger records `S-binding-013` to `S-binding-015`.

### Dead ends and surprises (all in the ledger)
- USGS `siteOutput=expanded` with `seriesCatalogOutput=true` returns HTTP 400; use basic output. A 404 means "no match", not an outage.
- USGS OGC API: `OVER_RATE_LIMIT` after about three anonymous calls. Not needed yet.
- CWMS Data API returns SI units by default (a lake at "1,500 m"); ask for `unit=EN`.
- CWMS offices NWK, NWO, NWP, NWS, NWW, POA, POH, SAC, SPN return zero series from the public API.
- NID official bulk and search endpoints: 403 / 404 anonymously. The hosted ArcGIS `NID_v1` layer works.
- TVA serves HTML to plain `curl`; it works with a browser User-Agent and `Accept: application/json`.
- A2W: plain `Elev` on tailwater locations (`Buford-Tailwater.Elev…`, `Below Allatoona.Elev…`) looked like pool series and were 70-150 ft off; fixed with a location-name filter. Island Creek Dam (`SAW:ROA Island Cr`) matched Kerr Reservoir by name and was rejected by R9.

## 4. Spot-check and error rate

Sample: 57 bindings chosen by provider-stratified random draw (seed fixed) plus 15 flagged, covering every provider. Independent checks per binding: second-origin agreement, operator-published levels (A2W Top of Normal, Top of Flood, Top of Inactive), NID dam within 6 km, NID id equals the A2W NIDID alias, name/distance. Table: `binding/spotcheck.csv` (data dir).

| Check | Result |
|---|---|
| Bindings with a second independent origin | 10 of 57 available, 10 agree |
| Operator levels available | 15, none contradicted (level between Top of Inactive and Top of Flood + 2 ft) |
| NID alias equals our NID link | 15 agree, 1 differs (Okeechobee, no NID link) |
| Judged wrong on manual review | **0 of 57** (95% upper bound about 5%) |

Manual review is by the research thread from station names, dam names and domain knowledge; there is no external ground truth, so treat 0/57 as "no error found", not as a measured 0%. A review of the 7 bound lakes whose station name does not contain the lake name (Wolf Creek Dam = Lake Cumberland, Bagnell = Lake of the Ozarks, Libby = Koocanusa, Big Bend = Sharpe, Gavins Point = Lewis and Clark, Salt Creek 18, Devil's Kitchen) found all correct, but these rely on the inside-lake geometry rule and should get the NID dam name as identity evidence.

**The criteria alone were not enough; the cross-origin rule R9 was.** Before R9 and the A2W tailwater filter, independent pairs of verified-class series disagreed for 4 lakes (Allatoona, Lanier, West Point, Kerr; 29-152 ft), all through a flagged A2W series. Final cross-validation: 123 independent pairs in 69 lakes, median gap 0.02 ft, 121 within 0.5 ft, 122 within 2 ft, 1 disagreement (Kerr, rejected). The residual risk sits in the 57 flagged single-origin lakes, which have no second origin to catch such an error, so they are the right place for human review.

### Known mis-match traps (seen in this run)
- River dam upstream or downstream on the same river: Wheeler vs Guntersville, Wilson vs Wheeler, Pickwick vs Wilson (caught by R7).
- Tailwater and below-dam series labelled `Elev`: A2W `Buford-Tailwater`, `Below Allatoona` (location-name filter plus R9); NWPS "above/below Dam" gauges.
- Local-datum stage presented as pool elevation: NWPS Catawba lakes (about 99 ft), A2W Payette (2 ft), Henrys Lake (13 ft), USGS no-data -999999 (rejected by R7 and the parser).
- Wrong small dam with a similar name: Island Creek Dam for Kerr (R9).
- Real deep drawdown that a fixed window rejects: Powell 3518 vs 3700, Mead 1038 vs 1220, Elephant Butte, Blue Mesa (accepted as flagged via the drawdown class).
- Same-name lakes: the directory has 16 duplicated names covering 41 ids (not 19). Several are one physical lake split by state (Kentucky Lake KY/TN, Lake Erie x4, Superior x3, Michigan x3, Oahe ND/SD, Flaming Gorge UT/WY) and legitimately share one series; true namesakes (Clear Lake CA/IA, Sardis MS/OK, Clinton IL/KS, Gull MI/MN, Indian NY/OH, Grand CO/LA, Crescent FL/OR, Eagle CA/MS) are separated by state and polygon distance. Eagle Lake MS first bound to a piezometer site (`Buck Chute @ Eagle Lake Piezometer Site`), a false positive found by scanning all bound station names; a piezometer/well/seepage name rule now rejects it and the lake binds to the Muddy Bayou control-structure landside gauge (876 m from the polygon, name sim 0.58), which still deserves a look.
- Datum offsets: NGVD29 vs NAVD88 differ by under 1 ft at most bound lakes and are inside the 2 ft agreement band; no offsets were applied.

## 5. Dam linkage (NID)

The hosted NID layer (92,627 dams) gives a repeatable lake-to-dam mapping.
- Of 401 `hasDam` lakes, 399 get a candidate dam; **368 (92%) resolve by name and geometry** (score >= 70, name sim >= 0.4), 17 more by geometry alone for human review (for example Lake Travis -> Mansfield Dam, Possum Kingdom -> Morris Sheppard Dam), 16 unresolved (Hawaii, a few NJ/CT, Absegami).
- Independent check: for 144 lakes where the USACE Access2Water record carries a NIDID, 140 are identical and the other 4 are zero-padding variants of the same dam (`VA05101` vs `VA051001`), so 144/144 agree.
- Failure modes: lake name differs from dam name (Waconda = Glen Elder Dam is caught through NID `OTHER_NAMES`), saddle dikes outrank the main dam (a penalty is applied), cross-state lakes (Flaming Gorge) need the 3 km override, and Kentucky Lake TN matched Pickwick Landing Dam at name sim 0 and was not accepted.
- Use in the binding: NID id, dam height, storage, purposes, owner and the federal operator give lake -> dam -> operator; the upstream/downstream chain still needs river-name plus river-mile joins (not built here).

## 6. Recommended onboarding pipeline

Automatic candidate -> machine probe -> review ledger -> reviewed binding.

```
catalog refresh (weekly)  ->  match (per lake)  ->  probe (live)  ->  criteria R1-R9  ->  binding ledger row
                                                                          |
              auto-accept to REVIEWED-by-rule?  NO: human gate  <---------+
              CANDIDATE -> MACHINE_VERIFIED -> REVIEWED -> (monitor) -> SUSPENDED when R6/R9 fail
```

Minimal binding record (extends `LakeSourceBinding`):

```json
{"lakeId":"Lake Hartwell|SC","status":"MACHINE_VERIFIED|REVIEWED|SUSPENDED","criteriaVersion":"binding-review-v1",
 "capability":"DIRECT_OPERATOR_POOL|DIRECT_LAKE_GAUGE|STAGE_ONLY",
 "live":[{"provider":"usgs","station":"02187010","series":"00062","unit":"ft","datum":"NAVD88","origin":"usgs","role":"primary|fallback","cadenceMin":60}],
 "history":{"provider":"cwms","series":"Hartwell.Elev-Pool.Inst.1Day.0.Raw-SHEF_SAS","firstYear":1961,"completeYears":64,"live":false},
 "plan":{"source":"a2w","levels":["Top of Normal","Bottom of Flood"]},
 "dam":{"nidId":"GA01702","method":"name+geometry"},
 "probe":{"at":"2026-10-13","lastObsAgeH":0.4,"medianFt":649.24,"deltaFullPoolFt":-10.76,"checks":{"R1":1,"R2":1,"R3":1,"R4":1,"R5":1,"R6":1,"R7":"strong","R8":1,"R9":"agree:usace,nwps"}},
 "reviewedBy":null,"reviewedAt":null,"reverifyEveryDays":7}
```

Workflow rules:
1. **Auto path (no human).** `VERIFIED` with an independent origin or inside the strong window, plus NID/A2W identity agreement: write the row as `MACHINE_VERIFIED`; batch it for review.
2. **Human review is required for:** flagged single-origin rows (57), `CONFLICT` and `REJECT_CONFLICT` lakes, `STAGE_ONLY` (32), state-sibling lakes, rows whose station name lacks the lake name (identity by geometry), and 10% of each batch drawn at random. The reviewer sees the ledger row, the 30-day values and the station description; the job is approve / reject / re-point.
3. **Re-probe weekly** with the same code. Two consecutive R6 or R9 failures set `SUSPENDED` and fall back to the next live series (Hartwell: CWMS stale, USGS takes over, flagged in the state, as production does now).
4. **Order of onboarding by yield:** Access2Water (all USACE, one GET per district), RISE, TVA, then USGS for non-federal lakes, then NWPS as live-only; then add the CWMS or USGS daily series for history. Add NID id for every `hasDam` lake.
5. **Open gaps worth chasing:** (a) history for NWPS-only lakes (resolve the NWPS gauge's `usgsId` / `usaceId` relay to its source, about 30 lakes); (b) 273 unbound lakes: 98 no-dam and 73 dam lakes with no candidate (state portals, Duke / Dominion / Brookfield / Ameren pages, NH DES, DE DNREC, SJRWMD, MN / WI DNR) and 95 where candidates were rejected (mostly stale or no-data USGS and CWMS feeds, 211 candidate failures on R6); (c) polygons for the five Great Lakes and Great Salt Lake.

## 7. Blockers and Michael actions (short)

- **M-B02 (high):** review/approve the machine-verified ledger (`data/verified_bindings.csv`, 347 rows incl. 32 stage-only) in batches; look hard at the 57 flagged rows. Nothing counts for the rubric until reviewed (B-binding-001).
- **M-B01 (low, optional):** a free USGS API key for the OGC API, so the pipeline can leave the legacy NWIS service when it retires (B-binding-004).
- No other action is needed; all other gaps were worked around or are source limits (B-binding-002, -003, -005, -006).

## 8. Honest limits

- "Machine-verified" is not "reviewed"; no coverage-ladder points exist until a human adopts the rows.
- The R7 level check compares with the directory `fullPoolFt`, which is itself uncertain (low confidence on 221 lakes). Weak and drawdown windows are wide on purpose, and the flagged tier carries that risk.
- The 57-lake spot check has no external ground truth. The 4 pre-R9 cross-origin failures show the real candidate-level error rate was non-zero; single-origin rows cannot be cross-checked.
- Complete-year counts use the provider's daily value (USGS `dv` stat 00003, then 32400; CWMS daily or mean of sub-daily; RISE daily). Mixed statistics and datums across a long record are not harmonised here.
- Liveness is a single-day snapshot (2026-10-13). A seasonal or temporary outage turns a lake into `REJECT` or `NONE` today; the weekly re-probe in section 6 is the fix.
- Only up to 4 CWMS series per location were probed and 5 sites per lake, so a few unbound lakes may have a better series further down the ranking.
