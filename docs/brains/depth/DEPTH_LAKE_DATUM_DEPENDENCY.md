# Depth -> Lake Brain: datum stamping dependency (APPROVED interface; Lake Brain NOT edited)

> **2026-10-14:** Michael approved this as the desired Lake interface (datum, datumAuthority, datumConfidence, referencePoolDatum, datumRelationship). Depth does not edit Lake Brain from this branch. Lake-side work is a separate Lake session; Depth re-runs its fleet analysis the moment Lake publishes more reviewed states.

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


## Update 2026-10-14 (long-run campaign): what Lake Brain still owns, and two findings

* **Duke**: 8 lakes are now defensible. Depth accepts a level in either documented frame (the 100-based scale, `shift = scale - 100`, or absolute feet against the full-pond elevation) and refuses one that is in neither. Lake Brain should publish whichever Duke returns and stamp NGVD29 (Duke's `Elevation` field says NGVD 29); Depth needs no change when it does.
* **New defensible lakes without a live Lake state** (the Depth side is ready; Lake owns the level): Reclamation and Duke lakes in `candidates.json` with `shiftPossible` and `rollout` not PILOT_VERIFIED. A new Lake state triggers a publish by fingerprint change; nothing else is needed from Depth.
* **Finding (Lake Brain, not changed here): Hartwell's `observationTime` runs about one hour ahead of reality.** On 2026-10-14 at 05:26 UTC Lake published Hartwell with `observationTime` 06:00Z while `generatedAt` was 05:24Z (Guntersville/Wheeler/Wilson/Pickwick show 05:00Z). The pattern fits a fixed EST (-5 h) offset applied during EDT. Depth refuses an observation more than 0.25 h in the future (`OBSERVATION_IN_FUTURE`), so Hartwell flaps to `unavailable`/DEGRADED for about the first 45 minutes of every hour. Depth does not widen its tolerance (the owning Brain should fix the timestamp; see the freshness-authority rule candidate in `DEPTH_BRAIN_MODEL_INPUTS.md`).
* **Finding (Lake Brain): 7 NWPS rebinds** remain exactly as listed above; they are Lake-side.
