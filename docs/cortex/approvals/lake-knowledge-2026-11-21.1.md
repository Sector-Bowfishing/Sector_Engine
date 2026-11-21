# Approval record: `lake-knowledge-2026-11-21.1` (PENDING)

| Field | Value |
|---|---|
| Release | `lake-knowledge-2026-11-21.1` (Lake Brain reviewed source bindings, `PACKAGED_IN_IMAGE`) |
| Release digest | `sha256:96f9a8a55f487c24a51343087db592745682ef8b83a67af891cd444ac00ed8a1` |
| Supersedes | `lake-knowledge-2026-11-20.1` (its bindings file changed: 17 lakes moved from accepted to held) |
| Status | **NOT_RECORDED: pending Michael's approval** |
| Requested scope | INTERNAL, CALIBRATION and CUSTOMER (same as 2026-11-20.1) |

## What changed in the release
- `LakeBrain/LakeSourceBindingsGenerated.swift`: `acceptedLakeIds` drops from 189 to 172. The 17 lakes held by the 2026-11-21 Mac mini dry-run gauge check (`docs/brains/LAKE_BRAIN_DRYRUN_CHECK_2026-11-21.md`) are now in `jobs/lake-brain/review/held_lakes.json` (`dryrunCheck`).
- Every other packaged file is unchanged.

## Until it is approved
- The Publisher (`PackagedReleaseResolver`) accepts only an `APPROVED` release, so a Publisher image built from this commit would refuse Lake artifacts. Approve before the next Publisher redeploy and LakeBrainJob rebuild; nothing is deployed by merging.

## To approve
Michael confirms in chat or in an "Owner approval (Michael, …)" comment on Sector_Ops #51; then set `approval.status` to `APPROVED` here and in `brains/lake/runtime/knowledge-release.json`.
