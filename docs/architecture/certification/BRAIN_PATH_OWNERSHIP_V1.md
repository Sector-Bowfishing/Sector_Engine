# Brain Path Ownership V1

## 1. Ownership model
`brainId → allowed artifact schemas → allowed path families`. The Publisher enforces it; it knows structure and authorization, never science.

| Owner | Authorized path families (target) | Notes |
|---|---|---|
| `wind` | `/lakes/{k}/states/wind`, `/lakes/{k}/profiles/wind`, `/lakes/{k}/validation/wind`, `/lakeFleet/{k}/slots/wind` (+ its `readiness/wind`, `modelVersions/wind`), `/brains/wind`, `/validation/wind`, `/health/brains/wind`, `/sources/{id}` where Wind is acquisition owner, `/health/sources/{id}` (same), own `/activity` events | `/snapshots/{k}/latest/wind` is LEGACY (§3) |
| `water-temp` | the same families with slot `waterTemp` / id `water-temp` | |
| `water-clarity` | the same families with slot `waterClarity` / id `water-clarity` | |
| `lake-brain` | `/lakes/{k}/brain`, `/lakes/{k}/states/lake`, **`/lakes/{k}/speciesPresence`**, `/lakeFleet/{k}/{slots/lake, riverSystem, …lake}`, registry/validation/health, owned sources | canonical lake species presence |
| `depth` | `depth` slot families | must not mutate Lake truth |
| `vegetation` | `vegetation` slot families | |
| `biological-state` (Fish Brain) | `/brains/biological-state`, `/validation/biological-state`, `/health/brains/biological-state`, the Species Intelligence paths (`/species/{id}` intelligence summary and/or `/speciesProfiles/{id}`, **decided in Fish certification**), future `/lakes/{k}/states/biology` | never `speciesPresence`, never `policy`, never identity fields |
| `sector-intelligence` | `intelligence` slot families, its registry/validation/health | synthesis only |
| Species Registry (Engine Platform) | species identity fields (`speciesId`, names, scientific name, aliases, environment classification) and `/speciesIndexes/{environment}/{speciesId}` | identity is independent of Fish Brain |
| Policy | species `policy` child (legality, conservation, invasive, harvest) | |
| Platform (scoring) | `/scores/{brainId}` (the one `ENGINE_READINESS_SCORE`), `/scores/engine` (provisional), control rollups | |
| Orchestrator | `/control/orchestratorV1/*`, `/jobs/*`, request records/outcomes, `/brains/{id}/publication`, `/brains/{id}/certification` | written through the Publisher |

### Required rejections (each becomes a Publisher test)
| Attempt | Result |
|---|---|
| `wind` → `/speciesProfiles/common_carp` | **REJECT** (cross-domain) |
| `biological-state` → `/lakes/{k}/states/wind` | **REJECT** |
| `biological-state` → `/lakes/{k}/speciesPresence` | **REJECT** (Lake owns presence) |
| `depth` → `/lakes/{k}/states/lake` or `/lakes/{k}/brain` | **REJECT** |
| any Brain → another Brain's `/brains/{id}` or `/scores/{id}` | **REJECT** |
| any Brain → `/access`, `/control/*`, `/jobs/*` | **REJECT** |
| `biological-state` → species identity or `policy` fields | **REJECT** |

## 2. Path statuses
| Status | Meaning | May a Brain's artifact target it? |
|---|---|---|
| `CANONICAL` | the authoritative serving path for that datum | yes (its owner) |
| `DERIVED_PROJECTION` | an intentional compact projection of canonical data, declared with its source (e.g. a fleet slot summarizing a lake state) | yes, written in the **same** atomic publish as its source |
| `LEGACY_READER_PRESENT` | duplicate/old path still read by someone | the owner keeps writing it **only until its readers move**, in the same atomic publish |
| `RETIREMENT_CANDIDATE` | zero readers proven; writers being removed | no new writers |
| `PLACEHOLDER` | declared (rules/contract) but holds no data | no |

**Duplication alone never justifies deletion.** Known current examples (all are classified during the owning Brain's certification, not now):
- `/snapshots/{k}/latest/*`: exact copies of `/lakes/{k}/states/*` (waterClarity, waterTemp→waterTemperature, lake→lakeState, intelligence→sectorIntelligence, wind, depth), ≈32 % of the database. Consumers still declare it as input.
- `/engine/score` = `/scores/engine`.
- `/control/fleet` readiness vs `/lakeFleet` readiness/slots.
- legacy `/control/orchestrator` vs `/control/orchestratorV1`.
- health/readiness/score/model identity repeated across registry, health, validation, fleet and control.

## 3. Path retirement procedure (all 14 steps, in order)
1. identify readers (code search: Engine, Ops, iOS, Android, Web, scripts)
2. identify writers
3. identify scheduler/job ownership
4. identify Ops usage (views, listeners)
5. identify dependent-Brain usage (declared inputs and actual reads)
6. define the canonical replacement
7. migrate each reader
8. test the replacement (field-level equality)
9. monitor (old content frozen; no regression)
10. prove old-reader count = 0
11. prove old-writer count = 0
12. preserve rollback (export of the old path in history storage)
13. explicit approval from Michael
14. only then retire

## 4. Source registry: acquisition owner vs consumers
`/sources/{sourceId}` distinguishes:
- `acquisitionOwnerBrainId`: the **one** Brain that runs the acquisition pipeline and writes the source record and health;
- `authorizedConsumers[]`: Brains allowed to use that provider's data (directly or via the owner's published contract).

A shared provider does not mean every consumer owns an acquisition pipeline. Records missing `acquisitionOwnerBrainId`, or with incomplete consumers, are fixed by the acquisition owner during its certification. A non-owner never rewrites a source record; it may be added as a consumer only through the owner's publish.

## 5. Path naming
Existing ids, slot keys and path casing are preserved (camelCase fields; kebab-case brainIds; snake_case speciesIds; `lakeKey` algorithm). New top-level roots require an approved row in the ownership matrix. No environment or version in path names (`/species/freshwater/...` is not allowed; environment is a classification, indexed separately).
