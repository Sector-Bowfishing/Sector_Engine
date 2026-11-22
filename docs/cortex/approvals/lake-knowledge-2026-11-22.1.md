# Approval record: `lake-knowledge-2026-11-22.1` (PENDING)

| Field | Value |
|---|---|
| Release | `lake-knowledge-2026-11-22.1` (Lake Brain reviewed source bindings, `PACKAGED_IN_IMAGE`) |
| Release digest | `sha256:a40d30b77554dbfd8d6be5a89885c20734c3418e5f053b850f3907a68365a114` |
| Supersedes | `lake-knowledge-2026-11-21.2` (APPROVED 2026-11-21) |
| Status | **NOT_RECORDED: pending Michael's approval** |
| Requested scope | INTERNAL, CALIBRATION and CUSTOMER (same as 2026-11-21.2) |

## What changed in the release
- `LakeBrain/LakeSourceBindingsGenerated.swift`: the table gains the **106** batch 2 records (`jobs/lake-brain/data/bindings.batch2.v1.json`) and `acceptedLakeIds` goes from 187 to **293** (`accepted_batch.json` + `accepted_batch2.json`). Lake's reviewed set (with the 5 pilots) goes from 192 to **298**.
- Batch 2 = the excluded research-bound lakes that passed the 2026-11-22 Mac mini re-check on an engine provider (Sector_Ops #51 comments 7074433014 and 7075462499). Review packet: `docs/brains/LAKE_BRAIN_ACCEPTED_BATCH2_2026-11-22.md`.
- Series fixed by the re-check: Logan Martin AL and Weiss AL live (Alabama Power guide curve → `Raw-APCO`), East Lynn WV history (rule curve → observed `OBS`), Rend Lake IL history (stopped `MVDhist-rev` → `datman-rev`).
- Every other packaged file is unchanged.

## Customer-facing effect (needs Michael's explicit OK)
- By the 2026-11-20 20:01Z owner rule (the customer Lake-level list is exactly Lake's reviewed set), `customer_lake_level_eligible.json` and `LakeLevelEligibility.validatedLakeIds` go from 192 to **298** lakes in the same PR. The operator-only list stays the 4 TVA mainstem pilots.

## Until it is approved
- The Publisher (`PackagedReleaseResolver`) accepts only an `APPROVED` release, so a Publisher image built from this commit would refuse Lake artifacts. Approve before the next Publisher redeploy and LakeBrainJob rebuild; nothing is deployed by merging.

## To approve
Michael confirms in chat or in an "Owner approval (Michael, …)" comment on Sector_Ops #51; then set `approval.status` to `APPROVED` here and in `brains/lake/runtime/knowledge-release.json`.
