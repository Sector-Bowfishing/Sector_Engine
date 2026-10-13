# Vegetation Brain — Fleet observability (recomputed against the canonical Lake Registry)

**Shadow / internal.** Data: [`data/vegetation_fleet_observability.csv`](data/vegetation_fleet_observability.csv), built by `python -m vegetation_brain fleet` from `registry/lakes.v1.json` (geometryVersion `v1`, generated 2026-10-13T20:20:54Z, sha256 `8ae465ab2e39ca78…`). Vegetation keeps **no polygon library of its own**.

Observability means: *can the SURFACE-vegetation observer look at this lake?* It says nothing about submerged vegetation, which no tier can observe.

## Rules
| Condition | Tier | Readiness |
|---|---|---|
| registry `geometry: null` | UNKNOWN | BLOCKED (`NO_GEOMETRY`) |
| area ≥ 5 km² | HIGH | PROFILED |
| 0.5 ≤ area < 5 km² | MEDIUM (`MIXED_PIXELS`: 10 m pixels mix with shore) | PROFILED |
| area < 0.5 km² | LOW (`TOO_NARROW`) | BLOCKED |
| geometryConfidence `LOW` | one tier lower (`GEOMETRY_LOW`) | unchanged unless the new tier is LOW and area < 0.5 |

## Result (621 lakes)
| | Research (legacy polygons) | **Canonical registry** |
|---|---|---|
| HIGH | ~498 | **476** |
| MEDIUM | ~86 | **83** |
| LOW | ~15 | **33** |
| UNKNOWN | ~22 | **29** |

Geometry confidence in the registry: HIGH 404 · MEDIUM 144 · LOW 44 · MISSING 29. 44 lakes are downgraded one tier because their geometry confidence is LOW. 42 lakes are BLOCKED, 579 PROFILED.

### What changed vs the research counts
* 7 more lakes have no geometry (research 22 → 29): **Conowingo Reservoir MD, East Okoboji IA, Ninigret Pond RI, Point Judith Pond RI, Chain O'Lakes IL** newly missing, and **Lake Shafer IN / Lake Waiau HI** (degenerate research polygons are refused by the registry).
* **Buckeye Lake OH** moves LOW → HIGH (the registry replaced the 6-vertex research polygon with the NHD water body).
* 40 lakes are lowered one tier by LOW geometry confidence (19 HIGH → MEDIUM, 21 MEDIUM → LOW).

### By registry region
| Region | HIGH | MEDIUM | LOW | UNKNOWN | Total |
|---|---|---|---|---|---|
| SE | 132 | 8 | 5 | 1 | 146 |
| W | 119 | 13 | 2 | 1 | 135 |
| MW | 82 | 6 | 1 | 14 | 103 |
| NE | 67 | 46 | 19 | 6 | 138 |
| GP | 66 | 8 | 4 | 0 | 78 |
| AK/HI | 10 | 2 | 2 | 7 | 21 |

### Geometry dependencies
* **MISSING (29, cannot be observed):** Great Lakes (Erie ×4, Michigan ×3, Superior ×3, Huron, Ontario), Green Bay, Lake of the Woods, Great Salt Lake, Iliamna, Chickahominy, East Okoboji, Conowingo, Chain O'Lakes, Shafer, Ninigret, Point Judith, and five Hawaiian ponds. Owner: Lake Brain geometry work.
* **LOW confidence (44):** observed only one tier lower and with capped confidence; fixing geometry is a Lake Brain task, not a Vegetation one.
* NE has the most LOW/MEDIUM lakes (small ponds): mixed-pixel density caveats apply there.

## Independent truth join (canonical geometry)
`withIndependentTruth` in the manifest is **0 until the NLA × Sentinel-2 run re-joins sites to the canonical analysis polygons** (research joined to legacy polygons: 69 lakes with an NLA site, 10 with FWC points). That recount is part of the validation report (`docs/brains/vegetation/VEGETATION_MATURITY_REEVALUATION.md`).
