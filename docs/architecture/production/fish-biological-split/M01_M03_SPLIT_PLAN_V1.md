Standards: Rehtac Cortex 3.1.1 (pin per CLAUDE.md)

# Fish / Biological split: M04 done, M01–M03 step-by-step plan (prepared 2026-10-31; M01–M03 NOT started, NOT authorised)

The deployed package `brains/fish/` (stable ID `biological-state`, `LEGACY_COMBINED`) serves two target Brains: **Fish Brain** `fish-knowledge` (what a species is and generally needs) and **Biological Brain** `fish-behavior` (what fish are likely doing now, from Fish knowledge applied to environmental outputs). Cortex BA-02 and BA-04 require the split; `cutover_order.json` defers both Fish cutover steps until M01–M03 are done. The combined package is never published as a combined unit.

## Done on this branch: M04 (charters; Cortex gate ENGINE_SAFE_DOCS)
| Item | Result |
|---|---|
| Target charters | `fish-knowledge.CHARTER.json` (predicts `speciesPresence`, `evidenceGradedRules`; **needs no Brain**, matching `authorizedInputs: []`) and `fish-behavior.CHARTER.json` (predicts `responseBandOrSpawnWindow`; needs Fish plus the environmental Brains), in this folder |
| Combined charter | `brains/fish/research/CHARTER.json` keeps every field and adds `targetBrain` per prediction and input, plus `splitInto`. It stays the charter the tools read until M02 |
| Water Temperature charter | `"fish behaviour (Fish owns it)"` becomes `"fish behaviour (Biological Brain owns it)"` |
| Checks | `mission-audit --repo .`: only the expected `LEGACY_COMBINED` finding, no `WRONG_OWNER`. `mission-audit --brain <target> --text <prediction>`: 0 findings for each of the three predictions; the control (response bands under fish-knowledge) is `WRONG_OWNER`. `research-check --charter .`: 0 findings. `brains/fish/tests/test_target_charters.py`: the partition is exact and unchanged |
| Why the target charters are not in `brains/fish/research/` | The Fish Kit spec pins that folder to exactly `CHARTER.json`, `GAPS.json`, `README.md` (P17), and the Cortex tools read one `research/CHARTER.json` per package. Recorded as a Cortex gap |

## M01: registry (Cortex gate ENGINE_APPROVAL)
1. `tools/architecture/stable_brain_ids.json`: add `fish-knowledge` and `fish-behavior`, each with its future directory (decision **S-1**, below). `biological-state` stays mapped to `fish`, unchanged.
2. `jobs/brain_platform/sector_brain_platform/control_manifest.json`: add both target IDs with `lifecycle` (decision **D-1**), no execution entry yet, and `activityState` PARKED. `gate_dispatch` already prevents double dispatch while the legacy package covers them.
3. `data_ownership.json` already names both targets (recognised as `TARGET`, `deployedAs: biological-state`). Change nothing there except the registry columns Cortex owns (Cortex maintenance session).
4. Do **not** add the target IDs to `keys.BRAINS` yet: that table drives the ownership checks and the Publisher's key guard. Adding them is part of M03, together with the new families (M06 proposal).
5. Verify: `mission-audit --repo .` still reports `LEGACY_COMBINED` (M01 alone does not clear it), and the architecture and orchestrator tests pass.

## M02: package split (ENGINE_APPROVAL)
1. Create the `fish-behavior` package directory (name: decision **S-1**). Move the files `mission-audit` classifies as fish-behavior: `bio_state.py`, `biological_assessment.py`, `evaluated_view.py`, `features.py`, `movement_outlook.py`, `run_state.py`, `schemas/condition_features.json`, `schemas/prediction.schema.json`, `tools/movement_cards.py`. Use `git mv`, so history is preserved.
2. Classify the 19 files `mission-audit` leaves UNCLASSIFIED. Proposed classification:
   - `run.py`: splits, one entry per package.
   - `publish_artifact.py`: one per package (M03).
   - `brain_platform.py`, `orchestration.py`, `contracts_in.py`: platform shims, copied per package from the shared platform, not duplicated logic.
   - `bands.py`: Fish (knowledge: response-band definitions).
   - `capability*.py`, `prereg_analysis.py`, `validation_log.py`: Fish, because the Biological Capability rubric 2.1 scores species knowledge; behaviour validation would get its own module later.
   - `tools/{gen_schemas,observations,review,review_plain}.py`: to review one by one.
   - `schemas/{latest_pointer,manifest,observation}.schema.json`: shared release schemas, kept with Fish.
   Each line is a proposal; the owner confirms them in the M02 PR.
3. One canonical implementation each (BR-05, BR-08). `fish-behavior` imports Fish knowledge only through a declared input (the Fish knowledge release or the Fish output contract), never by importing Fish modules.
4. `brain.json`, `BRAIN_OPERATING_CONTRACT.md`, `README.md` and `research/` for the new package. Each target charter from this folder becomes its package's `research/CHARTER.json` unchanged. The combined charter is retired with the legacy package.
5. Certification Kit V1 specs for both packages. `brains/fish/` keeps `biological-state` until M06; afterwards the legacy identity is retired, never reassigned (BA-04).
6. Pulse and jobs (M11): re-point `capability_run.py` and the in-process step in `orchestrate.py`.
7. Verify: the `mission-audit` split listing is empty; Kit V1 passes on both packages; the combined outputs are **byte-identical** before and after on fixed inputs (the same method as the Water Clarity retirement).

## M03: contracts (ENGINE_APPROVAL)
1. `fish-biological-assessment-v1` gets a versioned successor in the fish-behavior package, `fish-behavior-assessment-v1`. The old ID stays readable during migration (a consumer reads either; the field meanings are unchanged).
2. `fish-publication-v1` keeps the species publication (`/species/{id}`) for Fish. The behavioural-state children of `/brains/biological-state/{child}` move to a new fish-behavior publication contract.
3. Publisher registrations for both target IDs, without `/health/*` (Cortex 3.1). The new families are **proposals**; registering them in the Firebase data registry is M06 and needs production approval before any write.
4. Verify: `describe_contract --check` on both packages; sampled artifacts validate; the combined writer's output is unchanged.

## Not part of M01–M03 (each needs its own approval)
M05 (dependency re-pointing, including Sector Intelligence), M06 (Firebase families, readers moved, `biological-state` retired: production), M07 (per-Brain rubrics; frozen scores stay attributed to `biological-state` with their date), M08–M12, and the two Fish cutovers.

## What the decisions in Sector_Ops 20 must settle (restated for the nine-Brain architecture)
The original D-1 and D-3 (2026-10-17) were written for one Fish Brain. The 2026-10-17 merge closeout recorded interim answers: D-1 "Biological State stays a PILOT, `consumes: []`" and D-3 "Publisher cutover deferred". Cortex 3.0–3.1 have since split the Brain, so both need a fresh answer:

| Decision | Exactly what must be decided | Options | Recommendation | Blocks |
|---|---|---|---|---|
| **D-1** | After M02, is `fish-behavior` an **orchestrated Brain** that declares its inputs (`fish-knowledge` + wind, water-clarity, lake-brain, water-temp, depth, vegetation; recorder instrumentation already exists in `run_state.py`), or does it stay an **internal pilot** (`consumes: []`, undeclared reads; gap FISH-PRD-001)? And at what lifecycle is it registered? | (a) orchestrated, inputs declared, lifecycle `SHADOW` (runs internally, abstains honestly, never live-eligible); (b) pilot until validated | **(a)**: declared inputs are required by BA-06 and BR-09 the moment it is a Brain. `SHADOW` keeps every output out of the live lane until validation | M01 step 2 (lifecycle), M02 step 4 (`brain.json` consumes), M05 |
| **D-3** | How the Fish writer changes. (i) Confirm the combined package is never CENTRAL (Cortex already says so). (ii) Keep `run.py --write` as the **only** writer of `/brains/biological-state/*` and `/species/*`, unchanged, until M06; no dual write. (iii) The new families `/brains/fish-knowledge/*` and `/brains/fish-behavior/*` are written only through the Publisher, only after the M06 registry proposal is approved and readers have moved. (iv) The position of the two Fish steps in `cutover_order.json` | (ii) keep / dual-write; (iv) after Sector Intelligence / before it | (ii) **keep, no dual write**; (iv) **fish-knowledge, then fish-behavior, after Sector Intelligence's plan**: Intelligence must first be re-pointed (M05) or it would read a Brain that no longer updates | M03 step 3, M06, the Fish cutover plans |
| **/sources writer** | Who writes the Fish Brain's source records under `/sources/{id}` (`fam.sources`) | (a) each producing Brain, through the Publisher, like `/sources/{id}` in the Water Clarity and Water Temp registrations; (b) a platform writer | **(a)**: `fish-knowledge` owns its source records | M03 step 3 |
| **S-1** (new) | Directory names | `brains/fish/` stays Fish + new `brains/fish-behavior/`; or new `brains/fish-knowledge/` + `brains/fish-behavior/` | Keep `brains/fish/` for Fish (moving a directory other systems reference is gated, PROJECT §7) and add `brains/fish-behavior/` | M01 step 1, M02 step 1 |

Note: Sector_Ops 20 says D-1 and D-3 block "cutover step 2 (biological-state)". That predates the 2026-10-29 correction of the order (Water Clarity → Wind → Water Temp → Lake → Sector Intelligence; Fish deferred until after M01–M03). The decisions block M01–M03 and the deferred Fish steps, not step 2.
