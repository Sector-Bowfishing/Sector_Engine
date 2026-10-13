# Biological Brain (`biological-state`): integration contract

**Status:** RATIFIED by Sector Engine, 2026-10-12 (v1, species-knowledge side). It amends Sector_Ops `docs/BRAIN_INTEGRATION_REQUIREMENTS.md` §7 and `docs/SECTOR_BRAIN_RTDB_SCHEMA.md`, and Sector Ops adapts to it.

**Implementation:** `jobs/biological-brain/` (Python, stdlib only).

**Display name:** **Biological Brain**. The machine ID stays `biological-state`; slot `biology`; snapshot field `biologicalState`.

## 1. Two responsibilities, one brain

| Responsibility | Question | Status |
|---|---|---|
| **Species knowledge** | "What does Sector know about this fish?" | **Published** (this contract) |
| **Biological state** | "What is this fish likely doing on this lake right now?" | **Not started.** The existing `/lakes/{k}/states/biology` contract stands; nothing is written there until a state model is separately approved |

The Biological Brain interprets fish biology. It never makes the final bowfishing recommendation; that belongs to Sector Intelligence. It never reproduces water-temperature, clarity or wind science; it will consume those brains' normalized states.

## 2. Where the knowledge lives

| Layer | Location | Visibility |
|---|---|---|
| **Canonical detailed knowledge:** profiles, rules, evidence, full history, discrepancies, lake-specific biological metadata | `gs://sector-biology-private/biology/v1/` (`latest.json` → `releases/{researchVersion}/manifest.json` → hashed files) | **Private.** Project members only; public access prevention enforced; object versioning on |
| Authoring and git history of that knowledge | Sector's private research repository | Private |
| Code, schemas, contract, publisher | This repository (`jobs/biological-brain/`, this document) | Public |
| Lightweight summaries | Brain RTDB `sector-brain` | Ops allowlist only |

This public repository contains **no** proprietary species profiles, rules, evidence catalogues, papers or third-party data. Its tests use synthetic species.

**Engine owns the truth and the runtime contract.** The private bucket is only where the canonical artifacts are stored. Sector Ops never reads the bucket.

## 3. Canonical identifiers

- **`speciesId`:** `snake_case`, matching `^[a-z][a-z0-9_]{1,63}$` (e.g. `common_carp`, `grass_carp`, `smallmouth_buffalo`, `longnose_gar`).
- **Existing customer- and app-facing names and keys are unchanged.** They are mapped, not renamed:
  - `aliases[]` holds alternative names.
  - `appKeys{}` holds `iosFishIntelSpeciesId`, `iosRegulationKey`, `iosSpeciesGroupId`, `iosSpeciesGroupLabel` (e.g. "Buffalo Carp") and `engineSpawnTableName` (e.g. "Common carp").
- **App groups** (e.g. "Buffalo Carp" = the three buffalo species; "Gar") are published as `speciesGroups` on the registry entry. A group is not a species.
- **Lakes** use the canonical Engine directory `lakeId` (`"<name>|<state>"`) and the Brain RTDB slug. There is no second lake registry.

## 4. Scoring: the v2 Species Knowledge rubric

Eight dimensions, whole points 0–10:

| Dimension id | Label | Weight |
|---|---|---:|
| `seasonalLocationReproduction` | Seasonal location & reproduction | 20 |
| `habitatDepthCover` | Habitat, depth & cover | 20 |
| `temperatureOxygen` | Temperature & oxygen | 15 |
| `hydrologyRainInflowLevel` | Hydrology, rain, inflow & level | 15 |
| `foodFeedingLocation` | Food & feeding location | 10 |
| `dayNightMovement` | Day/night movement | 10 |
| `clarityLightWind` | Clarity, light & wind | 5 |
| `aggregationMobilityLifeStage` | Aggregation, mobility & life stage | 5 |

- **Overall:** `overallExact` = Σ(score × weight) / 100. `overallRounded` is the nearest 0.5, with ties rounding up.
- **Unknown is explicit:** a dimension with no usable evidence has `score: 0` **and** `status: "UNKNOWN"`. A 0 never means a measured lack of response.
- **`potentialGainPerPoint`** = weight / 100. This is rubric arithmetic, not a forecast.
- **What is not scored here:** maps, environmental feeds, Engine validation, night-bowfishing readiness, presence and policy. They are separate assessments.
- **Not a probability:** knowledge scores measure evidence completeness, not predictive accuracy.

**Engine does not score.** It validates the canonical bundle and refuses to publish (`BundleError`; nothing is written) when any of these fails:
- every file's SHA-256 and size match the manifest;
- each `speciesId` is snake_case and matches its profile;
- the eight dimensions are present, in order, with the v2 weights;
- scores are whole numbers 0–10;
- `UNKNOWN` is used exactly when the score is 0;
- overall = weighted sum, and rounded = `round_half(overall)`;
- `NOT_ASSESSED` species carry no scores;
- `REVIEWED` and `VALIDATED` are not used (promotion is a separate decision).

## 5. Separate concepts (never combined into one field)

| Concept | Field | Values |
|---|---|---|
| Knowledge score | `knowledge.overallExact` / `overallRounded` / `domains` | v2 numbers |
| **Research maturity** (new field) | `researchMaturity` | `NOT_STARTED`, `RESEARCH`, `REVIEWED` (not used yet), `VALIDATED` (not used yet) |
| Assessment | `assessment` | `ASSESSED`, `NOT_ASSESSED` |
| Brain lifecycle | `/brains/biological-state.status` | Shared Brain vocabulary; currently `PROFILED` |
| Runtime health | `/health/brains/biological-state.status` and `/brains/...health` | `HEALTHY`, … |
| Lake readiness | `/lakeFleet/{k}.readiness.biology` | Not written (no per-lake state) |
| Current biological state | `/lakes/{k}/states/biology` | Not written (not started) |
| Evidence quality of a state | Part of the future state's `provenance` | — |

## 6. Brain RTDB paths written

All of a publish is **one atomic multi-path update**.

### `/species/{speciesId}` (NEW root): species summary, about 1–5 KB each
```jsonc
{ "speciesId": "example_fish", "schemaVersion": 1, "displayName": "Example fish", "scientificName": "Exemplum piscis",
  "aliases": ["Example fish"], "appKeys": { "iosSpeciesGroupId": "example", "iosSpeciesGroupLabel": "Example Group" },
  "taxonomyStatus": "RESOLVED", "taxonomyNote": "…",
  "assessment": "ASSESSED", "researchMaturity": "RESEARCH",
  "researchVersion": "YYYY-MM-DD.n", "scoringVersion": "species-v2", "lastReviewedAt": "YYYY-MM-DD",
  "knowledge": { "rubric": "species-v2", "overallExact": 3.65, "overallRounded": 3.5,
                 "domains": { "seasonalLocationReproduction": { "label": "…", "weight": 20, "score": 6, "status": "SCORED", "potentialGainPerPoint": 0.2 }, "…": {} },
                 "strongest": ["…"], "weakest": ["…"], "unknownDomains": ["…"] },
  "nextResearchPriority": "…", "topGaps": ["…"], "contradictionCount": 3, "ruleCount": 48,
  "evidence": { "relationshipRecordCount": 40, "sourcesByVerification": { "…": 1 } },
  "openDiscrepancies": { "DISC-001": { "title": "…", "status": "OPEN", "class": "PRODUCTION / LEGACY DISCREPANCY" } },
  "policyNote": "…",                     // reference only; policy is not knowledge
  "separateAssessments": { "nightBowfishingReadiness": { "value": "…", "label": "INFORMAL" } },
  "history": [ { "date": "…", "rubric": "species-v2", "overallExact": 3.65, "overallRounded": 3.5, "reason": "…" } ],  // ≤ 14, rubric-tagged
  "profileRef": "gs://sector-biology-private/biology/v1/releases/…/species/example_fish.json", "profileSha256": "…",
  "updatedAt": "…" }
```
- Unknown values are **absent** (RTDB stores no null).
- `history` entries carry their rubric. Older rubrics (`v0-audit-11cat`, `v1-family-sprint`, `v1-14dim`) are **not comparable** with `species-v2`.
- A species removed from the registry has its `/species/{id}` node removed.

### `/brains/biological-state`: registry entry
Holds the standard registry fields:
- `displayName: "Biological Brain"`, `domain: "biology"`, `version`, `schemaVersion`, `enabled`, `health`, `status: "PROFILED"`, `statusBasis`
- `supportedLakeCount: 0`, `staleLakeCount: 0`, `lastSuccessfulRun`, `deploymentVersion`, `publishMode: "manual"`
- `breakdowns{ researchMaturity, assessment }` and `versions[]`

Plus these additive fields:
- `researchVersion`, `scoringVersion`, `manifestRef`, `manifestSha256`
- `responsibilities{ speciesKnowledge{status, speciesCount, assessedCount, notAssessedCount}, biologicalState{status: "NOT_STARTED", note} }`
- `researchMaturityDefinitions{}`
- `rubric{ id, dimensions{id → {label, weight}}, note }`
- `speciesGroups{}`
- `discrepancies{ openCount, items{ id → {title, status, class, species[], lakeId?, decision} } }`
- `knownLimitations[]`
- `orchestration` (the descriptor in §8)

### `/validation/biological-state`
`status: "NOT_VALIDATED"` plus a `statusNote`. That is the truth today: nothing is field-validated.

### `/health/brains/biological-state`
The standard health record, plus `publishMode`.

### `/activity/{id}`
One `kind: "version"` event when the published `researchVersion` changes.

**Not written:** `/lakes/{k}/states/biology`, `/snapshots/{k}/latest.biologicalState`, `/lakeFleet/{k}.readiness.biology`, `/schemaVersion`.

## 7. Discrepancies

Disagreements between canonical research and production or legacy systems are **published, never resolved silently**. Each has an `id`, `class`, `status`, `species[]`, an optional `lakeId`, and a `decision`. The classes are:
- `PRODUCTION / LEGACY DISCREPANCY`
- `LEGACY KNOWLEDGE DRIFT`
- `LEGACY CONSUMER`

For example: a species' canonical presence on a lake is `HISTORICAL`, while a shipping app still says `PRESENT`.
- The discrepancy stays `OPEN`.
- Production behaviour is unchanged.
- Changing customer behaviour is a separate approval.

## 8. Orchestration (no scheduler here)

`orchestration.DESCRIPTOR` publishes the brain's dependencies and what makes it stale. `orchestration.plan()` answers "is a run warranted?". The future Sector Brain Orchestrator owns scheduling, execution, retries, ordering, deduplication and failure isolation.

| Component | Behaviour |
|---|---|
| **Species knowledge** | Version-driven, never stale by age. It runs when `latest.json`'s `researchVersion` or `manifestSha256`, or the brain version, differs from what is published. |
| **Biological state** (not started) | Planned dependencies: water-temp, water-clarity and wind states, the canonical lake directory / lake-brain, the calendar, and the species knowledge version. It will be dependency-triggered and cached; it must never recompute per user page-load. |

A Biological Brain failure is isolated. It writes only its own paths, so it cannot affect other brains or `/conditions`.

## 9. Running

```
cd jobs/biological-brain
python3 -m unittest discover -s tests -v                 # synthetic fixtures, no network
python3 run.py --plan                                    # PUBLISH | SKIP with reasons
python3 run.py --dry-run --out out/                      # verify + build; reads the live RTDB (GET only); writes nothing
python3 run.py --write                                   # one atomic publish
```
Credentials: on Cloud Run, the job's service account (metadata server); locally, the gcloud user. No key files. The run refuses the Sector app databases.

There is no scheduled job. Deployment to Cloud Run, if ever wanted, is a separate decision.

## 10. Lake → species: not owned here (PROPOSED seam, 2026-10-12)

**Status:** PROPOSED. Nothing in this section is published or implemented. It needs ratification and approval before a writer exists.

The Biological Brain answers "what does Sector know about this species?". It does **not** answer "which species are on this lake?". That is lake context.

| Question | Owner |
|---|---|
| Which species are associated with this lake? | **Lake context** (the canonical lake directory / Lake Brain), keyed by the directory `lakeId` |
| What does Sector know about this species? | **Biological Brain** (`/species/{speciesId}`) |
| Which species matter on this lake now, and what does it mean for the bowfisher? | **Sector Intelligence** |

- The Biological Brain keeps **no lake registry**. It may *consume* lake presence later, for per-lake Biological State.
- Sector Intelligence keeps **no fish list** and **no copy of species knowledge**. It reads presence from lake context and knowledge from this brain.
- Sector Ops never maps species to lakes.

**Proposed presence record:** `/lakes/{lakeKey}/speciesPresence/{speciesId}` in the Brain RTDB, written by the lake-context owner:
```jsonc
{ "lakeId": "Example|ST", "speciesId": "example_fish",
  "presenceState": "historical",          // presence vocabulary below, verbatim
  "presenceAuthority": "canonical-research",
  "confidence": "medium", "nativeStatus": "…", "sourceTier": "…", "latestRecord": "YYYY",
  "sourceRef": "gs://… (private, text only)", "researchVersion": "…",
  "discrepancyIds": ["DISC-…"],           // when a production system disagrees
  "updatedAt": "…" }
```

**Presence vocabulary:** the existing research presence states, unchanged: `established`, `reported`, `stocked`, `inRangeUnconfirmed`, `historical`, `failed/eradicated`, `unknown`. A disagreement with a shipping app's presence value is a published discrepancy (§7) and is never resolved silently.

**Interface for Sector Intelligence:**
```
resolveLakeSpecies(lakeId) -> [{ speciesId, presenceState, presenceAuthority, confidence, latestRecord, sourceRef, discrepancyIds[] }]
```

**Flow (`evaluateLake(lakeId)`):**
1. Resolve the canonical lake.
2. `resolveLakeSpecies(lakeId)`.
3. Filter to relevant species by a presence policy. **Open decision:** which presence states count as relevant.
4. Read species knowledge from `/species/{speciesId}`.
5. Read current condition-brain states (water-temp, water-clarity, wind, …).
6. Read Biological State for those species where one exists (not started).
7. Produce Sector Intelligence.

None of this changes `/conditions`, `SpeciesDatabase`, `SpawnFactor`, `SpeciesLegality` or any shipping app behaviour.
