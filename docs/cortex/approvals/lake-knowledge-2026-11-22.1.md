# Approval record: `lake-knowledge-2026-11-22.1` (PENDING)

| Field | Value |
|---|---|
| Release | `lake-knowledge-2026-11-22.1` (Lake Brain reviewed source bindings, `PACKAGED_IN_IMAGE`) |
| Release digest | `sha256:d635f4a91c2bfc93e6f8b51542d0d84a8862f82aa54da440672dd0ee0fcae522` |
| Supersedes | `lake-knowledge-2026-11-21.2` (two packaged source files gained the CDEC provider types; no binding changed) |
| Status | **NOT_RECORDED: pending Michael's approval** |
| Requested scope | INTERNAL, CALIBRATION and CUSTOMER (same as 2026-11-21.2) |

## What changed in the release
- `LakeBrain/LakeSourceBindings.swift`: `LevelSeriesRef.Provider` gains `cdec` (with its `sourceId` and `providerName`), and `LakeHistorySource` gains `cdecDaily(station:sensor:dur:offsetFt:)`. These are types only: the reader is `LakeLevelFeedsCDEC.swift`, outside the release.
- `LakeBrain/LakeGeneratedBindings.swift`: a generated history record may name `cdecDaily` (optional `station`, `sensor`, `dur` fields).
- `LakeBrain/LakeSourceBindingsGenerated.swift`: unchanged. The accepted set, the reviewed set (192) and the customer Lake-level list are unchanged; no lake is bound to CDEC.

## Until it is approved
- The Publisher (`PackagedReleaseResolver`) accepts only an `APPROVED` release, so a Publisher image built from this commit would refuse Lake artifacts. Approve before the next Publisher redeploy and LakeBrainJob rebuild; nothing is deployed by merging.

## To approve
Michael confirms in chat or in an "Owner approval (Michael, …)" comment on Sector_Ops #51; then set `approval.status` to `APPROVED` here and in `brains/lake/runtime/knowledge-release.json`.
