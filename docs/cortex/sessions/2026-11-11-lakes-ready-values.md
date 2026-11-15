# Session record: `GET /lakes/ready` values, extent and directoryId (Sector_Engine #158)

Standards: Rehtac Cortex unavailable in this cloud session (`CORTEX_HOME` unset, no briefing hook); repo CLAUDE.md rules followed directly, pack sector/engine, pin ecaef70. Date: 2026-11-11. Branch: `cortex/lakes-ready-layers-2026-11-11` (off main b90e56a). Scheduled cloud session; the stalled MacBook session's work was not reused.

## Scope
Issue #158 (from iOS_Sector #227, owner approval 2026-11-10): per ready lake, a lake-wide value per layer, an extent (bbox now),
and `directoryId` in the app's `Name|ST` format next to the Brain key. Same rules as #156: customer-lane copies only, no read of
`/lakes/*/states` or `/brains/*`, no IAM change, flag stays off, no deploy.

## Done
- `LakesReadyAPI.swift`: `ReadyLake.directoryId` (= `lakeId`) and `brainKey` (`BrainPlatform.lakeKey`); `ReadyClarityLayer`
  (`valueFt` = copy `centralFt`, optional `lowFt`/`highFt`) and `ReadyWaterTempLayer` (`valueF`), taken from the same copy the
  #144 reader judged ready; `level` unchanged (readiness only); optional `extent`.
- `LakeRegistryExtents.swift`: parses the public Lake Registry index (`registry/lakes.v1.json`, LAKE_REGISTRY_GEOMETRY_CONTRACT.md)
  into `extent {bbox {west,south,east,north}, confidence}`; only a published shoreline at HIGH or MEDIUM, not `identity-risk`, with
  a valid box. `LakeRegistryExtentCache`: 30 min TTL, 60 s failure TTL, fetched alongside the snapshot. A failed fetch drops
  `extent`, never a lake. `SECTOR_LAKE_REGISTRY_INDEX_URL` overrides the URL.
- Server: the registry cache is built only inside the `SECTOR_LAKES_READY_OUTPUT=1` branch (flag off: no route, no fetch).
- Contract `contracts/phone/lakes-ready-v1.json` 1.0.0 → 1.1.0 (additive; response `version` stays 1), golden updated, Swift
  tests (ids, values, NO_VALUE, extent filters, cache TTLs, server form, flag off) and Python contract tests (additive-over-1.0
  check). Design note §9 updated. Engineering status re-recorded (`collect_certification.py`: failing none).

## Decisions (reversible, stated in the PR)
- Contract stays v1 (1.1.0): nothing changes meaning; new keys only.
- Extent source = the Lake Registry index, not `jobs/lake-surface/polygons.geojson.gz`: the registry is the published, confidence-
  rated geometry identity; the older polygons include degenerate and misplaced shapes (e.g. a zero-area Lake Shafer IN). The
  registry is public (no credential, no IAM) and not a Brain output, so the #156 read rule is kept.
- LOW-confidence and `identity-risk` lakes get no box (a box on the wrong water is worse than the app's default reach).
- No outline yet: the registry has display polygons, but serving them is a separate decision (size, caching, app drawing).

## Not done: blocked (owner decision)
- **Wind** (mph + FROM direction) and **Intelligence score**: no per-lake CUSTOMER-lane copy exists. Wind's only copy is the global
  `customer/wind/outlookModel`; the Wind publication contract is SHADOW. Sector Intelligence's publication contract allows
  RESEARCH to CALIBRATION only. Serving either needs a new Publisher copy (`customer/lakes/{k}/wind`, `.../intelligence`), its
  schema and gates, a `CUSTOMER_COPY_FAMILIES` entry and an Engine reader, or (wind only) a decision to let the Engine compute a
  lake-wide forecast with the Brain's chosen outlook model. Planned phone fields are documented in the contract, not frozen.

## Independent review (round 1) and fixes
- Blocking: none.
- Should-fix, fixed: a failed registry refresh dropped every box (now the last good index is served until a retry succeeds);
  `SECTOR_LAKE_REGISTRY_INDEX_URL=file://...` could not work through the HTTP client (now read from disk; tested).
- Nits, fixed: a clarity range that does not bracket the value is dropped; fixture `count`. Not changed (stated): 30 min TTL vs
  the bucket's 5 min max-age (the geometry is versioned); JSON booleans in a bbox (trusted source).

## Verification
- No Swift toolchain in this container (Docker Hub, mirror.gcr.io and download.swift.org refused by the egress proxy): Swift build
  and tests run in CI (`swift-tests.yml`) on the PR.
- pytest `tools/architecture` + `verification`: 233 passed, 5 skipped, 1 failed
  (`test_wind_package.py::test_staged_image_verifies_its_packaged_knowledge_release`, also fails on main in this container).
- `build_engineering_status.py --check`: OK after re-recording.
