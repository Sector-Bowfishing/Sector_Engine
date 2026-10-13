# Lake Brain: baselines, deep TVA history and operator-guide availability (research thread `baselines`)

**Status:** research only (2026-10-13). Branch `docs/lake-brain-research`. No deploy, no write to any RTDB or bucket, no change to the Engine or to `scoring.py`.
**Reproduce:** `research/lake-brain/baseline_eval.py` (methodology), `tva_pilot_history.py` (TVA composite), `guide_availability.py` (CWMS levels), `baseline_fetch.py` and `parse_rvdhun.py` (acquisition). Bulk data is outside Git (`Sector_Research_Data/lake-brain/history/`, manifest rows in `MANIFEST.jsonl`). Machine-readable results: `data/baseline_summary.json`, `data/guide_availability.csv`; source ledger: `ledger/baselines.jsonl`.

## 0. Answers in one page

| Question | Answer |
|---|---|
| Is there a decades-long daily pool-elevation source for the four TVA pilots? | **Not as one dataset, but a composite of three official TVA/NWS feeds gives 16 to 18 complete years for every pilot.** (a) NWS Huntsville `RVDHUN` daily text product (TVA-supplied pool elevations, 6-7 AM, 0.1 ft) 2005 to 2021-09-30; (b) NWS/TVA HADS `HP` pool elevation, hourly, 0.01 ft, 2022-10-27 to today; (c) for Pickwick only, CWMS `LRD Pickwick-Lake.Elev.Inst.1Hour.0.Raw-TVA` 2019-10 to today. USGS has **no** lake-elevation series (00062/62614/62615/72020) at any of the four lakes. |
| Does it agree with TVA's live values? | **Yes, exactly.** HADS hourly equals the shared TVA archive's hourly `ReservoirElevation` (48 of 48 points per lake, difference 0.00 ft) and equals the TVA operating-guide midnight value on 647 days with MAE 0.001 to 0.003 ft. No datum offset. |
| What status do the pilots get? | `SUFFICIENT` today (Guntersville 17, Wheeler 18, Wilson 18, Pickwick 16 complete years) instead of `INSUFFICIENT` until 2030. Uncapped lake score +2.0 (historyQuality 0.30 to 1.50, seasonalBaseline 0.20 to 1.00 while only the 5 pilots are profiled); the displayed score stays at the coverage gate cap 3.0 until 63 lakes (10 %) are profiled. |
| Is `>= 5 complete years = SUFFICIENT` defensible? | **No, not for storage and natural lakes.** At 5 years the baseline's class (NORMAL / UNUSUAL / VERY_UNUSUAL) differs from a long-record baseline on 12 to 33 % of days, and `VERY_UNUSUAL` fires on 7 to 30 % of days (nominal 4 %). Recommended: 10 complete years for NORMAL/UNUSUAL, 15 for VERY_UNUSUAL; 5 to 9 years `LIMITED` and provisional. TVA run-of-river pools are the benign case (88 to 91 % agreement at 7 years). |
| Window, band, ±days? | Keep p10-p90 / p02-p98 and ±7 days (±10 is marginally better, not worth a version bump). Keep a rolling window but **do not cap natural lakes at 30 years** (use all years: Lake Erie pinball loss -16 %, Champlain -6 %); storage lakes with operating changes (Pueblo) gain from recency weighting (half-life 5 y: -39 % pinball loss). |
| Is the STABLE rule defensible? | **No as written.** `abs(Δ24h) <= max(0.10 ft, seasonal p50)` marks 51 to 58 % of days STABLE on every managed lake *by construction* (median abs(Δ) is 0.09 to 0.17 ft), and on 43 to 88 % of days the p50 term, not the 0.10 ft floor, sets the threshold, so drawdown and refill at 0.15 to 0.3 ft/day read STABLE. Sensor noise is 0.004 to 0.034 ft per 24 h difference, so the floor is a policy choice, not a noise limit. Recommended: absolute floor (0.10 ft reservoirs, 0.05 ft natural/Great Lakes), no p50 term, trend from the 72 h mean rate for the label (flicker 9 to 36 % vs 16 to 48 %), keep p95 as RAPID with a 0.25 ft minimum. |
| Guide/flood-level availability | 143 of 621 directory lakes (23 %) match a USACE CWMS project with published Elev levels; **132 (21 %)** have a flood-pool bottom or top of conservation, **58 (9 %)** a seasonal guide curve, 89 a drought/bottom-of-conservation level (automatic spatial match, unreviewed upper bound). TVA's own API adds guide curves for 15 of 16 TVA lakes and zones for 9. 29 USACE-labelled lakes are in districts absent from the public CWMS host. No machine-readable guide found for Duke or other utilities; Alabama Power's appear only through CWMS SAM. |

## 1. Deep history for the four TVA pilots

### 1.1 What was tried

| Source | Result | Verdict |
|---|---|---|
| TVA `RestApi/operating-guide/{loc}` | Works from `curl` **with a browser-like `User-Agent` and `Accept: application/json`** (without `Accept` it returns an HTML snapshot page). Two calendar years only (`CurYrElev`, `PrevYrElev`). `?year=` is ignored. | live source; no history |
| TVA `RestApi/observed-data-48-hours/{loc}`, `/observed-data/{loc}` | 48 h hourly. Same host, same `User-Agent` rule. | live only |
| Guessed TVA history paths (`historical-data`, `observed-data-30-days`, `reservoir-history`, `lake-levels`, `metadata`) | HTTP 404 | dead end |
| USGS NWIS site service, bounding boxes around each lake polygon, `seriesCatalogOutput` | 9 519 / 20 369 / 575 / 4 261 series rows in the four boxes; **none** with parameter 00062, 62614, 62615, 62616, 62617, 72020, 72214, 72215 (only water-quality rows: `WHEELER LAKE AT WHEELER DAM`, `TENN-TOM WATERWAY AT CROSS ROADS`). | dead end |
| USGS `api.waterdata.usgs.gov` OGC API | HTTP 429 `OVER_RATE_LIMIT` (4 000 requests/hour per key, shared egress IP, no key) | blocked, see B-baselines-002 |
| CWMS (all offices) for Guntersville / Wheeler / Wilson | Only 15-minute precipitation (`LRN GVDA1-GUNTERSVILLE.Precip-Inc...`) | dead end |
| **CWMS `LRD Pickwick-Lake.Elev.Inst.1Hour.0.Raw-TVA`** | hourly 2019-10-06 to today; also `Kentucky-Lake` (1998-05 to today), `Normandy-Lake` (2019-11) and tailwaters; **needs QC** (2019-20 contain tailwater and Normandy-scale values: 17.2 and 868 ft; keep 406 to 420 ft) | accepted for Pickwick |
| **NWS Huntsville `RVDHUN` ("Daily River and Lake Summary") via IEM AFOS archive** | One product per day 2003 to 2021-09-30, TVA mainstem pool elevations (headwater, labelled 7 AM or 6 AM local), **0.1 ft resolution**. Guntersville HW from 2005-01-30, Wilson HW 2005, Wheeler 2005-11, Pickwick ("Pickwick Dam" 2003, "Pickwick HW" 2007, ID `PKDT1` from 2010) until 2014-04-17; Memphis `RVDMEG` also lists Pickwick headwater but its observed value is `M` (missing) from 2014 to 2019. Product ends 2021-09-30. | accepted (TVA-sourced) |
| **NWS HADS `HP` (pool elevation) via IEM `hads.py`** | hourly 0.01 ft, first value **2022-10-27** at `GVDA1`, `WHLA1`, `WLSA1`, `PICT1` (`GVHA1` is a duplicate pool-only ID). The same `HP` stream exists for the other TVA dams (probe of 17 IDs on 2023-06-15, section 1.6). Before 2022-10-27 the same station IDs carry only precipitation and tailwater. | accepted |
| ResOpsUS (Steyaert et al. 2022) | Daily storage/inflow/outflow for 679 reservoirs, 1974 to 2020. Web-search description only; TVA coverage not confirmed; dataset not obtained. | LEAD (not opened) |
| Web search for a TVA bulk historical download | none found (TVA publishes live levels, guides and 48 h tables only) | dead end |
| Satellite altimetry (DAHITI, Hydroweb, G-REALM) | Not attempted: the pools are 0.8 to 3 ft wide bands (p10-p90) on narrow river reaches; altimetry error is larger than the band. | rejected on physical grounds |

The one-line reason this works: TVA transmits pool elevation to the National Weather Service for river forecasts. NWS carried it in `RVDHUN` text until 2021 and in HADS (as `HP`) from late 2022, and the Iowa Environmental Mesonet archives both.

### 1.2 The composite (research build, `tva_pilot_history.py`)

Daily value per lake, precedence HADS (local midnight, US/Central, the Engine's convention) > CWMS LRD (Pickwick, local midnight) > RVDHUN (6 to 7 AM).

| Pilot | RVDHUN daily (NWS/TVA) | days | HADS HP hourly (NWS/TVA) | HADS@00:00 vs TVA guide 2025+ | composite days | complete yrs | first-last |
|---|---|---|---|---|---|---|---|
| GVDA1 | 2005-01-30 to 2021-09-30 | 5964 | 2022-10-27 to 2026-10-13 | 647 d: MAE 0.001 ft, p95 0.0, max 0.257 | 7404 | 17 | 2007-2025 |
| WHLA1 | 2005-11-23 to 2021-09-30 | 5697 | 2022-10-27 to 2026-10-13 | 647 d: MAE 0.001 ft, p95 0.0, max 0.17 | 7137 | 18 | 2006-2025 |
| WLSA1 | 2005-01-30 to 2021-09-30 | 5966 | 2022-10-27 to 2026-10-13 | 647 d: MAE 0.002 ft, p95 0.0, max 0.24 | 7406 | 18 | 2006-2025 |
| PICT1 | 2003-01-14 to 2021-12-30 | 4212 | 2022-10-27 to 2026-10-13 | 647 d: MAE 0.003 ft, p95 0.0, max 0.22 | 6209 | 16 | 2003-2025 |

Complete-year (>= 329 days) lists: Guntersville 2007-2020 and 2023-2025; Wheeler and Wilson 2006-2020 and 2023-2025; Pickwick 2003-2004, 2006-2013 and 2020-2025. **Gaps:** 2021-10-01 to 2022-10-26 for Guntersville, Wheeler and Wilson (year 2021 has 270 days, 2022 has 65); Pickwick 2014-04 to 2019-09 (RVDMEG observed value missing; CWMS starts 2019-10). Years in a gap are not complete, so they do not count.

### 1.3 Agreement with TVA's own values

| Check | n | Result |
|---|---|---|
| HADS hourly vs shared TVA archive hourly (`gs://sector-water-temp-archive/water-temp/tva/<LOC>/2026-10-07, -09`), 4 lakes | 48 per lake | identical (max abs(Δ) 0.00 ft) |
| HADS at local midnight vs Lake Brain history (TVA operating-guide midnight), 2025-01-01 to 2026-10-13 | 647 per lake | bias 0.000 to -0.001 ft, MAE 0.001 to 0.003 ft, p95 0.000 ft, 8 to 16 of 647 days differ by more than 0.02 ft (5 to 9 days by more than 0.05 ft, max 0.17 to 0.26 ft), mostly in Nov-Dec 2025 |
| CWMS LRD Pickwick (local midnight) vs the same | 643 | bias -0.001 ft, MAE 0.002 ft, max 0.22 ft |
| RVDHUN (6 or 7 AM, 0.1 ft) vs CWMS Pickwick hourly at 7 AM, 2019-2021 overlap | 485 | MAE 0.034 ft, bias +0.006 ft, p95 0.09 ft, max 0.28 ft (consistent with 0.1 ft rounding plus one hour of timing) |

**Datum.** The values are feet above mean sea level as TVA publishes them. CWMS metadata for the TVA records says `native-datum: OTHER, local-datum-name: unknown`; TVA's API gives no datum tag. Because HADS, CWMS and the TVA API are numerically identical, **no offset is needed** between sources; the label (NGVD29 vs NAVD88) remains whatever the Engine already stores in `operatingPools.datum` for TVA (unverified).

**Two cautions about the composite.**
1. *Resolution and time of day.* The 2005-2021 part is rounded to 0.1 ft and is a 6-7 AM reading, not midnight. In the HADS era the 00:00 and 07:00 local readings differ by 0.08 to 0.17 ft on average (p95 0.20 to 0.42 ft) because these pools hunt with the hydropower cycle. Building the baseline from 07:00 instead of 00:00 values moves the p10/p50/p90 edges by a median of 0.03 to 0.10 ft (max 0.14 to 0.36 ft) against p10-p90 widths of 0.8 to 2.0 ft (section 2.7). That is below the width but of the order of the distance by which today's reading sits from an edge (section 2.7).
2. *Why not stitch silently.* Mixed sources must stay separable: the daily CSV keeps a `sourceId` per row (the Engine already does), and the rate climatology (abs(Δ24h)) must be built only from the 0.01 ft hourly era, never from the 0.1 ft rounded years.

| Pilot | TVA level 2026-10-13 ft | basis (complete yrs) | p02/p10/p50/p90/p98 | percentile | historicalState |
|---|---|---|---|---|---|
| Guntersville | 593.7 | 2007-2025 | 593.6 / 593.8 / 594.1 / 594.5 / 594.7 | 5.0 | UNUSUAL |
| Wheeler | 553.35 | 2006-2025 | 553.1 / 553.3 / 553.8 / 554.2 / 555.0 | 12.5 | NORMAL |
| Wilson | 506.98 | 2006-2025 | 506.41 / 506.8 / 507.2 / 507.5 / 507.6 | 24.0 | NORMAL |
| Pickwick | 411.24 | 2003-2025 | 410.6 / 411.0 / 411.7 / 412.34 / 413.87 | 16.8 | NORMAL |

*Illustration only: the composite baseline applied to the 2026-10-13 TVA values (Guntersville sits 0.1 ft below its p10, i.e. at the resolution of the older data).*

### 1.4 Can Sector adopt it?

Yes, as a **one-time backfill plus the existing daily merge**: the daily TVA operating-guide merge already keeps history growing; the research composite fills 2005-2022 (and the Pickwick hourly feed). Proposed `LakeHistorySource` additions (research recommendation, no code change made):

| New case | Meaning | Rows | Notes |
|---|---|---|---|
| `nwsHadsDcp` | NWS/TVA HADS `HP`, hourly, via IEM `hads.py` (public-domain NWS data, free service, poll politely) | 2022-10-27 to today, 0.01 ft | Use for the one-time backfill. The ongoing feed stays the TVA RestApi / shared archive (no new poller). |
| `nwsRvdhunArchive` | NWS Huntsville `RVDHUN` text archive via IEM AFOS (plus `RVDMEG` for Pickwick 2013) | 2003/2005 to 2021-09-30, 0.1 ft, 6-7 AM | Static; fetch once, keep the parsed CSV in `gs://sector-lake-brain/history/<key>/`. Parser: `research/lake-brain/parse_rvdhun.py`; name patterns changed over time (`GUNTERSVILLE`, `GUNTERSVILLE HW`, `Guntersville HW`; Pickwick appears as `PICKWICK DAM`, `PICKWICK HW`, ID `PKDT1`), so use plausibility ranges as a guard. |
| `cwmsLrdTva` | CWMS `LRD <Lake>.Elev.Inst.1Hour.0.Raw-TVA` | Kentucky 1998+, Pickwick 2019+, Normandy 2019+ | Needs QC (spike filter, 406 to 420 ft for Pickwick). |

`sourceId` convention: `nws:hads:GVDA1:HP`, `nws:rvdhun:GVDA1`, `cwms:LRD:Pickwick-Lake.Elev.Inst.1Hour.0.Raw-TVA`. Rows from different sources for the same date resolve by the precedence above.

**Effect on the rubric** (`score_lake`, not edited): `historyQuality` and `seasonalBaseline` are shares over *profiled* lakes. With the 5 pilots profiled the shares go from 1/5 to 5/5, i.e. 0.30 to 1.50 and 0.20 to 1.00 points, **+2.0 uncapped**. The published value is capped at 3.0 by the coverage gate (< 10 % of lakes profiled) and at 5.0 by `NOT_VALIDATED`, so the displayed score does not move until coverage reaches 63 lakes. Past that point every additionally profiled lake needs its own deep history to keep these two shares high; section 3 sizes that.

### 1.5 Remaining history gaps and what they cost

* Guntersville / Wheeler / Wilson 2021-10 to 2022-10 and Pickwick 2014-04 to 2019-09: no machine-readable source found (NWS `RVD*` products stop or lose the value; HADS has no `HP` before 2022-10-27). Cost: none for status (16 to 18 other complete years), small for percentile tails.
* Request to TVA for its own daily archive is recorded as an optional action (M-baselines-01); it would also remove the 0.1 ft years.

### 1.6 Beyond the pilots

* **All 16 TVA directory lakes** have the HADS `HP` stream from 2022-10-27 (probe on 2023-06-15 returned an `HPIRZZZ` column for Norris `NRST1`, Douglas `DUGT1`, Watts Bar `WBOT1`, Fort Loudoun `FLDT1`, Chickamauga `CKDT1`, Nickajack `NKJT1`, Kentucky `KYDK2`, Cherokee `CRKT1`, Tims Ford `TMFT1`, South Holston `SHDT1`, Fontana `FONN7`, Hiwassee `HIWN7`; the `...T1` "Dam" IDs such as `NRTT1` carry tailwater only). That is 3.9 years: `LIMITED` (3 complete years 2023-2025) now, `SUFFICIENT` under the current rule in 2028. Not downloaded here (outside the pilot mission); the probe is recorded in the ledger.
* Nickajack (`NKJT1 ... HW`) appears in `RVDHUN` 2005-2021; Kentucky Lake has 27 complete years in CWMS LRD (used below as a TVA storage-style test lake).

## 2. Baseline methodology review

### 2.1 Test series

Twelve series spanning regimes; all re-implemented with the Engine's rules (`doy365`, type-7 quantile grid, ±7 d, complete year >= 329 days, most recent 30 complete years).

| Series | Record | Complete yrs (>=329 d) | Range ft | p05-p95 ft | Median abs daily change ft |
|---|---|---|---|---|---|
| Hartwell (USACE SAS, storage/hydro) | 1961-2026 | 64 (1962-2025) | 27.9 | 13.4 | 0.08 |
| Kentucky Lake (TVA) | 1998-2026 | 27 (1999-2025) | 19.8 | 5.5 | 0.12 |
| Cave Run (USACE LRL flood control) | 2002-2026 | 24 (2002-2025) | 37.0 | 16.7 | 0.08 |
| Allatoona (USACE SAM) | 2007-2026 | 18 (2008-2025) | 34.2 | 16.0 | 0.13 |
| Pueblo Res. (USACE SPA, arid storage) | 1998-2026 | 26 (1999-2025) | 67.5 | 48.6 | 0.1 |
| Shasta (USBR via CWMS) | 2013-2026 | 12 (2014-2025) | 182.2 | 146.0 | 0.32 |
| Guntersville (TVA pilot, composite) | 2005-2026 | 17 (2007-2025) | 3.1 | 1.5 | 0.1 |
| Wheeler (TVA pilot, composite) | 2005-2026 | 18 (2006-2025) | 6.8 | 4.5 | 0.1 |
| Wilson (TVA pilot, composite) | 2005-2026 | 18 (2006-2025) | 3.4 | 2.3 | 0.2 |
| Pickwick (TVA pilot, composite) | 2003-2026 | 16 (2003-2025) | 10.0 | 5.4 | 0.2 |
| Lake Erie (NOAA, natural Great Lake) | 1962-2026 | 64 (1962-2025) | 6.6 | 3.5 | 0.058 |
| Lake Champlain (USGS, natural) | 1907-2026 | 88 (1938-2025) | 10.6 | 5.5 | 0.04 |

**Engine reproduction check.** Hartwell, Oct 12 2026, history to 2026-10-06 from the stored Lake Brain CSV (basis 1996-2025): the script returns p02/p10/p50/p90/p98 = 643.34 / 649.89 / 655.58 / 660.54 / 661.89, **identical to the five numbers recorded in `LAKE_BRAIN_INTEGRATION.md` §6**. (CWMS timestamps are 00:00Z; the Engine's day is the prior US/Central day, so raw CWMS dates must be shifted by -1 day.)

### 2.2 Minimum number of years

Leave-one-year-out design: hold out one complete year, build a reference baseline from all other complete years, build a candidate baseline from `k` random other years, classify every day of the held-out year (±3 d around 24 sample days) with both. 150 draws per `k`. "Agreement" is the share of days where candidate and reference give the same `historicalState`.

**Class agreement with the long-record baseline (%)**

| Series | Complete yrs | k=3 | k=5 | k=7 | k=10 | k=15 | k=20 |
|---|---|---|---|---|---|---|---|
| Hartwell | 64 | 55.5 | 66.8 | 77.0 | 79.3 | 85.7 | 87.2 |
| Kentucky Lake | 27 | 73.3 | 80.9 | 84.3 | 88.6 | 91.9 | 95.2 |
| Cave Run | 24 | 66.1 | 75.6 | 80.6 | 84.8 | 90.9 | 95.2 |
| Allatoona | 18 | 68.0 | 77.2 | 82.7 | 87.9 | 95.2 | - |
| Pueblo Res. | 26 | 58.0 | 70.7 | 78.5 | 82.7 | 90.2 | 93.8 |
| Shasta | 12 | 61.0 | 72.8 | 78.8 | - | - | - |
| Guntersville | 17 | 78.6 | 85.6 | 89.2 | 93.0 | - | - |
| Wheeler | 18 | 79.7 | 85.3 | 89.8 | 93.2 | 97.2 | - |
| Wilson | 18 | 82.5 | 88.2 | 90.8 | 94.3 | 97.6 | - |
| Pickwick | 16 | 76.5 | 83.9 | 88.5 | 93.0 | - | - |
| Lake Erie | 64 | 52.3 | 70.1 | 73.6 | 73.1 | 81.5 | 85.1 |
| Lake Champlain | 88 | 59.8 | 67.3 | 76.2 | 80.4 | 82.7 | 86.3 |

**Band-edge error (RMSE of candidate minus reference edge, % of the p10-p90 width; entries are p10 / p90)**

| Series | p10-p90 width ft | k=3 | k=5 | k=10 | k=15 | k=20 |
|---|---|---|---|---|---|---|
| Hartwell | 9.72 | 52/17 | 42/14 | 36/9 | 32/7 | 27/6 |
| Kentucky Lake | 1.56 | 20/64 | 20/57 | 12/31 | 8/22 | 5/13 |
| Cave Run | 5.15 | 15/108 | 12/114 | 8/57 | 6/31 | 3/17 |
| Allatoona | 5.4 | 28/46 | 22/34 | 14/17 | 7/8 | - |
| Pueblo Res. | 37.44 | 48/15 | 35/10 | 23/6 | 15/5 | 10/4 |
| Shasta | 106.71 | 34/17 | 22/8 | - | - | - |
| Guntersville | 0.83 | 20/20 | 14/15 | 8/8 | - | - |
| Wheeler | 1.09 | 22/24 | 17/18 | 11/10 | 5/5 | - |
| Wilson | 0.9 | 19/15 | 14/11 | 8/7 | 5/4 | - |
| Pickwick | 1.98 | 26/43 | 19/36 | 10/18 | - | - |
| Lake Erie | 2.5 | 34/32 | 26/23 | 18/16 | 15/12 | 13/10 |
| Lake Champlain | 3.11 | 24/38 | 19/33 | 13/23 | 11/20 | 9/17 |

**Share of held-out days the candidate calls `VERY_UNUSUAL` (%, nominal 4; the same measure with a 20-year baseline is 7 to 8 on the storage lakes)**

| Series | k=3 | k=5 | k=7 | k=10 | k=15 | k=20 |
|---|---|---|---|---|---|---|
| Hartwell | 42 | 29 | 18 | 13 | 9 | 8 |
| Kentucky Lake | 20 | 14 | 11 | 10 | 8 | 7 |
| Cave Run | 28 | 19 | 14 | 12 | 9 | 8 |
| Allatoona | 28 | 19 | 15 | 11 | 8 | - |
| Pueblo Res. | 44 | 28 | 20 | 14 | 11 | 8 |
| Shasta | 48 | 30 | 24 | - | - | - |
| Guntersville | 13 | 9 | 8 | 5 | - | - |
| Wheeler | 13 | 10 | 8 | 6 | 5 | - |
| Wilson | 10 | 7 | 6 | 5 | 4 | - |
| Pickwick | 17 | 13 | 10 | 8 | - | - |
| Lake Erie | 44 | 27 | 24 | 19 | 13 | 8 |
| Lake Champlain | 36 | 29 | 20 | 13 | 10 | 10 |

Reading:
* **At 5 years** agreement is 67 to 88 %. The TVA run-of-river pools are the best case (85 to 88 %), storage and natural lakes the worst (67 to 81 %). One day in three is classified differently on Hartwell, Pueblo and Champlain.
* **`VERY_UNUSUAL` is not meaningful below about 15 years.** With 5 years of ±7 d windows there are about 75 values, so p02/p98 are essentially the sample minimum and maximum; 7 to 30 % of ordinary days exceed them. At 15 years the rate is 4 to 13 %.
* **Smallest `k` with agreement >= 90 %:** Wilson 7, Guntersville 10, Wheeler 10, Pickwick 10, Kentucky 15, Cave Run 15, Allatoona 15, Pueblo 15; Hartwell, Erie and Champlain stay at 85 to 87 % even at 20 years (their level depends on multi-year regimes, not on the day of year).
* In feet at 5 years the p10 / p90 edge error is 0.12 / 0.12 ft (Guntersville), 0.19 / 0.20 (Wheeler), 0.12 / 0.10 (Wilson), 0.38 / 0.72 (Pickwick), 0.31 / 0.89 ft (Kentucky Lake), 4.0 / 1.4 ft (Hartwell). At 10 years these roughly halve.

**Recommendation (research).** `NONE` < 2, `INSUFFICIENT` 2 to 4, `LIMITED` 5 to 9 (show NORMAL/UNUSUAL as provisional, never `VERY_UNUSUAL`), `SUFFICIENT` >= 10 for NORMAL/UNUSUAL, and `VERY_UNUSUAL` only with >= 15 complete years. For storage and natural lakes expect to stay `LIMITED` for the p02/p98 band however long the record. The four TVA pilots (16 to 18 years) pass all of these.

### 2.3 Window length, recency and structural change

Rolling-origin test: for each of the last 10 complete years (6 for Shasta), build the baseline only from earlier years and score every 9th day of the year. Table cells are *pinball loss relative to the Engine's last-30-years window* (below 1.00 is better) / *coverage of the p10-p90 band in %* (nominal 80).

| Series | Held-out years | last 5y | last 10y | last 20y | last 30y (Engine) | all years | all, half-life 10y | all, half-life 5y |
|---|---|---|---|---|---|---|---|---|
| Hartwell | 2016-2025 | 1.02 / 76 | 1.02 / 86 | 1.13 / 89 | 1.00 / 92 | 0.95 / 89 | 1.02 / 92 | 1.03 / 90 |
| Kentucky Lake | 2016-2025 | 1.04 / 77 | 1.04 / 81 | 1.01 / 85 | 1.00 / 84 | 1.00 / 84 | 1.00 / 84 | 1.00 / 84 |
| Cave Run | 2016-2025 | 1.08 / 70 | 1.00 / 74 | 1.00 / 78 | 1.00 / 79 | 1.00 / 79 | 0.99 / 78 | 0.99 / 77 |
| Allatoona | 2016-2025 | 1.08 / 71 | 1.02 / 79 | 1.00 / 83 | 1.00 / 83 | 1.00 / 83 | 0.99 / 82 | 0.98 / 81 |
| Pueblo Res. | 2016-2025 | 0.62 / 63 | 0.52 / 78 | 0.95 / 75 | 1.00 / 77 | 1.00 / 77 | 0.75 / 81 | 0.61 / 82 |
| Shasta | 2020-2025 | 1.39 / 68 | 0.98 / 73 | 1.00 / 72 | 1.00 / 72 | 1.00 / 72 | 1.02 / 73 | 1.06 / 69 |
| Guntersville | 2014-2025 | 0.99 / 80 | 0.99 / 82 | 1.00 / 83 | 1.00 / 83 | 1.00 / 83 | 0.98 / 82 | 0.97 / 82 |
| Wheeler | 2014-2025 | 1.01 / 82 | 0.99 / 85 | 1.00 / 85 | 1.00 / 85 | 1.00 / 85 | 0.99 / 84 | 0.99 / 85 |
| Wilson | 2014-2025 | 1.02 / 79 | 1.01 / 81 | 1.00 / 81 | 1.00 / 81 | 1.00 / 81 | 1.00 / 82 | 0.99 / 82 |
| Pickwick | 2010-2025 | 1.01 / 76 | 0.99 / 81 | 1.00 / 82 | 1.00 / 82 | 1.00 / 82 | 0.99 / 81 | 0.99 / 81 |
| Lake Erie | 2016-2025 | 0.89 / 35 | 0.98 / 44 | 1.16 / 57 | 1.00 / 60 | 0.84 / 68 | 0.90 / 63 | 0.87 / 62 |
| Lake Champlain | 2016-2025 | 1.16 / 65 | 1.09 / 65 | 1.03 / 72 | 1.00 / 72 | 0.94 / 83 | 1.00 / 73 | 1.04 / 72 |

* For the TVA pools and Kentucky Lake **window length hardly matters**: 10, 20, 30 years and all years are within 1 % pinball loss and 80 to 86 % coverage. A 5-year window under-covers (76 to 82 %) and costs about 0 to 4 % pinball loss.
* **Storage lakes with operating change need recency.** Pueblo's median p50 moved 25.7 ft between 1999-2009 and 2016-2025 (62 % of the band width); a 10-year window cuts the loss by 48 % and half-life weighting (5 y) by 39 % while restoring 80 % coverage (77 % with 30 y). Shasta (12 years) shows no benefit from any window.
* **Natural lakes need the opposite.** Erie and Champlain have multi-year regimes; the 30-year window covers only 60 % and 72 % of days for an 80 % band, and using *all* years is better (Erie pinball -16 %, coverage 68 %; Champlain -6 %, 83 %). Capping at 30 years throws away the information that makes "unusual" meaningful.
* Hartwell: all years -5 %, 30 years 92 % coverage; no case for a shorter window.
* Structural change (first versus last decade, median of 40 doy points):

| Series | first decade | last decade | median p50 shift ft | max abs shift ft | median abs shift as % of band width |
|---|---|---|---|---|---|
| Hartwell | 1962-1971 | 2016-2025 | -0.21 | 1.83 | 8.8 |
| Kentucky Lake | 1999-2008 | 2016-2025 | -0.04 | 0.51 | 9.3 |
| Cave Run | 2002-2011 | 2016-2025 | 0.19 | 12.69 | 4.3 |
| Pueblo Res. | 1999-2009 | 2016-2025 | 25.68 | 31.91 | 61.8 |
| Lake Erie | 1962-1971 | 2016-2025 | 1.81 | 2.17 | 78.6 |
| Lake Champlain | 1938-1947 | 2016-2025 | 0.55 | 1.48 | 25.3 |

**Recommendation.** Keep 30 years for managed pools; use all available years (cap ~60) when the lake has no operator (natural-surface); for storage reservoirs flag a change point (abs p50 shift > 25 % of band width between decades) and fall back to a half-life weighted quantile (half-life 5 to 10 years). The TVA pilots show no such shift in the composite years (extreme-year effects below).

### 2.4 ±7 days versus ±3, ±10, ±14

Pinball loss relative to ±7 d / coverage of p10-p90:

| Series | +-3 d | +-7 d (Engine) | +-10 d | +-14 d |
|---|---|---|---|---|
| Hartwell | 1.000 / 93 | 1.000 / 92 | 1.000 / 92 | 0.999 / 93 |
| Kentucky Lake | 1.011 / 82 | 1.000 / 84 | 0.998 / 85 | 1.003 / 86 |
| Cave Run | 1.010 / 78 | 1.000 / 79 | 0.995 / 80 | 0.991 / 80 |
| Allatoona | 1.018 / 79 | 1.000 / 83 | 0.992 / 84 | 0.985 / 86 |
| Pueblo Res. | 0.999 / 76 | 1.000 / 77 | 0.999 / 77 | 1.000 / 78 |
| Shasta | 1.006 / 72 | 1.000 / 72 | 0.996 / 72 | 0.992 / 71 |
| Guntersville | 1.018 / 79 | 1.000 / 83 | 0.998 / 82 | 0.993 / 84 |
| Wheeler | 1.013 / 82 | 1.000 / 85 | 0.996 / 86 | 0.999 / 86 |
| Wilson | 1.010 / 78 | 1.000 / 81 | 0.991 / 82 | 0.996 / 82 |
| Pickwick | 1.028 / 81 | 1.000 / 82 | 0.995 / 84 | 0.996 / 84 |
| Lake Erie | 1.001 / 60 | 1.000 / 60 | 0.999 / 60 | 0.997 / 60 |
| Lake Champlain | 1.003 / 72 | 1.000 / 72 | 0.999 / 73 | 0.998 / 73 |

±3 d is slightly worse everywhere (+1 to +3 % loss, 1 to 4 points less coverage) because 3 days x 20 years is too few samples; ±10 and ±14 are 0 to 1.5 % better with +1 to 3 points coverage. All differences are small relative to the min-years effect. **Keep ±7**; ±10 is acceptable if the method is revised for another reason.

### 2.5 Percentile bands and extreme years

Share of held-out days outside each band (rolling origin, all prior years up to 30) and the effect of removing the two most extreme basis years (by annual mean):

| Series | outside p10-p90 % (nominal 20) | outside p05-p95 % (10) | outside p02-p98 % (4) | p10-p90 width ft | 2 most extreme basis years | dropping them: median p10 shift ft | p90 shift ft |
|---|---|---|---|---|---|---|---|
| Hartwell | 7.6 | 3.7 | 1.5 | 9.71 | [2008, 2002] | 1.48 | 0.059 |
| Kentucky Lake | 16.0 | 7.9 | 4.2 | 1.56 | [2011, 2008] | -0.008 | -0.04 |
| Cave Run | 21.2 | 11.7 | 7.3 | 4.93 | [2025, 2011] | -0.013 | -0.096 |
| Allatoona | 17.4 | 9.8 | 5.4 | 5.78 | [2009, 2008] | 0.009 | -0.066 |
| Pueblo Res. | 22.9 | 9.6 | 5.9 | 37.03 | [2003, 2004] | 3.034 | 0.133 |
| Shasta | 27.6 | 22.8 | 20.7 | 114.23 | [2022, 2014] | 21.162 | 0.464 |
| Guntersville | 17.2 | 10.2 | 5.0 | 0.8 | [2015, 2014] | 0.0 | -0.004 |
| Wheeler | 15.2 | 9.5 | 4.5 | 1.08 | [2007, 2009] | 0.0 | 0.0 |
| Wilson | 19.0 | 11.7 | 5.7 | 0.9 | [2008, 2017] | 0.0 | 0.0 |
| Pickwick | 17.8 | 8.6 | 4.6 | 1.96 | [2003, 2007] | 0.079 | 0.044 |
| Lake Erie | 39.5 | 31.5 | 16.8 | 2.52 | [2020, 2019] | -0.022 | -0.295 |
| Lake Champlain | 27.8 | 15.0 | 5.7 | 3.17 | [2011, 2006] | -0.012 | -0.176 |

* On managed lakes the p10-p90 band is close to calibrated (15 to 21 % outside against a nominal 20 %; p02-p98 outside 4.2 to 7.3 % against 4 %). Hartwell is over-covered (7.6 %): the last decade was calmer than the 30-year window.
* Natural lakes and Shasta are not calibrated (Erie 40 % outside p10-p90): they follow multi-year regimes, which is a property of the lake, not a defect. `UNUSUAL` for these lakes will persist for months to years.
* **Extreme years.** Removing the two most extreme years moves the TVA edges by 0.00 to 0.08 ft (immaterial). It moves Hartwell's p10 by 1.5 ft (15 % of the band) and Pueblo's by 3.0 ft because the 2002 and 2008 droughts define the low tail. That is how a percentile band should behave; **do not trim droughts or floods from the basis**, but note that for storage lakes `UNUSUAL`-low thresholds depend on whether a drought is inside the 30-year window.
* p05-p95 would flag about half as many days as p10-p90 (4 to 12 % versus 8 to 21 % on the managed lakes). For a user-facing "is this normal" statement p10-p90 flags one day in five by design; if that is too chatty, p05-p95 is the knob, but it is a product decision, not a statistical one.

### 2.6 Guide-relative versus history-relative

Leave-one-year-out historical percentile compared with the operator guide: Hartwell (CWMS `Elev-GC` daily), Allatoona (CWMS guide curve 2017-), TVA pilots (operating-guide `GuideCurve` and `BtmOpZone`/`TopOpZone` applied to 2003-2025).

| Lake | Years | Spearman pct vs guide anomaly | RMSE vs guide ft | RMSE vs hist p50 ft | median abs(guide-p50) ft | zone vs hist agree % | Spearman pct vs zone position | above zone & hist-high % | below zone & hist-low % |
|---|---|---|---|---|---|---|---|---|---|
| Allatoona | 2017-2025 | 0.53 | 3.24 | 2.86 | 0.96 | - | - | - | - |
| Guntersville | 2007-2025 | 0.645 | 0.57 | 0.37 | 0.2 | 73.8 | 0.892 | 37.4 | 100.0 |
| Hartwell | 1999-2025 | 0.926 | 5.14 | 4.56 | 0.54 | - | - | - | - |
| Pickwick | 2003-2025 | 0.723 | 1.49 | 1.18 | 0.21 | 69.9 | 0.78 | 32.3 | 97.0 |
| Wheeler | 2006-2025 | 0.604 | 1.11 | 0.73 | 0.18 | 71.8 | 0.754 | 31.3 | 97.7 |
| Wilson | 2006-2025 | - | - | - | - | 82.2 | 0.97 | 74.9 | 95.7 |

* The two views **agree in rank** (Spearman 0.53 to 0.93 against the guide anomaly; 0.75 to 0.97 against position inside the TVA zone) but they are **not interchangeable**.
* The guide is a ceiling/target, not a typical level: the daily guide curve predicts the actual level *worse* than the historical median (RMSE 0.57 vs 0.37 ft Guntersville, 1.11 vs 0.73 Wheeler, 1.49 vs 1.18 Pickwick, 5.1 vs 4.6 Hartwell, 3.2 vs 2.9 Allatoona). Hartwell's median day sits 1.7 ft below its guide (top of conservation).
* "Above the TVA zone" is historically high only 31 to 37 % of the time on Guntersville, Wheeler and Pickwick (summer pools normally run above the zone top), whereas "below the zone" is historically low 96 to 100 % of the time. So an out-of-zone flag overstates unusual-high conditions; the zone is an operating target, history says what is normal.
* **Conclusion:** the hypothesis that anomaly-vs-guide is more informative than vs history is **not supported** for these lakes. Keep both as separate fields (as the Engine does). The guide's value is that it exists on day one: its median distance to the long-run p50 is 0.18 to 0.21 ft for the TVA mainstem pools (11 to 24 % of the band width, similar to or about twice the p50 error of a 5-year baseline at 9 to 13 %) and 0.5 ft (6 %) and 1.0 ft (18 %) for Hartwell and Allatoona. So for a lake with < 5 years of history a guide-relative statement is no worse than a short-history percentile and is available on day one; offer it instead of `INSUFFICIENT_HISTORY`.

### 2.7 Resolution, time of day and band edges

| TVA lake | days | mean abs diff 00:00 vs 07:00 ft | p95 ft | baseline p10/p50/p90 median shift ft | max shift ft |
|---|---|---|---|---|---|
| Guntersville | 1439 | 0.082 | 0.2 | [0.036, 0.04, 0.029] | 0.14 |
| Wheeler | 1439 | 0.097 | 0.27 | [0.045, 0.047, 0.034] | 0.2 |
| Wilson | 1439 | 0.165 | 0.42 | [0.082, 0.1, 0.088] | 0.36 |
| Pickwick | 1439 | 0.126 | 0.391 | [0.104, 0.045, 0.05] | 0.34 |

The p10-p90 width of the narrow TVA pools is 0.8 to 2.0 ft. A reading within 0.1 ft of an edge can flip class with the choice of 00:00 or 07:00 or with the 0.1 ft rounding of the old years (today's Guntersville is 0.1 ft below its p10). Suggestion: publish the signed distance to the nearest edge in feet and a flag `nearBandEdge` when it is < 0.1 ft, or apply a 0.1 ft dead band before changing `historicalState` between runs.

### 2.8 The STABLE rule

Hourly series at instrument resolution (24 h change at 00:00 local, same convention as the Engine): TVA HADS (3 pilots, 2022-11 to 2026-10), Pickwick and Kentucky CWMS, Cave Run, Allatoona, Pueblo; Erie and Champlain use daily means (marked *).

| Series (hourly) | Days | median abs d24 ft | p90 ft | sensor-noise sigma of a 24 h diff ft | % days STABLE (current rule) | % days seasonal p50 > 0.10 floor | % of STABLE days inside a 3-day move >= 0.5 ft |
|---|---|---|---|---|---|---|---|
| Pickwick (TVA, CWMS hourly) | 2330 | 0.15 | 0.61 | 0.0342 | 51.8 | 82.9 | 17.2 |
| Kentucky Lake (TVA, hourly) | 5169 | 0.12 | 0.44 | 0.0171 | 53.3 | 53.8 | 11.8 |
| Cave Run (USACE LRL, hourly) | 6125 | 0.1 | 0.707 | 0.0 | 58.0 | 54.7 | 12.6 |
| Allatoona (USACE SAM, hourly) | 6096 | 0.13 | 0.58 | 0.0086 | 53.1 | 66.7 | 17.0 |
| Pueblo (15-min) | 6081 | 0.088 | 0.225 | 0.0043 | 58.1 | 54.7 | 1.0 |
| Guntersville (TVA, HADS hourly) | 1432 | 0.1 | 0.28 | 0.0171 | 54.8 | 54.9 | 6.1 |
| Wheeler (TVA, HADS hourly) | 1432 | 0.1 | 0.38 | 0.0171 | 57.7 | 43.3 | 8.5 |
| Wilson (TVA, HADS hourly) | 1432 | 0.17 | 0.559 | 0.0342 | 51.5 | 88.4 | 18.4 |

* By construction `abs(Δ) <= p50` is true for half the days, so the rule marks 51 to 58 % of days STABLE on every managed lake whatever the lake does. The seasonal p50 exceeds the 0.10 ft floor on 43 to 88 % of days (always for Wilson in 11 months), so the floor is rarely the binding term.
* On every lake except Pueblo (1 %), 6 to 18 % of days labelled STABLE sit inside a 3-day move of 0.5 ft or more (fall drawdown, spring fill). The rule cannot say "rising" during a fill that proceeds at the lake's typical pace, which is exactly the situation bowfishers ask about.
* **Noise is not the reason for a 0.10 ft floor.** The sensor-noise sigma of a 24 h difference is 0.004 to 0.034 ft (from the second difference of the hourly series), 3 to 23 times smaller than 0.10. TVA's own diurnal hunting (hydropeaking) is far larger than noise: the daily label flips on 38 to 48 % of days on the TVA pools under the current rule.
* Alternatives (share STABLE % / day-to-day label flip %):

| Series | R0 current | 0.05 ft | 0.10 ft | 0.15 ft | 0.25 ft | 72 h mean rate <= 0.10 | RAPID % (p95 / with 0.25 floor) |
|---|---|---|---|---|---|---|---|
| Pickwick (TVA, CWMS hourly) | 52 / 40 | 18 / 27 | 37 / 37 | 51 / 35 | 69 / 28 | 54 / 26 | 5.4 / 5.4 |
| Kentucky Lake (TVA, hourly) | 53 / 38 | 23 / 30 | 44 / 37 | 59 / 33 | 77 / 22 | 56 / 26 | 5.2 / 5.2 |
| Cave Run (USACE LRL, hourly) | 58 / 19 | 37 / 17 | 50 / 17 | 60 / 16 | 69 / 14 | 52 / 13 | 5.0 / 5.0 |
| Allatoona (USACE SAM, hourly) | 53 / 28 | 21 / 21 | 39 / 25 | 56 / 23 | 74 / 16 | 44 / 22 | 5.0 / 5.0 |
| Pueblo (15-min) | 58 / 16 | 29 / 18 | 55 / 17 | 73 / 13 | 93 / 5 | 57 / 9 | 5.0 / 3.5 |
| Guntersville (TVA, HADS hourly) | 55 / 48 | 28 / 38 | 49 / 47 | 71 / 37 | 88 / 18 | 72 / 25 | 5.0 / 4.5 |
| Wheeler (TVA, HADS hourly) | 58 / 41 | 29 / 34 | 50 / 38 | 66 / 32 | 81 / 19 | 68 / 23 | 4.6 / 3.7 |
| Wilson (TVA, HADS hourly) | 52 / 45 | 18 / 27 | 34 / 38 | 47 / 40 | 65 / 37 | 56 / 36 | 5.2 / 5.2 |
| Lake Erie (NOAA, natural Great Lake)* | 72 / 30 | 47 / 39 | 71 / 29 | 83 / 21 | 94 / 9 | 92 / 11 | 5.4 / 3.1 |
| Lake Champlain (USGS, natural)* | 89 / 11 | 65 / 27 | 89 / 11 | 95 / 5 | 98 / 2 | 92 / 5 | 4.8 / 1.5 |

* An absolute floor removes the tautology and ranks lakes sensibly (Pickwick/Wilson are more active than Pueblo/Cave Run). **0.10 ft** gives 34 to 55 % STABLE on reservoirs; **0.25 ft** calls 65 to 93 % stable, which hides 0.15 to 0.25 ft/day fills; **0.05 ft** would call only 18 to 37 % stable and is inside the TVA diurnal swing.
* **Natural and large lakes need a lower floor.** On Erie and Champlain (median abs(Δ1d) 0.056 and 0.040 ft) a 0.10 ft floor makes 71 % and 89 % of days STABLE; 0.05 ft gives 47 % and 65 %. Lake size does not set the floor (Wilson, the smallest TVA pool, moves most); what matters is regime: Pickwick and Wilson (0.15 to 0.17 ft/day median), Guntersville, Wheeler, Kentucky, Allatoona, Cave Run and Pueblo (0.09 to 0.13), natural lakes (0.04 to 0.06).
* A 72 h mean-rate label (`abs(Δ72h)/3 <= 0.10 ft/day`) cuts the day-to-day flicker on four of the five TVA pools (flip 23 to 26 % versus 38 to 48 %; Wilson 36 vs 45) and still reports single-day moves through `change.h24`. It cannot be scored with the same "false-stable" metric because it is definitionally consistent with a 3-day move, so it is a presentation choice.
* RAPID (abs(Δ24h) > seasonal p95) fires on about 5 % of days by construction; on quiet natural lakes p95 is 0.13 to 0.22 ft, so add a minimum (0.25 ft) to avoid calling a 0.15 ft day "rapid".

**Recommended parameters (for the next `lake-level-rules` version, to be reviewed):**
`STABLE` if `abs(Δ24h) <= floor`, with `floor = 0.10 ft` for reservoirs and `0.05 ft` for lakes with no operator; drop the seasonal-p50 term; `RISING/FALLING` otherwise; `RAPID` if `abs(Δ24h) > max(seasonal p95, 0.25 ft)`; use the 72 h mean rate for the label shown to users when the hourly series has diurnal hunting (TVA, other hydropower pools), and keep p50/p95 only as context (`rateOfChangePercentile`). Build rate climatology only from >= 0.01 ft data. These are thresholds the data support; whether 0.10 ft is the right *visible* change for a bowfisher (about 1 inch per day) is a product decision (M-baselines-03).

## 3. Operator guide and flood-level availability

### 3.1 USACE CWMS `levels` API

`https://cwms-data.usace.army.mil/cwms-data/levels?office=<O>&level-id-mask=*.Elev*.*` works without a key. Levels come in metres, as constants or as seasonal (annual) curves (`seasonal-values`, `interval-origin`, `interval-months`). Names seen across offices: Top of Conservation (417 level records), Top of Flood (391), Bottom of Flood Control (147), Bottom of Flood (162), Top of Normal / Bottom of Normal, Guide Curve (20), Seasonal Rule Curve (10), Drought Level 1-3 (Hartwell, Russell, Thurmond), Top Con (SPK, USBR projects), Elev-Zone (SAJ: Kissimmee chain, Okeechobee).

Spatial match of each directory lake to a CWMS location (within 5 km of the lake polygon, or up to 25 km with a name match; `guide_availability.py`):

| | Lakes |
|---|---|
| Directory | 621 |
| Matched to a CWMS location with any Elev level | **143** (23 %) (140 within 5 km) |
| with a flood-pool bottom or top-of-conservation level | **132** (21 %) |
| with a seasonal (annual-curve) guide | **58** (9 %) |
| with a drought or bottom-of-conservation level | 89 |
| of the matched, with an Elev time series in the CWMS catalog | 102; span >= 5 y 93, >= 10 y 90, >= 20 y 52, >= 30 y 24 |

By office (the 20 largest are in `guide_availability.csv`): SAM 15 of 16 lakes matched (11 flood-bottom, 12 guide curves), LRL 14 of 14 (all flood-bottom, no seasonal guide), LRH 11 of 12, LRP 8 of 11, SWL 9 of 10, SWT 9 of 16, MVS 5 of 5, LRN 7 of 7, SPK 6 of 6, SAS 4 of 6. **29 directory lakes sit in districts with no data on the public CWMS host** (NWK 13, LRE 6, NWO 3, NWW 2, NWS 2, NWP 2, LRC 1). Catalog extents are coarse (earliest to latest time, not completeness; some include placeholder dates) and the spatial match can pick a neighbouring cascade project (Lake Russell matched to the Hartwell location; two Thurmond directory rows are the same lake), so every count here is an upper bound. The 23 lakes with no `cwmsOffice` that match a CWMS location are a free upgrade (e.g. Lake Mead via SPL Hoover, Travis via SWF, Kentucky Lake via LRN).

**What this gives the rubric:** `floodDroughtContext` needs a flood-pool bottom per profiled lake: 132 candidates (21 %), with the caveat that the spatial match is unreviewed and counts only after the binding review. `operatorPlan` (guide curve or zone): 58 seasonal guides in CWMS plus the TVA API below. The binding thread's `cwms_guides.json` (timeseries names rather than levels) overlaps and extends this (SAJ Elev-Zone, NAB Elev-Float, SPK Elev-Top Con).

### 3.2 Non-USACE operators

| Operator family (directory lakes) | Machine-readable guide | Notes |
|---|---|---|
| TVA (16) | `RestApi/operating-guide/{loc}`: `GuideCurve` for 15 of 16 lakes, `Top/BtmOpZone` for 9, `TopOfGates` for all; 43 TVA locations scanned, all return 365 rows | Wilson has a zone but no guide curve. `TopOfGates` is not a flood pool. Two calendar years only. Rule-curve changes since the 2004 Reservoir Operations Study (e.g. Wheeler winter minimum raised 0.5 ft) mean the *current* guide may not describe 2005-2019 operations. |
| USBR (70 by name) | RISE has elevation/storage series; flood-control top of conservation exists as CWMS SPK `Elev-Top Con` for many USBR projects (10 matched here). No RISE rule-curve parameter found. | RISE catalog filters were ignored in testing; see ledger. |
| Alabama Power (8) | Guide is published as charts/app content; 7 of 8 lakes match a CWMS location (6 with a flood level, 6 with a guide curve, via SAM). | Numeric feed not found. |
| Duke Energy (8) | Levels as feet relative to full pond (100 ft local datum) on web/phone/app; targets in relicensing documents. No API. | LEAD |
| States, water districts, local (89) | No uniform feed; SJRWMD/SFWMD regulation schedules appear in CWMS SAJ as `Elev-Zone`. | per-operator work |
| Natural / no operator (113) | none | history-only baselines; no flood-pool state (`UNKNOWN`) |

## 4. Bowfishing level facts, Sector status and gaps

### 4.1 Minimal level facts that matter

| Fact | Why it matters to a bowfisher | Computable from | Sector today (`LAKE_BRAIN_INTEGRATION.md` §7) |
|---|---|---|---|
| Level vs this date's normal (percentile, band) | shallow flats and backwaters are reachable when the pool is at or above normal; exposed flats when well below | history baseline | yes (`historicalState`, `seasonalPercentile`, `seasonalBand`), withheld until `SUFFICIENT` |
| Level vs operator guide / zone | operator intent: drawdown below summer pool, held at pool, above guide | guide curve or zone | yes (`levelState`, `differenceFromGuideFt`), only where a guide is bound |
| Drawdown below full pool (ft) | how much shoreline is dry; boat-ramp and flat access | directory `fullPoolFt` with `poolBasis=fullPool` | yes (`differenceFromNormalPoolFt`) |
| Direction and speed (24 h, 72 h, 7 d) | rising water floods vegetation and moves fish; falling water drains backwaters and concentrates fish | hourly or daily series | yes (`change`, `trendState`), STABLE rule needs the fix in 2.8 |
| Seasonal phase (refill, summer hold, fall drawdown, winter pool) | tells whether a rising or falling trend is the normal season move or an anomaly | slope of guide curve or of seasonal median | **missing**; trivial to add from the guide or the baseline p50 slope |
| Flood-pool inundation: in flood pool? how deep (ft above flood-pool bottom) | flooded vegetation and flooded fields = spawning and feeding habitat for carp, buffalo and gar | operator flood-pool bottom (CWMS Bottom of Flood / Top of Conservation) | state yes (`floodPoolState`), **depth missing**; 132 lakes could support it |
| Change over 14 and 30 days | magnitude of the spring rise, how long water has stood on vegetation | daily history | **missing**; cheap |
| Days since the pool last crossed summer pool / since last exceedance | vegetation that has been flooded for weeks versus days | daily history | **missing** |

Not computable from level alone: area of exposed shoreline or flooded vegetation (needs lake hypsometry or satellite water extent, handled by the context thread).

### 4.2 Literature (opened or metadata-verified; use as citations for the Biological and Intelligence Brains)

| Ref | What it supports | Verification |
|---|---|---|
| Zohary T., Ostrovsky I. (2011) Ecological impacts of excessive water level fluctuations in stratified freshwater lakes. *Inland Waters* 1:47-59. doi:10.5268/IW-1.1.406 | Peer-reviewed review of ecological impacts of excessive level fluctuation (title and bibliographic record only; abstract not retrieved) | Crossref record opened; full text blocked (HTTP 403) |
| Wantzen K.M. et al. (2008) Ecological effects of water-level fluctuations in lakes: an urgent issue. *Hydrobiologia* 613:1-4. doi:10.1007/s10750-008-9466-1 | Editorial introduction to a special issue: level fluctuation affects ecological processes and patterns in lakes and has received less attention than in rivers (abstract as summarised from the AWI repository record) | Crossref record and publisher abstract via search; AWI full text blocked |
| Howard R.J., Wells C.J. (2009) Plant community establishment following drawdown of a reservoir in southern Arkansas. *Wetlands Ecology and Management* 17:565-583. doi:10.1007/s11273-009-9134-x | A 0.3 m drawdown let vegetation colonise exposed soil, including waterfowl foods; seed banks survive years of flooding | USGS publication page opened |
| Vaisvil et al. (2022) Water-level fluctuations and water temperature effects on young-of-year Largemouth Bass in a southwest irrigation reservoir. *J. Fish and Wildlife Management* 13. doi:10.3996/jfwm-21-071 | Success of littoral spawners depends on timing and variability of water levels (abstract) | Crossref abstract opened; full text blocked |
| Nisbet M., Myers R. (Texas Parks and Wildlife Dept., prepared 2022-07-31) Falcon Reservoir 2021 fisheries management survey report, Federal Aid project F-221-M-4 | Low spawning-habitat availability in 2020-21 gave < 35 % probability of strong alligator gar year-class formation; flooded terrestrial vegetation was only 8 % in 2019 because of persistent low water; when water recedes, dense terrestrial vegetation establishes on the exposed bottom and is the main structural habitat once re-inundated | PDF opened and text extracted |
| Stoll S. et al. (2013) Complex interactions between pre-spawning water level increase, trophic state and spawning stock biomass determine year-class strength in a shallow-water-spawning fish. *J. Applied Ichthyology*. doi:10.1111/jai.12144 | Peer-reviewed study of pre-spawning water-level increase and year-class strength of a shallow-water spawner (title only; abstract not retrieved) | Crossref record opened; no abstract available |
| TVA (2004) staff recommendation on the preferred reservoir operating alternative (web-harvest copy) | Summer operating ranges held through Labor Day on Guntersville, Wheeler and Pickwick (and Chickamauga); the spring-fill-for-spawning rule is quoted by secondary sources only | page opened; spring-fill statement not on that page |

Evidence not found: peer-reviewed work specific to common carp, buffalo or gar and reservoir pool elevation (only the alligator gar agency report). Treat species-specific claims as agency-level evidence.

## 5. Blockers, actions and limits

* **B-baselines-001** history gaps (WORKED_AROUND); **B-baselines-002** USGS Water Data API key and rate limit (needs a free key, M-baselines-02); **B-baselines-003** districts missing from the public CWMS host; **B-baselines-004** no machine-readable guide for utilities; **B-baselines-005** no ground truth for what level change is visible to a bowfisher (M-baselines-03). Actions: M-baselines-01 (ask TVA for its daily archive), -02, -03.
* The methodology numbers rest on 12 series, 6 to 64 complete years; the held-out-year reference is itself an estimate, so "agreement" is stability evidence, not accuracy against truth. Rolling-origin windows are 6 to 10 held-out years and are noisy for Shasta.
* The CWMS guide counts are an automatic spatial match and are an upper bound; the 29 lakes outside the public host may still have data on district sites.
* No Lake Brain code, rubric or production artifact was changed.
