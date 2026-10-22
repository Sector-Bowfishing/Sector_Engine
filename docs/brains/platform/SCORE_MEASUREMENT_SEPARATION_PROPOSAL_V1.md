# Score measurement separation — proposal V1 (not active)

**Status:** PROPOSAL, 2026-10-20 (Cortex architecture completion, decisions D-5 and D-6). Nothing here is implemented. Every step below that changes a published `/scores/*` or `/brains/*` value, a rubric, or what Sector Ops reads needs Michael's approval, and the Sector Ops side is verified in the Sector Ops repository. Current production behaviour is unchanged.

## 1. The problem (observed in this repository)

Five different measurements share one score type and one aggregate (Cortex `scoring.md` SC-01, observation obs.09):

| `/scores/{id}` | What the value actually measures | Where it comes from |
|---|---|---|
| `lake-brain`, `biological-state`, `sector-intelligence` | operational readiness of a Brain (computed rubric: coverage, validation, health caps) | `jobs/brain_platform/sector_brain_platform/scoring.py` |
| `water-temp` | a frozen research-validation level (`water-temp-level-ladder-v1`) | `docs/brains/scoring/frozen-scores.json` |
| `water-clarity` | a frozen research score of a candidate that is NOT_DEPLOYED (8.0) | `frozen-scores.json` |
| `wind` | Wind certification rubric v1 (3.3; a computed block admitted by `wind_score_refresh`) | `frozen-scores.json` |
| `engine` | the mean of the five specialist values above (`engine-score-v1`) | `scoring.py` `score_engine` |

Every `brain.json` declares `score.type = ENGINE_READINESS_SCORE` for all of them. Separately, the Wind job still writes its own copy of validation scores under `/brains/wind/scores` and `/validation/wind` (`brains/wind/runtime/sector_wind/brain/publish.py`, values 3.1 / 5.4 from `brain_validation_evidence.py`), next to the canonical `/scores/wind` (3.3) — a second, stale writer of a score-like value (SC-04, obs.14).

## 2. Proposal A — label each measurement (D-6), backward compatible

1. **Additive field.** Each `/scores/{id}` block gains `measurement: {kind, basis, rubric}` with `kind` ∈ `DOMAIN_CAPABILITY | SCIENTIFIC_CONFIDENCE | PRODUCTION_READINESS | OPERATIONAL_HEALTH | HISTORICAL_MATURITY` (the five measurements of `scoring.md`). The existing `type: ENGINE_READINESS_SCORE`, `value` and every other field stay as they are, so today's Ops view keeps working.
   Proposed kinds: Lake, Biological, Intelligence → `PRODUCTION_READINESS`; Water Temp and Water Clarity frozen research scores → `SCIENTIFIC_CONFIDENCE`; Wind certification v1 → `HISTORICAL_MATURITY`; Wind Capability v2 and Fish Biological Capability v2 (when activated) → `DOMAIN_CAPABILITY`.
2. **Ops reads the label.** Sector Ops renders `measurement.kind` next to each value and stops presenting them as one comparable column (Sector Ops session).
3. **Engine aggregate.** Only after (2): `engine-score-v1` stops averaging different kinds — a rubric change (re-versioned `engine-score-v2`), approval-gated; until then the Engine score is labelled "mixed-measurement aggregate".
4. **Declarations.** `brain.json` `score` gains the same `measurement.kind` (schema change, additive).

Rollback: the field is additive; removing it restores today's payload exactly. Risk: low for (1), medium for (3) (a published value changes; needs a recorded baseline and approval).

## 3. Proposal B — retire Wind's self-published score copy (D-5)

1. **Inventory readers** of `/brains/wind/scores` and `/validation/wind/scores` in Sector Ops and Sector Intelligence (Sector Ops session). Sector Intelligence in this repository does not read them (verified 2026-10-20: no read of a `scores` child in `brains/sector-intelligence/runtime/`).
2. **Replace, then stop.** First publish a pointer `{canonical: "/scores/wind"}` in place of the values for one release window; then stop writing the child (the Publisher contract `wind-publication-v1` already does not list it as an authored child).
3. **Ownership.** Narrow `ownership.py` so a Brain cannot write a child named `scores` under `/brains/{id}` (score authority stays with the platform scorer, SC-04).

Rollback: re-enable the child write (one line in `publish.py`); the canonical `/scores/wind` is untouched throughout. Risk: low once (1) shows no reader.

## 4. What is NOT proposed

No change to any rubric's dimensions, weights or caps; no re-baselining; no change to Fish cohorts or to the adopted Wind Capability v2 (6.7); no production write.
