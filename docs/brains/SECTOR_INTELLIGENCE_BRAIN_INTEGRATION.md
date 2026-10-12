# Sector Intelligence Brain: integration contract

**Status:** v0.1, 2026-10-12. This is a metadata and dependency publisher only. It produces no evaluation.

**Brain ID:** `sector-intelligence` (reserved in the Sector Ops catalog, RTDB schema and rules). **Slot:** `intelligence`. **Display name:** Sector Intelligence.

**Question:** what does everything Sector knows mean for the bowfisher?

## 1. What Sector Intelligence is today

Four implementations exist. They are declared in `jobs/sector-intelligence-brain/catalog.json`, which is reviewed by hand. Facts that change at runtime are read live, never declared.

| Implementation | Lifecycle | Serves customers | Reads any Brain |
|---|---|---|---|
| `engine-conditions-score`: Engine `GET /conditions` (10 factors, regimes, gates, seeability ceiling, topReasons). Used by the iOS and Android apps | `PRODUCTION`, `NOT_VALIDATED` | **yes** | **no** |
| `ios-fishintel`: on-device attraction, huntability, recommendation class and biological state (Guntersville only) | `MERGED_UNRELEASED`: on iOS `Michael-Master` with no gate, in no release | no | no |
| `phase5a-guardrails`: species policy / conservation gate (iOS and Engine branches) | `UNMERGED` | no | no |
| `normalized-sector-intelligence`: the Brain synthesis | `NOT_STARTED` | no | no |

**There is no normalized Sector Intelligence evaluation for any lake.**
- The customer path computes every signal inside `/conditions`.
- The specialised brains republish or shadow some of those signals. Nothing reads them back.

## 2. What the publisher writes (Brain RTDB `sector-brain`)

| Path | Content |
|---|---|
| `/brains/sector-intelligence` | Shared registry shell, plus the fields below |
| `/health/brains/sector-intelligence` | **Publisher** runtime health: `lastRun`, `lastSuccess`, `durationMs`, `errorCount`, `engineRevision`, `dependencyFailures`, `staleInputs[]`, `notRegisteredInputs[]`. Dependency problems are listed here but do not change `status` while no implementation consumes a Brain |
| `/validation/sector-intelligence` | `status: NOT_VALIDATED`, `softwareTests[]` (each `kind: SOFTWARE_TEST`), `predictiveValidation.status: NONE`, `unvalidatedActiveModels` |
| `/lakes/{k}/states/intelligence` | Per lake: `evaluationStatus: NOT_EVALUATED`, `customerPath`, `inputs{slot}` (`PUBLISHED`, `STALE` or `NOT_PUBLISHED`, plus readiness, stateType, lastUpdatedAt, modelVersion), `inputCounts`, `provenance` |
| `/lakeFleet/{k}/slots/intelligence` | `stateType: NOT_EVALUATED`, `inputsPublished`, `inputsConsumed: 0` |
| `/activity/{id}` | Written on first registration, a version or catalog change, or a new Engine serving revision |

Registry fields on `/brains/sector-intelligence`:
- **Status:** `status: DISCOVERED`, `statusBasis`, `statusReasons[]`.
- **Lake counts:** `supportedLakeCount: 0` (lakes with a normalized evaluation), `evaluatedLakeCount: 0`, `directoryLakeCount`.
- **Engine serving:** `engineServing`, which records the serving revision, traffic %, image digest, and `lineageVerified` (whether the image matches the declared code lineage). It is read from Cloud Run at each run, so an Engine deploy shows up without anyone editing Ops.
- **Implementations:** `activeModel` and `modelRoster[]` (the implementations), plus `versions[]` for the Model versions tab.
- **Dependencies:** `dependencies{brainId}`, `dependencyOrder[]` and `dependencySummary`.
- **Blockers:** `blockers[]`, the declared ones plus those derived at runtime.
- **Vocabularies and contracts:** `vocabularies`, `inputContract`, `outputContract`, `knownLimitations`.
- **Orchestration and bookkeeping:** the `orchestration` descriptor, `catalogVersion`, `catalogSha256` and `fingerprint`.

**Never written:**
- the snapshot field `sectorIntelligence`;
- `/lakeFleet/{k}/readiness/intelligence`;
- any rating, score, window or driver.

Those appear only when a real evaluation exists.

## 3. Dependency semantics: "exists" is not "consumed"

Each `dependencies[brainId]` entry keeps these facts apart:

| Field | Meaning |
|---|---|
| `exists` | `/brains/{id}` is registered |
| `publishingStatus` | `PUBLISHING` (last success is within the brain's own `staleAfterHours`) · `STALE` · `VERSION_DRIVEN` (the brain publishes no age limit, e.g. species knowledge) · `NOT_REGISTERED` |
| `consumedBySectorIntelligence` | The **active** implementation actually reads this brain (`catalog.readsBrains`, reviewed) |
| `consumedBy[]` | Every implementation that reads it |
| `usedInLastEvaluation` | The last evaluation used it. Always `false` until evaluations exist |
| `connectionStatus` | `CONNECTED` / `CONNECTED_DEGRADED` only when consumed. Otherwise `AVAILABLE_NOT_CONSUMED` (registered) or `NOT_CONNECTED` (not registered) |
| `components` | Brain-published sub-capabilities read verbatim (Biological `speciesKnowledge` vs `biologicalState`; Clarity active vs candidate model; Water Temp and Wind production vs research candidate) |
| `customerPathToday` | How the customer path gets this signal today, without the brain |
| `missingReason` / `degradedReason` / `notConsumedReason` | Engine prose explaining the status |

Ops renders these fields. It never derives them.

## 4. Input contract (PROPOSED, for the future evaluation)

`IntelligenceInput { lakeId, lakeState, waterTemperatureState, waterClarityState, windState, biologicalKnowledge, biologicalState, policyContext, generatedAt, sourceVersions{brainId: version}, freshness{brainId: {generatedAt, stale}}, degradedInputs[] }`

- Each state is read from the brain's published state (`/snapshots/{k}/latest` and `/lakes/{k}/states/{slot}`) together with its `provenance`.
- Intelligence never re-derives a brain's value (e.g. it reads `clarity 4.6 ft, trend, authority, freshness, version` and never how it was computed).

## 5. Output contract (PROPOSED)

The existing Ops `IntelligenceState` lives at `/lakes/{k}/states/intelligence` and in snapshot `sectorIntelligence`.

When it exists, it adds:
- `inputVersions{brainId: version}`, so a reported result can be traced to the exact brain versions that produced it;
- `degradedInputs[]` and `limitingFactors[]`;
- each driver's `sourceSlot`;
- `intelligenceVersion`.

The Conditions Score's semantics are preserved. No new score is invented for the portal.

## 6. Orchestration

There is no scheduler or cron. `orchestration.py` declares the inputs and recompute triggers. `plan()` returns `PUBLISH` when:
- the fingerprint changes (upstream registration, publishing status, health, version or lifecycle; the serving revision or image; the catalog; the brain version);
- or the last publish is more than 24 h old.

Run it with:
- `python run.py --plan | --dry-run | --write`

## 7. Changing what is declared

`catalog.json` is the only place implementation facts live. When a brain becomes consumed, a release ships FishIntel, guardrails merge, or a normalized evaluation is built:
1. Update the catalog.
2. Bump `catalogVersion`.
3. Re-run the publisher.

A new Engine image that does not match `codeLineage.imageDigest` raises the `ENGINE_LINEAGE_UNVERIFIED` blocker until the catalog is reviewed.
