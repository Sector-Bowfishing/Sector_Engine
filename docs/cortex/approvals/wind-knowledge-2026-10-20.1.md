# Approval record: `wind-knowledge-2026-10-20.1`

> **APPROVED** by Michael on 2026-11-23 (Sector_Ops #51, the Wind move onto Pulse, step M3).

| Field | Value |
|---|---|
| Release | `wind-knowledge-2026-10-20.1` (Wind Brain packaged knowledge, `PACKAGED_IN_IMAGE`) |
| Contents | `brains/wind/runtime/lakes.json` (sha256 `1ded19e9…0dede51`, 2,157 bytes) and `brains/wind/runtime/sector_wind/brain/validation_evidence.json` (sha256 `0fb7ef09…bd09082ee`, 5,948 bytes) |
| Release digest | `sha256:690adf50929f1efe5dc85cda8f281b02313451f08871745304ed024af7e65b42` (unchanged by this record) |
| Approved by | Michael Cather (owner), in chat, 2026-11-23 06:21Z ("I approve these", answering the Wind move steps of Sector_Ops #51 comment 6889632595, item 1: the Wind knowledge release approval, M3) |
| Decision | Recorded on Sector_Ops #51 comment 7093271287 (2026-11-23 06:22Z) |
| Scope | **INTERNAL** and **CALIBRATION** use only, the same as the Water Clarity, Lake and Water Temp releases when they moved to Pulse. Wind artifacts declare lifecycle `CALIBRATION`. |
| Customer eligible | **No**. This approval does not make the release or any Wind output customer-eligible. |
| Promotion | None. No value, band, score, model, lake list or lifecycle state changes. |

## What this approval allows
- The central Publisher may accept Wind Brain artifacts that declare this release (`PackagedReleaseResolver` requires `APPROVED`), in the INTERNAL-lane families listed in `brains/wind/brain.json` (`operations.internalPublication`).

## What it does not allow
- The Wind flip (Engine #177), the Orchestrator and Publisher deploys, the first-publish baseline acknowledgement, or enabling wind in the execution control. Each needs Michael separately.
- The app's wind source decisions WS-1..WS-4, or any customer-visible change. The launch answer (deterministic NBM plus the risky-night flag, owner approval 2026-11-14) ships through the app, under its own approvals.
- Customer serving or customer publication. `operations.customerPublication` stays `NOT_ELIGIBLE`.
- The NBM point forecasts (#90) or the risky-night flag: both stay off behind their own switches, and neither is in this release.
- Any change to the release's files. Changing either file means a new `releaseId` and a new approval.

## Approval
Approved by Michael in chat on 2026-11-23 at 06:21Z, recorded on Sector_Ops #51 (comment 7093271287). Recording it changed only `approval` in `brains/wind/runtime/knowledge-release.json` (status `APPROVED`, this record, scope `INTERNAL` + `CALIBRATION`, not customer-eligible) and the matching text in `brains/wind/brain.json`. The release content and digest are unchanged.
