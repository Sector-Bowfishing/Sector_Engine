# Approval record: `lake-knowledge-2026-11-22.2` (PENDING)

| Field | Value |
|---|---|
| Release | `lake-knowledge-2026-11-22.2` (Lake Brain reviewed source bindings, `PACKAGED_IN_IMAGE`) |
| Release digest | `sha256:7343fbcbcb66a266636b6c5d31e097b25c9e265947cab50b0f643c5dcc193d61` |
| Supersedes | `lake-knowledge-2026-11-22.1` (APPROVED 2026-11-22 08:00Z, Sector_Ops #51 comment 7076252747: the CDEC, NOAA CO-OPS and USGS-stage provider types, no binding changed) |
| Status | **NOT_RECORDED: pending Michael's approval** |
| Requested scope | INTERNAL, CALIBRATION and CUSTOMER (same as 2026-11-22.1) |

Batch 2 was first packaged as `lake-knowledge-2026-11-22.1` on its branch; that id was taken on main by the approved #219 release, so batch 2 is this new id. The 22.1 record is unchanged. The digest above is after the #222 review fixes (2 lakes held, 3 history offsets recorded, one series id cleaned).

## What changed in the release
- `LakeBrain/LakeSourceBindingsGenerated.swift`: the table gains the **104** batch 2 records (`jobs/lake-brain/data/bindings.batch2.v1.json`) and `acceptedLakeIds` goes from 187 to **291** (`accepted_batch.json` + `accepted_batch2.json`). Lake's reviewed set (with the 5 pilots) goes from 192 to **296**.
- Batch 2 = the excluded research-bound lakes that passed the 2026-11-22 Mac mini re-check on a provider the engine already reads (Sector_Ops #51 comments 7074433014 and 7075462499; Michael's "Yes 1-4", 2026-11-22 06:39Z). Review packet: `docs/brains/LAKE_BRAIN_ACCEPTED_BATCH2_2026-11-22.md`.
- **Batch 2 is a lower-assurance tier than batch 1.** Batch 1 admitted only pre-registered waves with status VERIFIED or VERIFIED_CORROBORATED and no flags. Batch 2 admits, under "Yes 1-4", lakes those rules excluded: 57 coordinate-flagged, 29 VERIFIED_ENVELOPE (post-hoc envelope promotion) and 10 VERIFIED_FLAG (58 / 30 / 10 before the two holds below), plus wave-1 flagged rows and 8 history/live-mismatch lakes. Only 2 have an independent second gauge (Logan Martin AL, Red Lake MN); 30 others list the same gauge through another endpoint, which is not R9. The 15 ft history/live series check was not run for batch 2 (pending, Mac mini).
- History offsets recorded with their basis: Lake Washington WA +0.36 ft (1874-day mean, sd 0.08; the value had leaked into the series id, now clean), Rend Lake IL -0.55 ft, Toledo Bend TX -0.18 ft. The engine applies `offsetFt` to `usgsDaily` history (Toledo Bend), not to `cwmsDaily` (Washington, Rend): those two are recorded data only.
- Held out (not in this release): Lake Mattamuskeet NC (different history site/parameter, no full pool; batch 3 once checked) and Blue Marsh Lake PA (datum mix unresolved). Also not in it: Clinton Lake IL and Upper Klamath Lake OR (no engine adapter in batch 2's scope; Clinton could now use 22.1's `usgsStage`, a follow-up binding).
- `LakeBrain/LakeSourceBindings.swift` and `LakeBrain/LakeGeneratedBindings.swift`: unchanged from 22.1.

## Customer-facing effect
- By the 2026-11-20 20:01Z owner rule (the customer Lake-level list is exactly Lake's reviewed set), `customer_lake_level_eligible.json` and `LakeLevelEligibility.validatedLakeIds` grow from 192 to **296** lakes in the same PR. The operator-only list stays the 4 TVA mainstem pilots. Nothing reaches a customer until the customer flags and the Engine reader are turned on, each under its own approval.

## What approval allows
- Recording the 104 batch 2 bindings as the owner-approved Lake knowledge for INTERNAL, CALIBRATION and CUSTOMER scope, and with it the 296-lake customer Lake-level list.

## Before approval
- Approval is a record, not an enforced gate on the Lake path: Lake artifacts declare `knowledgeRelease` NONE (`brains/lake/runtime/publish_artifact.py:44`, `jobs/brain_platform/sector_brain_platform/publisher/flat_artifact.py:133`, `publisher/validate.py:188-195`), so nothing refuses a Lake artifact while this release is NOT_RECORDED. The customer flags are the only enforced gate. Nothing is deployed by merging; do not merge before approval.

## What it does not allow
- Turning on any customer flag or Engine reader (`SECTOR_LAKE_LEVEL_OUTPUT`, `SECTOR_BRAIN_OUTPUT_READER`, `SECTOR_LAKES_READY_OUTPUT`), a deploy, a schedule change or a live build: each is a separate owner decision.
- Binding Lake Mattamuskeet NC, Blue Marsh Lake PA, Clinton Lake IL, Upper Klamath Lake OR or any other lake outside this table: each binding goes through the acceptance gate.
- Any CDEC binding without written permission from California DWR (the 22.1 source-access rule is unchanged).

## To approve
Michael confirms in chat or in an "Owner approval (Michael, …)" comment on Sector_Ops #51, quoting the digest above; then set `approval.status` to `APPROVED` here and in `brains/lake/runtime/knowledge-release.json`.
