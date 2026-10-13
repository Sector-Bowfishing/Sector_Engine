# Vegetation Brain — Cross-Brain contracts (shadow)

Rule for every row: **Vegetation reads the upstream Brain's published state, passes its confidence through, and never recomputes or republishes the upstream truth.** Tests: `tests/test_state.py` (context-by-reference, wind/temp/clarity/depth/lake contract tests).

| Brain | Vegetation consumes | Vegetation uses it for | Must NOT |
|---|---|---|---|
| **Lake** (`states/lake`) | `poolAnomalyFt` (= `differenceFromNormalPoolFt`), `confidence`, `asOf`; registry geometry (`geometryConfidence`, `areaKm2`) | inundation context for potential habitat; flooded-shoreline hints (later); geometry tiering | compute or republish water level; keep a competing polygon library |
| **Depth** (`states/depth`, shadow) | `tier` (A/B/C/D/UNKNOWN), `evidenceKind` (`measured`/`contour`/`modeled`/`proxy`), effective depth bounds, shallow zones | **potential habitat only**, and only tier A/B/C measured/contour | infer submerged vegetation from depth; use GLOBathy/modeled depth (`assert_allowed_potential_basis` refuses it) |
| **Water Clarity** (`states/waterClarity`) | `secchiM` / clarity class, optical confidence | modify confidence/observability; Canfield colonisation ceiling input | turn clear water into a detection; invent clarity; edit Clarity code |
| **Water Temp** (`states/waterTemp`) | surface temperature / degree-day context | seasonal back-testing context (future, after the observation back-test) | calculate a competing temperature model; set seasonal state from temperature alone (test) |
| **Wind** (`states/wind`) | `surfaceDisturbed` flag (and later fetch/wave context) | observation-quality input: stricter SWIR limit → `GLARE`; confidence × 0.85 | contain wind science |
| **Biological** | nothing flows in; Biological READS Vegetation | owns "which fish prefer which vegetation"; consumes `presence/broadType/coverageClass/seasonalState/age/confidence` into its `vegetationDensity` driver | embed fish behaviour, species, or preference in Vegetation (test: no species strings) |
| **Intelligence** | nothing flows in | reads `forIntelligence` (see Intelligence contract) | — |

## Input shapes (read-only context passed to `build_state`)
```jsonc
{"lake":    {"poolAnomalyFt": 1.5, "confidence": "high", "asOf": "..."},
 "depth":   {"tier": "B", "evidenceKind": "contour", "shallowShare": 0.3},          // absent until Depth is live
 "clarity": {"secchiM": 1.8, "confidence": 0.7, "region": "FL"},
 "temp":    {"waterTempF": 71.0},
 "wind":    {"surfaceDisturbed": false}}
```
If an upstream Brain is absent, the corresponding output is `NOT_EVALUATED` / unchanged — Vegetation never substitutes a model of its own.

## Dependency status (from `jobs/README.md` on the adoption baseline and the Depth foundation branch; not re-verified live this cycle)
| Upstream | State | Effect on Vegetation |
|---|---|---|
| Lake | `lake-brain` is orchestrator-triggered for 5 pilot lakes; the geometry registry is published (621 lakes, 29 without geometry) | geometry tiering live; pool anomaly available only for pilots |
| Depth | shadow foundation (`feat/depth-brain-foundation`); no live `states/depth` | potential habitat `NOT_EVALUATED` (`DEPTH_BRAIN_UNAVAILABLE`) |
| Clarity | `water-clarity-brain` is MANUAL by decision (not deployed); fleet Secchi is not published | potential habitat `NOT_EVALUATED` (`CLARITY_UNAVAILABLE`); clarity confidence not applied |
| Water Temp | `water-temp-brain` publishes 621 lakes (orchestrator) | not consumed until the seasonal back-test passes |
| Wind | `wind-hourly` writes the wind slot hourly (candidate science) | a `surfaceDisturbed` flag is not defined by Wind yet; the GLARE guard is inactive until Wind publishes one |
