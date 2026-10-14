# Brain Lifecycle Model

The lifecycle describes the **Brain as a whole**. It is not a score, not claim maturity, and not the per-lake readiness ladder.

## 1. Canonical lifecycle (v1)
```
RESEARCH → PROFILED → SHADOW → CALIBRATION → PRODUCTION_READY → PRODUCTION
```
Off-ladder conditions: `BLOCKED`, `DEGRADED`, `RETIRED` (a Brain can be on a rung *and* have a condition; a condition is never a promotion).

| Stage | Exact meaning | Entry requirement | May customers consume it? |
|---|---|---|---|
| `RESEARCH` | question defined, evidence being gathered; no runtime state | a Brain Spec exists | no |
| `PROFILED` | per-lake/per-scope profile or inventory published; the Brain knows what it covers and what it lacks | profile node(s) published, coverage known | no |
| `SHADOW` | runs end-to-end and publishes compact canonical state for pilot scope; output is internal; not scheduled customer-facing | state contract + freshness + provenance + claim table published | no (internal/Ops only) |
| `CALIBRATION` | running on live/prospective data with a pre-registered validation plan; thresholds may still move | validation plan registered; prospective ledger or equivalent running | no, or flagged-unvalidated only |
| `PRODUCTION_READY` | meets the production policy and has a deployment/rollback plan; awaiting the explicit go decision | **overall ≥ 8.0 and every required critical dimension ≥ 7.5** (`model_v1.production_ready`) + Michael's go decision pending | not yet |
| `PRODUCTION` | customers consume it through the compact runtime path | `PRODUCTION_READY` + recorded approval + deployed | yes |

The production policy is **unchanged** and never lowered to promote a Brain. Unknown scores never pass it. Promotion to `PRODUCTION_READY` is a recorded human decision, never automatic.

## 2. Three different "ladders" — do not merge them
| Name | Scope | Vocabulary | Lives in |
|---|---|---|---|
| Brain lifecycle (this doc) | whole Brain | RESEARCH…PRODUCTION | `/brains/{id}.lifecycle` (new, additive) |
| Brain status (legacy) | whole Brain | DISCOVERED PROFILED CALIBRATION BETA VALIDATED PRODUCTION | `/brains/{id}.status` (live today) |
| Lake-slot readiness | one lake × one slot | same legacy ladder + DEGRADED/BLOCKED | `/lakeFleet/{k}/readiness/{slot}` |
| Model lifecycle | one model | RESEARCH CANDIDATE SHADOW REVIEW PRODUCTION RETIRED | `models.*.status` |

Per-lake readiness and model lifecycle **keep their own vocabularies** (they answer different questions). Only the brain-level `status` is superseded.

## 3. Compatibility strategy (no silent behaviour change)
1. **Add, don't replace.** `lifecycle` is a new field beside `status`; Ops continues to read `status` until Ops adopts `lifecycle`.
2. **Mapping is code, not convention:** `model_v1.LEGACY_LIFECYCLE_MAP`, mirrored in `conformance/model_v1.json`.
3. **Ambiguous values are flagged, not guessed** (`lifecycleMappingAmbiguous: true`): `BETA`, `REVIEW`, `IN_PROGRESS`, `VALIDATED`, `PRODUCTION_EVIDENCE`.
4. **Unknown strings raise** — the mapper never invents a stage.
5. **Nothing live is migrated by this campaign.** Migration of a Brain's registry is performed by the Brain's owner using `BRAIN_MIGRATION_CHECKLIST.md`.

## 4. Mapping table (legacy → v1)
| Legacy value (where) | v1 | Ambiguous? | Note |
|---|---|---|---|
| `DISCOVERED` (status/readiness) | `RESEARCH` | no | |
| `IN_PROGRESS` (some Brain docs, capability states) | `RESEARCH` | **yes** | Biological uses it for a *capability state*, not a lifecycle: do not map capability words to lifecycle |
| `PROFILED` | `PROFILED` | no | |
| `SHADOW`, model `CANDIDATE` | `SHADOW` | no | |
| `CALIBRATION` | `CALIBRATION` | no | |
| `BETA` (Clarity registry today) | `CALIBRATION` | **yes** | BETA meant "internal, not customer"; owner confirms SHADOW vs CALIBRATION |
| model `REVIEW` | `CALIBRATION` | **yes** | |
| `VALIDATED` | `PRODUCTION_READY` | **yes** | legacy VALIDATED was validation, not the production policy; owner re-checks against §1 |
| `PRODUCTION`, `ACTIVE_PRODUCTION` | `PRODUCTION` | no | |
| `PRODUCTION_EVIDENCE` (Clarity model) | `PRODUCTION` + `evidenceOnly:true` | **yes** | already carried as `evidenceOnly` |
| `DEGRADED`, `BLOCKED`, `RETIRED` | unchanged conditions | no | |

Current registry values (read 2026-10-14): lake `CALIBRATION`, water-temp `CALIBRATION`, wind `CALIBRATION`, sector-intelligence `CALIBRATION`, biological-state `PROFILED`, depth `PROFILED`, water-clarity `BETA`. Proposed v1 targets are in `BRAIN_MIGRATION_CHECKLIST.md` §2 — proposals for each owner, not changes.
