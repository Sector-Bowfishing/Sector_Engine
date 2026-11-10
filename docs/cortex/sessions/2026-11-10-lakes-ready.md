# Session record: `GET /lakes/ready` from customer-lane copies (Sector_Engine #156)

Standards: Rehtac Cortex unavailable in this cloud session (`CORTEX_HOME` unset); repo CLAUDE.md rules followed directly, pack sector/engine, pin ecaef70. Date: 2026-11-10. Branch: `feat/lakes-ready-2026-11-10` (off main 5d011b5).

## Scope
Issue #156: a customer Engine endpoint listing the lakes with real Brain data for the iOS lake picker (iOS_Sector #227,
`ReadyLakeSource`). Owner rules (Sector_Ops #53): additive, flag default off, no IAM, no deploy, no Publisher switch, no production call.

## Done
- `API/LakesReadyAPI.swift`: `LakesReadyResponse` v1, `LakesReadyConfig` (`SECTOR_LAKES_READY_OUTPUT`, default off),
  `CustomerLakesSnapshot` (serves only `customer/lakes/{k}/{clarity|waterTemp|level}` from one read of `customer/lakes`),
  `CachingBrainOutputReader` (60 s, one fetch at a time per path). Per-layer status comes from the #144 readers unchanged.
- Server: `lakes/ready` registered only with the flag on (off → no route → 404, as `/lake/level`); reader from
  `SECTOR_BRAIN_OUTPUT_READER` (none by default → `200`, `lakes: []`).
- `wind` and `intelligence`: no per-lake CUSTOMER-lane copy exists, so v1 never emits them (documented in the contract and §9).
- Contract `contracts/phone/lakes-ready-v1.json`; synthetic golden `verification/fixtures/phone-contract/lakes-ready-v1.golden.json`
  (top level, so the `/conditions` golden loaders skip it); `LakesReadyAPITests` (16) and `verification/test_lakes_ready_contract.py` (8).
- Design note §9, path ownership matrix reader column, fixtures README.

## Decisions (reversible, stated in the PR)
- One subtree read instead of ~1,900 per-copy reads per request; freshness still evaluated per request.
- A layer is present only when ready (absent = not ready), not reported as "unavailable".
- `level` keeps the Lake level gates (`SECTOR_LAKE_LEVEL_OUTPUT=1` and `validatedLakeIds`), so the picker never advertises a
  level `/lake/level` would not serve.

## Independent review (round 1) and fixes
- Blocking: none.
- Should-fix, fixed: a failed read was cached for 60 s (now never kept); the subtree read had the 2 s per-copy bound (now 5 s);
  the raw bytes were re-parsed and formatters rebuilt on every request (the parsed snapshot is cached; formatters built once).
- Nits, fixed: the 10-minute future bound is documented as `/lakes/ready`'s own for `level`; env read once in `main.swift`;
  tests for a failed-then-good read, a lossy-key copy with another lakeId, non-object copies. The open-ended cache key set
  went away with the snapshot cache (one entry).

## Verification
- `swift build --build-tests` + `swift test` in `swift:6.1-jammy` (Docker, image via mirror.gcr.io after Docker Hub 429s):
  488 tests, 0 failures (after the review fixes).
- pytest `verification` (45 passed, 6 skipped), `tools/architecture` (187 passed after the digest re-record), `tools/cutover`,
  `jobs/brain-orchestrator/tests`: pass. `tools/research`: 2 failures that also fail on main in this container (read-only files, root).
- `collect_certification.py`: failing none (after installing the wind/vegetation runtime requirements into the venv).
- `swift package resolve` in the container rewrote `Package.resolved`; that change was reverted and is not in the PR.

## Not done / gated (owner)
- Flipping `SECTOR_LAKES_READY_OUTPUT`, setting `SECTOR_BRAIN_OUTPUT_READER`, the reader IAM grant, the `PUBLISHER_CUSTOMER_*`
  switches, deploys. Customer-lane copies for wind (per lake) and Intelligence need their Brains first.
