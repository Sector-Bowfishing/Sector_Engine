# Vegetation Brain — Score v1 PROPOSAL (not adopted)

**PROPOSAL ONLY.** Vegetation has no official score and no `/scores/vegetation`; nothing here is wired into `brain-scores`, `control.py` or Ops. Ratification, weights and critical dimensions are Michael's decision. It follows the shape of the platform scorer (`jobs/brain_platform/sector_brain_platform/scoring.py`: dimensions with weights summing to 100, **gates cap, never add**, UNKNOWN stays unknown and is excluded from completeness).

## 1. Production policy (given)
`overall ≥ 8.0` **and** every required/critical dimension `≥ 7.5`.

## 2. Dimensions (weights sum to 100)

| # | Dimension | Weight | Critical | What it rewards (and the anchor for ≥ 7.5) |
|---|---|---|---|---|
| 1 | **Source authority** | 12 | **Yes** | Observations rest on an open, documented sensor with a validated method; truth sets are authoritative and independent (agency surveys, EPA NLA). ≥ 7.5: ≥ 3 independent truth families in use, licences cleared |
| 2 | **Spatial accuracy** | 12 | **Yes** | Registry geometry (canonical) at ≥ MEDIUM confidence; measured cell localisation; shoreline/arm handling. ≥ 7.5: measured cell-level localisation error and shore handling validated; ≥ 85 % of observable lakes on HIGH/MEDIUM geometry |
| 3 | **Presence accuracy** | 18 | **Yes** | Pre-registered precision/recall/F1/IoU, shore-matched, leave-one-lake-out, open-water FPR. ≥ 7.5: the `PARTIAL` gate passed in ≥ 3 regions |
| 4 | **Validation** | 16 | **Yes** | Independence, breadth, pre-registration, negative controls, calibration of confidence. ≥ 7.5: ladder state `PARTIAL` with the VALIDATED breadth gaps documented, or `VALIDATED` |
| 5 | **Provenance & confidence** | 10 | **Yes** | Every cell/lake carries evidence kind, scene ids, age, refusal reason, calibrated confidence. ≥ 7.5: confidence reliability curve measured |
| 6 | **Density usefulness** | 8 | Only if exposed | Density classes validated (kappa/within-one gates). Not exposed ⇒ scored as built (low), not critical |
| 7 | **Seasonality** | 8 | Only if exposed | Lake-specific back-tested seasonal states beating the calendar baseline. Not exposed ⇒ scored as built |
| 8 | **Fleet coverage (truth-backed)** | 8 | No | Share of lakes that are *observable AND in a validated regime AND recently observed* — **not** raw observability. Large coverage with low truth scores low |
| 9 | **Freshness** | 4 | No | Share of observed lakes with an observation ≤ 14 days old; stale/UNKNOWN lakes count against it |
| 10 | **Scalability** | 4 | No | Pipeline cost/automation/idempotence; orchestrator-ready; canonical geometry; no manual steps |

Total 100. (Research rubric critical set was authority, spatial, presence, density, validation, provenance; density is moved to "critical if exposed" because Vegetation V1 deliberately does not expose density until its gate passes.)

## 3. Gates (cap the overall; evaluated before any increase)
| Gate | Fires when | Cap |
|---|---|---|
| `NOT_VALIDATED` | validation ladder state `NOT_VALIDATED`/`RESEARCH` | 3.0 |
| `CALIBRATION_ONLY` | state `CALIBRATION` | 5.0 |
| `PARTIAL_REGIONS` | state `PARTIAL` | 7.5 (PARTIAL cannot reach production alone) |
| `SPECIES_CLAIM` | any output names a species from multispectral data | 0 on authority |
| `SUBMERGED_OBSERVED` | any "observed submerged" output from Sentinel-2 fleet processing | 2.0 |
| `MODELED_DEPTH_HABITAT` | potential habitat derived from GLOBathy/modeled depth | 4.0 |
| `UNKNOWN_AS_NONE` | a refusal published as "no vegetation" | 4.0 |
| `MAX_COMPOSITE` | a max/second-highest/≥2-vote composite in production | 5.0 |
| `NO_PROVENANCE` | outputs without evidence kind/age/refusal reason | 4.0 |

## 4. Things the score must NOT reward
* fake species identification · unvalidated submerged detection · GLOBathy-derived habitat · large raw fleet coverage with low truth · percentages without calibration · a seasonal state from a calendar rule.

## 5. Evaluation at the current state (illustration; research-only, from the maturity inputs)
authority 3.5 · spatial 2.0 · presence 3.0 · validation 3.0 · provenance 3.0 (before this cycle's implementation work) · density 1.0 · seasonality 2.0 · coverage 0 · freshness 0 · scalability 4.0 ⇒ weighted ≈ 2.3, further capped to ≤ 3.0 by `NOT_VALIDATED`. Production policy not met; critical dimensions below 7.5: authority, spatial, presence, validation, provenance. The live research maturity tracker is `jobs/vegetation-brain/vegetation_brain/maturity.py` (`official: false`).

## 6. Adoption steps (none taken)
1. Michael ratifies dimensions, weights and the critical set. 2. Add `score_vegetation()` to `scoring.py` and `vegetation` to `ALL_BRAINS` behind a shadow flag that keeps it out of Engine roll-ups (same follow-up as Depth). 3. Publish `/scores/vegetation` only after the Brain is registered with Michael's approval. 4. Re-baseline after the first fleet shadow run.
