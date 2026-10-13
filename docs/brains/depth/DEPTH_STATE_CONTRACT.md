# DepthState Contract v1 (SHADOW)

Status: **shadow / internal. Not ratified, not consumed by any customer surface.** Implementation: `jobs/depth-brain/depth_brain/` (tests: `jobs/depth-brain/tests/`, golden fixtures `tests/fixtures/*.json`). Platform contract: `docs/brains/BRAIN_PLATFORM_CONTRACT.md` (slot `depth` is reserved there; no new path convention is invented).

## 1. What Depth publishes

> How has the depth of the water we care about shifted from its reference condition?

Depth publishes **environmental depth state**: a level-driven *shift* of reference depths, plus reference depth information **only where real contour evidence supports it**. It does not publish fish preference, lake level, vegetation or clarity.

## 2. Paths (platform slot `depth`)

| Path | Written by | Content |
|---|---|---|
| `/lakes/{k}/states/depth` | depth | DepthState (below). Written only for lakes with a live Lake Brain state (or a pilot) |
| `/snapshots/{k}/latest/depth` | depth | same payload (snapshot field `depth`) |
| `/lakeFleet/{k}/readiness/depth`, `/modelVersions/depth`, `/slots/depth` | depth | readiness ladder + slot record |
| `/brains/depth`, `/validation/depth`, `/health/brains/depth` | depth | registry, honest `NOT_VALIDATED`, health |
| `/activity/{ms13}-depth-{nnn}` | depth | own events only |

Scores: **none**. `/scores/depth` is platform-written and does not exist; Depth never carries an official score. The research-only maturity (4.3 on the proposed rubric) lives on `docs/depth-brain-research` and is NOT an Engine score.

## 3. Sign convention (everywhere)

`shiftFt = currentLevelFt - referencePoolFt`. Negative = lake lower than reference; reference depths are shallower by |shiftFt|. The effective depth of a point whose **reference depth** is d is `d + shiftFt`; <= 0 means dry. Equal to Lake Brain's `differenceFromNormalPoolFt` when the reference is the directory full pool.

## 4. DepthState (`stateSchema: sector-brain-depth-state-v1`)

```jsonc
{ "lakeId": "Lake Hartwell|SC", "brainId": "depth", "slot": "depth", "schemaVersion": 1, "stateSchema": "sector-brain-depth-state-v1",
  "kind": "observed" | "unavailable",                    // platform vocabulary; "observed" only from a DIRECT observed Lake Brain level
  "reference": { "referencePoolFt": 660, "referencePoolBasis": "fullPool", "referencePoolConfidence": "high",
                 "referencePoolDatum": "NGVD29", "referencePoolSource": "CWMS Hartwell.Elev... Top of Conservation",
                 "datumAssessment": { "status": "SAME_SOURCE|SAME_DATUM|CONVERTED|INCOMPATIBLE|UNKNOWN", "sigmaFt": 0.0, "reasons": [] } },
  "level":     { "currentElevationFt": 649.37, "datum": "NGVD29", "observedAt": "...", "sourceCapability": "DIRECT_OPERATOR_POOL",
                 "levelDeltaFromReferenceFt": -10.63, "sourceBrain": "lake-brain", "sourceBrainVersion": "...", "lakeBrainDifferenceFromNormalPoolFt": -10.63 },
  "effectiveDepth": { "mode": "shiftOnly" | "zoned" | "unknown",
                      "shiftFt": -10.6, "uncertaintyFt": 0.29, "confidence": "HIGH|MEDIUM|LOW", "evidenceKind": "levelDelta",
                      "resolvable": true, "sigmaComponentsFt": { "pool": 0.25, "level": 0.1, "datum": 0.1 }, "sigmaAssumed": ["pool","level","datum"],
                      "reasons": [ "..." ],              // only when mode = unknown
                      "flags": [ "..." ] },
  "coverage":  { "sourceTier": "A|B|C|D|UNKNOWN", "researchTier": "A|B|B-partial|B-binary|C|D|U", "evidenceKind": "contour|measured|proxy|unknown",
                 "contourCoverage": 0.9, "knownAreaShare": 0.9, "unknownAreaShare": 0.1, "contourIntervalFt": 2, "surveyYear": 2015 },
  "referenceZones": { ... }, "effectiveZones": { ... },   // ONLY tier A/B/C lakes with supported contour shares (section 6)
  "facts": [ "..." ], "limitations": [ "..." ],
  "freshness": { "generatedAt", "sourceObservationAt", "stale": false, "evidenceStale": false, "staleReasons": [], "refreshReason" },
  "provenance": { "brainId": "depth", "brainVersion": "depth-brain-0.1.0-shadow", "modelVersion": "effective-depth-shift-v1",
                  "processingVersion": "...", "generatedAt", "sources": [...], "inputAgeHours", "readiness": "CALIBRATION", "qualityFlags": [],
                  "validationRef": "/validation/depth", "inputFingerprint": "..." } }
```

Absent means unknown. A shift state has **no** absolute depth field, no mean/max depth, no flats/channels/drop-offs, and no score.

### Refusal reason codes (`effectiveDepth.reasons`)
`CANDIDATE_BLOCKED` (+ blockedReasons), `LAKE_STATE_MISSING`, `MISSING_REFERENCE_POOL`, `MISSING_CURRENT_LEVEL`, `LEVEL_NOT_DIRECT_OBSERVATION`, `LEVEL_SOURCE_NOT_DIRECT`, `LEVEL_UNIT_NOT_FEET`, `MISSING_OBSERVATION_TIME`, `OBSERVATION_IN_FUTURE`, `LEVEL_TOO_OLD` (> 48 h), `REFERENCE_NOT_A_POOL_ELEVATION`, `REFERENCE_POOL_CONFIDENCE_LOW`, `LEVEL_DATUM_CONFLICT`, `DATUM_UNKNOWN`, `DATUM_INCOMPATIBLE`, `IMPLAUSIBLE_SHIFT` (> 80 ft).
Candidate blockers (manifest): `NO_VERIFIED_LEVEL_BINDING`, `DATUM_CONVERSION_NOT_ENABLED` (NGVD29 vs NAVD88, convertible but not enabled), `REFERENCE_NOT_A_POOL_ELEVATION`, `REFERENCE_POOL_CONFIDENCE_LOW`, `MISSING_REFERENCE_POOL`, `LEVEL_SOURCE_NOT_DIRECT`.

## 5. Uncertainty

`sigma = sqrt(sigmaPool^2 + sigmaLevel^2 + sigmaDatum^2)`. Pool: high 0.25 / medium 1.0 / low 3.0 ft (low is refused). Level: operator pool 0.1, lake gauge 0.15. Datum: same source 0, same datum 0.1, converted 0.3. Labels: HIGH <= 0.5 ft, MEDIUM <= 1.2 ft, else LOW. `resolvable` = |shift| > 2 sigma. **These components are research estimates (flagged `sigmaAssumed`), not instrument specifications.**

## 6. Contour zones (tier A/B/C only)

`referenceZones` reports shares of the *surveyed* surface at the survey reference pool: `shareUnder3Ft`, `share3To6Ft`, `share6To10Ft`, `shareUnder6Ft`, `shareUnder10Ft`, `shareDeeper`. A field exists **only if the contour interval resolves its edges** (edge a multiple of the interval, or interval <= 3 ft). A 5 ft survey publishes only the 10 ft split; nothing is interpolated to a finer edge. `support` carries interval, coverage, survey year.

`effectiveZones` re-bins those shares for the current shift as **(lo, hi) bounds** (a shifted edge that falls between supported levels cannot be a point), widened by the shift uncertainty. It is `available: false` until the survey's reference pool elevation and datum are verified (`SURVEY_REFERENCE_POOL_UNVERIFIED`) - today that is every lake. A rising lake flags `floodedMarginUnquantified`.

## 7. Future zone-level contract (`DepthZoneState`, NOT built)

Lake-level only today (`zoneId = "lake"`). Per-zone/segment states require licensed contour geometry and a reference-pool-verified survey. Planned shape: `reference{meanDepthFt?,p10?,p90?,source}`, `effective{meanDepthFt?,range?,shiftFt}`, `shallowShares{under3?,threeToSix?,sixToTen?}`, `morphology{flat?,channelEdge?,steepBank?}`, `evidenceKind: measured|contour|modeled|proxy|unknown`, `confidence`, `support`, `surveyAge`. **Fields are omitted when evidence cannot support them; `modeled`/`proxy` may never populate depth, shares or morphology.**

## 8. Staleness and orchestration

`stalenessModel: FINGERPRINT` (a pure function of the Lake Brain state, the manifest and the Depth version). `plan()` returns PUBLISH when the input fingerprint changes. `evidenceStale` is set when the Lake Brain observation is > 6 h old or Lake Brain flags its own state stale. No Cloud Run job, scheduler or orchestrator registration exists; adopting it is a separate decision.

## 9. Amendments (2026-10-14, additive; `stateSchema` stays `...-v1`)

* `reference.datumAssessment.status` adds **`SAME_OPERATOR_SYSTEM`** (one operator publishes pool and level on one system, datum name unconfirmed; sigma 0.1) and an optional **`evidenceConfidence`** (`high|medium`) for reviewed datum evidence; `medium` caps a lake at MEDIUM_CONFIDENCE rollout.
* `level` adds `lakeBrainGuideFt` and `lakeBrainDifferenceFromGuideFt` (copied context: designed seasonal pool vs unusual drawdown).
* `coverage` adds `depthEvidence` (the named depth source for tier A/B/C, or "none: lake-level stage-area (hypsometry) only"; never names modeled evidence) and `surveyYear`.
* `effectiveZones`: shares are re-based to the **survey** reference pool (`shift_survey = shift + referencePool - surveyPool`, same datum required, else `{available:false, reason: SURVEY_REFERENCE_DATUM_NOT_COMPATIBLE}`); bands whose bound is wider than 0.25 of the surface are **withheld** and listed in `withheldBands` (with `withheldWhy`); `dry` and shallow bands are the informative ones. Enabled in shadow only for lakes whose survey reference pool is VERIFIED and whose preregistered validation passed (5 TWDB lakes).
* Registry node `/brains/depth` carries Engine-computed Ops summary fields (`fleet`, `breakdowns`, `research{maturity, official:false}`, `scoreStatus: NOT_ESTABLISHED`, `primaryBlocker`, `lakeDependency`, `orchestration`, `fieldValidation`, `statusBasis`, `blockers[]`); none is hardcoded (`ops_summary.py`).
* New refusal/blocked codes: `LEVEL_DATUM_CONFLICT`, `SURVEY_REFERENCE_DATUM_NOT_COMPATIBLE`, `DUKE_LOCAL_SCALE_NOT_ENABLED`.
