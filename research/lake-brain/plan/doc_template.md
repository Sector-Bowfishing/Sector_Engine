# Lake Brain: deep history extension and operator-plan / flood-pool evidence (research thread `plan`, wave 2)

**Status:** research only (2026-10-13). Branch `docs/lake-brain-research`. GET-only against public services; no write to any RTDB or bucket, no deploy, no change to `scoring.py`.
**Reproduce:** `research/lake-brain/plan/` (`hads_fetch.py`, `usgs_fetch.py`, `cwms_pull.py`, `twdb_fetch.py`, `coops_fetch.py`, `history_extension.py`, `plan_evidence.py`, `plan_finalize.py`, `plan_crosscheck.py`, `plan_score.py`). Bulk data is outside Git (`Sector_Research_Data/lake-brain/plan/`, retention rows in `MANIFEST.jsonl`). Machine-readable results in `data/`: `history_extension.csv`, `history_extension_summary.json`, `plan_flood_evidence.csv`, `plan_summary.json`, `plan_crosscheck.json`, `plan_score_deltas.json`. Ledger: `ledger/plan.jsonl`.
**Scope:** the 258 core machine-verified bound lakes (`VERIFIED`, `VERIFIED_CORROBORATED`) and the 57 flagged ones (`VERIFIED_FLAG`) from `binding-review-v1`. Nothing here counts for the rubric until a human adopts the bindings (rubric `cannotCount`, blocker B-binding-001).

## 0. Answers in one page

| Question | Answer |
|---|---|
| How many of the 71 bound lakes without 5 complete years now have them? | **48 move to SUFFICIENT** (36 core, 12 flagged), 44 from NONE and 4 from LIMITED/INSUFFICIENT; 39 of the 48 have 10 or more complete years, 25 have 15 or more. The 4 TVA pilots (16 to 18 years) were already counted by the baselines thread and are not new. 19 lakes stay short: 13 NONE, 6 LIMITED (section 1.4). |
| Resulting history share (core, 258) | **SUFFICIENT 79.8 % -> 93.8 %** (206 -> 242 lakes); baseline (SUFFICIENT or LIMITED) 87.6 % -> 99.6 %. With flagged: 78.4 % -> 93.7 %. Under a 10-year rule (the baselines-thread recommendation) 46.5 % -> 58.1 %. |
| Biggest unlock | The IEM HADS archive, which holds the NWS gauge pool-elevation stream (`HPIR*`) from 2010-12/2011 onward for the NWS location ids that NWPS serves: **34 NWPS-relay lakes, 34 of 34 recovered (27 core, 7 flagged)**, each 5 to 15 complete years, agreeing with the live NWPS feed at a median 0.000 ft (max 0.063 ft; one lake needed a constant 1.7 ft datum shift). The other 14 gains come from USGS (statistics the binding thread skipped), CWMS (the right tsid), TWDB, CO-OPS and NWS RVDHUN. |
| Authoritative plan / flood evidence (core 258) | A verified join of CWMS levels + CWMS time-series guides + Access2Water levels (with NWS-LID / USGS-id / NID aliases) + TVA operating guide gives **plan (guide curve OR zone) 119 lakes = 46.1 %** (was 48 = 18.6 % in the published state), **flood-pool bottom 157 = 60.9 %** (was 83 = 32.2 %). 32 have a seasonal guide, 102 a conservation zone (top AND bottom). The previous operatorPlan text was a strict subset: 0 lakes lost, 71 plan and 74 flood lakes added. |
| Tier-2 regulators | TWDB conservation / dead pool adds 13 core lakes (all Texas), NWPS `normalThreshold` adds 9 more normal-pool-only lakes. They agree with the USACE top of conservation within 1 ft on 10 of 11 overlapping lakes (all 11 within 3 ft). |
| Score effect (unmodified rubric, uncapped) | Core 258, NOT_VALIDATED: **5.9 -> 6.3 (history) -> 6.7 (strict plan/flood) -> 6.8 (tier 2)**; with a VALIDATED gate 7.4 -> 7.8 -> 8.2 -> 8.3. Displayed value stays 5.0 until validation lifts (section 4). |
| New sources worth integrating | HADS archive (history), CWMS `/levels` seasonal values + time-series guides and A2W `levels` with aliases (plan/flood), TWDB recent-conditions (Texas), CO-OPS `daily_mean`. Not worth it at scale: FERC eLibrary (JavaScript-only, local datums in PDFs), USBR RISE (no operating-criteria parameter). |
| Bowfishing | 87 of the 258 core lakes have both 5 or more years of history and a seasonal plan; 40 have a seasonal swing of 5 ft or more, 22 of 10 ft or more (Summersville 77 ft, Tygart 54 ft, Fontana 58 ft, flagged); these are the lakes where "x ft below/above the guide" changes what a bowfisher is told (section 5). |

## 1. Part A: deep history for the bound lakes that lacked 5 complete years

### 1.1 Method

Target list: the 71 bound lakes (55 core, 16 flagged) whose `verified.csv` `completeYears` was below 5. For each lake the best long source was found in this order (full source table in the ledger, S-plan-001 to S-plan-013):

1. **NWPS-relay lakes (34).** The NWPS gauge id is an NWS location id; the IEM HADS archive (`hads.py`) keeps the raw DCP stream of that id, including `HPIR*` pool elevation, from about 2010-12. Pulled in 3-year chunks, one request at a time (IEM returns HTTP 429 above about one request per 15 to 20 s; the fetcher backs off 60 s doubling to 10 min). Daily value = median of the readings in the lake-local calendar day (spike-robust).
2. **NWPS `usgsId` relay.** The NWPS gauge metadata names the USGS site (9 lakes). USGS holds decades under statistics the binding thread did not request: `30800` (observation at 24:00, Taneycomo 1987+, Lahontan), `32400` (Topaz, Bartlett, Priest) and instantaneous values reduced to daily (`iv`, Ute 2007+, Buckeye 2019+). Gage-height (`00065`) series carry a constant local datum: the offset is estimated against HADS over at least 365 overlapping days (residual sd <= 0.20 ft, or MAE <= 0.20 and p95 <= 0.50 ft; 60 days allowed when sd <= 0.10) and applied only then.
3. **USACE.** The binding thread probed only the first two tsids per CWMS location, which were empty for Chatfield, Buckhorn, Okatibbee, Pend Oreille and Lake Washington. The hourly raw/rev tsids carry 14 to 40 years.
4. **Other:** TWDB (Amistad 1968+, Falcon 1953+, the earlier "empty" was an endpoint issue), NOAA CO-OPS `daily_mean` (Lake St. Clair 1995+), NWS RVDHUN text (Nickajack 2007 to 2021, Tims Ford 2003 to 2013, parsed file reused from the baselines thread).

Composite rule: the first source in precedence order wins on a date; a secondary fills earlier dates after its constant offset is applied. A complete year is at least 329 daily values in a calendar year before the current one, as in the rubric.

### 1.2 Result

{{SUMMARY_TABLE}}

Per-lake table (all 48 gains; `data/history_extension.csv` has the full 71 rows with offsets, cadence and notes). "live MAE" is the mean absolute difference between the new daily series and the live NWPS 30-day feed on the same local days (n/a: the live feed is not NWPS).

{{EXT}}

### 1.3 Agreement, datums, timing, resolution

| Check | Result |
|---|---|
| New HADS series vs the live NWPS feed (33 lakes with a live overlap of 23 to 31 days) | median MAE 0.000 ft, maximum 0.063 ft (Lake Sharpe), 32 of 33 within 0.05 ft. HADS and NWPS are the same DCP stream, so this confirms units, timezone and datum rather than independence. |
| Datum shift | One lake: **Cayuga Lake** (flagged) HADS raw sits a constant 1.7 ft below NWPS (residual MAD 0.03 ft); the history was shifted to the live datum, historic stability unverified. D'Arbonne (USGS gage height + 40.20 ft, sd 0.02), Topaz (+4899.97 ft, sd 0.15), Priest Lake (+2434.40 ft, sd 0.05 over only 68 overlap days) are gage-height datums found by overlap. |
| Independent second origin | USGS vs HADS over 600 to 1,015 overlap days: Herrington (offset 0.00 ft, sd 0.09), D'Arbonne, Topaz, Indian Lake NY (MAE 0.09 ft, p95 0.15) agree; Bartlett's USGS gage height (offset +1599.95, sd 33 ft) does not and was not used. |
| Stage-to-elevation switch | PSLI1 (Priest Lake) HADS carries local gage height (3.06 ft) until 2013-11-18 and elevation afterwards; the prefix was shifted by the jump (+2434.42 ft) and then agrees with USGS to 0.04 ft. Any NWPS-relay history should be screened for such switches (the 34 pulls were range-checked against the directory pool). |
| Time of day | HADS early years are often **one reading per day**: 12 of the 34 gauges have 2.5 or fewer readings per day in their first year (typically 07:00 or 08:00 local; Neely Henry 23:00), 15 are already hourly or finer. A daily "midnight" series is therefore a 7 AM reading for those early years. RVDHUN years (Nickajack, Tims Ford) are 6-7 AM readings at **0.1 ft** resolution; everything else is 0.01 ft. |
| Mixed statistics | USGS 24:00 observations, daily means, CWMS hourly means and HADS medians are all treated as "the daily value"; day-to-day noise is below 0.05 ft for the lakes checked and not corrected. |

Do not use these years to build the rate climatology (abs change per 24 h) for the 12 lakes with a daily-reading first year: the baselines-thread rule (rate statistics only from the sub-daily era) applies.

### 1.4 What stays short (19 lakes)

{{NOT}}

The 9 TVA tributary lakes are LIMITED in practice (HADS `HP` from 2022-10-27 gives 3 complete years 2023 to 2025; SUFFICIENT under the 5-year rule in 2028); `verified.csv` still calls them NONE because the binding thread did not pull that stream. Dead ends are recorded in the ledger (RVD products of seven WFOs do not carry the TVA tributary pool ids; the CWMS `LPMS` TVA series have 0 to 3 complete years; the SFWMD data service needs registered credentials; ResOpsUS is a 299 MB download that was not fetched, M-plan-03).

## 2. Part B1: the authoritative plan / flood evidence table

### 2.1 Rules (fixed before counting)

* **guide** = a seasonal Guide Curve / Rule Curve: CWMS `/levels` entry with `seasonal-values`, a CWMS time series named `Elev-Guide Curve` (and `GC`, `Guide_Curve`, `Guide-Curve`), A2W level of type REGULAR/IRREGULAR, or the TVA `GuideCurve` series with a non-zero annual swing (Nickajack's guide is constant 633.5 ft and does not count).
* **zone** = BOTH a top (`Top of Conservation*`, `Top of Normal`, `Top of Constant Conservation`) AND a bottom (`Bottom of Normal`, `Bottom of Conservation`, `Drought Level n`). TVA: `TopOpZone` and `BtmOpZone`.
* **flood** = an operator flood-pool bottom: `Top of Conservation*`, `Top of Constant Conservation`, `Bottom of Flood`, `Bottom of Flood Control` (CWMS level or A2W level, or the CWMS `Elev-Top Con` series).
* **plan strict** = guide OR zone. **Inclusive** adds a seasonal Top-of-Conservation curve with no bottom and the three regulation-schedule lakes (Kissimmee chain, Okeechobee).
* **verified match** = the operator project is within 5 km of the lake polygon AND (normalised name match OR NID id equal OR NWS-LID / USGS-id alias equal OR it is the bound live series), AND a conservation / flood level is within 100 ft of the lake's observed 30-day median or directory pool. Projects without coordinates (23 A2W projects) match only through the alias keys. A weaker tier (project within 0.5 km of the polygon, level within 25 ft) is kept separate: 2 lakes (Neely Henry via `HNHenry`, Pend Oreille via Albeni Falls Dam).

### 2.2 What the earlier counts missed

The baselines thread counted 143 of 621 directory lakes by spatial match (unreviewed), and the binding thread's `operatorPlan` text covered 117 of the 315 bound lakes because it read levels only from the *bound* provider's own probe (A2W-bound lakes, TVA, CWMS guide series). The join by lake adds: lakes bound through NWPS, USGS or RISE whose reservoir has USACE levels (Tenkiller, Kaw, Canton, Skiatook, Moomaw, Pend Oreille, John Redmond and others); lakes bound through CWMS whose levels were never read (only time-series guides were); CWMS time-series guides (`Elev-Top Con` for USBR-owned flood space in SPK, `Elev-Zone`, `Elev-L1..L3`); and A2W projects with no coordinates, matched by the NWS Handbook-5 id, USGS station and NIDID aliases in the A2W record.

| Core lakes (258) | published state (operatorPlan text) | this join, strict | inclusive | + tier 2 |
|---|---|---|---|---|
| plan (guide or zone) | 48 (18.6 %) | **119 (46.1 %)** | 140 (54.3 %) | 152 (58.9 %) |
| flood-pool bottom | 83 (32.2 %) | **157 (60.9 %)** | 157 | 163 (63.2 %) |
| guide curve (seasonal) | n/a (guide + zone merged) | 32 | 38 lakes with a seasonal Top-of-Conservation curve | |
| lakes lost vs the old text | | 0 | | |

With flagged lakes added (315): plan 126 (40.0 %), flood 168 (53.3 %). By the binding provider of the core lakes:

{{PROV}}

NWPS-bound lakes are mostly non-federal (36 core lakes, 9 matched); the 33 USBR-bound lakes get only 14 flood matches (USBR flood space appears in CWMS only where USACE manages it) and no guide.

### 2.3 Verification

* **Match quality.** Of the 258 core lakes, 165 match an operator project at the strong tier and 2 at the weak tier; the TVA lakes match through their bound station. Traps found and removed: Lake of the Ozarks (polygon touches Truman Lake: level 46 ft off, now rejected), Devil's Kitchen Lake (the 4-letter CWMS code `CHEN` matched inside its name; Cheney Lake is in Kansas), Kerr Reservoir VA (matched the Arkansas River `RS Kerr LD15` by name only), Alamo/Shasta/Blue Mesa/Dworshak (drawdown lakes, kept because name, geometry and bound station agree).
* **Independent confirmation of levels.** The tier-1 top of conservation was compared with an unrelated regulator value for the 11 core lakes that have both: TWDB conservation pool (Canyon 909, Cedar Creek 322, Buchanan 1020, Texoma 617, Travis 681, Possum Kingdom 999, Sam Rayburn 164.4 ft: all equal) and the NWPS `normalThreshold` (Tenkiller 632, Skiatook 714, Canton 1615.4 equal; Kaw 1013 vs 1010) -> 10 of 11 within 1 ft, 11 of 11 within 3 ft (`data/plan_crosscheck.json`).
* **Seasonal values.** The CWMS `PENS` Top of Conservation seasonal values for Grand Lake o' the Cherokees (742 winter, 744 May to July, 743 August, 741 September, 742 November) equal the GRDA-published 2017 rule curve (a public monthly CSV, S-plan-022) month by month.
* **Not independently verified:** the 119 lakes were not hand-reviewed one by one; unmatched US lakes with a federal or state operator (30 USBR lakes, Alabama Power 4, Georgia Power 3, Santee Cooper 2, Dominion 2, ODNR 4, Sabine River Authority 3) are the evidence gap.

## 3. Part B2: other operators and regulators (tested)

| Source | Tested | Finding | Decision |
|---|---|---|---|
| USBR RISE catalog | parameter index (233 elevation, 234 storage series) | no rule-curve, top-of-conservation or flood-control parameter; USBR flood space appears only in CWMS SPK (`Elev-Top Con`) | dead end for plan evidence (S-plan-019) |
| TWDB recent-conditions | JSON for 122 Texas reservoirs | `conservation_pool_elevation`, `dead_pool_elevation`, `flood_control_lake`; 13 core lakes; matches CWMS exactly where both exist | accept as tier 2 (S-plan-017) |
| NWPS gauge `normalThreshold` | 48 bound gauges | non-zero for 11; agrees with USACE top of conservation (3 of 4 identical); origin not stated | tier 3, flood only (S-plan-018) |
| GRDA | public Datawrapper CSV | monthly rule curve 1958 to 2017 for Grand Lake | confirms CWMS (S-plan-022) |
| Kansas KARS PhysicalLakeData | ArcGIS layer, 76 lakes | `Elev_ft` normal pool only | lead, low value (S-plan-023) |
| FERC eLibrary / licence PDFs | eLibrary page; operator pages for Santee Cooper (P-199), Appalachian Power Smith Mountain (P-2210), Duke Catawba-Wateree (P-2232) | eLibrary is JavaScript-only (no anonymous API found). Seasonal targets exist but live in PDFs, settlement agreements and local datums: Marion rule curve about 72.0 ft winter to 75.5 ft summer, Lake Norman target 94 to 98 ft local datum (seasonal), Smith Mountain 793 to 795 ft with operations "not guided by a target elevation". | **lead, not a feed.** Effort: about 1 to 2 hours of manual curation per project (find the order, read the exhibit, convert the datum), about 25 projects for the bound non-federal lakes; do not parse PDFs at scale (S-plan-020) |
| Santee Cooper lake-data page | search result shows a daily table with a rule-curve column | host did not resolve from this environment | lead; test from a browser (M-plan-04, S-plan-021) |
| USACE water-control manuals | not downloaded | the CWMS levels are the machine-readable form of the manuals' pool tables | covered by tier 1 |
| Oklahoma / Nebraska state programs | search only | no state-level seasonal curve feed found; Oklahoma's GRDA lakes are covered through CWMS SWT and the GRDA CSV | no action |

## 4. Part B3: score deltas with the unmodified rubric

`plan_score.py` runs `research/lake-brain/tools/research_score.py` (which calls `score_lake` unchanged) over shares computed from the real per-lake evidence. Trend (observed) and source authority are 100 % for profiled lakes by construction. Profiled = core 258 (41.5 % coverage, ladder 5 points). The "uncapped" column ignores the validation gate; the displayed value stays 5.0 while validation is NOT_VALIDATED and the coverage gate (10 %) is passed.

| Step (core 258, 5-year rule) | plan | flood | history | baseline | uncapped, NOT_VALIDATED | uncapped, VALIDATED |
|---|---|---|---|---|---|---|
| S0 published research state | 0.186 | 0.322 | 0.798 | 0.876 | 5.9 | 7.4 |
| S1 + history extension | 0.186 | 0.322 | 0.938 | 0.996 | **6.3** (+0.4) | 7.8 |
| S2 + authoritative plan/flood (strict) | 0.461 | 0.609 | 0.938 | 0.996 | **6.7** (+0.4) | 8.2 |
| S3 + inclusive seasonal curves | 0.543 | 0.609 | 0.938 | 0.996 | 6.8 (+0.1) | 8.3 |
| S4 + tier 2 (TWDB, NWPS normal pool) | 0.589 | 0.632 | 0.938 | 0.996 | 6.8 (+0.0) | 8.3 |

Sensitivity: with the baselines-thread 10-year rule for SUFFICIENT, S0 -> S4 is 5.4 -> 6.3 (NOT_VALIDATED) and 6.9 -> 7.8 (VALIDATED). With the 57 flagged lakes included (315 profiled): S0 6.2, S1 6.6, S2 7.0, S4 7.1 (NOT_VALIDATED). Dimension view (core, S4): operatorPlan 5.9 of 10, floodDroughtContext 6.3 of 10, historyQuality 9.4 of 10, seasonalBaseline 10.0 of 10 (`data/plan_score_deltas.json` has all dimensions and the PARTIAL gate).

Honesty notes: (1) every number is conditional on a human reviewer adopting the binding and on the Engine ingesting the evidence; (2) the rubric's `floodDroughtContext` looks at the state's `floodPoolState`, which the Engine must compute from these levels; (3) the plan share counts a lake with a constant top and bottom of conservation as a "zone", which tells the bowfisher where the conservation pool is but not the season.

## 5. Part C: what would change what a bowfisher is told

Only facts from pages opened in this thread are cited. The product claim ("flooded shoreline vegetation and shallow backwaters make carp and gar reachable; drawdowns remove boat access") is qualitative; no source found gives elevation thresholds.

* **Spring rise above the seasonal guide / conservation pool.** An opened bowfishing habitat guide (bowhuntersunited.com, 2023) says drainage ditches and agricultural fields connected to rivers flood after heavy rain, carp and other rough fish leave the main channel to feed and spawn there, they can be stranded as water recedes, and most boats cannot reach these areas. For reservoirs the equivalent signal is "x ft above the operator's seasonal guide" or "in the flood pool" (157 core lakes have a flood-pool bottom; 87 also have 5 or more years of history and a seasonal plan).
* **Large winter-to-summer swings: the message changes most.** Seasonal swing of the operator curve (CWMS seasonal values, TVA guide): Summersville 77 ft, Tygart 54, Fontana 58 (flagged), Hiwassee 45, Douglas 46, Cherokee 32, Sutton 27, Sardis MS 24, Grenada 22, Enid 20, Allatoona 17 ft (winter 823 ft, summer 840 ft), Smith (AL) 14 ft. 40 core lakes swing 5 ft or more, 22 swing 10 ft or more, 57 swing 2 ft or more. For these, "pool is at 836 ft, 4 ft below the summer pool" is actionable; "normal for the date" alone hides whether the curve is rising.
* **Drawdown and access.** A Reclamation release (opened) announces a scheduled 6.2 ft Banks Lake drawdown to 1563.8 ft in late August to early September and lists boat-ramp minimum elevations: an operator plan plus ramp minimums turns a level into "ramp unusable".
* **Facts that would not change the message.** Run-of-river TVA mainstem pools (guide swing 1.5 to 5 ft; Nickajack constant), natural lakes (no plan), and lakes whose only plan fact is a constant top of conservation (it says "in/out of the flood pool", not "ahead of/behind the season").
* **Percentile history still matters** where no plan exists (natural lakes, 139 core lakes without a strict plan): "level normal for the date" is then the only available context, and the 5 to 15 years recovered here are what make it available for 34 NWPS-relay lakes.

## 6. Blockers and actions (full rows in `ledger/plan.jsonl`)

| ID | Item | Priority |
|---|---|---|
| M-plan-01 | Adopt tier-1 plan/flood evidence in the lake profiles after binding review (+0.4 to +0.8 uncapped) | high |
| M-plan-02 | Optional: register an SFWMD data-service client id for Istokpoga/Kissimmee (B-plan-001, +0.06) | low |
| M-plan-03 | Approve a one-time ResOpsUS download (about 299 MB) to test TVA tributary coverage (B-plan-002) | medium |
| M-plan-04 | Check lakes.santeecooper.com in a browser for a daily Marion rule-curve value (B-plan-004) | low |
| M-plan-05 | Optional: request the TVA pool-elevation archive for the 9 tributary projects (same as M-baselines-01) | medium |
| B-plan-003 | 8 short-record lakes (Hebgen, Monticello SC, two Ohio lakes, Rye Patch, two Massachusetts ponds, Ross Lake): no archive, no action; they age into SUFFICIENT in 2028 to 2029 | low |

## 7. Honest limits

* HADS/NWPS-relay history is not independent of the live feed; it proves lineage, not accuracy. Gauge datum changes inside the 2011 to 2026 window (a NWPS gauge re-datumed) would not be caught except by the range check and the Priest Lake style jump screen.
* The first years of many HADS series are one reading a day at 07:00 to 08:00 local time; baselines built on them mix times of day with later hourly means.
* Rainy Lake (flagged) merges a USGS series (Water Survey of Canada, 1992 to 2020) that has no overlap with the HADS stream; it is level-compatible within 0.2 ft but datum-uncalibrated, and its 5 complete years sit at the threshold. Indian Lake NY (123 years) mixes three USGS parameter/statistic series.
* The plan join is machine-verified, not hand-reviewed; 2 lakes are weak-tier matches. Constant "zones" and seasonal curves are counted equally in `plan strict`; the seasonal subset is listed separately.
* TVA GuideCurve is read from the two-calendar-year API; it is the annual guide, not a historical series. TVA tributary guide swings of 18 to 58 ft are consistent with a flood-control guide, but no TVA document stating that was opened, so they are not counted as flood-pool bottoms.
* Score values assume the evidence is ingested for all profiled lakes; the production Engine reads only some providers today (`--providers` in `fleet_score.py` shows the narrower case).
