# Depth Brain: NWS NWPS datum audit

Date 2026-10-14. Research only. Raw data: `~/Desktop/Development/Sector_Research_Data/depth-brain/datum3/nwps/`. Machine twin: `jobs/depth-brain/depth_brain/data/proposals/provider_rules.json`. Extends section 3.6 of `DEPTH_DATUM_AUDIT.md`.

Question: for the NWPS-backed lakes, which gauges publish a **pool elevation in a stated datum**, which publish stage (gage zero known), and which are unknown? Rule: HG is never assumed to be elevation; the NWS datum table is never accepted on its own.

## 1. Bottom line

* The provider-level verdict stays **UNKNOWN**. Nothing in the NWPS API documents what the datum table's `value` means, and the live tables contradict the data (below).
* 43 NWPS candidate lakes: 40 are served as "Pool" (SHEF HP), 1 as "Lake Elevation" (HL, Lake Poinsett), 2 as "Stage" (HG, Crescent Lake FL and Liberty Reservoir MD). 33 have a high/medium-confidence full-pool figure (the brief's 32 may exclude one lake, for example Lake Gaston, whose NWPS value was -999 at fetch).
* **7 lakes can be resolved today without trusting NWPS**, because the NWPS number is *numerically identical* to a labelled source that also holds the pool: 6 USACE lakes whose NWPS "Pool" equals the CWMS Elev series at the same location that carries Top of Conservation (John Redmond, Canton, Kaw, Tenkiller, Skiatook, Moomaw) and Youghiogheny (equals USGS 62615, NAVD88 by USGS definition, and its CWMS pool location is tagged NAVD88). Recommended path: **rebind the live source to CWMS (or USGS 62615) and apply the existing CWMS same-source rule**; keep NWPS only as a backup.
* 3 more are reproduced against a labelled USGS series but their **pool figure's datum is undocumented** (Herrington NGVD29, Ute NAVD88, Priest NGVD29 via gage zero). 1 (Russell) matches USGS 00062 and is the Hartwell-method case.
* The remaining 22 of the 33 stay UNKNOWN: 12 with empty datum tables and no cross-check, 4 with a nonzero or contradicted table, 3 with only a "datum value 0", 2 local or unreliable (Topaz, Scituate), 1 stage (Liberty).

## 2. What each NWPS product means (documented vs not)

| Item | What is documented | Source |
|---|---|---|
| SHEF `HP` | "Elevation, pool ... usually expressed in MSL" | SHEF Code Manual (2012), already in the audit |
| SHEF `HL` | "Elevation, natural lake ... in MSL" | same |
| SHEF `HG` | river stage (height above gage zero) | same |
| SHEF `HK` / `HF` | lake height above a datum "usually not MSL" / forebay elevation | same |
| `MSL` | not a datum realization: NGVD29 and NAVD88 both qualify | n/a |
| NWPS `/gauges/{id}` | `pedts.observed` (e.g. HPIRZ), `status.observed.primary` + unit, `datums.vertical.value[]` (label, abbrev, description, value), `datums.notes`, `hydronotes`, `dataAttribution` | [fetched] swagger `api.water.noaa.gov/nwps/v1/docs/swagger.json` |
| NWPS `/gauges/{id}/stageflow/observed` | `primaryName` is a label: **Pool** (HP), **Stage** (HG), **Lake Elevation** (HL) | [fetched, 43 of 43] |
| Datum `value` | **not defined anywhere in the swagger**. `gaugeZeroDatum` exists only under `inundation`. Convention seen: the datum table lists the elevation of *gage zero* in that datum, so 0 would mean "reading is elevation in that datum" | inferred, undocumented |
| Fourth/fifth PEDTS letters (`IRZ`, `IRG` ...) | source/probability codes, not datum | audit |

So `primaryName` is a trustworthy HP/HG/HL label, but "Pool" does **not** prove a geodetic elevation (Lake Vermilion MN is "Pool" and reads 56.7 ft, a local scale), and a datum table does not prove which datum the reading uses (Priest Lake lists two).

## 3. Evidence tests run (all [fetched] on 2026-10-14, hourly overlap, same-hour matching)

1. **NWPS vs CWMS** for the 9 lakes whose pool is a CWMS Top of Conservation. Six have a CWMS `Elev.Inst` series at the pool location: NWPS minus CWMS mean is between -0.008 and +0.001 ft and the max absolute difference is 0.05 ft or less (John Redmond 30-minute series: exactly 0.000). These NWPS feeds are the USACE DCP data. CWMS location `vertical-datum` (API): NGVD29 for all six. Lake Russell's CWMS series is daily only and returned no recent values; Youghiogheny and Flannagan returned no `Elev.Inst` catalog name under the guessed mask.
2. **NWPS vs USGS** for the 8 gauges tested (7 had current overlapping data; Indian Lake had none). Identical (mean diff 0.000, sd 0 to 0.007): Herrington vs 62614 (NGVD29 by USGS definition), Ute vs 62615 and Youghiogheny vs 62615 (NAVD88), Russell vs 00062 (datum unspecified by USGS), Minnetonka vs 00065. **Priest Lake** NWPS = 00065 + 2434.64 (the NGVD29 table value) to 0.003 ft, and misses by 3.79 ft with the NAVD88 table value, so with two table datums the reading follows NGVD29. **Bartlett** NWPS = 00065 + 1599.46 (NGVD29) **+ 0.54 ft** (sd 0.015): an unexplained constant between NWS and USGS.
3. **Table vs reading contradictions**: Canton lists NAVD88=0.6 while its NWPS value equals the CWMS NGVD29 series; John Redmond lists NGVD29=995 and Lake of the Ozarks NGVD29=560 and Flannagan NGVD29=1200 and Indian Lake NGVD29=1604.23 while their readings are elevation-sized (so `value` is not a gage-zero for the pool reading, or these tables describe a different gauge on the same lid); Seneca lists STND 0, NGVD29 -1.33 and NAVD88 0; Scituate lists MHW 0 (a tidal datum on an inland reservoir).

## 4. Classification of the 43 gauges

| Class | Meaning | In the 33 pool-bearing lakes | In all 43 |
|---|---|---|---|
| ELEV_IDENTICAL_TO_CWMS | 6 | 6 |
| ELEV_IDENTICAL_TO_LABELLED_USGS | 3 | 3 |
| TABLE_VALUE_REPRODUCES | 1 | 1 |
| ELEV_IDENTICAL_TO_UNLABELLED_USGS | 1 | 2 |
| TABLE_ZERO_ONLY | 3 | 6 |
| TABLE_NONZERO_UNEXPLAINED | 3 | 3 |
| TABLE_CONTRADICTED | 1 | 1 |
| LOCAL_OR_UNRELIABLE | 2 | 3 |
| STAGE_CODE | 1 | 2 |
| NO_TABLE_NO_CHECK | 12 | 16 |

Class meanings. **ELEV_IDENTICAL_TO_CWMS**: pool elevation identical to a CWMS series with a known location datum. **ELEV_IDENTICAL_TO_LABELLED_USGS**: identical to USGS 62614/62615 (datum fixed by the parameter code). **TABLE_VALUE_REPRODUCES**: reading reproduced from USGS gage height plus the NWS table value. **ELEV_IDENTICAL_TO_UNLABELLED_USGS**: identical to 00062/00065 (datum not declared). **TABLE_ZERO_ONLY**: table lists a datum with value 0 and nothing else checks it. **TABLE_NONZERO_UNEXPLAINED / TABLE_CONTRADICTED / LOCAL_OR_UNRELIABLE / STAGE_CODE / NO_TABLE_NO_CHECK**: unusable as is.

| Lake | NWS id | PEDTS / label | Obs (ft) | Directory pool (basis, conf) | Datum table | Class | Evidence |
|---|---|---|---|---|---|---|---|
| Canton Lake (OK) | CNLO2 | HPIRG / Pool | 1610.73 | 1615.4 (fullPool, high) | NAVD88=0.6 | **ELEV_IDENTICAL_TO_CWMS** | CWMS CANT.Elev.Inst.1Hour.0.Ccp-Rev (location datum NGVD29): n=60 hourly pairs, NWPS-CWMS mean -0.001 ft, max |diff| 0.01 ft |
| John Redmond Reservoir (KS) | JRLK1 | HPIRG / Pool | 1044.44 | 1041 (fullPool, high) | NGVD29=995 | **ELEV_IDENTICAL_TO_CWMS** | CWMS JOHN.Elev.Inst.1Hour.0.Ccp-Rev (location datum NGVD29): n=58 hourly pairs, NWPS-CWMS mean -0.008 ft, max |diff| 0.05 ft |
| Kaw Lake (OK) | KAWO2 | HPIRG / Pool | 1009.22 | 1010 (fullPool, high) | empty | **ELEV_IDENTICAL_TO_CWMS** | CWMS KAWL.Elev.Inst.1Hour.0.Ccp-Rev (location datum NGVD29): n=60 hourly pairs, NWPS-CWMS mean 0.001 ft, max |diff| 0.03 ft |
| Lake Moomaw (VA) | MOOV2 | HPIRG / Pool | 1566.65 | 1582 (fullPool, high) | empty | **ELEV_IDENTICAL_TO_CWMS** | CWMS Moomaw.Elev.Inst.30Minutes.0.Rev-DCP (location datum NGVD29): n=59 hourly pairs, NWPS-CWMS mean 0.0 ft, max |diff| 0.0 ft |
| Lake Tenkiller (OK) | TENO2 | HPIRG / Pool | 625.2 | 632 (fullPool, high) | empty | **ELEV_IDENTICAL_TO_CWMS** | CWMS TENK.Elev.Inst.15Minutes.0.Rev-SCADA (location datum NGVD29): n=31 hourly pairs, NWPS-CWMS mean 0.001 ft, max |diff| 0.02 ft |
| Skiatook Lake (OK) | SKLO2 | HPIRG / Pool | 710.83 | 714 (fullPool, high) | empty | **ELEV_IDENTICAL_TO_CWMS** | CWMS SKIA.Elev.Inst.1Hour.0.Ccp-Rev (location datum NGVD29): n=60 hourly pairs, NWPS-CWMS mean -0.002 ft, max |diff| 0.02 ft |
| Herrington Lake (KY) | DIXK2 | HPIRG / Pool | 733.88 | 740 (fullPool, high) | NGVD29=0 | **ELEV_IDENTICAL_TO_LABELLED_USGS** | USGS 03286000 62614 (NGVD29 by USGS parameter definition): n=236, mean diff 0.0, sd 0.0; NWPS table NGVD29=0 agrees |
| Ute Lake (NM) | UTEN5 | HPIRG / Pool | 3785.29 | 3788.86 (fullPool, high) | empty | **ELEV_IDENTICAL_TO_LABELLED_USGS** | USGS 07226800 62615 (NAVD88 by USGS parameter definition): n=239, mean diff 0.0, sd 0.0; NWPS table empty |
| Youghiogheny River Lake (MD) | YGBP1 | HPIRG / Pool | 1439.24 | 1438.35 (fullPool, high) | empty | **ELEV_IDENTICAL_TO_LABELLED_USGS** | USGS 03077000 62615 (NAVD88 by USGS parameter definition): n=237, mean diff 0.0, sd 0.007; pool is CWMS LRP Top of Conservation, location datum NAVD88 |
| Priest Lake (ID) | PSLI1 | HPIRA / Pool | 2436.77 | 2437.64 (fullPool, high) | NAVD88=2438.43; NGVD29=2434.64 | **TABLE_VALUE_REPRODUCES** | NWPS = USGS 12393000 gage height (00065) + 2434.64 (the NWS NGVD29 table value) to 0.003 ft over 236 hours; adding the NAVD88 table value (2438.43) misses by 3.79 ft |
| Lake Minnetonka (MN) | MTKM5 | HPIRP / Pool | 928.24 | 929.4 (naturalSurface, low) | empty | **ELEV_IDENTICAL_TO_UNLABELLED_USGS** | USGS 05289000 00065 gage height reads the same elevation-scale value (diff 0.0); site alt 927 NAVD88 is a land-surface altitude, not the gage datum |
| Lake Russell (R.B. Russell) (GA) | RBDS1 | HPIRG / Pool | 473.34 | 475 (fullPool, high) | empty | **ELEV_IDENTICAL_TO_UNLABELLED_USGS** | USGS 02188100 00062 (datum unspecified by parameter): n=237, mean diff 0.0, sd 0.001; table empty; pool is CWMS SAS Top of Conservation (NGVD29) |
| Blackshear (GA) | WWCG1 | HPIRZ / Pool | 236.93 | 237 (fullPool, high) | NGVD29=0 | **TABLE_ZERO_ONLY** | table lists the datum with value 0 (gauge zero = datum zero by NWS convention; convention not documented in the NWPS API) |
| Canandaigua Lake (NY) | CNDN6 | HPIRG / Pool | 687.51 | 688 (naturalSurface, low) | NGVD29=0 | **TABLE_ZERO_ONLY** | table lists the datum with value 0 (gauge zero = datum zero by NWS convention; convention not documented in the NWPS API) |
| Lake Poinsett (SD) | PONS2 | HLIRG / Lake Elevation | 1650.84 | 1646 (naturalSurface, low) | NAVD88=0 | **TABLE_ZERO_ONLY** | table lists the datum with value 0 (gauge zero = datum zero by NWS convention; convention not documented in the NWPS API) |
| Lake Sharpe (SD) | BBDS2 | HPIRV / Pool | 1420.7 | 1420 (fullPool, high) | NGVD29=0 | **TABLE_ZERO_ONLY** | table lists the datum with value 0 (gauge zero = datum zero by NWS convention; convention not documented in the NWPS API) |
| Lewis and Clark Lake (SD) | GPDN1 | HPIRG / Pool | 1207.51 | 1207.5 (fullPool, med) | NAVD88=0 | **TABLE_ZERO_ONLY** | table lists the datum with value 0 (gauge zero = datum zero by NWS convention; convention not documented in the NWPS API) |
| Seneca Lake (NY) | GNVN6 | HPIRG / Pool | 444.48 | 445 (naturalSurface, low) | STND=0; NGVD29=-1.33; NAVD88=0 | **TABLE_ZERO_ONLY** | table lists the datum with value 0 (gauge zero = datum zero by NWS convention; convention not documented in the NWPS API) |
| Flannagan Reservoir (VA) | FLAV2 | HPIRZ / Pool | 1394.51 | 1396 (fullPool, high) | NGVD29=1200 | **TABLE_NONZERO_UNEXPLAINED** | table value nonzero while the reading is elevation-sized; value semantics unclear |
| Indian Lake (NY) | INDN6 | HPIRZ / Pool | 1642.39 | 1651.29 (fullPool, high) | NGVD29=1604.23 | **TABLE_NONZERO_UNEXPLAINED** | table value nonzero while the reading is elevation-sized; value semantics unclear |
| Lake of the Ozarks (MO) | LKSM7 | HPIRZ / Pool | 657.4 | 660 (fullPool, high) | NGVD29=560 | **TABLE_NONZERO_UNEXPLAINED** | table value nonzero while the reading is elevation-sized; value semantics unclear |
| Bartlett (AZ) | BRTA3 | HPIRG / Pool | 1787.15 | 1798 (fullPool, high) | NGVD29=1599.46 | **TABLE_CONTRADICTED** | NWS table NGVD29=1599.46 equals USGS 09509502 gage datum, but NWPS = gage height + 1599.46 + 0.54 ft (sd 0.015) over 239 hours: unexplained constant |
| Lake Vermilion (MN) | LVOM5 | HPIRG / Pool | 56.74 | 1350 (naturalSurface, low) | empty | **LOCAL_OR_UNRELIABLE** | coded HPIRG ("Pool") but reads 56.7, a local scale; true surface about 1,300 ft |
| Scituate Reservoir (RI) | SCIR1 | HPIRZ / Pool | 279.11 | 284 (fullPool, high) | MHW=0 | **LOCAL_OR_UNRELIABLE** | table lists MHW=0 (a tidal datum) for an inland reservoir |
| Topaz Lake (NV) | TOPN2 | HPIRG / Pool | 4983.28 | 5000.38 (fullPool, high) | empty | **LOCAL_OR_UNRELIABLE** | USGS 10297000 00062 reads 83.31; USGS lists gage datum altitude 4900.00 LMSL (not NGVD29/NAVD88): NWPS = 4900 + 00062 |
| Crescent Lake (FL) | CELF1 | HGIRP / Stage | 1.68 | 4 (naturalSurface, low) | NAVD88=0 | **STAGE_CODE** | HG "Stage" |
| Liberty Reservoir (MD) | MFEM2 | HGIRR / Stage | 410.86 | 420 (fullPool, high) | empty | **STAGE_CODE** | HG "Stage" |
| American Falls Reservoir (ID) | AFRI1 | HPIRG / Pool | 4310.58 | 4354.5 (fullPool, high) | empty | **NO_TABLE_NO_CHECK** |  |
| Badin Lake (NC) | BADN7 | HPIRZ / Pool | 540.27 | 541.1 (fullPool, high) | empty | **NO_TABLE_NO_CHECK** |  |
| Burton (GA) | TIGG1 | HPIRZ / Pool | 1864.78 | 1866.6 (fullPool, high) | empty | **NO_TABLE_NO_CHECK** |  |
| Cayuga Lake (NY) | CAYN6 | HPIRZ / Pool | 383.7 | 381.9 (naturalSurface, low) | empty | **NO_TABLE_NO_CHECK** |  |
| Crab Orchard Lake (IL) | CODI2 | HPIRG / Pool | 404.86 | 405 (fullPool, high) | empty | **NO_TABLE_NO_CHECK** |  |
| Devil's Kitchen Lake (IL) | DKLI2 | HPIRG / Pool | 508.08 | 510 (fullPool, high) | empty | **NO_TABLE_NO_CHECK** |  |
| High Rock Lake (NC) | HGRN7 | HPIRZ / Pool | 650.63 | 655 (fullPool, high) | empty | **NO_TABLE_NO_CHECK** |  |
| Keuka Lake (NY) | KKPN6 | HPIRZ / Pool | 713.6 | 715 (naturalSurface, low) | empty | **NO_TABLE_NO_CHECK** |  |
| Lake Gaston (VA) | GASN7 | HPIRZ / Pool | -999 | 200 (fullPool, high) | empty | **NO_TABLE_NO_CHECK** | NWPS primary -999 at fetch (missing); operator Dominion; stageflow last value 199.56 |
| Lake Petenwell (WI) | PETW3 | HPIRP / Pool | 923.21 | 923.9 (fullPool, high) | empty | **NO_TABLE_NO_CHECK** |  |
| Neely Henry (AL) | RGLA1 | HPIRZ / Pool | 507.46 | 508 (fullPool, high) | empty | **NO_TABLE_NO_CHECK** |  |
| Oconee (GA) | WDMG1 | HPIRZ / Pool | 434.32 | 435 (fullPool, high) | empty | **NO_TABLE_NO_CHECK** |  |
| Oneida Lake (NY) | CLEN6 | HPIRG / Pool | 368.61 | 369 (naturalSurface, low) | empty | **NO_TABLE_NO_CHECK** |  |
| Pleasant (AZ) | LKPA3 | HPIRR / Pool | 1652.37 | 1702 (fullPool, high) | empty | **NO_TABLE_NO_CHECK** |  |
| Rainy Lake (MN) | FFCQ6 | HPIRP / Pool | 1107.02 | 1108 (naturalSurface, low) | empty | **NO_TABLE_NO_CHECK** |  |
| Sinclair (GA) | SNCG1 | HPIRZ / Pool | 338.11 | 340 (fullPool, high) | empty | **NO_TABLE_NO_CHECK** |  |

## 5. Direct answers

**Gauges that truly publish a pool elevation in a stated datum.** None is stated by NWS in a documented way. Those where an independent labelled source reproduces the number, so the datum is known from that source: John Redmond, Canton, Kaw, Tenkiller, Skiatook, Moomaw (CWMS location NGVD29); Youghiogheny (62615, NAVD88; CWMS NAVD88); Herrington (62614, NGVD29); Ute (62615, NAVD88); Priest (NGVD29 via the table value). Those that merely say "datum, value 0": Blackshear, Sharpe, Lewis and Clark (and Canandaigua, Seneca, Poinsett, which are natural surfaces with no pool).

**Stage with a known gage-zero elevation.** Crescent Lake FL (HG, NAVD88 0, natural surface, not a pool), Liberty Reservoir MD (HG reads 410.86, elevation-sized, but no table: HG is not elevation by rule, so UNKNOWN). Bartlett's table value is the stage gauge zero (matches USGS) but the NWPS series adds a further 0.54 ft, so it is not usable without NWS/SRP clarification. None qualifies, because no gage-zero is explicitly converted.

**Unknown.** All others: 16 with an empty datum table and no cross-check (Neely Henry, Pleasant, Burton, Oconee, Sinclair, American Falls, Crab Orchard, Devil's Kitchen, Badin, High Rock, Rainy, Cayuga, Keuka, Oneida, Petenwell, Gaston), the table-nonzero/contradicted group, and the local-scale gauges.

## 6. Unlock count and exact external evidence needed

| Path | Lakes | Evidence on file | Still needed |
|---|---|---|---|
| Rebind to CWMS Elev series (same-source rule) | 6 | numerical identity + CWMS location datum NGVD29 | decision to rebind in Lake Brain; none external |
| Rebind to USGS 62615 or CWMS (Youghiogheny) | 1 | identity + 62615 = NAVD88 + CWMS pool location NAVD88 | decision to rebind |
| Pool datum for Herrington (KU), Ute (NM ISC), Priest (IDWR) | 3 | series datum known | the operator document for the pool figure must state its datum |
| Russell (Hartwell method) | 1 | NWPS = USGS 00062; CWMS pool NGVD29 | paired 00062 vs CWMS Elev series (CWMS series was empty) |
| Everything else | 22 | none usable | per-gauge: NWS (WFO/RFC) confirmation of the datum semantics of the HP product and of the `value` column; the operator's statement of the pool datum |

Exact request to NWS (unsent): *"For NWPS gauge <lid>, is the observed HP/HL product an elevation, and in which vertical datum (NGVD29 or NAVD88)? What does the 'value' in datums.vertical represent (elevation of gage zero in that datum)? Please correct the empty or inconsistent tables for the gauges listed."* Plus, per lake, the operator confirmation of the pool datum.

## 7. Proposals recorded

See `proposals/provider_rules.json`: `nwps` provider UNKNOWN; a SAME_SOURCE rule for the 6 CWMS-identical lakes (conditional on rebinding the live source); a SAME_DATUM (NAVD88) rule for Youghiogheny (conditional on rebinding to USGS 62615 or CWMS); all other NWPS lakes UNKNOWN with the class as the reason.
