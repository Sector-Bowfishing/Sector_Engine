# Depth -> Lake Brain: datum stamping dependency (request; Lake Brain NOT edited)

Lake Brain owns the lake level and (eventually) the canonical statement of what vertical reference that level is in. Depth only consumes `lakes/{k}/states/lake`. Today (live read 2026-10-13/14):

| Lake | `datum` published | Depth's source of datum knowledge |
|---|---|---|
| Guntersville, Wheeler, Wilson, Pickwick (TVA) | **null** | provider audit: one TVA system for pool and reading (`SAME_OPERATOR_SYSTEM`, NGVD29 inferred, sigma 0.1 ft) |
| Lake Hartwell | `NGVD29` | reviewed override (CWMS location NGVD29 + USGS 00062 pairing) |

Because the state carries no datum for TVA, Depth cannot *verify* the relationship from the live state; it can only refuse when a stamped datum disagrees with the audited one (`LEVEL_DATUM_CONFLICT`). Stamping closes that loop and lets Depth move from inferred to verified without a manifest edit.

## Requested Lake-side contract (additive fields on `states/lake`; no behaviour change for existing consumers)

```jsonc
{ "lakeId": "Guntersville|AL",
  "levelFt": 593.6,                      // existing currentElevationFt (no rename requested; shown for the mapping)
  "referencePoolFt": 595.0,              // the pool the Lake Brain's own difference is taken against (existing normalPoolRef value)
  "referencePoolRef": "engine-directory:fullPoolFt",
  "datum": "NGVD29",                     // vertical datum of levelFt, in {NGVD29, NAVD88, LOCAL, PROJECT, UNKNOWN}; absent = unknown
  "datumAuthority": "operator-document | api-metadata | usgs-parameter-definition | reviewed-pairing | inferred",
  "datumConfidence": "VERIFIED | INFERRED | UNKNOWN",
  "referencePoolDatum": "NGVD29",        // datum of referencePoolFt, if it differs or is separately known
  "datumRelationship": "SAME_SOURCE | SAME_DATUM | SAME_OPERATOR_SYSTEM | CONVERTED | UNKNOWN",
  "datumEvidenceRef": "docs/brains/depth/DEPTH_DATUM_AUDIT.md#...",   // optional pointer
  "generatedAt": "..." }                  // already provided by freshness.generatedAt
```

Rules Depth would apply to the new fields (tests already cover the guards): stamped `datum` that conflicts with the audited datum -> refuse (`LEVEL_DATUM_CONFLICT`); `datumConfidence = INFERRED` never raises Depth above its current confidence; `UNKNOWN` never blocks a lake whose relationship Depth has independently proven; Depth never copies a datum onto a lake that lacks evidence.

## Why Lake Brain, not Depth

* Lake chose the source (TVA REST, CWMS, USGS parameter) and knows its semantics at binding time; Depth re-derives them after the fact.
* Intelligence/Ops get one canonical statement instead of two.

## Other Lake-side items Depth depends on

| Item | Status |
|---|---|
| Fleet bindings live (87 more Depth-defensible lakes need `states/lake`) | `feat/lake-brain-adoption` unmerged; live Lake states = 5 (verified by RTDB read) |
| Guide context (`guideFt`, `differenceFromGuideFt`) | published; Depth copies it into `level.*` for designed-drawdown context |
| Seasonal pool awareness (Hartwell 660 summer / 656 winter) | via guide only; a reference-pool-by-season field would let Depth state "below guide" vs "below summer pool" |
| `datum: null` on TVA states | requested above |

## Addendum (2026-10-14): lakes that resolve only if Lake Brain rebinds

| Lake | Current Lake binding | Rebind target | Evidence | Depth result after rebind |
|---|---|---|---|---|
| John Redmond (KS), Canton (OK), Kaw (OK), Tenkiller (OK), Skiatook (OK), Moomaw (VA) | NWPS pool (HP) | CWMS `Elev` series at the project that holds Top of Conservation | NWPS pool numerically identical to the CWMS Elev series (mean difference <= 0.008 ft, max <= 0.05 ft); CWMS location datum NGVD29 | SAME_SOURCE, sigma 0 |
| Youghiogheny River Lake (MD) | NWPS | USGS 62615 or the CWMS series | NWPS pool identical to USGS 62615 (NAVD88); pool is a CWMS location tagged NAVD88 | SAME_DATUM (NAVD88) |

The NWPS datum tables for these gauges are empty or contradictory (Canton lists NAVD88 0.6 while the feed equals the NGVD29 CWMS series), so Depth will not accept the NWPS-bound series on its own. `accepted_provider_rules.json` lists them under `heldWithReason`. Source detail: `DEPTH_NWPS_DATUM_AUDIT.md`.
