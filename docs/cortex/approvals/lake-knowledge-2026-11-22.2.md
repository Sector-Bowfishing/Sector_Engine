# Approval record: `lake-knowledge-2026-11-22.2` (PENDING)

| Field | Value |
|---|---|
| Release | `lake-knowledge-2026-11-22.2` (Lake Brain reviewed source bindings, `PACKAGED_IN_IMAGE`) |
| Release digest | `sha256:652a52695504c73e9bd90b5d2e371653d54b428a621840eb1538e2952189245d` |
| Supersedes | `lake-knowledge-2026-11-22.1` (APPROVED 2026-11-22 08:00Z, Sector_Ops #51 comment 7076252747: the CDEC, NOAA CO-OPS and USGS-stage provider types, no binding changed) |
| Status | **NOT_RECORDED: pending Michael's approval** |
| Requested scope | INTERNAL, CALIBRATION and CUSTOMER (same as 2026-11-22.1) |

Batch 2 was first packaged as `lake-knowledge-2026-11-22.1` on its branch; that id was taken on main by the approved #219 release, so batch 2 is this new id. The 22.1 record is unchanged.

## What changed in the release
- `LakeBrain/LakeSourceBindingsGenerated.swift`: the table gains the **106** batch 2 records (`jobs/lake-brain/data/bindings.batch2.v1.json`) and `acceptedLakeIds` goes from 187 to **293** (`accepted_batch.json` + `accepted_batch2.json`). Lake's reviewed set (with the 5 pilots) goes from 192 to **298**.
- Batch 2 = the excluded research-bound lakes that passed the 2026-11-22 Mac mini re-check on a provider the engine already reads (Sector_Ops #51 comments 7074433014 and 7075462499; owner approval in principle 2026-11-22 06:39Z). Review packet: `docs/brains/LAKE_BRAIN_ACCEPTED_BATCH2_2026-11-22.md`.
- `LakeBrain/LakeSourceBindings.swift` and `LakeBrain/LakeGeneratedBindings.swift`: unchanged from 22.1 (they keep the CDEC, CO-OPS and USGS-stage provider types). No batch 2 lake is bound to CDEC, CO-OPS or USGS stage.
- Not in the release: Clinton Lake IL (USGS gage height + site altitude) and Upper Klamath Lake OR (USGS 72275) passed the re-check but had no engine adapter in batch 2's scope. Clinton could now use 22.1's `usgsStage`; that is a follow-up binding, not part of this release.

## Customer-facing effect
- By the 2026-11-20 20:01Z owner rule (the customer Lake-level list is exactly Lake's reviewed set), `customer_lake_level_eligible.json` and `LakeLevelEligibility.validatedLakeIds` grow from 192 to **298** lakes in the same PR. The operator-only list stays the 4 TVA mainstem pilots.

## What approval allows
- The central Publisher may accept Lake Brain artifacts that declare this release (`PackagedReleaseResolver` requires `APPROVED`).
- Customer use of the release, including CUSTOMER-lane level copies for the 106 batch 2 lakes once the Publisher, LakeBrainJob and Engine reader are rebuilt and enabled under their own approvals.

## Until it is approved
- The Publisher accepts only an `APPROVED` release, so a Publisher image built from a commit carrying this release would refuse Lake artifacts. Do not merge before approval, or approve before the next Publisher redeploy and LakeBrainJob rebuild. Nothing is deployed by merging.

## What it does not allow
- Turning on any customer flag or Engine reader (`SECTOR_LAKE_LEVEL_OUTPUT`, `SECTOR_BRAIN_OUTPUT_READER`, `SECTOR_LAKES_READY_OUTPUT`), a deploy, a schedule change or a live build: each is a separate owner decision.
- Binding Clinton Lake IL, Upper Klamath Lake OR or any other lake to a new provider: each binding goes through the acceptance gate.
- Any CDEC binding without written permission from California DWR (the 22.1 source-access rule is unchanged).

## To approve
Michael confirms in chat or in an "Owner approval (Michael, …)" comment on Sector_Ops #51, quoting the digest above; then set `approval.status` to `APPROVED` here and in `brains/lake/runtime/knowledge-release.json`.
