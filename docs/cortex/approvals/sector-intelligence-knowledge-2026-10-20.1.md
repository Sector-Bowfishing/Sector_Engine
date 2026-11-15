# Approval record: `sector-intelligence-knowledge-2026-10-20.1`

> **DRAFT: not yet approved.** This record is prepared ahead of time. It takes effect only when Michael says "approve the Sector Intelligence knowledge release" and the `Approved by` and `Decision` rows below are filled in from his Sector_Ops #51 owner approval. Do not merge before that.

| Field | Value |
|---|---|
| Release | `sector-intelligence-knowledge-2026-10-20.1` (Sector Intelligence catalog, `PACKAGED_IN_IMAGE`) |
| Contents | One file: `brains/sector-intelligence/runtime/catalog.json` (sha256 `71d5f2d6…401f221e5e`, 11,559 bytes) |
| Release digest | `sha256:c295f528cf00b68987f023b45f1becaa5a2b1fdd872477497951bffa6df7c8ce` (unchanged by this record) |
| Approved by | PENDING (Michael Cather, owner, in chat) |
| Decision | PENDING (Sector_Ops #51 owner approval, the release step of the Sector Intelligence switch-on) |
| Scope | **INTERNAL** and **CALIBRATION** use only, the same as the Water Clarity, Lake and Water Temp releases when they moved to Pulse. |
| Customer eligible | **No**. This approval does not make the release or any Sector Intelligence output customer-eligible. |
| Promotion | None. No score, weight, band, binding, catalog entry or lifecycle state changes. |

## What this approval allows
- The central Publisher may accept Sector Intelligence artifacts that declare this release (`PackagedReleaseResolver` requires `APPROVED`), in the INTERNAL-lane families listed in `brains/sector-intelligence/brain.json`.

## What it does not allow
- The Sector Intelligence flip, the `SI_ARTIFACT_JOB=on` Orchestrator deploy, the Publisher deploy, the first-publish baseline acknowledgement, or enabling sector-intelligence. Each needs Michael separately.
- A combined 0–100 score in the app. The launch answer is **factors only** (owner approval on Sector_Ops #51); the relationship test did not hold.
- Customer serving or customer publication. `operations.customerPublication` stays `NOT_ELIGIBLE`.
- Any change to the catalog. Changing the file means a new `releaseId` and a new approval.
