# Lake Brain: operator plan and flood-pool evidence (the two weakest score dimensions)

**Read-only evidence map.** No evidence was added to any profile, binding, table or rubric by this document. It recomputes what authoritative, documented operator plan and flood-pool evidence exists, per operator and per provider, how many strict-binding lakes it covers, and which new sources would unlock the most lakes. `UNKNOWN` is a valid answer wherever an operator publishes no flood level or no plan; the score rubric does not credit it (section 6), but the Brain must not invent a value to fix that.

Written 2026-10-13. Inputs: `jobs/lake-brain/data/bindings.proposed.v1.json` (196 accepted-eligible rows, with their `plan.levels[]`, `dam` NID record, `provider`), `bindings.proposed.v1.excluded.json`, `jobs/lake-brain/review/held_lakes.json`, and from the research branch `docs/research/lake-brain/data/plan_flood_evidence.csv` (315 rows), `plan_crosscheck.json`, `plan_summary.json`, `LAKE_BRAIN_PLAN_HISTORY_RESEARCH.md`. Script: `jobs/lake-brain/readiness/plan_flood_by_operator.py` (run with `--evidence <plan_flood_evidence.csv>`; tests in `test_readiness.py`).

## 1. The dimensions and their definitions

Rubric `lake-brain-score-v1`: **operatorPlan** (weight 10) is the share of profiled lakes whose profile has `operatingPools.guideCurve.available` or an `operatingZoneSource`; **floodDroughtContext** (weight 5) is the share of published states whose `floodPoolState` is not `UNKNOWN`. Research strict definitions, fixed before counting (`LAKE_BRAIN_PLAN_HISTORY_RESEARCH.md` 2.1) and used by the generated table:

- **guide** = a seasonal Guide Curve (CWMS `/levels` with seasonal values, a CWMS `Elev-Guide Curve` series, an A2W REGULAR / IRREGULAR level, or a TVA `GuideCurve` series with a non-zero annual swing).
- **zone** = BOTH a top (`Top of Conservation*`, `Top of Normal`, `Top of Constant Conservation`; TVA `TopOpZone`) AND a bottom (`Bottom of Normal`, `Bottom of Conservation`, `Drought Level n`; TVA `BtmOpZone`). A top without a bottom is **not** a zone.
- **plan strict** = guide or zone. **flood strict** = an operator flood-pool bottom (`Top of Conservation*`, `Top of Constant Conservation`, `Bottom of Flood*`).
- **verified match** = the operator project within 5 km of the lake polygon and (name, NID id or alias match), and a conservation or flood level within 100 ft of the lake's observed 30-day median or directory pool.

## 2. Where the numbers stand

Recomputed from the committed table (`plan.planStrict`, `plan.floodStrict`, and the level roles actually present agree: 84 and 111):

| Population | Lakes | Plan strict | Flood strict |
|---|---|---|---|
| Accepted-eligible (the 196) | 196 | **84 (42.9 %)** | **111 (56.6 %)** |
| Strict machine-verified, with the 76 held-back lakes (coordinate 58, series 14, provider terms 4) | 272 | 118 (43.4 %) | 157 (57.7 %) |

The strict-272 figure combines the table for the 196 with `plan_flood_evidence.csv` for the 76 held lakes (6 of them have no evidence row because they come from wave 2, where no plan search was run). Reconciliation, stated because the two sources differ by one lake: the research CSV marks Okatibbee Lake\|MS `planStrict` true, the generated table has it false (a top without a bottom in the table's level roles). The table is used throughout, it is the conservative reading.

Projected dimension values on the 196 (unmodified rubric; arithmetic in `LAKE_BRAIN_PRODUCTION_READINESS_MATRIX.md`): operatorPlan **4.3** (84/196), floodDroughtContext **5.7** (111/196). 7.5 needs 147 lakes for either.

## 3. Evidence by operator group (accepted-eligible 196)

NID `operatorName` of the lake's dam, as carried in the table (lakes with no NID dam record appear as unknown). "Neither" counts lakes with no strict plan and no strict flood level.

| Operator group | Lakes | Plan | Flood | Both | Neither | Reading |
|---|---|---|---|---|---|---|
| USACE | 96 | 62 | 87 | 60 | 7 | Best covered. CWMS levels and the A2W (Access2Water) project listing are machine-readable, name the same levels, and agree with each other. 27 USACE lakes have a flood-pool bottom but no zone bottom (section 5, S-B). The 7 with neither have no verified operator match (Clarks Hill / Thurmond, Columbus MS, Eufaula / W.F. George, Jordan NC, Kerr NC, Kerr VA, Lewis and Clark). |
| TVA | 11 | 11 | **0** | 0 | 0 | The TVA RestApi publishes a guide curve and an operating zone but **no flood-pool bottom**. `floodPoolState` stays `UNKNOWN` (flag `noOperatorFloodPoolThreshold`), correctly. |
| USBR | 24 | 4 | 10 | 4 | 14 | USBR RISE has no rule-curve, top-of-conservation or flood parameter (parameter index: 233 elevation, 234 storage series only). USBR flood space appears only where a USACE district manages it in CWMS (e.g. SPK `Elev-Top Con`). |
| State | 16 | 0 | 3 | 0 | 13 | No machine-readable state feed found. |
| Public utility (investor-owned or public power) | 13 | 2 | 4 | 2 | 9 | Seasonal targets exist but live in FERC licence PDFs, settlement agreements and local datums. |
| Local government | 12 | 1 | 3 | 0 | 8 | Includes the Texas river authorities (Lake Buchanan, Lake Travis, Possum Kingdom: levels reach the table through CWMS). |
| Private | 9 | 0 | 0 | 0 | 9 | None found. |
| No NID dam record (natural or outlet-regulated lakes) | 14 | 4 | 4 | 4 | 10 | Pend Oreille and similar lakes join a USACE project (Albeni Falls); the rest have nothing. |
| Fish and Wildlife Service | 1 | 0 | 0 | 0 | 1 | |
| **All** | **196** | **84** | **111** | **70** | **71** | 125 lakes have a verified operator match, 71 have none. |

(Rows are `plan_flood_by_operator.py` output, grouped by the NID `operatorName` of the lake's dam.)

By binding provider (the provider the strict binding uses, not the operator): a2w 75 lakes plan 44 / flood 70; cwms 42: 20 / 28; nwps 21: 6 / 7; rise 19: 2 / 5; usgs 28: 1 / 1; tva 11: 11 / 0. The pattern is that **plan and flood evidence follows the operator, not the provider**: an NWPS or USGS gauge on a USACE lake still gets levels when the lake is joined to its CWMS or A2W project by name, NID id or alias.

By lake class (plan / flood of lakes in class): R1 run-of-river 10 of 20 / 2 of 20; R2 flow-through 17 of 43 / 23 of 43; R3 dendritic storage 25 of 53 / 40 of 53; R4 open-basin storage 28 of 64 / 41 of 64; N2 regulated natural 4 of 11 / 4 of 11; N1 natural 0 of 3; R5 0 of 1; X mega 0 of 1 / 1 of 1.

## 4. Why the remaining lakes have no flood level: UNKNOWN is often the right answer

The 85 lakes in the 196 with no strict flood level split by NID purpose (counted from `dam.floodControl`):

| Reason | Lakes | Meaning |
|---|---|---|
| NID lists **no flood-control purpose** | 47 | Hydropower, water supply, recreation or irrigation reservoirs. No flood pool exists, or it is not an operator-defined pool. `UNKNOWN` is correct. |
| No NID dam record or purpose unknown | 12 | Mostly natural and outlet-regulated lakes. `UNKNOWN` is correct unless an outlet rule is published. |
| NID lists flood control but no flood level documented | 26 | Of these, **9 are TVA** (TVA publishes no flood-pool bottom: `UNKNOWN` is correct as published). **17 are a true evidence gap:** USACE 7 (Clarks Hill / Thurmond, Eufaula / W.F. George, Jordan NC, Kerr NC, Kerr VA, Lewis and Clark, Seminole), State 4 (Great Sacandaga, Indian Lake, Lake Marion, Lake Moultrie), Private 2 (Hebgen, Lake of the Ozarks), Local government 2 (Eagle Creek, Ross Lake), USBR 1 (Box Butte), Public utility 1 (Topaz). |
| (Evidence exists without an NID flood flag) | +10 | 6 lakes with NID flood false and 4 with unknown still have a documented flood-pool bottom; they are in the 111. |

Ceiling for floodDroughtContext on the 196 if **every** NID flood-control lake were documented: 127 + 10 = **137 of 196 = 69.9 % = 7.0**. It cannot reach 7.5 by evidence on this fleet.

## 5. Sources ranked by lakes unlocked (within the 196; none applied)

"Unlocked" counts lakes that currently lack the credit and would gain it. "Class" says whether it is new evidence or a decision about existing evidence.

| Rank | Source / action | Gives | Lakes unlocked | Class and effort | Terms / grade |
|---|---|---|---|---|---|
| 1 | **S-B Definition decision** (not a source): a documented Top of Conservation plus an operator-published lower-pool level (Top of Inactive, Bottom of Power, Minimum, Bottom of Operating) accepted as a "zone" | plan | **36** (e.g. Alum Creek, Center Hill, Chatfield, Dale Hollow, Falls Lake, Raystown, Sam Rayburn, Boysen, Canyon Ferry, Keyhole, Possum Kingdom) | **A semantic call by Michael, not evidence.** The levels are already in the table. It changes what "zone" means in the research definition and the rubric fact; it would lift plan 84 to 120 (4.3 to 6.1). Not applied. | Operator-published; grade A for the levels, but "lower pool is a zone bottom" is an interpretation |
| 2 | **S-C TWDB recent-conditions** (122 Texas reservoirs: `conservation_pool_elevation`, `dead_pool_elevation`, `flood_control_lake`) | flood and a zone-shaped pair | plan **9** (5 of them overlap with rank 1), flood **4** (Conroe, Fork, Livingston, Tawakoni) | New evidence, already fetched in research. Small adapter (no adapter exists: TWDB has no strict lake bound today). Matches CWMS exactly where both exist (7 of 7 Texas pairs equal). | State agency JSON; tier 2; terms not recorded as restrictive, to confirm |
| 3 | **S-A Remaining USACE joins** (CWMS / A2W) for lakes with no verified operator match: Clarks Hill / Thurmond, Eufaula / W.F. George, Jordan NC, Kerr NC and VA (one lake), Columbus MS, Lewis and Clark | plan and flood | up to **7** USACE lakes | Research join found no verified match; yield unknown, could be 0 (e.g. Kerr VA matched only an Arkansas River lock by name and was rejected). About a day of join checks. | USACE public data, grade A once matched |
| 4 | **S-E FERC licence curation** (rule curves and seasonal targets for non-federal hydropower) | plan, sometimes flood | **25** non-federal hydropower lakes lack plan (Badin, Cheat, Claytor, Deep Creek, Don Pedro, Grand Lake, Great Sacandaga, Hebgen, Herrington, High Rock, Jordan AL, Billy Chinook, Buchanan, Gaston, Greenwood, Livingston, Marion, Monticello, Moultrie, Murray, Travis, Ozarks, Lay, Smith, Possum Kingdom); real yield unknown | **Manual:** about 1 to 2 hours per project (find the order, read the exhibit, convert the datum); eLibrary is JavaScript-only; PDF parsing at scale is not recommended (research S-plan-020). Seasonal targets confirmed to exist for Santee Cooper (Marion rule curve about 72.0 ft winter to 75.5 ft summer), Lake Norman (not in the 196), Smith Mountain (operations "not guided by a target elevation"). | Federal licence documents; grade A when read correctly; high effort |
| 5 | **S-D NWPS gauge `normalThreshold`** | flood only (tier 3) | **2** (Herrington Lake KY, Oconee GA) | Origin of the threshold is not stated; agrees with USACE Top of Conservation in 3 of 4 identical cases. | Tier 3, not recommended as a stand-alone flood bottom |
| 6 | **S-F USBR** | plan | 0 known; **20** USBR lakes lack plan | RISE has no rule-curve parameter (research S-plan-019, dead end). USBR operating criteria are PDFs. | n/a |
| 7 | State programmes (Kansas KARS `Elev_ft`, Oklahoma, Nebraska) | normal pool only | 0 | Normal pool is already the directory full pool; no zone or flood level | n/a |
| 8 | Santee Cooper lake-data page (daily rule-curve column) | plan for Marion, Moultrie | 2 (lead) | The host did not resolve from the research environment; test from a browser | Lead, not a feed |

Reading the table honestly: **the largest "unlock" is a definition, not a source.** Real new evidence available now is small (TWDB: 4 lakes with neither, 5 more with a zone-shaped pair) and the remaining real gains (S-A, S-E) are manual and uncertain.

### What each path does to the score (196 lakes, from `project_scores.py`)

| Scenario | Plan | Flood | operatorPlan | floodDroughtContext |
|---|---|---|---|---|
| Today's table | 84 | 111 | 4.3 | 5.7 |
| + TWDB tier 2 (S-C) | 93 | 115 | 4.7 | 5.9 |
| + S-B definition decision (36) | 120 | 111 | 6.1 | 5.7 |
| + S-C and S-B (overlap 5) | 124 | 115 | 6.3 | 5.9 |
| + NWPS tier 3 flood (2) | 124 | 117 | 6.3 | 6.0 |
| Ceiling (all NID flood-control lakes documented) | n/a | 137 | n/a | 7.0 |

7.5 needs 147 lakes: no row reaches it.

## 6. The score does not credit UNKNOWN, and cannot

Both dimensions are shares of **all** profiled lakes or states. A lake with no flood pool, or an operator that publishes none, is a zero in the share, however correct the `UNKNOWN`. This is a property of the rubric, not of the evidence. The honest options are to say so in the readiness reading (done in the matrix), to change the fleet mix, or for Michael to change the rubric. None of that is done here, and the Brain must not publish a level it has not documented to improve a number.

## 7. What real evidence would move each dimension

| Dimension | What moves it | What does not |
|---|---|---|
| operatorPlan | Documented seasonal guide curves or two-sided zones for USBR (20), non-federal hydropower (25), state and local lakes: FERC licence work (rank 4), USBR operating criteria (no feed found), operator web pages with machine-readable tables (none found for Alabama Power, Dominion, Duke, Santee Cooper). A decision on S-B. | Treating a normal pool or a top of conservation alone as a plan; the research score deliberately did not. |
| floodDroughtContext | Flood-pool bottoms for the 17 evidence-gap lakes; TWDB for 4; more flood-control reservoirs in the fleet. | Declaring a flood state where the operator publishes no bottom; TVA stays `UNKNOWN`. |

## 8. Safeguards kept

- Nothing was written to `bindings.proposed.v1.json`, profiles, RTDB or a bucket.
- Every count above is reproducible by the committed script and the research CSV; it does not rely on prior documents' numbers.
- The 9 TVA flood-control lakes and the 47 lakes with no flood-control purpose are classed `UNKNOWN`-valid, not gaps.
