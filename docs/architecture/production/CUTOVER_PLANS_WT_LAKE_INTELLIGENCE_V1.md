Standards: Rehtac Cortex 3.1.1 (pin per CLAUDE.md)

# Cutover plans: Water Temperature, Lake, Sector Intelligence (prepared 2026-10-31; NOTHING here is executed or authorised)

[REMAINING_BRAIN_MIGRATIONS_V1.md](REMAINING_BRAIN_MIGRATIONS_V1.md) requires each of these Brains to have its own cutover plan before migration. Each plan below applies the **nine common gates** (G1–G9) in order to that Brain's facts, verified at `origin/main` `ca669772`. Order (enforced by `jobs/brain_platform/sector_brain_platform/cutover_order.json`): Water Clarity → Wind → **Water Temperature → Lake → Sector Intelligence**. A failure at any gate halts that Brain only. Every live step needs the owner's approval for that step. Identity names and grants are in the private record (Sector_Ops 19); identity classes are in `platform/security/identity_split_plan.json`.

Common prerequisites for all three: Water Clarity's cutover is complete (Sector_Ops 18 and the `CUTOVER_COMPLETE` flip); Wind's cutover is complete (7-day shadow equivalence first); the recurring Publisher job (`jobs/brain-publisher/`, Engine PR 70) is deployed and wired, and the Orchestrator writes publication requests.

## 1. Water Temperature (`water-temp`, step 3)
**Before:** Swift job `WaterTempBrainJob` (`brains/water-temperature/runtime/`), started by the Orchestrator when 6 h stale, running as the shared writer identity (database admin). It writes `/lakes/{k}/states|profiles/waterTemp`, `/lakes/{k}/validation/water-temp`, `/lakeFleet/{k}/...waterTemp`, `/brains/water-temp/{child}`, `/validation/water-temp`, `/sources/{id}`, `/health/brains/water-temp/{child}`, `/health/sources/{id}`, `/activity/*`, plus the legacy snapshot copies and `lakeId`. Python builder `runtime/publish_artifact.py` (`water-temp-publication-v1`) exists in SHADOW. Knowledge: `model`, COMPILED_IN_BINARY, approval NOT_RECORDED. Score `/scores/water-temp` from `frozen-scores.json`. Consumers: Ops, Sector Intelligence.

| Gate | Water Temperature action | State today |
|---|---|---|
| G1 Artifact | Add CENTRAL mode to the job image: a thin Python entry runs `WaterTempBrainJob --dry-run DIR`, seals that write set with `publish_artifact.py` and stores it create-only under `artifacts/water-temp/` (the Water Clarity `run.py` CENTRAL pattern). **Do not** add a Swift sealing path: that would be a second implementation of the envelope (architecture.md, single implementation) | builder exists (SHADOW); no emitter; decision **WT-1** |
| G2 Identity | The job moves to its own read-only identity (identity plan S4); the shared writer stops being its runtime identity; denial probe | shared writer |
| G3 Health | Remove `/health/brains/water-temp/{child}` and `/health/sources/{id}` from the Water Temp registration (`publisher/registry.py`), as was done for Water Clarity; the builder classifies them `ORCHESTRATOR_DERIVED`; extend `health_mirror.py` to derive them | still registered |
| G4 Release | The model is compiled in. Record it as a packaged release with a digest (BR-11), or record the decision that a compiled model is released by image digest. Lifecycle stays CALIBRATION; no promotion | NOT_RECORDED; decision **WT-2** |
| G5 Baseline | Private read-only capture of every Water Temp path for the pilot lakes; equivalence diff of the sealed artifact plan against live (zero unexplained differences); acknowledge the baseline | not done (needs a credentialed read, gated) |
| G6 Rehearsal | Build, plan, acknowledge, publish and restore against an in-memory fake seeded from the capture (`clarity_pilot.py rehearse` pattern, generalised) | not done |
| G7 Publish once | One Publisher publication; readback of every path against the immutable record; score, health and consumers unchanged | not done |
| G8 Retire | Remove the Swift job's database write path (`BrainStore.update` on Water Temp paths) in the same approved change as `cutoverStatus: CUTOVER_COMPLETE` + exit record. Water Temp's P14 is Swift-scoped, so the X14 equivalent is the Swift write-ownership gate pinned to zero write sites | not done |
| G9 Rollback | `LivePublisher.rollback` (previous immutable artifact, never over newer data); the job's previous image restores the direct writer only together with the shared identity (and so only by an approved revert of S4) | defined |

## 2. Lake (`lake-brain`, step 4)
**Before:** Swift job `LakeBrainJob` (`brains/lake/runtime/`), started when 26 h stale, as the shared writer identity. It writes `/lakes/{k}/states/lake`, `/lakes/{k}/brain`, `/lakes/{k}/speciesPresence`, `/lakeFleet/{k}/...lake` and Lake-only fleet children, `/brains/lake-brain/{child}`, `/validation/lake-brain`, `/sources/{id}`, `/health/brains/lake-brain/{child}`, `/health/sources/{id}`, `/activity/*`, plus legacy snapshot copies and `lakeId`. Builder `runtime/publish_artifact.py` (`lake-publication-v1`) in SHADOW. Knowledge: reviewed bindings (compiled in) and species presence (private bucket release, `DEGRADE_EXPLICITLY`), both NOT_RECORDED. Consumers: Ops, Sector Intelligence, Depth, Vegetation; Water Temperature and Water Clarity read Lake state.

| Gate | Lake action | State today |
|---|---|---|
| G0 Lake-only preconditions | (a) the Hartwell CWMS fetch-failure retry fix (`origin/fix/lake-brain-cwms-retry`) merged and deployed first, so the baseline is not captured during a known failure mode; (b) the Lake capability contract decisions D1–D8 (Sector_Ops 22). Of these, **D3 (species presence → Fish)** changes the write set: if presence moves to Fish, `/lakes/{k}/speciesPresence` must leave Lake's registration before G5, or the baseline is captured on the wrong owner | open |
| G1 Artifact | As Water Temp: a Python entry runs `LakeBrainJob --dry-run DIR` (with `--read-rtdb` GET-only for previous profiles) and seals it with `publish_artifact.py` into `artifacts/lake-brain/` | builder exists; decision **WT-1** applies to both Swift Brains |
| G2 Identity | Own read-only identity (identity plan S5); denial probe | shared writer |
| G3 Health | Drop `/health/brains/lake-brain/{child}` and `/health/sources/{id}` from the registration; Orchestrator-derived | still registered |
| G4 Release | Bindings: as WT-2. Species presence: a private release with a digest, verified by the Publisher's release resolver; never committed (public repository) | NOT_RECORDED |
| G5 Baseline | Private capture, pilot lakes, including `/lakes/{k}/brain` and the Lake-only fleet children; zero unexplained differences | not done |
| G6 Rehearsal | Fake seeded from the capture, including a forced CWMS failure (the run must degrade honestly, never blank a lake) | not done |
| G7 Publish once | One publication; readback; Water Temp, Water Clarity, Depth and Vegetation consumers unchanged (their readers' outputs diffed before and after) | not done |
| G8 Retire | Swift write path removed + `CUTOVER_COMPLETE` + exit record, same change | not done |
| G9 Rollback | `LivePublisher.rollback`; consumer outputs re-checked after a rollback | defined |

## 3. Sector Intelligence (`sector-intelligence`, step 5, last)
**Before:** Python, **in process inside the Orchestrator** (`brains/sector-intelligence/runtime/run.py --write`, staged as `jobs/sector-intelligence-brain/`), as the Orchestrator's identity. It runs when a dependency materially changes. It writes `/lakes/{k}/states/intelligence`, `/lakeFleet/{k}/...intelligence`, `/snapshots/{k}/latest/sectorIntelligence` and its brainVersion (Brain-authored for evaluated pilot lakes, not a Publisher projection), `/brains/sector-intelligence/{child}`, `/validation/sector-intelligence`, `/health/brains/sector-intelligence/status`, `/activity/*`. Builder `runtime/publish_artifact.py` in SHADOW. Knowledge: `intelligence-catalog`, PACKAGED_IN_IMAGE, approval NOT_RECORDED, `REFUSE` when unavailable. It consumes Lake, Water Temp, Water Clarity, Wind and the **legacy combined `biological-state`**.

| Gate | Sector Intelligence action | State today |
|---|---|---|
| G0 Intelligence-only preconditions | (a) **every upstream Brain it consumes is already CENTRAL** (it publishes last, consuming published outputs only); (b) **the Fish/Biological input**: until M01–M05, Intelligence keeps consuming `biological-state` as a read (consumption is not drift, BA-07). After the split, M05 re-points it to `fish-behavior` (assessment) and `fish-knowledge` (species facts). The cutover does not wait for M05, but its baseline must be re-captured after M05 | open |
| G1 Artifact | Move Intelligence **out of the Orchestrator process** into its own job that emits one sealed artifact under `artifacts/sector-intelligence/` (identity plan S6). Rejected alternative: letting the Orchestrator identity create Brain artifacts, which mixes the coordinator with a producer (architecture.md: an executor must not decide publication) | builder exists; no job; decision **SI-1** |
| G2 Identity | Its own read-only identity; the Orchestrator stops writing Intelligence paths (code pin: no Intelligence path in the Orchestrator's own writes) | Orchestrator identity |
| G3 Health | Drop `/health/brains/sector-intelligence/status` from the registration; Orchestrator-derived | still registered |
| G4 Release | `intelligence-catalog` packaged with `knowledge-release.json`; record an approval or use the CALIBRATION-lane exception explicitly (owner-visible, never promoted) | NOT_RECORDED; decision **SI-2** (same question as Sector_Ops 18 D2) |
| G5 Baseline | Capture after all upstream Brains are CENTRAL; zero unexplained differences, including the evaluated lakes' snapshot fields | not done |
| G6 Rehearsal | Fake seeded from the capture, including a missing upstream Brain: Intelligence must abstain or mark UNKNOWN, never substitute (BA-08) | not done |
| G7 Publish once | One publication; readback; Ops panels unchanged; `customerPublication` stays NOT_ELIGIBLE (no customer path is touched; IO-10) | not done |
| G8 Retire | `run.py --write` and the in-process step removed from `orchestrate.py`, together with `CUTOVER_COMPLETE` + exit record | not done |
| G9 Rollback | `LivePublisher.rollback`. The previous Orchestrator image restores the in-process writer only by an approved revert | defined |

## 4. Decisions these plans need (batched)
| ID | Decision | Options | Recommendation |
|---|---|---|---|
| WT-1 | How the Swift Brains emit their artifact | (a) a Python entry wraps the Swift `--dry-run DIR` output and seals it with the existing Python builder; (b) port the envelope and sealing to Swift | (a): one implementation of the envelope, and the builders and their tests already exist |
| WT-2 | Release record for compiled-in knowledge (Water Temp model, Lake bindings) | (a) a packaged `knowledge-release.json` with a digest over the compiled source inputs; (b) treat the image digest as the release | (a), consistent with Water Clarity and Sector Intelligence |
| SI-1 | Sector Intelligence execution | (a) its own job and identity; (b) stay in process with an artifact | (a) |
| SI-2 | Intelligence catalog release approval | record approval / CALIBRATION-lane exception | decide together with Sector_Ops 18 D2 |
| L-1 | Species presence ownership before Lake's baseline | (Sector_Ops 22 D3) | move to Fish first (Cortex BA-02: Fish owns per-lake species presence) |
