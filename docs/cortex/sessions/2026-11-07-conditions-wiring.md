# Session record: conditions consolidation, tile wiring into `/conditions` (Sector_Ops #53)

Standards: Rehtac Cortex unavailable in this cloud session (`CORTEX_HOME` unset); repo CLAUDE.md rules followed directly, pack sector/engine, pin ecaef70. Date: 2026-11-07. Branch: `feat/conditions-wiring-2026-11-07`.

## Scope
Spec `CONDITIONS_CONSOLIDATION_SPEC_V1` §1/§4: wire the NWS/NBM adapter (#145) and the Brain customer-copy readers (#144) into
`/conditions` through `TileShadow.resolve` and the per-tile flags (#143). Every flag stays `off`; nothing is deployed or switched.

## Done
- `Conditions/ConditionsTileWiring.swift`: per-tile wiring (table in the spec's Engine implementation note). Injectable sources
  (`ConditionsTileProviders`); production uses `.live`.
- `Conditions/BrainOutputReaderConfig.swift`: reader from env `SECTOR_BRAIN_OUTPUT_READER` (default none = every copy UNKNOWN);
  `rtdb` = GET-only, `customer/` paths only, sector-brain database only.
- `SectorEngineAPI.conditions`: flags read once per request; windOutlookModel decided concurrently with the (unchanged) env forecast;
  clarity resolved before the score; the other tiles applied to the built response; `tileSources` reports what was served.
- Additive response fields `lakeLevel`, `clarityBrain`, `waterTempBrain`, `generation.bindingSource` (all omitted unless served).
- Foundation extensions (additive): `TileShadow.resolve(shadowLog:)`, `TileShadow.oldPathEntry`, `TileSources.build(resolved:)`.
- Forecast: `windModel` parameter threaded through `ForecastCache` (key unchanged for the env model).
- `ConditionsInput.clarityBrainVisibilityFt` + `ClarityFactor.visibilityFt` override (nil by default; serve-only; changes the score).

## Found and fixed while testing
- An `async let` group in the response step aborted the Linux runtime ("freed pointer was not the last allocation", the failure
  ConditionsSnapshot documents for revs 00041-00042). Replaced by unstructured tasks; the new suite reproduces the crash otherwise.

## Verification
- `swift build --build-tests` + `swift test` in `swift:6.1-jammy` (the production toolchain, run in Docker in this session):
  463 tests, 0 failures, incl. 25 new `ConditionsTileWiringTests` (every tile off/shadow/serve, fallback, breaker open, frozen
  fields untouched, PhoneContractTests' validator + the build 28 decoder over every golden with all flags off AND all in serve).
- `verification/fixtures/conditions/response_contract.golden.json`: the three new top-level fields and `generation.bindingSource` added.
- pytest `tools/architecture`, `verification`, `tools/research`: pass except 2 tests that also fail on main in this container
  (they rely on read-only files, and the container runs as root).

## Not done / gated (owner)
- Turning any flag to `shadow`/`serve` (Remote Config), setting `SECTOR_BRAIN_OUTPUT_READER`, the IAM read grant, deploys.
- Not verified here: live NWS/NBM latency against the 3 s serve deadline; macOS build (CI covers it).
