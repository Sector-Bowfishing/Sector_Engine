# Approval record: `lake-knowledge-2026-11-02.1`

| Field | Value |
|---|---|
| Release | `lake-knowledge-2026-11-02.1` (Lake Brain reviewed source bindings, `PACKAGED_IN_IMAGE`) |
| Release digest | `sha256:be71a8a8783bf91195f8ba7815e419dbfb99bdcd37f159cad31c04780fc5fdb1` (unchanged by this record) |
| Approved by | Michael Cather (owner), in chat, 2026-11-12 ~07:00Z |
| Decision | Sector_Ops #51, "Owner approval (Michael, 2026-11-12 ~07:00Z, posted by chat): Lake decisions + Ops panels deploy + Engine CORS", item 2 (M3 in the 06:52Z runner plan) |
| Scope | **INTERNAL** and **CALIBRATION** use only. The owner approved the release without naming a scope; the runner chose this narrower reading to match Water Clarity's release when it moved to Pulse. |
| Customer eligible | **No**. This approval does not make the release or any Lake output customer-eligible. |
| Promotion | None. No value, score, binding, catalog entry or lifecycle state changes. |

## What this approval allows
- The central Publisher may accept Lake Brain artifacts that declare this release (`PackagedReleaseResolver` requires `APPROVED`), in the INTERNAL-lane families listed in `brains/lake/brain.json` (`operations.internalPublication`).

## What it does not allow
- Merging Sector_Engine#168, the Orchestrator and Publisher deploys (M5), the first-publish baseline acknowledgement (M6) or enabling lake-brain (M7). Each needs Michael separately, after the B2 IAM paste and the Mac mini steps.
- The species-presence release (`gs://sector-lake-brain`, `presence/latest.json`). It stays approval `NOT_RECORDED`.
- Customer serving or customer publication. `operations.customerPublication` stays `NOT_ELIGIBLE` with `approvalRef: null`.
- Any change to the bindings. Changing a file in the release means a new `releaseId` and a new approval.

## Related decision (same approval, item 1)
- **L-H1:** Lake reads the Mac mini's local TVA archive, not live TVA only.
