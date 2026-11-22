# Generation Brain operating contract

Read this first in any session that touches `brains/generation`. Owner direction: Michael, chat 2026-11-22 19:37Z, recorded on Sector_Ops #51 (comment 7084558461): build it; real measured or official operator data only.

## 1. IDENTITY
`brainId` `generation` (stable; never renamed). Display name Generation Brain. Directory `brains/generation`. Lifecycle CALIBRATION. Slot and snapshot field `generation`.

## 2. MISSION
Tell a bowfisher whether the dam on their lake is releasing or generating now, how much water is moving (discharge, turbine, spill, MW, units on where the operator states them), and when the operator's published schedule starts or stops it, for every directory lake with a dam where an official source publishes it.

## 3. BOWFISHER DECISION
Whether tonight's tailwater or the current-swept water near the dam will be moving or settled, and when generation starts or stops (the Generation tile; the old Engine's current / generation factor and tailwater regime).

## 4. OWNERSHIP
Dam release and generation state per lake: release status (GENERATING, SPILLING, RELEASING, OFF, UNKNOWN), measured discharge, turbine and spill flow, generation MW, units on as stated by the operator, the operator's published schedule and its next start and stop, tailwater elevation as published with the release, and the per-dam refresh cadence. Recorded as owner direction 2026-11-22; the Cortex architecture still lists dam releases under Lake Brain (CORTEX_GAPS CG-3.1-19).

## 5. NON-OWNERSHIP
Pool elevation and water-level trend (Lake Brain), water clarity (Water Clarity), water temperature, fish behaviour, depth, vegetation. No rating, score or recommendation: the final shooting assessment is Sector Intelligence's. Generation never derives units or discharge from megawatts, never fills a missing reading, and never reads a source whose access is not ALLOWED.

## 6. DEPENDENCIES
The Lake Registry (lake identity) through the packaged dam catalog. No other Brain. Providers: `tva-generation-schedule`, `usace-cwms-release`, `swpa-generation-schedule`, `usbr-rise-release`, `usgs-waterdata-discharge` (providers/PROVIDERS.json), each read only when `runtime/knowledge/source_access.json` says ALLOWED.

## 7. COMMUNICATION CONTRACTS
Publishes `generation-publication-v1` (contracts/), per-lake state `generation-dam-state-v1` (contracts/generation-dam-state-v1.schema.json). Consumers: Ops, Sector Intelligence (not yet wired). Customer integration: none.

## 8. RESEARCH WORKSPACE
Logical workspace `generation`. Offline tooling in `research/tools/generation_research` (catalog build, release writer, records with evidence). No research data in the repository.

## 9. RESEARCH INITIATION RULES
A research task starts from a gap in `research/GAPS.json`: binding a pending source (CWMS release series, RISE release item, TVA LocationID, USGS tailwater gauge) or a source-access check. Probes use documented services only, at most hourly per series, with the agency named.

## 10. RESEARCH STOP RULES
Stop a binding probe when the series is bound with evidence, when the operator publishes nothing usable, or when access needs the operator's permission (then list it, do not build it). Stop validation after the pre-registered week.

## 11. EVIDENCE HIERARCHY
1. The operator's own release and schedule (TVA, USACE CWMS, SWPA, Reclamation). 2. A USGS discharge gauge below the dam, labelled `downstreamGauge` (the river, not the dam). Nothing else; never a model or an estimate.

## 12. CANONICALIZATION
Times are UTC ISO-8601 (`...Z`) from each source's stated zone or offset. Flow in cfs, elevation in ft, power in MW; SI responses are converted, other units refused. One state per lake key (`lake_key(lakeId)`).

## 13. VALIDATION
NOT_VALIDATED. Pre-registered: compare the published release picture with each operator's published schedule over one week (docs/brains/GENERATION_BRAIN_PLAN.md section 5). Tests prove parsers, assembly and freshness on labelled hand-built fixtures.

## 14. PUBLISHING
Only `run.py --write`, only from an APPROVED knowledge release and with `GENERATION_WRITE_APPROVED=1`. The current release is a candidate (NOT_RECORDED): BLOCKED_AWAITING_APPROVED_RELEASE. Registered PARKED with no execution target and no execution-control entry; customer publication off.

## 15. PATH OWNERSHIP
`/lakes/{k}/states/generation`, `/lakeFleet/{k}/{slots,readiness,modelVersions}/generation`, `/snapshots/{k}/latest/generation`, `/snapshots/{k}/latest/brainVersions/generation`, `/brains/generation/{child}`, `/validation/generation`, `/health/brains/generation/{status,staleLakeCount}`, own `/activity` events. Lake identity fields are platform-owned.

## 16. SCORING
Generation has no score and no rubric (`scoreStatus` NOT_ESTABLISHED). Adding one is an owner decision.

## 17. COST RULES
Free public sources. At most one read per series per hour (owner source-access rule); the adaptive cadence reads most dams less often. No cloud job exists; creating one is gated (costs money).

## 18. SECURITY
No credentials in the package. Read-only GETs to public services with a Sector User-Agent. The RTDB writer refuses the app database and checks ownership on every path.

## 19. SESSION CLOSEOUT FORMAT
Start with the `Standards:` line; list what changed, the tests and digests run, the coverage counts (`dams.json` counts), and every gated item batched for Michael.
