# Approval record: `water-temp-knowledge-2026-11-03.1`

> **APPROVED** by Michael on 2026-11-16 (Sector_Ops #51, owner approval B1–B5, item B2).

| Field | Value |
|---|---|
| Release | `water-temp-knowledge-2026-11-03.1` (Water Temp Brain model definition, `PACKAGED_IN_IMAGE`) |
| Contents | One file: `brains/water-temperature/runtime/WaterTemperatureBrain/WaterTemperatureBrain.swift` (sha256 `84cd6002…3883087`, 22,429 bytes) |
| Release digest | `sha256:9e1bb9e23392cc1775c675b8853ecf5e60528fe23c78118626008ae1871ef280` (unchanged by this record) |
| Approved by | Michael Cather (owner), in chat, 2026-11-16 ~03:38Z |
| Decision | `owner-approval-2026-11-16/sector-ops-51-b1-b5`, item B2 (Sector_Ops #51 comment 6906604228) |
| Scope | **INTERNAL** and **CALIBRATION** use only, the same as the Water Clarity and Lake releases when they moved to Pulse. |
| Customer eligible | **No**. This approval does not make the release or any Water Temp output customer-eligible. |
| Promotion | None. No value, band, score, binding, catalog entry or lifecycle state changes. |

## What this approval allows
- The central Publisher may accept Water Temp Brain artifacts that declare this release (`PackagedReleaseResolver` requires `APPROVED`), in the INTERNAL-lane families listed in `brains/water-temperature/brain.json` (`operations.internalPublication`).

## What it does not allow
- The Water Temp flip, the Orchestrator and Publisher deploys, the first-publish baseline acknowledgement, or enabling water-temp. Each needs Michael separately.
- Showing a ± range in the app. The launch answer is "Estimate" with no range (owner approval 2026-11-14); the range failed WT-NOW-2, -3 and -4.
- Customer serving or customer publication. `operations.customerPublication` stays `NOT_ELIGIBLE`.
- Any change to the model. Changing the file means a new `releaseId` and a new approval.

## Addendum 2026-11-20: approved for customer use

> **APPROVED for CUSTOMER use** by Michael (owner), in chat, 2026-11-20 ~15:04Z; recorded on Sector_Ops #51.

- The manifest's approval scope is now `INTERNAL`, `CALIBRATION`, `CUSTOMER`, and `customerEligible` is `true`.
- The release itself is unchanged: same `releaseId`, files and `releaseDigest`, so artifacts already built against it still verify.
- This records the release's eligibility only. It does not turn on any customer copy (`PUBLISHER_CUSTOMER_*` stays Michael's switch), does not change `operations.customerPublication` in `brain.json` (the Brain stays `PRE_PRODUCTION`), and changes no value, band, score, binding, catalog entry or lifecycle state.
