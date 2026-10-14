# BRAIN_SPEC — Vegetation Brain (Sector Brain Model v1 conformity, 2026-10-14)

Status: **SHADOW**, internal. Not registered live, not scheduled, not deployed, no live writer. Research maturity 2.70 (**not** an official score; `scoreStatus: NOT_ESTABLISHED`).

| Section | Content |
|---|---|
| **Brain ID** | `vegetation` (slot `vegetation`; reserved in `BRAIN_PLATFORM_CONTRACT.md` §2) |
| **Mission** | Tell a bowfisher whether surface-reaching aquatic vegetation was seen on a lake, where, how old the look is, and how sure Sector is — and say UNKNOWN when it cannot look |
| **Bowfishing decision improved** | WHERE to look (cover edges, weed beds, pads), WHAT is limiting (cover that blocks boats/arrows), WHAT changed (age of the look). *Habitat value vs shootability is Intelligence's synthesis.* |
| **Owns** | surface-vegetation presence/extent evidence, broad class (V1: `SURFACE_REACHING_MIXED`), observation date/age, evidence kind, confidence, refusal reasons, provenance, `potentialOnly` habitat evidence |
| **Does not own** | depth (Depth), water level (Lake), optical water state (Clarity), temperature (Water Temp), wind and glare (Wind), fish preference for vegetation (Biological), the recommendation (Intelligence), geometry (Lake Registry) |
| **Upstream dependencies** | Lake Registry geometry (required); shared Clarity lake-surface pass evidence (pilot input; Sentinel-2 L2A underneath; a per-cell plant-fraction raster from Clarity is requested); Lake pool anomaly, Depth tier/evidenceKind, Clarity Secchi, Wind `surfaceDisturbed` (all optional context, none live today) |
| **Downstream consumers** | Sector Intelligence (`forIntelligence`), Biological (`vegetationDensity` driver), Sector Ops (registry fields). No customer surface |
| **Canonical runtime state** | `/lakes/{k}/states/vegetation` (`sector-brain-vegetation-state-v1`): `surfaceVegetation`, `submergedVegetation` (always `NOT_OBSERVABLE`), `seasonalState` (UNKNOWN), `observation`, `potentialHabitat` (`potentialOnly`), `claimMaturity`, `validation`, `geometry`, `forIntelligence`, `limitations`, `freshness`, `provenance` — see `VEGETATION_STATE_CONTRACT.md`. Compact; no raster or research artifact is a runtime input |
| **Confidence model** | rule-based, **not calibrated** (`RULE_BASED_NOT_CALIBRATED`): evidence kind × read coverage × geometry confidence × Clarity/Wind modifiers, **capped by validation state** (`NOT_VALIDATED` ⇒ ≤ 0.45) |
| **UNKNOWN / refusal policy** | cloud, shadow, haze, glare, dark water, shore-adjacent, bloom-ambiguous, ice, no scene, no geometry, … ⇒ `UNKNOWN` + reason code; **never** "no vegetation". `NOT_OBSERVED` only after a genuine look |
| **Freshness policy** | observation fresh ≤ 14 d, evidence-stale > 45 d; state `staleAfterHours` 72 (TIME) |
| **Execution model** | below |
| **Input fingerprint** | scene ids, evidence kind, plant-cell count, geometry tier/version, Wind flag, Clarity Secchi, Depth tier, manifest and Brain versions (`state.input_fingerprint`; `state.plan()` returns PUBLISH/SKIP; tested) |
| **Score dimensions** | authority, spatial, presence, density, seasonality, submerged, validation, provenance, coverage, scalability (`maturity.py`); Score v1 proposal adds freshness (`VEGETATION_SCORE_V1_PROPOSAL.md`) |
| **Critical dimensions** | authority, spatial, presence, validation, provenance; density and seasonality only when exposed |
| **Claim-level validation requirements** | Claim table below |
| **Lifecycle state** | SHADOW (technical RESEARCH entry met; published validation state `NOT_VALIDATED`) |
| **Production requirements** | overall ≥ 8.0 and every critical ≥ 7.5 (unchanged); PARTIAL gate on fresh truth; product-slice decision; Ops presentation fixed; orchestration and cost review |
| **Storage budget** | research data dir ≤ 5 GB review threshold; any dataset > 2 GB needs a reason. Currently 0.51 GB. Store the recipe: manifests, URLs, scripts, result tables |
| **Research stop conditions** | no further research without a Level-3 claim question; the next evidence is fresh truth (EXTERNAL SOURCE/FIELD), not more literature or tuning |
| **Ops summary** | `ops_summary.registry_extras` (computed, `official:false`); gaps in `VEGETATION_OPS_VISIBILITY_GAP.md` |
| **Customer exposure policy** | none. When exposed: only "Likely surface vegetation" / "Surface vegetation observed" (after PARTIAL) / "Potential vegetation habitat" / "No reliable vegetation observation"; never species, submerged-observed, density percentages |
| **Cost expectations** | no schedule; fingerprint no-op; compute only for lakes whose inputs changed; reuse Clarity's Sentinel-2 reads (measured: ≈ 7.6 MB per 5 km scene read; 30–52 % of clear scenes pass acceptance) |
| **Runtime expectations** | state is a few KB; the observer is offline/batch only and must never run on a customer or Ops request; research artifacts are never read at runtime |

## Claim table (Level 1 / 2 / 3) and claim-level maturity
| Claim | Level | Required validation | Claim maturity now |
|---|---:|---|---|
| Agency vegetation observation shown as-is (FWC, SFWMD littoral, TVA when obtained) | 1 | source, date, units, licence | **NOT_ASSESSED** (not built; Michael's product-slice decision) |
| Geometry tier (observable / mixed / too small / none) | 2 | formula, edge cases | **VERIFIED** |
| Observation age / freshness | 2 | date arithmetic | **VERIFIED** |
| Surface vegetation presence (satellite) | 3 | PARTIAL/VALIDATED gates on independent truth | **NOT_VALIDATED** (SHADOW) |
| Broad type, density, seasonal state | 3 | type: classifier validation; density: kappa/within-one; seasonal: strengthened baselines | **NOT_ASSESSED** / **NOT_VALIDATED** |
| Potential habitat | 3 | Depth tier A/B/C + Clarity + field check | **NOT_ASSESSED** (`potentialOnly`) |
| Submerged vegetation observed | 3 | — | **NOT_OBSERVABLE** (never published) |

A failing Level-3 claim does not disable the truthful Level-1/2 fields (agency observations, geometry tier, age).

## Execution / scheduling matrix
| Component | Current trigger | Recommended trigger | Needs schedule? | Fingerprint? | Reason |
|---|---|---|---|---|---|
| Provider ingestion — Sentinel-2 scenes | **none: Vegetation consumes the shared Clarity per-pass evidence** (`vegetation_brain/shared.py`; pilot 2026-10-14: 2.2 MB, 1.85 s CPU for 8 lakes) | Clarity's pass detection fires the fingerprint change; Vegetation `plan()` publishes or skips | No new schedule | scene ids + observed share | one ingestion path, many consumers; no second reader |
| Provider ingestion — agency vegetation (Level 1) | none | manual refresh on survey publication; annual | No | source date | surveys change yearly |
| Brain compute (observer + state) | manual/dry-run | dependency-driven: new accepted pass for a lake, registry geometry version, Wind/Clarity/Depth state change | No | yes (`plan()`) | no change ⇒ no work; affected lake only |
| Prospective validation logging | none | timed snapshots only when a fresh-truth protocol exists | Maybe, later | frozen predictions | needed only if bowfisher/field truth arrives (shared field framework) |
| Score publication | none (no scorer) | platform scorer after a state change, `--if-changed` | No | state fingerprint | scoring is shared-platform work |
| Control-plane publication | none | existing orchestrator after a state change | No | yes | Ops reads cached control state |
| Maintenance / staleness | none | cheap hourly staleness rollup in the orchestrator (already exists) | No new job | n/a | TIME staleness only |

## Rubric audit (directive §13)
Mismatches found (documented as proposals; rubric NOT changed): gate (c) NLA belt statistic is not co-located with shoreline plots; presence/density dimensions reward dense polygon truth that does not exist for reservoirs while V1 refuses density/type/submerged by design; seasonal *labels* may be unnecessary for the product; coverage counts observed lakes instead of useful (pilot/agency-backed) lakes. See `VEGETATION_PRODUCTION_READINESS_MATRIX.md` §4.

## Cross-Brain field compatibility (future Sector Field Validation Framework)
One trip could give Vegetation: `surfaceVegetationObserved` (yes/no/unsure), `approxCategory` (none/scattered/moderate/dense/mat), `typeHint` (pads/reeds/mat/other), photo optional, with trip id, lake, time, GPS. Vegetation will not build its own field program.
