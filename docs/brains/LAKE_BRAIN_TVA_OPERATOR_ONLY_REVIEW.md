# Lake level: TVA mainstem lakes as operator-only (review, 2026-11-20)

**Decision (owner, 2026-11-20, Sector_Ops #45):** the TVA lakes do not need a second, independent gauge; TVA is a credible source.
This reverses decision 2 of 2026-11-02 for **Guntersville|AL, Wheeler|AL, Wilson|AL and Pickwick Lake|TN** only. They join the
customer Lake-level list (`customer_lake_level_eligible.json` = `LakeLevelEligibility.validatedLakeIds`) as an **operator-only**
class (`operatorOnlyLakeIds`): the level is TVA's own reading, with no independent check. Lake Hartwell|SC is not part of this.

Nothing here changes a gate, threshold, the Lake Beta validation verdicts or the customer copy schema (`sector-customer-lake-level-v1`).
Being listed opens nothing by itself: Lake must be BETA, `PUBLISHER_CUSTOMER_LAKE_LEVEL=1`, the copy must be fresh, and the Engine
reads copies only with `SECTOR_LAKE_LEVEL_OUTPUT=1` and the Brain reader.

## Why there is no second gauge

Every other published series for these pools repeats TVA (NWS NWPS GVHA1 matched TVA 1,311 of 1,312 hours; IEM HADS is TVA's
transmitter; NWS RVDHUN daily reports; the CWMS `Pickwick-Lake…Raw-TVA` series). USACE does not publish these TVA projects, USGS has no
pool gauge there, and TVA keeps no separate lock elevation (Sector_Ops #45, 2026-11-05/06). Research note: Sector project doc
`claude/tva-lake-levels-research.md` (2026-11-20).

## Source (already bound; unchanged)

TVA REST `observed-data-48-hours/{id}` (hourly headwater, end-of-hour stamps; "Midnight" is 00:00 of the next day) and
`operating-guide/{id}` (GuideCurve, TopOpZone, BtmOpZone, TopOfGates). Ids: Guntersville GVDA1, Wheeler WHLA1, Wilson WLSA1,
Pickwick PICT1 (`brains/lake/runtime/LakeBrain/LakeSourceBindings.swift`).

## History (from `jobs/lake-brain/history/BACKFILL_LOG.md`, backfill 2026-10-13; quoted, not re-run)

| Lake | span | complete years | baseline status |
|---|---|---|---|
| Guntersville | 2005-01-30 to 2026-10-13 | 17 | SUFFICIENT |
| Wheeler | 2005-11-23 to 2026-10-13 | 18 | SUFFICIENT |
| Wilson | 2005-01-30 to 2026-10-13 | 18 | SUFFICIENT |
| Pickwick | 2003-01-14 to 2026-10-13 | 16 | SUFFICIENT |

All four clear SUFFICIENT (≥ 5 years) and the VERY_UNUSUAL gate (≥ 15 years).

**Gaps left unfilled, not estimated:** 2021-10-01 to 2022-10-27 (392 days) for Guntersville, Wheeler and Wilson; Pickwick 2005-01-14 to
2005-11-22 and 2014-04-17 to 2019-10-07.

**History vs live (consistency):** the composite's HADS local-midnight values against the live TVA operating-guide rows,
2025-01-01 to 2026-10-13: n = 647 per lake; mean abs 0.0012 / 0.0014 / 0.0019 / 0.0026 ft (Guntersville / Wheeler / Wilson /
Pickwick); median and p95 0.000; max 0.257 / 0.170 / 0.240 / 0.220 ft; days differing > 0.05 ft: 5 / 7 / 9 / 8. The TVA guide value wins
by rule on shared days. A fresh re-run against today's live feed was **not** done here (no network to TVA from this session);
the next prospective ledger scoring covers it.

**0.1 ft RVDHUN rows stay out of the rate statistics:** `LakeLevelBaseline.lowResolutionSourcePrefix = "nws:rvd"`; the baseline builder
skips any day pair touching a `nws:rvd…` row when building the |Δ24h| climatology (`LakeLevelBaseline.swift`, and
`LAKE_BRAIN_RULES_V2_RESULTS.md`). They still feed the level climatology (shift 0.03–0.10 ft).

## Datum, guide curve and flood pool

- TVA publishes "feet above mean sea level" without naming a datum; recorded as **inferred NGVD29, not stated by TVA**. The level is
  compared only with TVA's own guide from the same system, so the comparison is self-consistent. NAVD88 − NGVD29: Guntersville
  +0.535, Wheeler +0.125, Wilson +0.151, Pickwick −0.046 ft (matters only against NAVD88 sources or bathymetry).
- **Wilson** has an operating zone only; TVA publishes no guide curve for it.
- `TopOfGates` is not a flood pool, so `floodPoolState` is **UNKNOWN** for these lakes.

## Known risks and follow-ups (not in this change)

1. **Credit "Source: TVA" in the app.** The customer copy has no source field; adding one would change `sector-customer-lake-level-v1`.
   The app can label it from `operatorOnlyLakeIds` instead (follow-up for iOS/Web).
2. iOS `TVAGenerationService` places the "Midnight" row 24 h early (open bug; Lake itself handles it correctly).
3. TVA's provisional last day can read high (0.17–0.45 ft at Guntersville on 2026-11-05).
4. Daily-managed pools flip the trend label often (TVA mainstem: 32 % of STABLE days inside a move, 38 % label changes in the v2 results).
5. Written confirmation from TVA of in-app use (with credit) and of the datum; TVA's legal notices restrict only logos and trademarks.
