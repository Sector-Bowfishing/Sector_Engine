# Session record: Fish measured-only water temp, fleet runner (OFF), Vegetation adapter (2026-11-22)

Standards: Rehtac Cortex 3.1.2 @ ecaef70 (clean), pack sector/engine

## Owner instructions
- Work from the Fish all-lakes plan (2026-11-22), §4 build steps 1–3. Michael was asleep: only work that needs no new owner approval.
- Anything that would change what publishes, or graduate Fish from pilot, stays behind a switch that is OFF.
- Keep the 45-day vegetation freshness rule exactly as is (plan §7 item 4 is Michael's decision).
- Standing approvals used: branch, commit, push the branch, open a PR. No merge, deploy, rules or IAM.

## Changes (branch `feat/fish-sensor-temp-and-fleet-runner-2026-11-22`)
| Change | What |
|---|---|
| Measured-only water temp | `bio_state.normalize_inputs` now enforces the `contracts_in` rule. It reads the Water Temp Brain's `evidenceClass` (`water-temp-state-v1`; values `sensor` and `modeled`, `WaterTemperatureBrain.EvidenceClass`). Only `sensor` is used. Any other value gives slot status `NOT_MEASURED`, reason `MODELLED_INPUT`. A missing value gives `NOT_MEASURED`, reason `EVIDENCE_CLASS_MISSING`. In both cases the values are dropped and the temperature features are UNKNOWN. A STALE slot stays STALE. |
| Fleet runner, OFF | `run_state.py --fleet` iterates a lake directory (`--directory`) through the same per-lake path as a pilot. It is refused unless `FISH_FLEET_RUNNER=1`; any other value, or none, is OFF. The directory has no region or waterbody type, so a lake without a reviewed `--lake-context` entry in the rules vocabulary is REFUSED with `NO_LAKE_CONTEXT`. Nothing is inferred from the name, state or coordinates. Today the 621-lake directory gives 5 pilot states and 616 refusals. Outputs stay local files (`fleet_run.json` plus a per-lake state). |
| Vegetation adapter | `vegetation_adapter.py` maps the Vegetation Brain's published state (`sector-brain-vegetation-state-v1`) and the plan's provisional A6 lake answer to the `contracts_in` vegetation shape. `contracts_in` gains `SURFACE_REACHING_MIXED`, Vegetation's own unclassified broad type. It counts as shallow vegetation, and floodedVegetation is UNKNOWN for it, never FALSE. Density comes only from Vegetation's calibrated `coverageClass`; nothing is derived from a plant share. The age rule is untouched (`MAX_VEG_AGE_DAYS = 45`). |

## Verification
- Pilot golden: `tests/golden/run_state_pilot_golden.json` was produced by origin/main @ 16d2bc14's `run_state.py` (pre-fleet), for all 5 pilots, offline and live (a fake RTDB). The new code reproduces it byte for byte (stdout, file and re-run) with the switch unset, `0` and `1`.
- Fish suite: 477 passed, 2 skipped. Vegetation 174 passed. Sector Intelligence 122 passed. Brain cert kit 32 passed. Architecture cross-Brain coupling passed (the Fish tests read a pinned Vegetation state fixture, not Vegetation code).
- `data-check`: the run adds one `UNREGISTERED_PATH` finding (FD-01), `run_state.py` reading `/species/{id}` in fleet `--live` mode. It is the same read the pilot already makes, and that read is already listed. No new write paths.

## Findings for Michael (not decided here)
1. **Vegetation density.** Fish needs a density to call `shallowVegetatedHabitat` TRUE. Vegetation's density gate has not passed (`coverageClass` NOT_CALIBRATED), so every PRESENT lake is UNKNOWN even when it is fresh. The plan's "density from the plant fraction" was not built, because it would mean inventing thresholds.
2. **Lake context.** No reviewed region or waterbody type exists for the 616 non-pilot lakes in Fish's vocabulary. Vegetation's `fleet.json` uses a different vocabulary (SE/NE/…, R1–R5/N1–N3), and mapping it would be a guess.
3. **Water temp.** `evidenceClass` is per lake (a configured sensor), not per reading. A sensor lake whose sensor is not fresh publishes the model value, but that state is `stale`/`evidenceStale`, so Fish already reads it as STALE.
4. The A6 lake-answer field names follow the Vegetation plan and need the Vegetation lane's agreement.

## Not done (gated)
- Graduating FISH-PRD-001, turning the fleet switch on anywhere, or publishing fleet output.
- Any change to the 45-day rule.
