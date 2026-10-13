# Audited fetch tables vs the published Lake Registry — identity and geometry-agreement blocks

Lake Brain owns canonical lake identity and publishes the Lake Registry (`gs://sector-lake-registry`, v1, generated 2026-10-13T20:20Z). Wind does **not** fix identity. Each of the 74 audited fetch tables was cross-checked against the registry (`research/audited_vs_registry.py`, `data/audited_vs_registry.json`): area of the NHD feature the table was built from vs the registry shoreline union, the table's GNIS name vs the directory name, and the registry's `pointFlag` / confidence. **Fifteen audited lakes are blocked** (no bank word of any kind) until Lake Brain resolves them; the manifest enforces it (`exposure_allowed` false; tests).

## A. Lake-identity risk (registry `pointFlag: identity-risk`, confidence LOW) — 6 audited lakes
| Lake ID | Registry evidence | Audited table was built on | Area ratio (registry / table) | Verdict |
|---|---|---|---|---|
| **Andrews Lake\|DE** | directory point 12.7 km from the polygon (allowed 3.0 km) | NHD **"McColley Pond"** (0.232 km²), seed 6.7 km away | **0.36** | **Different water body.** Table unusable. |
| **Griffith Lake\|DE** | 6.3 km; polygon 0.159 km² | NHD **"Killen Pond"** (0.319 km²), seed 6.1 km | **0.50** | **Different water body.** |
| **Hiwassee Lake\|NC** | 8.9 km; registry source OSM; NHD name differs from the directory name | NHD **"Persimmon Lake"** (23.9 km²), seed 8.9 km | 1.02 | **Ambiguous.** The registry's polygon has the same area as the audited feature, so the table may well describe the right reservoir (named "Persimmon Lake" in NHD); the *directory name/point* disagree. Lake Brain must rule. (Earlier note calling it a wrong water body is withdrawn.) |
| **Eagle Lake\|MS** | 4.1 km | NHD "Eagle Lake" (19.5 km²), name matches | 1.00 | Geometry agrees; **directory coordinate is off ≈ 4 km** (also shifts the forecast point) |
| **Long Lake\|ME** | 4.8 km | NHD "Long Lake" (24.4 km²) | 1.00 | same |
| **Sherman Reservoir\|NE** | 4.6 km | NHD "Sherman Reservoir" (9.9 km²) | 1.00 | same |

## B. Audited table disagrees with the registry polygon (area ratio outside 0.8–1.25) — 6 more audited lakes (blocker `auditedGeometryAreaMismatch`)
| Lake ID | Ratio | GNIS name matches directory? | Note |
|---|---|---|---|
| Bowdish Reservoir\|RI | 0.68 | no | possible partial/other feature |
| Watchaug Pond\|RI | 1.36 | no | registry union larger |
| Norris Lake\|TN | 1.40 | yes | table may cover part of the reservoir (arms) — fetch from a partial polygon is unsafe |
| Lake Texoma\|TX | 1.45 | yes | same |
| Roosevelt\|AZ | 1.53 | yes | same |
| Neely Henry\|AL | 1.251 | yes | marginal (limit 1.25) |
These are blocked because a fetch table that covers only part of the water body mis-measures open-water runs; whether the registry or the table is right is Lake Brain's/Wind's joint review.

## C. Noted, not blocking (area agrees; name or confidence differs)
Buckeye Lake OH and DeGray AR (GNIS name differs from the directory name; area ratio 1.00), Sevier Lake UT (registry confidence LOW; area ratio 1.00). Waimaluhia Reservoir HI has no registry geometry (and an untested HI forecast domain): blocked.

## What Lake Brain needs to decide (per lake) and what Wind can supply
1. Which water is the directory entry? (A: name/point vs polygon; B: which polygon is the whole reservoir.)
2. If the polygon is right: correct the directory coordinate (also fixes the forecast sampling point). If the audited feature is right: replace the registry polygon.
Wind can supply: table SHA-256 prefixes (Andrews 8fa2941c3b04, Griffith bc347a2db835, Hiwassee 416877cb8380, Eagle 9c1d73c7bf99, Long 476d44f1951a, Sherman 7582a8d6403d), seed distances, the NHD features used (`data/identity_risk_audited_lakes.json`, `data/audited_vs_registry.json`).

## Wind policy until resolved
No bank labels or exposure shares for these 15 lakes; wind direction/tonight for the six identity-risk lakes should carry "representative point may be off". After Lake Brain publishes a corrected registry version, rebuild the manifest (`python -m sector_wind.brain.fleet build --registry … --audited-check …`); Wind rebuilds an audited table only if the underlying feature changed.
