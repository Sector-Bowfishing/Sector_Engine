# Lake Brain: disposition of the 14 history/live mismatch lakes

Status: research and tooling only. Nothing here is REVIEWED, nothing here changes a binding that ships, a lifecycle, a rubric or a cloud resource.
Run date 2026-10-13. Branch `feat/lake-fleet-bindings`. Every number below was produced by the scripts named at the end and can be reproduced offline.

## 1. Result

| Disposition | Lakes | Count |
|---|---|---|
| **FIXED** (every pre-registered criterion passes; becomes a MACHINE_VERIFIED *candidate* needing human review) | Blue Mesa, Buffalo Bill (series correction), Glendo, Jordanelle, Koocanusa, Navajo, Pineview, Shelbyville | **8** |
| **NEEDS HUMAN REVIEW** (one documented gap each) | Canyon Lake TX, Detroit, Jackson Lake WY, Rend, Taneycomo | **5** |
| **NO DEFENSIBLE MATCH** | Bartlett | **1** |
| CORRECTLY HELD | none | 0 |

The headline finding is that the hold was mostly **not a datum problem**. The "more than 15 ft" flag came from the rules-v2 hold-out QA (`holdout_v2.py`, `seriesQa.mismatchOver15ft`), and that QA has two defects:

1. **Its statistic cannot tell a drawdown from a datum error.** It compares the median of the history since 2025-01-01 with the median of the live series' last 30 days. For a reservoir that is drawn down in autumn the two differ by tens of feet inside one and the same series. Computed on the *live series alone* (no history involved) the same statistic gives: Blue Mesa -54.3 ft, Pineview -57.2, Jackson -26.8, Detroit -21.9, Navajo -21.2, Glendo -19.7, Jordanelle -19.2, Canyon +20.0, Bartlett +19.9, Koocanusa +17.4 (all more than 15 ft). Ten of the 14 flags reproduce on the live series by itself.
2. **Its series selection loaded the wrong water body.** `holdout_data.load_lake_series` takes, among the candidate files, the one with the most complete years. For four lakes that was not the series the bindings generator emits: Shelbyville and Rend were scored against their **tailwater** daily series (61.5 ft and 30.9 ft away), Taneycomo against **Table Rock Dam headwater**, a different lake (213.7 ft away), and Bartlett against a plan composite. So the rules-v2 hold-out results for those lakes were computed on series no generated binding would use (a note for the validation owner; not changed here).

What the generator would actually emit (`build_record`) was tested instead, against the live series, date by date.

## 2. Method and the criteria (fixed before any result)

The acceptance criteria were committed **before any date-matched comparison was computed**: `jobs/lake-brain/bindings/mismatch14_criteria.py`, commits `5934c8b0` (criteria) and `cb7123ae` (the short-feed rule S1 made explicit; still before any result). The only numbers known at that time were the hold-out QA medians above. The values are frozen by a unit test.

A lake is FIXED only if the history source the generator would emit (or one corrected series chosen by semantic identity, never by fit) passes **all** of:

| Gate | Rule (value) |
|---|---|
| O1 | at least 365 matched calendar days (UTC day key, the research convention) inside the 1095 days that end at the history's last day |
| O2 | median abs(live - history) <= 0.5 ft |
| O3 | p95 abs(live - history) <= 2.0 ft |
| O4 | history has a value within 45 days of the run date |
| P1 | directory `fullPoolFt` within 1.0 ft of an operator-published pool elevation (source cited) |
| P2 | every live value of the window lies inside the operator's documented minimum / maximum pool (+/- 1.0 ft); an undocumented bound fails |
| D1 | datum relation identical by construction (same provider, location, parameter) or documented by the operator / USGS; **never a fitted offset** |
| S1 | a live feed that serves only a short window (NWPS ~30 days, Access2Water latest value) must be tied to a record-holding read of the same series by >= 20 matched days, median <= 0.1 ft, max <= 0.5 ft |

Nothing was relaxed after a failure. Where a criterion failed the lake is not FIXED even if a looser rule would have passed it (Detroit, Rend, below). `datumOffsetFt` is 0.0 for all 14 lakes: no offset is applied anywhere.

Both series are read from the provider APIs (read-only, one request at a time, descriptive User-Agent, IEM/HADS 15 s apart) and reduced to one value per UTC day. Raw bodies are cached outside Git (`Sector_Research_Data/lake-brain/mismatch14/cache`), so `mismatch14_probe.py --offline` reproduces every figure.

## 3. Per-lake table

"Live" is what the generated binding reads; "History" what its baseline would be built from. All 14 live series are **elevations of the pool at the dam/forebay in feet, not gauge stage**, except where noted. Overlap = classification test (live vs generator history, 1095-day window).

| Lake | Live: provider / series / datum | History (generator) | Operator reference (P1) | Overlap days / median / p95 / max (ft) | Disposition |
|---|---|---|---|---|---|
| Bartlett AZ | NWPS BRTA3 `HPIRG` (pool elevation, ft; NWPS lists no datum) | IEM HADS BRTA3 PE `HP`, daily median | USBR Bartlett Dam: active conservation top 1798, dead storage top 1610, crest 1821 (dir 1798, diff 0.0) | 1095 / 0.0 / 0.0 / 0.0 (same feed) | NO DEFENSIBLE MATCH (P2) |
| Blue Mesa CO | RISE item 78, ft | RISE 78 | USBR Blue Mesa Dam: joint-use / active top 7519.4, dead 7358.0, crest 7528.0 (diff 0.0) | 1095 / 0.0 / 0.0 / 0.0 | **FIXED** |
| Buffalo Bill WY | **RISE 152 (replaced by RISE 146)**, ft | RISE 146 | USBR Buffalo Bill Dam: active top 5393.5, dead 5158.0, crest 5395.0 (diff 0.0) | 1095 / 0.0 / 0.0 / 0.0 (live 146 = history 146) | **FIXED (series correction)** |
| Canyon TX | A2W SWF:SMCT2 `SMCT2.Elev.Inst.1Hour.0.Decodes-Rev` (ft; native NGVD-29, CDA estimate to NAVD88 +0.3447) | CWMS SWF `SMCT2.Elev.Inst.~1Day.0.Decodes-Rev` | A2W levels: top of conservation 909, bottom of inactive 762, top of dam 974 (diff 0.0) | 1095 / 0.007 / 0.021 / 5.7 | NEEDS HUMAN REVIEW (S1) |
| Detroit OR | A2W NWP:DET `DET.Elev-Forebay.Inst.0.0.MIXED-REV` (ft, NGVD29) | USGS 14180500 param 62614 (above NGVD 1929), daily stat 32400 | A2W: top of conservation 1563.5, bottom of power 1425, top of dam 1579 (diff 0.0) | 1094 / 0.465 / **3.095** / 14.69 | NEEDS HUMAN REVIEW (O3, S1) |
| Glendo WY | RISE item 374, ft | RISE 374 | USBR Glendo Dam: active top 4635.0, dead 4545.0, crest 4675.0 (diff 0.0) | 1095 / 0.0 / 0.0 / 0.005 | **FIXED** |
| Jackson Lake WY | A2W NWW:JCK `JCK.Elev-Forebay.Inst.~1Day.0.USBR-COMPUTED-REV` (ft) | CWMS NWDP, same tsid, back to 1909 | A2W: top of normal 6768, streambed 6728, top of dam 6780 (dir 6769, diff 1.0) | 1091 / 0.0 / 0.0 / 0.0 | NEEDS HUMAN REVIEW (S1) |
| Jordanelle UT | RISE item 471, ft | RISE 471 | USBR Jordanelle Dam: **joint-use pool top 6166.4** (active conservation top is a different row, 6130.0), dead 5902.0, crest 6185.0 (diff 0.0) | 1095 / 0.0 / 0.0 / 0.0 | **FIXED** |
| Koocanusa MT | CWMS NWDP `LIB.Elev-Forebay.Inst.1Hour.0.IRIDIUM-REV` (ft, NGVD29) | CWMS NWDP `LIB.Elev-Forebay.Ave.~1Day.1Day.CBT-RAW` | Corps Libby Dam: full pool 2459, minimum pool 2287 (NGVD29) (diff 0.0) | 1088 / 0.11 / 0.708 / 1.805 | **FIXED** |
| Shelbyville IL | CWMS MVS `Lk Shelbyville-Kaskaskia.Elev.Inst.30Minutes.0.lrgsShef-rev` (ft, native NAVD-88) | CWMS MVS `...~1Day.0.datman-rev` (pool) | MVS CWMS levels: summer pool 599.7, rule-curve minimum 590.0, 100% flood control 626.5 (diff 0.0) | 1093 / 0.30 / 0.33 / 0.52 | **FIXED** |
| Taneycomo MO | USGS 07053600 param 62615 (lake elevation, NAVD88) | USGS daily values, same site and parameter | FERC P-2221 notice: 701.35 ft NGVD29 (dir 701.1, diff 0.25); no operator min/max found | 1091 / 0.105 / 0.932 / 2.75 | NEEDS HUMAN REVIEW (P2) |
| Navajo NM | RISE item 612, ft | RISE 612 | USBR Navajo Dam: **joint-use pool top 6085.0** (active conservation top 5990.0 is a different row), dead 5775.0, crest 6108.0 (diff 0.0) | 1095 / 0.0 / 0.0 / 0.0 | **FIXED** |
| Pineview UT | RISE item 656, ft | RISE 656 | USBR Pineview Dam: joint-use pool top 4900.0, dead 4818.0, crest 4908.0 (diff 0.0) | 1095 / 0.0 / 0.0 / 0.0 | **FIXED** |
| Rend IL | CWMS MVS `Rend Lk-Big Muddy.Elev.Inst.30Minutes.0.lrgsShef-raw` (ft, native NAVD-88) | CWMS MVS `...~1Day.0.MVDhist-rev` (stops 2024-07-23); candidate `datman-rev` | MVS CWMS levels: 405.0 (0% flood control), aux spillway 415.0 (diff 0.0); no lower bound | 1092 / **0.55** / 0.58 / 2.05 (vs datman-rev); 8 days vs MVDhist | NEEDS HUMAN REVIEW (O2, P2, O4 on the generator history) |

For the RISE lakes live and history are the same catalog item, so O1-O3 are a consistency check (same item, same dates, same day-key); the semantic proof for those rows is P1/P2 (the operator's published pool and the live range, e.g. Jordanelle's three-year maximum 6166.57 ft against a published 6166.4 ft) and the demonstration that the QA flag reproduces on the live series alone.

## 4. Evidence per lake

### FIXED (8)

* **Blue Mesa, Glendo, Jordanelle, Navajo, Pineview.** RISE daily elevation of the dam forebay. The date-matched comparison is trivially exact (same item). The hold-out "mismatch" is the seasonal statistic: live series median since 2025 vs last 30 days = -54.3, -19.7, -19.2, -21.2, -57.2 ft. Live ranges over the window sit inside the USBR dead-storage-to-crest range. Directory full pool equals the USBR joint-use pool top in every case. Pineview's last RISE value is 2026-10-08 (five days stale at run time): a freshness note for the runner, not a mismatch.
* **Buffalo Bill: the binding itself is wrong, and is corrected.** The research bound the lake to RISE item 152 (`South Fork Dike at Buffalo Bill Reservoir`, parameter FB). That item **does not track the pool**: over three years it stays between 5392.0 and 5394.2 ft (standard deviation 0.47 ft). RISE item 146 (`Buffalo Bill Reservoir Dam and Powerplants`, same parameter) ranges 5350.3-5389.3 ft (standard deviation 10.5 ft) and shows the autumn drawdown. The Reclamation Wyoming Area Office operations report (`BBR26_Jun.pdf`) gives the end-of-May 2026 elevation as 5371.84 ft; RISE 146 on 2026-05-31 is **5371.84 ft** to the hundredth, RISE 152 is 5393.32 ft. Live 152 vs history 146 differs by a median of 25.45 ft (p95 38.3), which is what the hold-out saw; live 146 vs history 146 is exact. The correction is a live-series replacement (152 to 146), history RISE 146 (73 complete years, 1953-2025). The research R7 check had passed 152 as "strong": a flat series near full pool passes a plausibility check, which is why this needed a pool-tracking test.
* **Koocanusa.** Same CWMS location and parameter; the live series is the hourly IRIDIUM telemetry, the history the daily CBT average. Median 0.11 ft, p95 0.71 ft. The three-year maximum 2456.2 ft stays below 2459 ft NGVD29; a NAVD88 reading would reach 2462.8 ft, so there is no datum slip.
* **Shelbyville.** The hold-out compared the pool with `Shelbyville TW-Kaskaskia` (tailwater, 537.9 ft). The generator's history is the pool series `Lk Shelbyville-Kaskaskia ... datman-rev`. The two pool series differ by a tight constant 0.30 ft (p95 0.33 ft), below the 0.5 ft tolerance. Both are native NAVD-88 in the CDA vertical-datum record; the documented NAVD88-to-NGVD29 estimate is +0.2692 ft and is **not** applied. The 0.30 ft is unexplained and disclosed.

### NEEDS HUMAN REVIEW (5): one gap each

* **Canyon Lake TX and Jackson Lake WY.** Every criterion passes except S1(a). Access2Water serves only the latest value, so a 20-day tie to the CWMS record cannot be built in one session. The one-point tie is exact for both (diff 0.00 ft at the same timestamp, same tsid, CDA office SWF / NWDP). Closing it needs a 20-day A2W/CDA log (a daily poll) or a human acceptance that the tsid string is the CDA series name. Jackson's P1 passes at exactly the tolerance (directory 6769, Top of Normal 6768, Max Non-Damaging 6769); the directory also carries `hasDam: false` for Jackson Lake, which is wrong (Jackson Lake Dam exists).
* **Detroit.** O3 fails (p95 3.095 ft > 2.0) and S1(a) is open. The cause is a day-key convention, not a datum: USGS 62614 daily values are statistic 32400, "Observation at 24:00" (the value dated 2026-10-10 is the 23:45 PDT reading, 1497.68 ft), while the probe reduces the CWMS series to a UTC-day median (1498.55 ft for that date). Shifting the history one day gives median 0.08 ft / p95 0.61 ft. That is a **diagnostic only**: the rule was not changed after the failure. A human may adopt a day-key-aligned comparison as a new criteria version. The CWMS daily siblings (`~1Day.0.MIXED-REV`, `Ave.~1Day.1Day.CBT-REV`) are listed in the catalog but the public CDA returns no values for them.
* **Taneycomo.** O1-O4 and P1 pass. The hold-out loaded Table Rock Dam headwater, a different lake. FIXED is withheld only because P2 needs a documented operator range and the licence exhibits (FERC eLibrary P-2221) could not be retrieved; 700.2-704.5 ft in three years is plausible but undocumented. Taneycomo is a regulated tailwater lake of Table Rock Dam: its band is set by Powersite Dam operations.
* **Rend.** The generator's history `MVDhist-rev` stopped on 2024-07-23 (O4 fails; 8 matched days). The same location's `datman-rev` daily series is current but sits a **constant 0.55 ft** from the live 30-minute series (p95 0.58 ft), failing O2 by 0.05 ft; the reviewed `lrgsShef-rev` live series gives the same 0.55 ft (diagnostic), so this is a series difference inside the MVS database. The documented NAVD88-to-NGVD29 estimate (+0.3075 ft) does not explain it. P2 also has no documented lower bound. The criterion was not relaxed. The hold-out's 30.9 ft was the Rend Lk TW series.

### NO DEFENSIBLE MATCH (1)

* **Bartlett.** Live NWPS BRTA3 `HPIRG` and its history IEM HADS BRTA3 `HP` are the same NWS DCP stream (31-day tie: max 0.03 ft), so there is no live/history mismatch; the QA flag is the seasonal artefact (+19.9 ft inside the live series). But the **history is unusable**: seven days carry a 289.3 ft sentinel, the fresh pull differs from the research cache on 25 days (up to 552 ft in one), and 59% of the 2020-2026 daily values (1445 of 2438 days) lie in constant runs of 7+ days, one of them 810 days at 1726.6 ft. P2 fails on the sentinel. The only other candidate (USGS 09509502 stage plus fitted altitude) was already rejected by the research (sd 33 ft, `merged=NO`) and would need a fitted offset, which is not allowed. No uncorrupted history exists in the research cache.

## 5. Provider traps found

1. **Multi-year median vs 30-day median** is not a series test (QA statistic above).
2. **Most-complete-years file selection** picks tailwater, a neighbouring dam's headwater or a composite.
3. **RISE items can be flat "forebays".** Buffalo Bill item 152 passed the research checks but is not the pool. Test that a pool series actually moves with the season.
4. **USBR project pages carry several pool tops.** Jordanelle: active conservation 6130.0 vs joint-use 6166.4. Navajo: active conservation 5990.0 vs joint-use 6085.0 (also the spillway crest). The directory's full pool is the joint-use top.
5. **HADS HPIRG carries sentinels and stuck values.** A 289.3 ft sentinel and multi-hundred-day constant runs (Bartlett). Another HADS cache file, WLHN2, has 23.7% of its days in runs of 30+ days; see follow-ups.
6. **USGS daily statistic.** 62614 daily values are "observation at 24:00" (code 32400), not a daily mean; a UTC-day median is a different quantity (Detroit).
7. **A2W district is not the CDA office.** A2W lists NWP:DET and NWW:JCK; the series live in CDA office NWDP. A2W returns the latest value only; its history must be read from CDA.
8. **CWMS catalog lists series the public CDA does not serve** (Detroit daily siblings).
9. **MVS CWMS series are native NAVD-88**, 0.27-0.31 ft below the NGVD29 figure the Corps publishes for the pool, and sibling series in the same database can sit a constant 0.3-0.55 ft apart (Shelbyville, Rend). Documented offsets are estimates and were not applied.
10. **RISE writes 0.0 for a missing day and stamps at 06:00/07:00 UTC**; the UTC date is the key. Pineview's feed was five days stale.
11. **Directory facts to correct** (not changed here): Jackson Lake `hasDam: false`; Jackson `fullPoolFt` 6769 vs operator Top of Normal 6768.
12. **Rend's history `MVDhist-rev` is a stopped series** (2024-07-23) that the research history picker kept because it had the most years.

## 6. What the generator does with this

* `jobs/lake-brain/bindings/mismatch14_dispositions.json` holds the machine-readable result; `build_mismatch14_dispositions.py` derives it from the probe results and the per-lake operator references and refuses to call a lake FIXED unless every gate passes.
* `build_bindings_table.py` reads it. By default it writes the **separate** file `jobs/lake-brain/data/bindings.proposed.v1.recovered.json` (8 MACHINE_VERIFIED records with a `recovery` block, `reviewRequired: true`) and leaves `bindings.proposed.v1.json` (196 lakes), `.excluded.json`, the review pack and the generated Swift **byte-identical**. `--include-recovered` merges them into the main table for the next generation (204 lakes); it is off by default. `load_fixed_dispositions` refuses a lake outside the 14-lake hold list, a FIXED record that is not review-required, and any record with a non-zero datum offset.
* The 14 ids stay in `held_lakes.SERIES_MISMATCH`, so `ingest_review_result.py` still refuses to accept any of them. They are **not** in any already-built review sample or pack; they are a separate "newly recovered" list.
* Buffalo Bill's record replaces the live primary (RISE 152 to 146), the history source, the history counts and the probe block, and drops 152 from the fallbacks.

To promote after Michael's review: (1) review `bindings.proposed.v1.recovered.json`; (2) remove the accepted ids from `held_lakes.SERIES_MISMATCH` and `build_bindings_table.HISTORY_LIVE_MISMATCH`; (3) `python3 jobs/lake-brain/bindings/build_bindings_table.py --include-recovered`; (4) regenerate the Swift and run the review-pack builder, which then sees 204 eligible lakes. Steps 2-4 are lead decisions and were not performed.

## 7. Not done, and why

* No FIXED lake was marked REVIEWED, no `accepted_batch.json` was written, no review pack was rebuilt (HUMAN REVIEW).
* Canyon / Jackson: a 20-day A2W log is the only way to meet S1(a) without a human accepting the identity argument (TIME or DECISION).
* Detroit: a day-key-aligned comparison needs a new pre-registered criteria version (DECISION).
* Taneycomo: the FERC P-2221 exhibits (EXTERNAL SOURCE).
* Rend: a decision on the 0.55 ft series offset, or the operator's explanation (EXTERNAL SOURCE).
* Bartlett: a new history source (EXTERNAL SOURCE).
* The operator references for the USACE lakes come from the Corps' own CWMS / A2W level records; the USBR figures from the usbr.gov project pages; Libby and Taneycomo from the Corps listing and a FERC notice (web lookups, cited in `mismatch14_specs.json`). The Colorado Sun / press figures were not used as evidence.

## 8. Reproduce

```
python3 jobs/lake-brain/bindings/mismatch14_probe.py [--offline]            # live vs history, writes Sector_Research_Data/.../probe_results.json
python3 jobs/lake-brain/bindings/build_mismatch14_dispositions.py [--check]  # applies the pre-registered criteria
python3 jobs/lake-brain/bindings/build_bindings_table.py [--check] [--include-recovered]
python3 -m pytest jobs/lake-brain/bindings -q                                # 66 tests (13 existing + 53 new)
```

Files: `mismatch14_criteria.py`, `mismatch14_probe.py`, `mismatch14_specs.json` (probe plan and operator references), `build_mismatch14_dispositions.py`, `mismatch14_dispositions.json`, `test_mismatch14.py`, and `jobs/lake-brain/data/mismatch14_probe_results.json` (the raw per-test results).
