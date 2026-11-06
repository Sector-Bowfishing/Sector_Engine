# Session record: conditions consolidation, Brain output readers + Publisher customer copies (Sector_Ops #53)

Standards: Rehtac Cortex 3.1.2 @ ecaef70 (clean), pack sector/engine. Date: 2026-11-06. Branch: `feat/conditions-brain-readers-2026-11-06`.

## Scope
Spec `CONDITIONS_CONSOLIDATION_SPEC_V1` §0, §1, §4, §5: the Engine readers and the Publisher writers for the four new CUSTOMER-lane
copies. A separate foundation PR adds the tile flags and shadow helper, so nothing here is wired into `/conditions`
(`SectorEngineAPI.swift`, `ConditionsSnapshot.swift` and `main.swift` are untouched). New files only on the Swift side.

## Done
- **Swift readers** (`Sources/SectorEngine/API/`): `ClarityBrainOutputAPI`, `WaterTempBrainOutputAPI`, `GenerationBindingOutputAPI`,
  `WindOutlookModelOutputAPI`, with a shared read step `BrainCopyRead.swift`. Each reads only its `customer/` copy through
  `BrainOutputReader` and fails closed to UNKNOWN with a reason (`NO_READER`, `NO_PUBLICATION`, `SCHEMA_MISMATCH`, `LAKE_ID_MISMATCH`,
  `STALE`, `NO_SOURCE`, `NO_VALUE`). Freshness is checked on every request; the wind decision is stale 14 days after `updatedAt`.
- **Publisher writers** (`publisher_live/customer_{clarity,water_temp,generation_binding,wind_outlook_model}.py` + `customer_copies.py`):
  pure planners mirroring `customer_lake_level.py` (readiness BETA+, lakeId match, freshness, source class, UNKNOWN written once over a
  copy that stops passing). Each sits behind its spec §5 switch, default off. The live package may not read the environment
  (`test_publisher_live_boundary`), so the caller passes its environment mapping in.
- **Registration:** `publisher/paths.py` `CUSTOMER_COPY_FAMILIES` (status `PLACEHOLDER`, includes the existing level copy) and the path
  ownership matrix (json + md).
- **Rules:** `platform/security/rtdb.rules.customer-copies.PROPOSED.json`, not applied (deny every client, as today).
- Design note `CUSTOMER_BRAIN_OUTPUT_PATH_V1.md` §8.

## Review fixes (independent review of #144)
- Clarity freshness bounded by `evaluationTime + staleAfterHours` (a 4-day-old evaluation re-published by a new run is STALE).
- Switch off withdraws live copies with UNKNOWN (`NOT_ENABLED`); generation binding STALE after 30 days in the reader.
- Source times more than 10 minutes in the future are refused (writers and readers); zoneless `reviewedAt` is unparseable;
  empty lakeId returns early; fractional-second dates tested.

## Gaps (owner / owning Brain)
- Water Temp `modeled` lakes publish no source observation time: no copy (`NO_OBSERVATION_TIME`).
- Lake publishes no dam bindings: `reviewed-lake-bindings-v1` binds pool sources only. Writer reads a proposed `damBinding`; today every lake is `NO_DAM_BINDING`.
- Wind publishes no outlook-model decision: writer reads a proposed `activeProductionModel.outlookModel`; today `NO_PUBLICATION`.
- The CUSTOMER-lane Cortex family is still undeclared (CG-3.1-8).

## Verification
- `swift test`: all suites, 0 failures (incl. `PhoneContractTests`, 10 new tests in `ConditionsBrainOutputTests`).
- pytest platform suites (`jobs/brain_platform` 946 incl. 53 new, orchestrator, scores, publisher, runner, cutover), `verification`,
  `tools/architecture`, `tools/research`: pass after the digests are re-recorded.
- Cortex `data-check`: identical findings before and after (no new finding). `rules-check` on the proposed rules: 0 findings.

## Not done / gated
- No deploy, IAM, rules deployment, production read or write, flag change or merge.
