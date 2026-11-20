# Approval record: `lake-knowledge-2026-11-20.1`

| Field | Value |
|---|---|
| Release | `lake-knowledge-2026-11-20.1` (Lake Brain reviewed source bindings, `PACKAGED_IN_IMAGE`) |
| Release digest | `sha256:7d8fe25dab620d3fc93c90d82c47254272c2c848da8e5ae997fc46d1f48ca5f8` |
| Supersedes | `lake-knowledge-2026-11-02.1` (its bindings file changed: 189 machine-verified bindings accepted) |
| Approved by | Michael Cather (owner), in chat, 2026-11-20 ~20:08Z; recorded on Sector_Ops #51 |
| Scope | **INTERNAL**, **CALIBRATION** and **CUSTOMER** |
| Customer eligible | **Yes** |

## What changed in the release
- `LakeBrain/LakeSourceBindingsGenerated.swift` now embeds `acceptedLakeIds` (189 lakes) from `jobs/lake-brain/data/accepted_batch.json`, accepted on the owner's all-lakes direction (Sector_Ops #51 comment 7049169954). Packet: `docs/brains/LAKE_BRAIN_ACCEPTED_BATCH_2026-11-20.md`.
- Every other packaged file is unchanged.

## What this approval allows
- The central Publisher may accept Lake Brain artifacts that declare this release (`PackagedReleaseResolver` requires `APPROVED`).
- Customer use of the release, carried from the 2026-11-20 addendum to `lake-knowledge-2026-11-02.1`.

## What it does not allow
- Turning on any customer copy: `PUBLISHER_CUSTOMER_LAKE_LEVEL` stays Michael's switch, and the customer Lake-level list (`customer_lake_level_eligible.json`) is unchanged.
- The species-presence release (`presence/latest.json`): it stays approval `NOT_RECORDED`.
- Any change to the bindings: changing a file in the release means a new `releaseId` and a new approval.
