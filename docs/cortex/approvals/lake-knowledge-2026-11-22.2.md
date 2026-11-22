# Approval record: `lake-knowledge-2026-11-22.2` (PENDING)

| Field | Value |
|---|---|
| Release | `lake-knowledge-2026-11-22.2` (Lake Brain reviewed source bindings, `PACKAGED_IN_IMAGE`) |
| Release digest | `sha256:31a8d1ea989baf00e612d46ff3ef090582629dd0869a353c2d02a98927e5358f` |
| Supersedes | `lake-knowledge-2026-11-21.2` (two packaged source files gained the Reclamation Hydromet provider types; no binding changed) |
| Status | **NOT_RECORDED: pending Michael's approval** |
| Requested scope | INTERNAL, CALIBRATION and CUSTOMER (same as 2026-11-21.2) |

`.2` because the parallel CDEC reader branch drafts `lake-knowledge-2026-11-22.1`. Whichever of the two merges second rebases, recomputes the digest over both sets of type changes, and takes the next free id.

## What changed in the release
- `LakeBrain/LakeSourceBindings.swift`: `LevelSeriesRef.Provider` gains `hydromet` (with its `sourceId` and `providerName`), and `LakeHistorySource` gains `hydrometDaily(region:site:param:offsetFt:)`. Doc comments name division CWMS offices (`NWDP`, `NWDM`) as valid `station` values; the CWMS behaviour is unchanged. These are types only: the reader is `LakeLevelFeedsHydromet.swift`, outside the release.
- `LakeBrain/LakeGeneratedBindings.swift`: a generated history record may name `hydrometDaily` (new optional `region` field; `site` and `param` already exist).
- `LakeBrain/LakeSourceBindingsGenerated.swift`: unchanged. The accepted set, the reviewed set (192) and the customer Lake-level list are unchanged; no lake is bound to Hydromet.

## Until it is approved
- The Publisher (`PackagedReleaseResolver`) accepts only an `APPROVED` release, so a Publisher image built from this commit would refuse Lake artifacts. Approve before the next Publisher redeploy and LakeBrainJob rebuild; nothing is deployed by merging.

## To approve
Michael confirms in chat or in an "Owner approval (Michael, …)" comment on Sector_Ops #51; then set `approval.status` to `APPROVED` here and in `brains/lake/runtime/knowledge-release.json`.
