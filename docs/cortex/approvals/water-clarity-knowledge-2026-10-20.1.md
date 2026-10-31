# Approval record: `water-clarity-knowledge-2026-10-20.1`

| Field | Value |
|---|---|
| Release | `water-clarity-knowledge-2026-10-20.1` (Water Clarity packaged catalog, `PACKAGED_IN_IMAGE`) |
| Release digest | `sha256:a16a9b38466c9b67af5f6454932e204a66bbb926c9f05f9110a0048e75c28f34` (unchanged by this record) |
| Approved by | Michael Cather (owner), in session, 2026-10-31 |
| Decision | Sector_Ops #18, D2 |
| Scope | **INTERNAL** and **CALIBRATION** use only |
| Customer eligible | **No**. This approval does not make the release or any Water Clarity output customer-eligible. |
| Promotion | None. No value, score, catalog entry or lifecycle state changes. |

## What this approval allows
- The central Publisher may accept Water Clarity artifacts that declare this release, in the INTERNAL-lane families listed in `brains/water-clarity/brain.json` (`operations.internalPublication`). The `--release-approval-not-recorded-ok` calibration exception is no longer needed for this release.

## What it does not allow
- Customer serving or customer publication. `operations.customerPublication` stays `NOT_ELIGIBLE` with `approvalRef: null`. Customer eligibility needs its own approval.
- Any change to the catalog. Changing a file in the release means a new `releaseId` and a new approval.
- Any deploy, run or schedule change. Those are approved separately.
