# Vegetation Brain — State contract (v1, shadow)

Schema id `sector-brain-vegetation-state-v1` · slot `vegetation` (`/lakes/{k}/states/vegetation`, `/lakeFleet/{k}/readiness/vegetation`, snapshot field `vegetation`; reserved by `BRAIN_PLATFORM_CONTRACT.md` §2). Implementation: `jobs/vegetation-brain/vegetation_brain/state.py`; vocabularies in `contract.py`. **Shadow only: nothing is written live; there is no live writer.**

## 1. Principles
1. V1 observes **surface-reaching aquatic vegetation only**. Submerged vegetation is `NOT_OBSERVABLE` and `submergedVegetation.observed` is always `false`.
2. **Unknown is not none.** Unreliable evidence is `UNKNOWN` with a reason code (`REFUSALS`), never `NOT_OBSERVED`.
3. **Vegetation publishes plant/environment state only.** Depth, water level, optical water state, temperature, wind, fish preference and the recommendation belong to other Brains (see `VEGETATION_CROSS_BRAIN_CONTRACTS.md`).
4. Density and seasonal states are **withheld** until their pre-registered gates pass.
5. Every output carries evidence kind, observation date/age, confidence and provenance.

## 2. Shape (names follow Depth/Clarity conventions: `kind`, `freshness`, `provenance`, `limitations`)
```jsonc
{
  "lakeId", "brainId": "vegetation", "slot": "vegetation", "schemaVersion": 1, "stateSchema": "sector-brain-vegetation-state-v1",
  "kind": "observed | unavailable",              // observed only when presence is PRESENT or NOT_OBSERVED
  "headline": "Likely surface vegetation",       // closed set, see §4
  "modelVersion": "surface-vegetation-observer-v1", "brainVersion": "...", "generatedAt",
  "surfaceVegetation": {
    "status": "PRESENT | NOT_OBSERVED | UNKNOWN", "statusReason",
    "coverageClass": "SPARSE|MODERATE|DENSE|UNKNOWN|NOT_CALIBRATED",   // NOT_CALIBRATED until the density gate passes
    "observedPlantCells", "readInteriorCells", "interiorCells",          // counts, never percentages
    "broadType": "SURFACE_REACHING_MIXED | UNKNOWN", "typeBasis": "NOT_CLASSIFIED",
    "observedAt", "ageDays", "source": {"collection", "sceneIds"},
    "confidence": {"level": "NONE|LOW|MEDIUM|HIGH", "score", "basis": "RULE_BASED_NOT_CALIBRATED", "reasons", "validationState"}
  },
  "submergedVegetation": {"status": "NOT_OBSERVABLE", "observed": false, "reason": "..."},
  "seasonalState": {"state": "EMERGING|GROWING|PEAK|DECLINING|DORMANT|UNKNOWN", "basis", "backtestGate": "PASSED|NOT_PASSED"},
  "observation": {"evidenceKind": "SATELLITE_SINGLE_PASS|SATELLITE_ACCEPTED_PASS|SATELLITE_PERSISTENCE|SURVEY|NONE",
                  "persistence": "MEDIAN_OF_ACCEPTED|INSUFFICIENT|NOT_APPLICABLE", "acceptedScenes", "cloudState", "refusalShares",
                  "isolatedCellsDropped", "lowCoverageFallback", "notes"},
  "potentialHabitat": {"potentialOnly": true, "observed": false, "status": "EVALUATED|NOT_EVALUATED", "reasons", "basis",
                       "maxColonizationDepthFt": {"model": "canfield-1985-*", "centralFt", "lowFt", "highFt", "ciNote"}, "headline": "Potential vegetation habitat"},
  "context": {"consumed": {"lake","depth","clarity","temp","wind"}},   // which upstream states were read; values are not republished
  "validation": {"state": "NOT_VALIDATED | RESEARCH | CALIBRATION | PARTIAL | VALIDATED", "ref": "/validation/vegetation"},
  "geometry": {"tier", "geometryConfidence", "areaKm2", "reasons", "source": "lake-registry (canonical)"},
  "forIntelligence": {...}, "limitations": [...], "freshness": {...platform envelope...}, "provenance": {..., "inputFingerprint"}
}
```
`kind` is a platform state kind (`observed` / `unavailable`). `broadType` never takes `FLOATING_LEAF` / `FLOATING_MAT` / `EMERGENT` in V1 because no validated type classifier exists; the closed vocabulary reserves them for later.

## 3. Refusal / quality reasons (UNKNOWN, never "no vegetation")
`CLOUD, SHADOW, HAZE, GLARE, DARK_WATER, SHORE_ADJACENT, INSUFFICIENT_VALID_PIXELS, SCENE_TOO_OLD, NO_SCENE, ICE_OR_SNOW, NO_GEOMETRY, GEOMETRY_LOW, TOO_NARROW, BLOOM_AMBIGUOUS, PASS_NOT_ACCEPTED, BOTTOM_REFLECTANCE`. Definitions: `contract.REFUSAL_DOC`. `BLOOM_AMBIGUOUS` and `BOTTOM_REFLECTANCE` are reserved (no detector yet) and listed as limitations.

## 4. Product language (closed set; `language.headline`)
| Situation | Words |
|---|---|
| PRESENT, validation ≥ PARTIAL (for the region) | **Surface vegetation observed** |
| PRESENT, validation < PARTIAL (all lakes today) | **Likely surface vegetation** |
| `potentialOnly` product | **Potential vegetation habitat** |
| NOT_OBSERVED on a valid look | No surface vegetation seen on the latest clear look |
| UNKNOWN, stale, or no scene | **No reliable vegetation observation** |

Forbidden in any Brain output or derived copy (enforced by test): "grass is here", any species name (hydrilla, milfoil, lily, lotus, …), "submerged vegetation here/observed", "underwater grass".

## 5. Observer summary (what produces the numbers)
* Pixel rule (production rule): `NDVI(B8A,B4) ≥ 0.30`, plus a **provisional absolute NIR floor** (0.03) that removes dark-water ratio noise (research: 6–10 % of open-water pixels crossed 0.30 from rounding). To be calibrated on negative-control lakes, not on truth lakes.
* Cell (50 m): `plantFraction ≥ 0.5` of seen pixels; ≥ 50 % of the cell must be seen; cells touching the lake edge are `SHORE_ADJACENT` and never claimed.
* Pass acceptance: the scene must read ≥ 50 % of interior cells (fallback ≥ 25 %, flagged).
* Persistence: per-cell **median** over ≥ 3 accepted scenes within ±21 days; otherwise the nearest accepted pass with `persistence: INSUFFICIENT`.
* Forbidden: max / second-highest / votes ≥ 2 composites.
* A **single un-accepted pass is never published** (`PASS_NOT_ACCEPTED`); a **burst check** excludes implausible scenes when ≥ 3 accepted scenes exist.
* Presence: `PRESENT` needs ≥ 3 plant cells after dropping isolated singletons; `NOT_OBSERVED` needs ≥ 50 % of interior cells read.

## 6. Readiness mapping (platform ladder)
`BLOCKED` (geometry missing/LOW area) → `PROFILED` (observable, nothing run) → `CALIBRATION` (shadow observation exists, not validated) → `DEGRADED` (stale or fully refused). `BETA/VALIDATED/PRODUCTION` unreachable until the pre-registered gates pass and Michael approves.

## 7. Freshness
Staleness model `TIME`; observation fresh ≤ 14 days, stale > 45 days (`evidenceStale`); state generated hourly-capable but meaningful at satellite cadence (`staleAfterHours` 72).
