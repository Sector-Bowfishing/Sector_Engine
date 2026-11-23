# Weather Brain — BRAIN OPERATING CONTRACT

> Rules and decisions only. Ids and edges live in [`brain.json`](brain.json); the state contract is [`contracts/weather-state-v1.md`](contracts/weather-state-v1.md).
> Terminology: bowfisher / bowfishers.

## 1. IDENTITY
`brainId` `weather` (locked in `tools/architecture/stable_brain_ids.json`), Weather Brain, domain `condition`, lifecycle **CALIBRATION**,
contract version 0.1.0, owner Michael (owner decision 2026-11-22, Sector_Ops #51). Slot `weather`.

## 2. MISSION
Own the measured weather at each directory lake: barometric pressure and its trend, air temperature, humidity and dew point, sky (cloud and
present weather) and precipitation, from NWS station observations and the official NWS forecast grid; and say whether the weather is
changing (the weather-change signal). Real measured or official forecast data only, never an invented estimate.

## 3. BOWFISHER DECISION
Is the weather turning before or during the trip (a front, a fast pressure change, rain starting)? Indirectly: are the water-level and
water-temperature readings current, because Lake and Water Temp refresh on this Brain's signal.

## 4. OWNERSHIP
`/lakes/{k}/states/weather`; `/lakeFleet/{k}/slots|readiness|modelVersions/weather`; `/brains/weather/{child}` (registered children only);
`/validation/weather`. The weather-change thresholds (`weather-change-thresholds-v1`) and the freshness tiers. Sources
`nws-station-observations`, `nws-forecast-grid`.

## 5. NON-OWNERSHIP
Wind (the Wind Brain), water level (Lake), water temperature (Water Temp), clarity, fish behaviour, whether tonight is good (Sector
Intelligence), lake identity (the Lake Registry), customer scoring, `/health/*` and `/sources/*` (Orchestrator-owned), `/snapshots/*`.

## 6. DEPENDENCIES
Lake Registry (`registry.lakes` ≥ 1.0.0, the Engine directory `GET /lakes`). Providers above (`domainInterpreter: true`). No Brain dependency.

## 7. COMMUNICATION CONTRACTS
Publishes `weather-publication-v1` (Publisher-derived, `contracts/weather-publication-v1.json`) carrying `sector-brain-weather-state-v1`.
Consumers: ops, lake-brain, water-temp, sector-intelligence, through the published state only (no imports of this runtime).

## 8. RESEARCH WORKSPACE
Logical workspace `weather-brain`, resolved under `SECTOR_RESEARCH_ROOT`. No research data in Git.

## 9. RESEARCH INITIATION RULES
Research starts only from a gap in `research/GAPS.json` (WX-001…WX-004) with its stop condition.

## 10. RESEARCH STOP RULES
Each gap stops at its stated condition; the pre-registered comparisons (plan §5) stop on their fixed windows, whatever the result.

## 11. EVIDENCE HIERARCHY
Station observation > official NWS forecast grid > nothing. A forecast value is labelled `forecastGrid` and never presented as observed.
No interpolation, no model of our own, no carry-forward of an old value.

## 12. CANONICALIZATION
Units: °F, %, inHg (with hPa), inches. Pressure is sea-level pressure via the station's own SLP − altimeter offset, else labelled
`altimeter`. Trends use one station's raw series. Times are UTC ISO 8601. The NWS → value rules are the Engine adapter's
(NWS_WEATHER_ADAPTER_V1), ported value for value.

## 13. VALIDATION
Pre-registered in `docs/brains/WEATHER_BRAIN_PLAN.md` §5: pressure and air temperature against independent station observations, the
change signal against NWS surface analyses and observed rain. Thresholds are not tuned to results; a failed criterion produces a new
thresholds version with its reason.

## 14. PUBLISHING
CALIBRATION, internal only, `customerPublication` false. The Brain has a **gated live writer**: `run.py --write` applies the dry
run's write set through `sector_weather.writer.RtdbWriter` (the platform client, as Depth and Generation) and refuses unless the knowledge
release is APPROVED (exit 2) and `WEATHER_WRITE_APPROVED=1` is set (exit 3). Today the release is NOT_RECORDED, so it refuses. The Brain is
registered DISABLED: nothing starts it. Turning it on is the owner checklist in plan §6.1.

## 15. PATH OWNERSHIP
As §4, enforced by `sector_brain_platform.ownership` and the Publisher registry (`weather_specs`). Never `/scores`, `/snapshots`, `/health`,
`/sources`, another Brain's slot, or a whole `/lakeFleet/{k}` row.

## 16. SCORING
Weather has no score. A readiness score needs a rubric approved by the owner.

## 17. COST RULES
Free public API. Run cost: one small Cloud Run job, capped at 2 USD/month in the manifest exception. No paid source without owner approval.

## 18. SECURITY
No credentials: NWS needs none. The User-Agent contact is configuration (`SECTOR_WEATHER_USER_AGENT`), not code. The client refuses any
host other than api.weather.gov. No customer data is read or written.

## 19. SESSION CLOSEOUT FORMAT
`Standards:` line; what changed; tests run and results; thresholds version touched (must be none unless a new version is introduced with
its reason); open questions for the owner.
