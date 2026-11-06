# Sector Intelligence: its own artifact job (SI-1 (a)), plan first (Sector_Ops #50 / #51)

**PLAN ONLY. No code in this change, and nothing run, deployed, granted or enabled.** Intelligence is step 5, the last in `cutover_order.json`. Its synthesis is not validated (Sector_Ops #39), and it is not eligible for customers.

## Today
- Intelligence runs **inside the Orchestrator** (`orchestrate.py` `kind: in-process`). It runs `brains/sector-intelligence/runtime/run.py --write`, which builds one flat update with `sector_intelligence_brain.build_updates` and **writes the Brain database directly** (`rtdb.update`) with the Orchestrator's identity.
- **Engine #102 refuses in-process Brains in local runner mode**, so a Pulse cycle never runs it. That is deliberate until this plan is done.
- **What already exists:**
  - the artifact builder `runtime/publish_artifact.py` (`sector-intelligence-publication-v1`, SHADOW);
  - its registry families;
  - `NotAuthored` rows that make the `/health/brains/sector-intelligence` process fields Orchestrator-derived;
  - a packaged `knowledge-release.json` (the catalog).
- **It reads:**
  - every upstream Brain's registry, health and validation;
  - the pilot lakes' `/snapshots/{k}/latest`, `/lakeFleet/{k}`, `/lakes/{k}/speciesPresence` and `/species`;
  - `/lakeFleet`;
  - the Engine's Cloud Run service (its serving revision);
  - `GET /lakes` on the customer Engine.

## Target
Intelligence becomes a Brain job like Water Clarity:
1. It computes exactly what it computes today.
2. It seals **one** artifact, create-only, under `artifacts/sector-intelligence/`.
3. The central Publisher publishes it.
4. It never writes the database.

On the Mac, the Orchestrator grants Pulse the lease when its decision model says `DEPENDENCY_CHANGED`. There is no cron.

## Code steps (each a draft PR with no production effect)
| # | Change | Notes |
|---|---|---|
| SI-A1 | `run.py` central mode: `--artifact-dir DIR` / `--artifact-bucket B`, the same `build_updates`, sealed by `publish_artifact.build_artifact`, stored create-only (as Water Clarity's `run.py`). `--write` stays until SI-A6 | **It also accepts `ENGINE_REVISION`.** A read-only identity cannot read Cloud Run, so the serving revision would be UNKNOWN off-cloud: the same finding as the 2026-11-03 Water Clarity parity |
| SI-A2 | Orchestrator: Intelligence becomes `kind: job` (artifact mode), started or leased like Water Clarity. In local runner mode, the lease goes to Pulse | the in-process path is removed only at SI-A6 |
| SI-A3 | Health: a `health_mirror.SPECS` entry `sector-intelligence` with `status ← health` (the map from #111) | the registry already refuses `/health` from the Brain |
| SI-A4 | Release: verify that the packaged release stages into the Publisher image (`deploy-job.sh --stage-only`) and resolves | single folder; no subfolder issue |
| SI-A5 | Pulse catalog `sector-intelligence-central`, run by the Pulse session in the Pulse repository | `WHILE_LEASE_HELD`; the read-only database token; `ENGINE_REVISION` from owner config |
| SI-A6 | Retire (G8): remove `--write` and the in-process path, and set `CUTOVER_COMPLETE`, in the same change | after its one publish |

## Gates (G0–G9, as `CUTOVER_PLANS_WT_LAKE_INTELLIGENCE_V1.md` §3)
- **G0 (order):** every Brain it reads publishes centrally first: Water Clarity (done), Wind, Water Temp and Lake. Fish is re-pointed after the Fish split (M05). A baseline taken before then would be on the wrong owners.
- **G5 / G6:** `tools/cutover/rtdb_capture.py` and `lake_rehearsal.py` (#113) generalise. They need an Intelligence path list and a run step for `run.py`'s central mode.
- **G7:** one publish. The consumers are Ops and the internal Beta check (`beta.py`); their outputs are diffed before and after.
- **Customer:** unchanged (NOT_ELIGIBLE, IO-10).

## Decisions for the owner
- **SI-P1:** draft SI-A1 to SI-A4 as code PRs now (no production effect), or wait until Lake and Water Temp are central. *Recommended:* SI-A1 and SI-A3 now, because they are small and remove the off-cloud blockers; the rest after Lake.
- **SI-P2:** keep `--plan` (the skip decision) in the Orchestrator process, or move it into the job. *Recommended:* into the job, so the Orchestrator runs no Brain code.

## Cost
On Pulse, $0 in cloud jobs. One run is under a minute, and it runs only when a dependency changes.
