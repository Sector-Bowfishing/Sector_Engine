# Approval record: `lake-knowledge-2026-11-22.3` (PENDING)

| Field | Value |
|---|---|
| Release | `lake-knowledge-2026-11-22.3` (Lake Brain reviewed source bindings, `PACKAGED_IN_IMAGE`) |
| Release digest | `sha256:d4e8dbb39444b789f01c736a92edc2679527231130a73a4d249afb3e968efefc` |
| Supersedes | `lake-knowledge-2026-11-22.1` (APPROVED 2026-11-22 08:00Z, Sector_Ops #51 comment 7076252747: the CDEC, NOAA CO-OPS and USGS-stage provider types, no binding changed) |
| Status | **NOT_RECORDED: pending Michael's approval** |
| Requested scope | INTERNAL, CALIBRATION and CUSTOMER (same as 2026-11-22.1) |

Batch 2 on PR #222 was packaged first as `.1` (id taken on main by #219's approved release), then as `.2` (never approved, never on main). The 2026-11-22 Mac mini live checks changed the packaged table again, and the release tool requires a new id when content changes, so batch 2 is now `.3`. The 22.1 record is unchanged.

## What changed in the release
- `LakeBrain/LakeSourceBindingsGenerated.swift`: the table gains the **102** batch 2 records (`jobs/lake-brain/data/bindings.batch2.v1.json`) and `acceptedLakeIds` goes from 187 to **289** (`accepted_batch.json` + `accepted_batch2.json`). Lake's reviewed set (with the 5 pilots) goes from 192 to **294**.
- Batch 2 = the excluded research-bound lakes that passed the 2026-11-22 re-check on a provider the engine already reads (Sector_Ops #51 comments 7074433014 and 7075462499; Michael's "Yes 1-4", 2026-11-22 06:39Z), less the lakes held after review and after the live checks (Sector_Ops #51 comment 7085401013). Review packet: `docs/brains/LAKE_BRAIN_ACCEPTED_BATCH2_2026-11-22.md`.
- **Batch 2 is a lower-assurance tier than batch 1.** Batch 1 admitted only pre-registered waves with status VERIFIED or VERIFIED_CORROBORATED and no flags. Batch 2 admits, under "Yes 1-4", lakes those rules excluded: coordinate-flagged, VERIFIED_ENVELOPE (post-hoc envelope promotion) and VERIFIED_FLAG rows (counts in the packet), plus wave-1 flagged rows and history/live-mismatch lakes. Only 2 have an independent second gauge (Logan Martin AL, Red Lake MN).
- Held out (not in this release): Lake Mattamuskeet NC (different history site/parameter, no full pool; batch 3 once checked), Blue Marsh Lake PA (check (b) FAIL: NAVD88 - NGVD29 = -0.74 ft, sd 0.00, 2,877 pairs over 61 days; for batch 3), Lake Darling ND (check (b) FAIL: NWS DARN8 fallback +1.06 ft vs the dam series; CWMS fallback 0.00) and Rend Lake IL (check (b) FAIL: live CWMS lrgsShef-raw 0.55 ft below both NWS RNDI2 and the datman-rev history). Also not in it: Clinton Lake IL and Upper Klamath Lake OR (no engine adapter in batch 2's scope; Clinton could now use 22.1's `usgsStage`, a follow-up binding).
- History offsets, each with its basis in the history entry's note (applied once by the runner for every provider since #229): Devils Lake ND **1400.00** (corrected from 1401.33, which read 1.33 ft above live on 30 matching days, sd 0.02), Lake Washington WA +0.36 ft (sign confirmed by the live check, which measured +0.44 ft; see "Decisions"), Toledo Bend TX -0.18 ft.
- The 15 ft history/live rule, as written, flags Navajo NM, Allegheny PA, Canyon TX and Mississinewa IN. In all four, history and live are the same series and agree within 0.005 ft on matching days (seasonal drawdown or fill). They stay in the release, recorded as flagged by the rule as written, owner decision pending.
- `LakeBrain/LakeSourceBindings.swift` and `LakeBrain/LakeGeneratedBindings.swift`: unchanged from 22.1.

## Customer-facing effect
- By the 2026-11-20 20:01Z owner rule (the customer Lake-level list is exactly Lake's reviewed set), `customer_lake_level_eligible.json` and `LakeLevelEligibility.validatedLakeIds` grow from 192 to **294** lakes in the same PR. Every reviewed TVA lake is on that list like any other lake (the 4 mainstem pilots plus batch 2's Kentucky KY, Kentucky TN, Cherokee and Chickamauga): Michael dropped the operator-only class on 2026-11-22 19:34Z ("every lake needs to be added", Sector_Ops #51 comment 7084511040), reversing the 2026-11-20 choice. Fontana NC and Hiwassee NC (TVA, still excluded with no reviewed binding) are not on the list: adding them needs a binding through the acceptance gate. Nothing reaches a customer until the customer flags and the Engine reader are turned on, each under its own approval.

## Decisions for Michael (not applied here)
- Lake Washington offset: keep +0.36 ft (1874-day mean, sd 0.08) or use the measured +0.44 ft (sd 0.06, 1,369 hourly pairs 2026-06-18..08-17, a post-hoc window because the history stopped on 08-17)?
- The 15 ft rule: keep it as written (it flags the 4 lakes above) or base it on matching days?
- Lake Darling: drop NWS DARN8 as a fallback or give it a -1.06 ft offset. Rend Lake: decide which series is right before release. Blue Marsh: apply -0.74 ft to the NGVD29 fallback and history, as for Beltzville?
- Salamonie IN and Lake Washington WA history series have stopped updating: rebind to continuing series.

## What approval allows
- Recording the 102 batch 2 bindings as the owner-approved Lake knowledge for INTERNAL, CALIBRATION and CUSTOMER scope, and with it the 294-lake customer Lake-level list.

## Before approval
- Approval is a record, not an enforced gate on the Lake path: Lake artifacts declare `knowledgeRelease` NONE (`brains/lake/runtime/publish_artifact.py:44`, `jobs/brain_platform/sector_brain_platform/publisher/flat_artifact.py:133`, `publisher/validate.py:188-195`), so nothing refuses a Lake artifact while this release is NOT_RECORDED. The customer flags are the only enforced gate. Nothing is deployed by merging; do not merge before approval.

## What it does not allow
- Turning on any customer flag or Engine reader (`SECTOR_LAKE_LEVEL_OUTPUT`, `SECTOR_BRAIN_OUTPUT_READER`, `SECTOR_LAKES_READY_OUTPUT`), a deploy, a schedule change or a live build: each is a separate owner decision.
- Binding any held lake (Mattamuskeet, Blue Marsh, Lake Darling, Rend Lake), Clinton Lake IL, Upper Klamath Lake OR or any other lake outside this table: each binding goes through the acceptance gate.
- Any CDEC binding without written permission from California DWR (the 22.1 source-access rule is unchanged).

## To approve
Michael confirms in chat or in an "Owner approval (Michael, …)" comment on Sector_Ops #51, quoting the digest above; then set `approval.status` to `APPROVED` here and in `brains/lake/runtime/knowledge-release.json`.
