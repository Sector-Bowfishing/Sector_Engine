# Lake Brain: accepted bindings, batch 2, 2026-11-22 (owner direction)

**Decision.** Michael, 2026-11-22 06:39Z, "Yes 1-4" (recorded in Sector_Ops #51 comment 7075462499) to the batch 2 research (comment 7074433014): batch 2 is the excluded research-bound lakes that passed the Mac mini re-check. The knowledge release built from it (`lake-knowledge-2026-11-22.2`; the id `.1` is taken by the approved #219 provider-types release) comes back to Michael for the final OK, as batch 1 did.

**What was checked.** Every lake in `bindings.proposed.v1.excluded.json` (231) was re-checked on 2026-11-22 against fresh readings with the same rules as the 192: binding-review-v1 R1-R9 (R6 live, R7 30-day median within -25..+8 ft of full pool, R9 an independent second source within 2 ft), the dry-run checks (b) fallback within 0.5 ft, (c) within 5 ft of the 7-day median, (d) guide curve / operating zone / full pool within 25 ft, and the dry-run (b) fallback check. The runner's 15 ft history/live series rule was **not** run for batch 2 (`seriesCheck` n/a for every lake): it is PENDING, to run on the Mac mini. 108 passed on a provider the engine already reads. Two of them have no engine adapter yet (Clinton Lake IL reads USGS gage height 00065 plus the site altitude; Upper Klamath Lake OR reads USGS 72275) and move to the new-provider work with the other 29, leaving 106. After the #222 review two more are **held** for live checks on the Mac mini (below), so **104 are accepted here**.

**Files.** `jobs/lake-brain/data/bindings.batch2.v1.json` (records, built by `jobs/lake-brain/bindings/build_batch2_table.py` from the same research inputs as the 196 with `build_bindings_table.build_record`; each record carries `verification.batch2Check`), `jobs/lake-brain/data/accepted_batch2.json` (same fields as `accepted_batch.json`), `jobs/lake-brain/data/batch2/checks_2026-11-22.csv` (the per-lake check evidence).

**Series fixed by the re-check** (same pattern as the 2026-11-21 dry-run fixes):
- Logan Martin AL and Weiss AL: the research row read Alabama Power's guide curve (`GC-APCO`); live is now the observed `Raw-APCO` (462.70 / 561.73 ft vs guide 462.44 / 561.43 ft on 2026-11-22). The first pass of the check had read the guide curve for both; the evidence rows are the re-check on `Raw-APCO`.
- East Lynn Lake WV: history was the `RUL` rule curve; now the observed `OBS` series, as for the other LRH lakes.
- Rend Lake IL: the history series `MVDhist-rev` stops in 2024-07; now the continuing daily `datman-rev` (from 1971). It reads +0.55 ft (max 0.61) above live over the last 71 days.
- History/live mismatch lakes (8, held since the rules-v2 hold-out QA): Canyon TX, Koocanusa MT, Shelbyville IL and Taneycomo MO now agree with live within 0.7 ft; Buffalo Bill WY and Navajo NM read the same RISE item for history and live; Bartlett AZ reads the same NWS gauge (HADS) for both.

**Assurance tier: lower than batch 1.** Batch 1 admitted only pre-registered waves with status VERIFIED or VERIFIED_CORROBORATED and no flags. Batch 2 admits, under Michael's "Yes 1-4", lakes batch 1's rules excluded: **57 coordinate-flagged** (off_water 51, identity_risk 6 by the coordinate check), **29 VERIFIED_ENVELOPE** (post-hoc R7h envelope promotion) and **10 VERIFIED_FLAG**, plus wave-1 flagged rows and the 8 history/live-mismatch lakes. (Before the two holds: 58 coordinate-flagged, 30 VERIFIED_ENVELOPE, 10 VERIFIED_FLAG.) Treat batch 2 as a separate, lower-assurance tier when reading its levels.

**Counts (the 104).** Capability: DIRECT_OPERATOR_POOL 57, DIRECT_LAKE_GAUGE 47. Research status: VERIFIED 62, VERIFIED_ENVELOPE 29, VERIFIED_FLAG 10, VERIFIED_CORROBORATED 3. Providers: usgs 33, a2w 24, cwms 18, nwps 16, rise 9, tva 4. History: INSUFFICIENT 2, NONE 12, SUFFICIENT 90. Why they were excluded (any reason): coordinate-flag 57, flagged 10, flagged-wave1 27, history-live-mismatch 8, post-hoc 36. Gauge position: at dam (operator pool/forebay series) 55, on lake (inside the outline) 44, at dam / lake edge 4, on lake (named), position off the outline 1.

**Second source (R9).** Only **2** lakes have an independent second gauge: Logan Martin AL (NWS CCSA1, -0.02 ft vs Raw-APCO) and Red Lake MN (USGS 05074000, +0.28 ft vs the USACE dam series). The other 30 rows that showed a "second source" read the **same gauge through another endpoint** (USGS `usgs2:<same site>` for 27 lakes, CWMS NWDM for Lake Oahe ND and Longview MO, and NWPS YGBP1 vs USGS 03077000 for Youghiogheny River Lake MD, presumed to be the same gauge until the Mac mini confirms it). They are labeled "same gauge, other endpoint" and do not count as R9.

**History offsets (measured, recorded with their basis in the history entry's `note`).** `offsetFt` is added to the history reading:
- Lake Washington WA: `LWSC.Elev-Lake.Inst.1Hour.0.NWSRADIO-RAW` carried a leaked comparator annotation in its series id (`(+0.36ft over 1874d, sd 0.08)`); the id is now clean and +0.36 ft (1874-day mean, sd 0.08 ft) is recorded as `offsetFt`. The sign is as the comparator reported it; direction to be confirmed on the Mac mini.
- Rend Lake IL: -0.55 ft (datman-rev reads +0.55 ft above live over 71 days, so the history is shifted down by 0.55 ft).
- Toledo Bend Reservoir TX: -0.18 ft (two-gauge mean, USGS 08025350 NGVD29 vs live 312914093422701 NAVD88; VDatum -0.285 ft; Sector_Ops #51 comment 7076370263).
- The engine applies `offsetFt` only to `usgsDaily`, `hadsDaily` and `cdecDaily` history. Lake Washington and Rend Lake are `cwmsDaily`, so their offsets are recorded data, not applied by the runner, until `cwmsDaily` gains an offset (follow-up).

**Held out of batch 2 (review of #222; live data needed, Mac mini).**
- Lake Mattamuskeet NC: history reads a different site and parameter (USGS 0208458893 00062) from live (020845889205 62615), and the lake has no full pool, so R7 and check (d) do not apply. Goes to batch 3 once the history/live relation is checked.
- Blue Marsh Lake PA: HOLD; the datum mix between the live series and the `Rev-DCP` history is unresolved.
- Both rows stay in `checks_2026-11-22.csv` with result HOLD; they have no record and are not accepted.

**Still to run on the Mac mini (needs live data; not changed here).** Check (b) on the 39 lakes with fallbacks, the Blue Marsh datum mix, and the 15 ft history/live series check for all 104.

**Duplicates (follow-up; the directory is not changed here).** Two directory entries read the same gauge:
- Lake Strom Thurmond (Clarks Hill) SC (batch 2) and Clarks Hill / J.S. Thurmond GA (batch 1): USGS 02193900.
- Lake Oahe ND (batch 2) and Lake Oahe SD (batch 1): CWMS NWDM OAHE.
- Kentucky Lake KY and Kentucky Lake TN (both batch 2): TVA KYDK2.

**Customer list.** By the 2026-11-20 20:01Z owner rule (the customer Lake-level list is exactly Lake's reviewed set), the list goes from 192 to 296 in this PR. That is customer-facing and is gated by the release approval. If batch 2 should publish a level state without a customer copy yet, the list tool needs a different rule; say so in review.

**Not changed.** No schedule, no deploy, no live build; the Mac mini keeps running the approved `lake-knowledge-2026-11-21.2` until this is merged, approved and rebuilt. `acceptedReviewedAt` stays the batch 1 date (the generator carries one review date); the batch 2 date is in `accepted_batch2.json`.

| Lake | Live source (provider: station) | Excluded for | Gauge position | Level 2026-11-22 (ft) | Second source | History years (class) |
|---|---|---|---|---|---|---|
| Allegheny Reservoir\|PA | a2w: LRP:Kinzua | coordinate-flag | at dam (operator pool/forebay series) | 1306.52 | — | 12 (SUFFICIENT) |
| Assawompset Pond\|MA | usgs: 415026070563603 | flagged, flagged-wave1 | on lake (inside the outline) | 53.15 | — | 1 (INSUFFICIENT) |
| Bartlett\|AZ | nwps: BRTA3 | history-live-mismatch | on lake (inside the outline) | 1791.99 | — | 14 (SUFFICIENT) |
| Bay Springs Lake\|MS | cwms: SAM:Whitten.Elev.Inst.15Minutes.0.Raw-USGS | post-hoc | at dam (operator pool/forebay series) | 409.71 | — | 0 (NONE) |
| Bear Lake\|UT | usgs: 10055000 | flagged-wave1, post-hoc | on lake (inside the outline) | 5911.54 | same gauge, other endpoint: usgs2:10055000 (+0.00 ft) | 109 (SUFFICIENT) |
| Beaver\|AR | a2w: SWL:Beaver_Dam | coordinate-flag | at dam (operator pool/forebay series) | 1110.73 | — | 62 (SUFFICIENT) |
| Beech Fork Lake\|WV | a2w: LRH:BeechFk | coordinate-flag | at dam (operator pool/forebay series) | 588.01 | — | 5 (SUFFICIENT) |
| Blackshear\|GA | nwps: WWCG1 | coordinate-flag | on lake (inside the outline) | 233.43 | — | 12 (SUFFICIENT) |
| Bowman-Haley Reservoir\|ND | a2w: NWO:BOHA | coordinate-flag | at dam (operator pool/forebay series) | 2748.43 | — | 8 (SUFFICIENT) |
| Buckhorn Lake\|KY | a2w: LRL:Buckhorn | coordinate-flag | at dam (operator pool/forebay series) | 766.53 | — | 23 (SUFFICIENT) |
| Buffalo Bill Reservoir\|WY | rise: 152 | history-live-mismatch | at dam (operator pool/forebay series) | 5392.49 | — | 30 (SUFFICIENT) |
| Bull Shoals Lake\|AR | a2w: SWL:Bull_Shoals_Dam | coordinate-flag | at dam (operator pool/forebay series) | 652.09 | — | 75 (SUFFICIENT) |
| Burton\|GA | nwps: TIGG1 | coordinate-flag | on lake (inside the outline) | 1864.42 | — | 15 (SUFFICIENT) |
| Caddo Lake\|TX | a2w: MVK:Caddo Lake | coordinate-flag | at dam (operator pool/forebay series) | 167.2 | — | 91 (SUFFICIENT) |
| Cagles Mill Lake\|IN | a2w: LRL:CaglesMill | coordinate-flag | at dam (operator pool/forebay series) | 636.24 | — | 8 (SUFFICIENT) |
| Calamus Reservoir\|NE | rise: 215 | coordinate-flag | at dam (operator pool/forebay series) | 2237.88 | — | 26 (SUFFICIENT) |
| Canandaigua Lake\|NY | nwps: CNDN6 | flagged-wave1, post-hoc | on lake (inside the outline) | 687.09 | — | 10 (SUFFICIENT) |
| Canyon Lake\|TX | a2w: SWF:SMCT2 | history-live-mismatch | at dam (operator pool/forebay series) | 907.69 | — | 61 (SUFFICIENT) |
| Catahoula Lake\|LA | cwms: MVK:Catahoula Lake-Center.Elev.Inst.1Hour.0.DCP-rev | flagged, flagged-wave1 | at dam (operator pool/forebay series) | 27.96 | — | 53 (SUFFICIENT) |
| Cecil M. Harden Lake\|IN | a2w: LRL:CMHarden | coordinate-flag | at dam (operator pool/forebay series) | 644.29 | — | 8 (SUFFICIENT) |
| Chautauqua Lake\|NY | usgs: 03013946 | flagged-wave1, post-hoc | on lake (inside the outline) | 1306.88 | same gauge, other endpoint: usgs2:03013946 (+0.00 ft) | 51 (SUFFICIENT) |
| Cherokee Lake\|TN | tva: CRKT1 | coordinate-flag | at dam (operator pool/forebay series) | 1046.7 | — | 0 (NONE) |
| Chickamauga Lake\|TN | tva: CKDT1 | coordinate-flag | at dam (operator pool/forebay series) | 677.48 | — | 0 (NONE) |
| Clear Lake\|CA | usgs: 11450000 | post-hoc | on lake (inside the outline) | 1322.66 | same gauge, other endpoint: usgs2:11450000 (+0.00 ft) | 107 (SUFFICIENT) |
| Clearwater Lake\|MO | a2w: SWL:Clearwater_Dam | coordinate-flag | at dam (operator pool/forebay series) | 494.46 | — | 77 (SUFFICIENT) |
| Crater Lake\|OR | usgs: 11492200 | flagged-wave1, post-hoc | on lake (inside the outline) | 6165.2 | same gauge, other endpoint: usgs2:11492200 (+0.00 ft) | 52 (SUFFICIENT) |
| Dardanelle\|AR | cwms: SWL:LD10_Dardanelle-Headwater.Elev.Inst.1Hour.0.Decodes-raw | coordinate-flag | at dam (operator pool/forebay series) | 337.63 | — | 51 (SUFFICIENT) |
| Devil's Kitchen Lake\|IL | nwps: DKLI2 | coordinate-flag | on lake (inside the outline) | 507.92 | — | 11 (SUFFICIENT) |
| Devils Lake\|ND | usgs: 05056500 | coordinate-flag, post-hoc | on lake (inside the outline) | 1449.85 | same gauge, other endpoint: usgs2:05056500 (+0.00 ft) | 53 (SUFFICIENT) |
| Diamond Lake\|OR | usgs: 14312450 | flagged-wave1, post-hoc | on lake (inside the outline) | 5183.53 | same gauge, other endpoint: usgs2:14312450 (+0.00 ft) | 22 (SUFFICIENT) |
| Eagle Lake\|MS | cwms: MVK:Muddy Bayou-Landside.Elev.Inst.1Hour.0.DCP-rev | coordinate-flag | at dam (operator pool/forebay series) | 74.92 | — | 8 (SUFFICIENT) |
| East Lynn Lake\|WV | cwms: LRH:EastLynn-Lake.Elev.Inst.15Minutes.0.OBS | coordinate-flag | at dam (operator pool/forebay series) | 657.92 | — | 13 (SUFFICIENT) |
| Fort Peck Lake\|MT | cwms: NWDM:FTPK.Elev.Inst.1Hour.0.Best-MRBWM | coordinate-flag | at dam (operator pool/forebay series) | 2220.95 | — | 8 (SUFFICIENT) |
| Garrisons Lake\|DE | usgs: 01483510 | coordinate-flag, flagged-wave1, post-hoc | on lake (inside the outline) | 5.74 | same gauge, other endpoint: usgs2:01483510 (+0.00 ft) | 10 (SUFFICIENT) |
| Grand Lake\|CO | rise: 372 | flagged-wave1, post-hoc | at dam (operator pool/forebay series) | 8366.61 | — | 15 (SUFFICIENT) |
| Greenwood Lake\|NJ | usgs: 01383000 | coordinate-flag, post-hoc | on lake (inside the outline) | 618.48 | same gauge, other endpoint: usgs2:01383000 (+0.00 ft) | 16 (SUFFICIENT) |
| Harlan County Lake\|NE | a2w: NWK:HACO | coordinate-flag | at dam (operator pool/forebay series) | 1932.97 | — | 7 (SUFFICIENT) |
| Higgins Lake\|MI | usgs: 442805084411001 | post-hoc | on lake (inside the outline) | 1153.4 | same gauge, other endpoint: usgs2:442805084411001 (+0.00 ft) | 35 (SUFFICIENT) |
| Horsetooth Reservoir\|CO | rise: 87 | coordinate-flag | at dam (operator pool/forebay series) | 5407.85 | — | 38 (SUFFICIENT) |
| Houghton Lake\|MI | usgs: 442400084472801 | post-hoc | on lake (named), position off the outline | 1137.41 | same gauge, other endpoint: usgs2:442400084472801 (+0.00 ft) | 43 (SUFFICIENT) |
| Jamestown Reservoir\|ND | rise: 451 | coordinate-flag | at dam (operator pool/forebay series) | 1429.77 | — | 72 (SUFFICIENT) |
| Kentucky Lake\|KY | tva: KYDK2 | coordinate-flag | at dam (operator pool/forebay series) | 354.73 | — | 0 (NONE) |
| Kentucky Lake\|TN | tva: KYDK2 | coordinate-flag | at dam (operator pool/forebay series) | 354.73 | — | 0 (NONE) |
| Keuka Lake\|NY | nwps: KKPN6 | flagged-wave1, post-hoc | on lake (inside the outline) | 713.04 | — | 11 (SUFFICIENT) |
| Lake Barkley\|KY | a2w: LRN:BAHK2 | coordinate-flag | at dam (operator pool/forebay series) | 354.9 | — | 8 (SUFFICIENT) |
| Lake Champlain\|VT | usgs: 04294500 | flagged-wave1, post-hoc | on lake (inside the outline) | 93.71 | same gauge, other endpoint: usgs2:04294500 (+0.00 ft) | 88 (SUFFICIENT) |
| Lake D'Arbonne\|LA | usgs: 07366364 | coordinate-flag | on lake (inside the outline) | 78.61 | — | 16 (SUFFICIENT) |
| Lake Darling\|ND | a2w: MVP:LakeDarling_Dam | coordinate-flag | at dam (operator pool/forebay series) | 1596.16 | — | 25 (SUFFICIENT) |
| Lake Francis Case\|SD | usgs: 06442996 | coordinate-flag | on lake (inside the outline) | 1343.0 | same gauge, other endpoint: usgs2:06442996 (+0.00 ft) | 26 (SUFFICIENT) |
| Lake Geneva\|WI | usgs: 423525088260400 | flagged | at dam / lake edge | 864.24 | same gauge, other endpoint: usgs2:423525088260400 (+0.00 ft) | 21 (SUFFICIENT) |
| Lake George\|NY | usgs: 04278000 | flagged-wave1, post-hoc | on lake (inside the outline) | 319.05 | same gauge, other endpoint: usgs2:04278000 (+0.00 ft) | 112 (SUFFICIENT) |
| Lake Gogebic\|MI | usgs: 04035995 | flagged | on lake (inside the outline) | 1294.23 | same gauge, other endpoint: usgs2:04035995 (+0.00 ft) | 53 (SUFFICIENT) |
| Lake Hudson\|OK | a2w: SWT:HUDS | coordinate-flag | at dam (operator pool/forebay series) | 620.18 | — | 8 (SUFFICIENT) |
| Lake Koocanusa\|MT | cwms: NWDP:LIB.Elev-Forebay.Inst.1Hour.0.IRIDIUM-REV | history-live-mismatch | at dam (operator pool/forebay series) | 2438.25 | — | 50 (SUFFICIENT) |
| Lake Memphremagog\|VT | usgs: 04295500 | coordinate-flag, flagged-wave1, post-hoc | on lake (inside the outline) | 679.48 | same gauge, other endpoint: usgs2:04295500 (+0.00 ft) | 86 (SUFFICIENT) |
| Lake Mendota\|WI | usgs: 05428000 | post-hoc | on lake (inside the outline) | 849.51 | same gauge, other endpoint: usgs2:05428000 (+0.00 ft) | 72 (SUFFICIENT) |
| Lake Minnetonka\|MN | nwps: MTKM5 | post-hoc | at dam / lake edge | 928.32 | — | 0 (NONE) |
| Lake Monona\|WI | usgs: 05429000 | post-hoc | on lake (inside the outline) | 843.99 | same gauge, other endpoint: usgs2:05429000 (+0.00 ft) | 70 (SUFFICIENT) |
| Lake Oahe\|ND | cwms: NWDM:OAHE.Elev.Inst.1Hour.0.Best-MRBWM | post-hoc | at dam (operator pool/forebay series) | 1593.23 | same gauge, other endpoint: cwms-nwdm:NWDM:OAHE (-0.00 ft) | 8 (SUFFICIENT) |
| Lake Pepin\|MN | a2w: MVP:LakeCity | coordinate-flag, flagged, post-hoc | at dam (operator pool/forebay series) | 667.85 | — | 0 (NONE) |
| Lake Petenwell\|WI | nwps: PETW3 | coordinate-flag | on lake (inside the outline) | 923.55 | — | 14 (SUFFICIENT) |
| Lake Quinault\|WA | usgs: 12039490 | flagged | on lake (inside the outline) | 186.82 | same gauge, other endpoint: usgs2:12039490 (+0.00 ft) | 0 (NONE) |
| Lake Russell (R.B. Russell)\|GA | nwps: RBDS1 | coordinate-flag | on lake (inside the outline) | 473.79 | — | 41 (SUFFICIENT) |
| Lake Sakakawea\|ND | cwms: NWDM:GARR.Elev.Inst.1Hour.0.Best-MRBWM | post-hoc | at dam (operator pool/forebay series) | 1824.14 | — | 0 (NONE) |
| Lake Sammamish\|WA | usgs: 12122000 | flagged-wave1, post-hoc | on lake (inside the outline) | 26.29 | same gauge, other endpoint: usgs2:12122000 (+0.00 ft) | 27 (SUFFICIENT) |
| Lake Sharpe\|SD | nwps: BBDS2 | coordinate-flag | at dam / lake edge | 1420.8 | — | 5 (SUFFICIENT) |
| Lake Shelbyville\|IL | cwms: MVS:Lk Shelbyville-Kaskaskia.Elev.Inst.30Minutes.0.lrgsShef-rev | history-live-mismatch | at dam (operator pool/forebay series) | 598.68 | — | 54 (SUFFICIENT) |
| Lake Strom Thurmond (Clarks Hill)\|SC | usgs: 02193900 | post-hoc | on lake (inside the outline) | 317.1 | same gauge, other endpoint: usgs2:02193900 (+0.00 ft) | 68 (SUFFICIENT) |
| Lake Taneycomo\|MO | usgs: 07053600 | history-live-mismatch | on lake (inside the outline) | 701.19 | — | 29 (SUFFICIENT) |
| Lake Tenkiller\|OK | nwps: TENO2 | coordinate-flag | on lake (inside the outline) | 624.96 | — | 15 (SUFFICIENT) |
| Lake Tschida\|ND | rise: 550 | coordinate-flag | at dam (operator pool/forebay series) | 2057.95 | — | 76 (SUFFICIENT) |
| Lake Washington\|WA | cwms: NWDP:LWKW.Elev-Lake.Inst.1Hour.0.IRIDIUM-REV | flagged, flagged-wave1 | at dam (operator pool/forebay series) | 20.62 | — | 30 (SUFFICIENT) |
| Logan Martin\|AL | cwms: SAM:LoganMartin.Elev.Inst.1Hour.0.Raw-APCO | post-hoc | at dam (operator pool/forebay series) | 462.7 | independent: nwps:CCSA1 (-0.02 ft vs Raw-APCO) | 0 (NONE) |
| Long Pond (Lakeville)\|MA | usgs: 414945070560301 | coordinate-flag, flagged, flagged-wave1 | on lake (inside the outline) | 53.58 | — | 1 (INSUFFICIENT) |
| Longview Lake\|MO | a2w: NWK:LGVM | post-hoc | at dam (operator pool/forebay series) | 891.23 | same gauge, other endpoint: cwms-nwdm:NWDM:LGVM (-0.00 ft) | 0 (NONE) |
| Mark Twain Lake\|MO | cwms: MVS:Mark Twain Lk-Salt.Elev.Inst.30Minutes.0.lrgsShef-rev | coordinate-flag | at dam (operator pool/forebay series) | 602.1 | — | 42 (SUFFICIENT) |
| Millwood\|AR | a2w: SWL:Millwood_Dam | coordinate-flag | at dam (operator pool/forebay series) | 259.08 | — | 59 (SUFFICIENT) |
| Mississinewa Lake\|IN | cwms: LRL:Mississinewa-Lake.Elev.Inst.15Minutes.0.Decodes-raw | coordinate-flag | at dam (operator pool/forebay series) | 721.2 | — | 7 (SUFFICIENT) |
| Monroe Lake\|IN | a2w: LRL:Monroe | coordinate-flag | at dam (operator pool/forebay series) | 537.31 | — | 8 (SUFFICIENT) |
| Mullett Lake\|MI | usgs: 04129950 | flagged-wave1, post-hoc | on lake (inside the outline) | 592.36 | same gauge, other endpoint: usgs2:04129950 (+0.00 ft) | 8 (SUFFICIENT) |
| Navajo Reservoir\|NM | rise: 612 | history-live-mismatch | at dam (operator pool/forebay series) | 6073.81 | — | 63 (SUFFICIENT) |
| Okeechobee\|FL | a2w: SAJ:Okeechobee | flagged-wave1, post-hoc | at dam (operator pool/forebay series) | 14.91 | — | 94 (SUFFICIENT) |
| Oneida Lake\|NY | nwps: CLEN6 | flagged-wave1, post-hoc | on lake (inside the outline) | 369.19 | — | 9 (SUFFICIENT) |
| Oologah Lake\|OK | a2w: SWT:OOLO | coordinate-flag | at dam (operator pool/forebay series) | 640.33 | — | 8 (SUFFICIENT) |
| Owasco Lake\|NY | usgs: 04235396 | flagged-wave1, post-hoc | at dam / lake edge | 711.46 | same gauge, other endpoint: usgs2:04235396 (+0.00 ft) | 43 (SUFFICIENT) |
| Rainy Lake\|MN | nwps: FFCQ6 | flagged, flagged-wave1 | on lake (inside the outline) | 1106.32 | — | 0 (NONE) |
| Red Lake\|MN | a2w: MVP:RedLake_Dam | flagged-wave1 | at dam (operator pool/forebay series) | 1173.67 | independent: usgs2:05074000 (+0.28 ft) | 29 (SUFFICIENT) |
| Rend Lake\|IL | cwms: MVS:Rend Lk-Big Muddy.Elev.Inst.30Minutes.0.lrgsShef-raw | history-live-mismatch | at dam (operator pool/forebay series) | 402.71 | — | 49 (SUFFICIENT) |
| Salamonie Lake\|IN | cwms: LRL:Salamonie-Lake.Elev.Inst.15Minutes.0.USGS-rev | coordinate-flag | at dam (operator pool/forebay series) | 739.1 | — | 8 (SUFFICIENT) |
| Sebago Lake\|ME | usgs: 01063995 | flagged-wave1, post-hoc | on lake (inside the outline) | 262.66 | same gauge, other endpoint: usgs2:01063995 (+0.00 ft) | 25 (SUFFICIENT) |
| Seneca Lake\|NY | nwps: GNVN6 | flagged-wave1, post-hoc | on lake (inside the outline) | 443.81 | — | 9 (SUFFICIENT) |
| Sinclair\|GA | nwps: SNCG1 | coordinate-flag | on lake (inside the outline) | 338.18 | — | 15 (SUFFICIENT) |
| Smithville Lake\|MO | a2w: NWK:SMIE | coordinate-flag | at dam (operator pool/forebay series) | 863.73 | — | 8 (SUFFICIENT) |
| Starvation Reservoir\|UT | rise: 767 | flagged-wave1, post-hoc | at dam (operator pool/forebay series) | 5693.51 | — | 54 (SUFFICIENT) |
| Stonewall Jackson Lake\|WV | a2w: LRP:StonewallJackson | coordinate-flag | at dam (operator pool/forebay series) | 1068.94 | — | 8 (SUFFICIENT) |
| Stump Lake\|ND | usgs: 05056665 | coordinate-flag, post-hoc | on lake (inside the outline) | 1451.0 | same gauge, other endpoint: usgs2:05056665 (+0.00 ft) | 26 (SUFFICIENT) |
| Swanson Reservoir\|NE | rise: 134012 | coordinate-flag | at dam (operator pool/forebay series) | 2734.08 | — | 72 (SUFFICIENT) |
| Toledo Bend Reservoir\|TX | usgs: 312914093422701 | coordinate-flag | on lake (inside the outline) | 167.42 | — | 39 (SUFFICIENT) |
| Tuttle Creek Lake\|KS | cwms: NWDM:TUCR.Elev.Inst.1Hour.0.Best-NWK | coordinate-flag | at dam (operator pool/forebay series) | 1079.59 | — | 8 (SUFFICIENT) |
| Walker Lake\|NV | usgs: 10288500 | flagged, flagged-wave1 | on lake (inside the outline) | 3914.01 | same gauge, other endpoint: usgs2:10288500 (+0.00 ft) | 19 (SUFFICIENT) |
| Walter F. George / Eufaula\|GA | usgs: 02343240 | coordinate-flag | on lake (inside the outline) | 186.5 | — | 18 (SUFFICIENT) |
| Weiss\|AL | cwms: SAM:Weiss.Elev.Inst.1Hour.0.Raw-APCO | coordinate-flag | at dam (operator pool/forebay series) | 561.73 | — | 8 (SUFFICIENT) |
| Wild Horse Reservoir\|NV | usgs: 13174000 | flagged-wave1, post-hoc | on lake (inside the outline) | 6181.78 | same gauge, other endpoint: usgs2:13174000 (+0.00 ft) | 22 (SUFFICIENT) |
| Youghiogheny River Lake\|MD | nwps: YGBP1 | coordinate-flag | on lake (inside the outline) | 1426.2 | same gauge, other endpoint (presumed: NWPS YGBP1 relays USGS 03077000; to confirm on the Mac mini): usgs2:03077000 (-0.05 ft) | 14 (SUFFICIENT) |
