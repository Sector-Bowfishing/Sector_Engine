# Session record: `/conditions` range check (400 for an out-of-range coordinate)

Standards: Rehtac Cortex unavailable in this cloud session (`CORTEX_HOME` unset); repo CLAUDE.md rules followed directly, pack sector/engine, pin ecaef70. Date: 2026-11-11. Branch: `cortex/conditions-range-check-2026-11-11` (off main bff46699). Session: scheduled approved-work runner.

## Scope
Owner approval (Michael, 2026-11-10 ~23:57Z) on Sector_Ops #51, item 1: `/conditions` and the `/conditions/batch` points return 400 when
`lat` ∉ [-90, 90] or `lon` ∉ [-180, 180], with a Swift test; merge under the standing approvals. Cause: deploy run 42889797052 stopped at the
smoke check `/conditions?lat=95&lon=0` must return 400 (got 503).

## Done
- `Sources/SectorEngine/Conditions/CoordinateRange.swift`: `isValid(lat:lon:)`, inclusive bounds; NaN and infinities fail (`Double("nan")` parses).
- `SectorEngineServer/main.swift`: GET `/conditions` answers 400 for an out-of-range coordinate; POST `/conditions/batch` answers 400 if any point is out of range.
- `Tests/SectorEngineTests/CoordinateRangeTests.swift`.
- Certification digest re-recorded (`Sources/`, `Tests/` are digest roots): `failing: none`; engineering status rewritten and `--check` OK.

## Decisions (reversible)
- **Whole batch rejected** on any bad point, rather than dropping it: a dropped point would shift `results` against the request order.
- **Check lives in the library**, so it is unit-testable; the server target has no test target. The deploy smoke checks the route end to end.

## Verification
- Swift is not installed in this cloud runner; `swift-tests` (macOS + Linux 6.1) CI is the Swift proof.
- No deploy, IAM, rules or flag change from this branch.
