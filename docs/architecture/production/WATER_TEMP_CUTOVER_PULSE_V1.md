# Water Temp onto Pulse (b4): cutover plan (PREP, Sector_Ops #51)

**Status: plan only.** Nothing in this document has been run against production, deployed, granted or enabled. Every gated step is Michael's. This plan follows the Owner approval "Wind and Water Temp cutover PREP" (Sector_Ops #51, 2026-11-15). The pattern is the Lake move (Engine #168); the earlier gates G1–G9 are in `CUTOVER_PLANS_WT_LAKE_INTELLIGENCE_V1.md`. Identity, bucket and IAM details stay in the private Sector_Ops #51 (step WT-H1).

## Where Water Temp stands

| Item | State |
|---|---|
| Launch answer | **Approved (2026-11-14):** the water temperature labelled **"Estimate"**, with **no ± range**. The range failed WT-NOW-2, -3 and -4. The Brain's own output is unchanged; the app hides the range (iOS #247). Changing the Brain's band or score is a separate, gated decision. |
| Artifact entry | `brains/water-temperature/runtime/artifact_entry.py`: runs `WaterTempBrainJob --dry-run`, with `--read-rtdb` for GET-only reads of the previous state, and seals one `water-temp-publication-v1` artifact. No database write. |
| Staged fragment | `tools/ops/hybrid-stage/water-temp.json` (Pulse job `water-temp-central`, primary `pulse`, CENTRAL), readiness 2. |
| Order | Water Temp is cutover step 3, after Wind (step 2). Without an owner order review (WT-ORD), `hybrid_stage.py apply` refuses with `CUTOVER_ORDER`. |
| Flip | A draft PR, stacked on the Wind draft flip (do not merge). |
| G3 (#129) | Draft and conflicting. In CENTRAL artifact mode the Swift job must stop writing its own `/health/brains/water-temp` and its 3 sources, as Water Clarity did (X14). The health rows then move to the Orchestrator together with the Cortex ownership rows and a pin bump. This lands in the same approved change as the flip. |
| Knowledge release | `water-temp-knowledge-2026-11-03.1`, approval `NOT_RECORDED` (WT-G4a/b). |
| Data it reads | No bucket and nothing from the TVA archive (it needs no read grant), only the database's previous state, through the existing read-only identity. |

## Decisions for Michael
1. **WT-ORD:** let Water Temp go **ahead of Wind** (record an order review), or keep it **after Wind**.
   - **Recommended: ahead of Wind.** Water Temp is simpler: Swift, every 6 h, no 7-day comparison, no W-H2/W-H3. Its blockers are mostly G3 and the release approval. Wind has the longest list.
   - With the review recorded, the flip uses `--order-review-ref owner-approval-<date>/sector-ops-51#WT-ORD`.
2. **WT-G4a/b:** the knowledge release scope (today, the Swift Brain file only) and its approval record.
3. **The TVA history upload (below):** where it goes.

## The TVA history upload plan (b4)

**What it is.** The TVA discharge archive (Nickajack, Guntersville, Wheeler, Wilson, Pickwick: hourly observed and predicted data) used to be written hourly by the cloud job `water-temp-tva-archive` into `gs://sector-water-temp-archive/water-temp/tva/`. That job is **paused**, and the bucket was last written **2026-10-14**. Since then the collector has run on Pulse. The MacBook history was merged into it on 2026-11-08 (`merge_archive.py`, 97 hours added), and it lives on the Mac mini at:

```
<pulse-job-data>/water-temp-tva-archive/archive/water-temp/tva/
```

**Why upload it.**
- The bucket is the off-machine copy.
- Lake's L-H1 option (b) and any later research read it.
- Water Temp itself does **not** need it to run.

**Size.** It was 19 MB on 2026-11-06 and grows by a few KB per dam per day, so expect **about 20–30 MB**. Step 1 prints the exact size before anything is uploaded.

**Target (no overwrite).** The upload goes to a **new prefix**, so nothing already in the bucket is replaced:
```
gs://sector-water-temp-archive/water-temp/tva-snapshots/2026-11-pulse/
```
The bucket's daily files up to 2026-10-14 stay as they are. The snapshot is the complete merged archive. Folding it into `water-temp/tva/` would be a separate, later step, done with `merge_archive.py` semantics, not a blind copy.

**Commands (Michael; nothing is run here).** There are two parts: a pack-and-checksum on the Mac mini (read-only on the archive), then a create-only `gcloud storage cp --no-clobber` to the new prefix from Cloud Shell. The exact commands are on Sector_Ops #51 ("WT TVA upload commands (for Michael)"), not here, because they name local paths on the Mac mini.

**Cost:** pennies; it's tens of MB on Standard storage.

## Mac mini work (the Mac mini helper does this under this approval)
- The Pulse catalog entry `water-temp-central`: OFF, lease-only, `WHILE_LEASE_HELD`, running `artifact_entry.py --job <built WaterTempBrainJob> --read-rtdb <db> --artifact-dir <local>`, with `SECTOR_ENGINE_COMMIT` set.
- A `WaterTempBrainJob` release build from the snapshot commit, and `publication.waterTempJobBinary` set.
- One local dry run that seals an artifact. Nothing is uploaded.

## Gated steps, in order (each Michael's; exact commands are on Sector_Ops #51)
1. **Decisions:** WT-ORD, WT-G4, the TVA upload target.
2. **Code (standing approvals):**
   - G3-2: the Swift job stops writing its own health in artifact mode, and the fixture is re-recorded;
   - #129 is rebased.
   - Both stay draft until the flip change.
3. **Cortex maintenance:** the Water Temp health ownership rows, then a pin bump.
4. **Mac mini:** the build, the catalog entry OFF, and one dry run.
5. **M1 IAM WT-H1** (five bindings, idempotent script, on #51).
6. **M3:** record the knowledge release approval.
7. **M4:** one approved change that merges #129 (G3), the Cortex pin and the flip PR, with the real approvalRef, `--blockers-cleared` and, if chosen, the WT-ORD order review.
8. **M5:** deploy the Orchestrator and the Publisher from `main`, restating every live switch.
9. **M6:** the first-publish baseline acknowledgement (the first-publish run sheet on Sector_Ops #51 (built on `jobs/brain_platform/sector_brain_platform/publisher_live/baseline.py`)).
10. **M7:** `execution_control.py enable … --brains water-clarity,lake-brain,water-temp` (plus `wind` if it's live).
11. **M8/M9:** the watched first publish, then a 2-cycle watch (about 12 h).
12. **Retire the direct writer** (the B6 pattern) after 3 clean days, with `CUTOVER_COMPLETE`.
13. **The TVA upload** (above), any time. It's independent of the cutover.

**Halt and roll back (any step):**
- `execution_control.py brain --brain water-temp --disable`;
- revert the flip change and redeploy;
- the Publisher's own rollback, for a bad publish;
- remove the WT-H1 bindings using the same condition files.
