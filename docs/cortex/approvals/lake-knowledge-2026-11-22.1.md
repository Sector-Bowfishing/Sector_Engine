# Approval record: `lake-knowledge-2026-11-22.1` (PENDING)

| Field | Value |
|---|---|
| Release | `lake-knowledge-2026-11-22.1` (Lake Brain reviewed source bindings, `PACKAGED_IN_IMAGE`) |
| Release digest | `sha256:930ca8e42de0c28f9440a7ac2a91b6ac3437e9e3afae3a665a608dd5e53596bc` |
| Supersedes | `lake-knowledge-2026-11-21.2` (two packaged source files gained the CDEC, NOAA CO-OPS and USGS-stage provider types; no binding changed) |
| Status | **NOT_RECORDED: pending Michael's approval** |
| Requested scope | INTERNAL, CALIBRATION and CUSTOMER (same as 2026-11-21.2) |

## What changed in the release
- `LakeBrain/LakeSourceBindings.swift`: `LevelSeriesRef.Provider` gains `cdec` (with its `sourceId` and `providerName`), and `LakeHistorySource` gains `cdecDaily(station:sensor:dur:offsetFt:)`. These are types only: the reader is `LakeLevelFeedsCDEC.swift`, outside the release.
- `LakeBrain/LakeSourceBindings.swift` (2026-11-22, `feat/lake-readers-coops-usgsstage-2026-11-22`, folded into this same pending release): `Provider` also gains `coops` and `usgsStage`, and `LakeHistorySource` gains `coopsDaily(station:)` and `usgsStageDaily(site:datum:stat:)`. Types only: the readers are `LakeLevelFeedsCOOPS.swift` and `LakeLevelFeedsUSGSStage.swift`, outside the release.
- `LakeBrain/LakeGeneratedBindings.swift`: a generated history record may name `cdecDaily` (optional `station`, `sensor`, `dur` fields), `coopsDaily` (`station`) or `usgsStageDaily` (`site`, `datum`, `stat`).
- `LakeBrain/LakeSourceBindingsGenerated.swift`: unchanged. The accepted set, the reviewed set (192) and the customer Lake-level list are unchanged; no lake is bound to CDEC, CO-OPS or USGS stage.

## What approval allows
- The central Publisher may accept Lake Brain artifacts that declare this release (`PackagedReleaseResolver` requires `APPROVED`).
- Customer use of the release.

## Until it is approved
- Approval is a record, not an enforced gate on the Lake path: Lake artifacts declare `knowledgeRelease` NONE (`brains/lake/contracts/describe_contract.py:25`, `flat_artifact.py`), so nothing refuses a Lake artifact while this release is NOT_RECORDED. Nothing is deployed by merging.

## What it does not allow
- Binding any lake to CDEC, NOAA CO-OPS or USGS stage: each binding goes through the acceptance gate.
- **CDEC needs DWR's permission first.** CDEC's `robots.txt` disallows `/dynamicapp/`, the path of the JSONDataServlet the reader uses. Under the owner rule (Michael, 2026-11-22: use a source only if its terms / robots.txt do not forbid automated reading), no CDEC binding is made without written permission from California DWR.

## To approve
Michael confirms in chat or in an "Owner approval (Michael, …)" comment on Sector_Ops #51; then set `approval.status` to `APPROVED` here and in `brains/lake/runtime/knowledge-release.json`.
