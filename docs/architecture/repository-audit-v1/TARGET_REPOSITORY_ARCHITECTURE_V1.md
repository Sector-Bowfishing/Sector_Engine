# Target Repository Architecture V1 (LOCKED FOR PHASE 1; NOT IMPLEMENTED)

**Status:** `REPOSITORY_ARCHITECTURE_V1_APPROVED_FOR_PHASE_1` (locked 2026-10-14; see `REPOSITORY_ARCHITECTURE_V1_DECISION_LOCK.md`). Approved for additive foundation work only. Nothing here is implemented; no runtime file has moved. Alternatives considered and rejected are in §12.

## 1. Design principles (derived from the audit)

1. **Directory = ownership.** A path answers "who owns this?" before any file is opened.
2. **A Brain has one home**; everything that defines how it works lives there (contract, runtime, builder, contracts, rubric, validation, tests). Raw research does not.
3. **Domains are separated by build/deploy boundary, not by language.** A Brain with Swift runtime and Python tooling keeps both in its home. Languages follow SwiftPM / pip needs.
4. **Boundaries are enforced by tooling** (SwiftPM target graph, an import-lint test, `PROVIDERS.json` consumer check), not by convention.
5. **No runtime input lives in `docs/`.**
6. **Incremental.** The layout can be reached one Brain at a time with compatibility shims; Swift `Package.swift` and the customer Dockerfile stay at the root.
7. **Simpler, not more bureaucratic.** Mandatory pieces are few; no empty ceremonial directories (each created directory holds a README or schema stating its purpose and import rules).

## 2. Proposed tree

```
Sector_Engine/
├── Package.swift  Package.resolved  Dockerfile  deploy.sh  README.md        (root build entrypoints stay)
│
├── engine/                          CUSTOMER-SERVING ENGINE (class A)
│   ├── Sources/                     SectorEngine (scoring: Aggregator, Factors, Config, WhereToLook, Forecast, API) + SectorEngineServer
│   ├── Tests/                       Engine-owned tests only
│   ├── data/                        full_pool.csv, temp_sensors.csv (build-time reference data)
│   └── docs/                        endpoint & scoring docs, scoreVersion history
│
├── providers/                       SHARED ACQUISITION (class C)
│   ├── PROVIDERS.json               providerId, acquisitionOwner, healthOwner, authorizedConsumers, costClass, licenseRef, raw-cache policy (a CATALOG, not an entity registry)
│   ├── swift/Sources/SectorProviders/   Open-Meteo, USGS, TVA, CWMS, SWPA, Alabama Power, USBR, NWS, MRMS, NOAA water
│   ├── python/sector_providers/     NBM/RTMA/HRRR/RRFS/MADIS, STAC/Sentinel, TVA archive helpers (only what Python jobs need)
│   └── fixtures/<providerId>/       recorded payloads shared by Swift+Python parity tests
│
├── platform/                        BRAIN PLATFORM (never Brain-specific)
│   ├── python/sector_brain_platform/    installable package (pyproject.toml); stdlib-only
│   ├── swift/Sources/SectorBrainPlatform/   BrainPlatform, BrainContract, BrainRTDBStore
│   ├── orchestrator/                executor, control plane, lineage preflight, deploy
│   ├── publisher/                   Publisher service + Orchestrator API (from feat/publisher-v1-shadow)
│   ├── scoring/                     scorer, beta, score publisher, rubrics/ (engine, beta); SCORING.md
│   ├── registries/                  THREE DIFFERENT THINGS, never one "registry":
│   │   ├── brains/                  BRAIN REGISTRY: GENERATED from brains/*/brain.json (registered Brains, machine edges, path families, job manifest, dependency order)
│   │   ├── lakes/                   LAKE REGISTRY (canonical entity identity, Platform-owned): schema, generator, small identity source, manifest pointing at released geometry
│   │   └── species/                 SPECIES REGISTRY (canonical entity identity, Platform-owned; CERT-8)
│   ├── lineage/                     image labels, preflight, identity/lineage block
│   └── ops/                         alerting, warm tags
│
├── contracts/                       SHARED, LANGUAGE-NEUTRAL, VERSIONED
│   ├── schemas/                     platform envelope, publication artifact, control state, lineage, score block, freshness
│   ├── conformance/                 cross-language fixtures (was docs/brains/conformance)
│   └── README.md                    version policy, how a Brain registers a published contract
│
├── brains/                          SPECIALIST BRAINS (class B) — one home each
│   ├── _template/                   STANDARD_BRAIN_PACKAGE_V1 skeleton + BRAIN_OPERATING_CONTRACT.template.md
│   ├── wind/
│   ├── fish/                        brainId: biological-state
│   ├── lake/                        intelligence ABOUT lakes: hydrology, pool/level interpretation, lake source bindings, lake-specific species presence, validation (consumes the Lake Registry; does not own identity)
│   ├── water-temperature/
│   ├── water-clarity/
│   ├── depth/
│   ├── vegetation/
│   └── sector-intelligence/
│
├── tests/                           CROSS-CUTTING ONLY
│   ├── architecture/                import-lint, "no runtime input in docs", brain.json schema, PROVIDERS consumer check
│   ├── integration/                 Publisher + Brain handoff, orchestrator + brain.json
│   └── e2e/                         shadow/conformance runs (offline)
│
├── tools/                           repo-wide dev tooling (generators, linters); no domain logic
├── deploy/                          per-deploy-unit Dockerfiles/scripts that don't belong to one Brain (brain-jobs image, orchestrator)
│
└── docs/
    ├── architecture/                governance (this audit, data architecture, certification)
    ├── platform/                    platform models & contracts (was docs/brains/platform + root contracts)
    ├── history/                     consolidation, handoffs, closeouts, scope notes, cost-freeze (private-content review first)
    └── README.md                    "where do I find…" index
```

## 3. Ownership of each major directory

| Directory | Owner | May depend on | Must not contain |
|---|---|---|---|
| `engine/` | Engine (customer) | `providers`, `platform/contracts` | Brain runtime; provider clients; research |
| `providers/` | Platform (per-provider owner in `PROVIDERS.json`) | nothing domain | thresholds, gates, scoring, Brain interpretation, credentials |
| `platform/` | Platform | `contracts`, `providers` (health/IO only) | any Brain's logic or data; sibling Brain imports |
| `contracts/` | Platform, change-controlled | — | Brain-private schemas |
| `brains/<id>/` | that Brain | `providers`, `platform`, other Brains' `contracts/` | other Brains' internals; customer Engine code; raw research data; secrets |
| `tests/` | Platform | everything (read) | unit tests owned by one domain |
| `docs/` | governance | — | runtime inputs, per-Brain operating docs (those live with the Brain) |

## 4. Boundaries

* **Engine-serving boundary.** `engine/` is the only code that answers customer HTTP. It never reads `sector-brain` directly. Customer behavior changes only by a versioned, deliberate cutover (class D) that bumps `scoreVersion`/response version and appears in a decision record. Moving files must not change `scoreVersion` or any response byte (guarded by a golden-response test run before/after each migration phase).
* **Provider boundary.** Acquire, parse, normalize, report source health. Never interpret domain meaning. One client per provider per language; authorized consumers declared and checked.
* **Platform boundary.** Everything common to all Brains (see `PLATFORM_REPOSITORY_INVENTORY` §6). Platform never imports a Brain; Brains register via `brain.json`.
* **Specialist Brain boundary.** A Brain owns its domain truth, builder, schemas, rubric, validation and tests; it publishes through the Publisher (target) and consumes only others' `contracts/`.
* **Customer integration modes** (`customerIntegrationMode` in `brain.json`; replaces `customerDirect`):
  * `none`: no customer path (default).
  * `embedded`: the **customer Engine imports/executes a Brain-owned contract/library** (today: Water Temp; potentially Clarity visibility). It does **not** mean the Brain writes the customer database, and does **not** mean the Brain calls arbitrary customer internals. The Brain publishes a library target; Engine links the library, never the Brain's job/runtime.
  * `published`: the customer Engine consumes the Brain's **published contract/state** (class D) through an approved, versioned cutover.
  * **Dependency direction is always Customer Engine → approved Brain contract/library, never Brain → customer Engine implementation or API.** This is why Clarity's dependency on customer `GET /conditions` and `/lakes` is a defect to remove in the Clarity phase (RA-20).

### 4a. Provider model (RA-8, RA-10)

`providers/PROVIDERS.json` is a **catalog**. Per provider, at minimum:

| Field | Meaning |
|---|---|
| `providerId` | stable id (e.g. `open-meteo`, `usgs-nwis`, `tva-rest`) |
| `acquisitionOwner` | who owns the client/parser code and its changes (`platform`, or a named Brain for a Brain-exclusive source) |
| `healthOwner` | who publishes the source-health record (what `ownership.py` calls "owner" today) |
| `authorizedConsumers` | engine / Brains allowed to import it |
| `domainInterpreter` | per consumer, who interprets the data (declared in the consumer's `brain.json`; never the provider) |
| `costClass` | budget classification (free, metered, paid; per-call or egress notes) |
| `licenseRef` | terms/license reference where appropriate |

These four ideas (`acquisitionOwner`, `healthOwner`, `authorizedConsumers`, `domainInterpreter`) are **separate**; today's single `ownership.py` owner stops standing for all of them (design now, implementation later).
Practical boundary: shared, reused or customer-serving acquisition converges on `providers/`. A **Brain-exclusive single-consumer** client (e.g. Wind's NBM/RTMA ingest) may stay inside that Brain during migration if it is registered with an explicit owner, moving it adds no architectural value, and it can later move without changing the Brain's contract. No Brain gets its own general-purpose copy of a shared provider (no `wind/openmeteo.py`, `clarity/openmeteo.py`, `water-temp/openmeteo.py`). No TVA consolidation before D8.

## 5. Shared contract strategy

* **One definition per contract.** Platform contracts live only in `contracts/schemas/`; Python and Swift implement them and prove equality with `contracts/conformance/`.
* **Brain published contracts** live only in `brains/<id>/contracts/` (JSON Schema + a short consumer note + version). They are the **only** files another Brain may reference. Private/internal schemas stay beside the runtime.
* `brain.json` lists which contracts a Brain publishes and consumes; the generator builds the **Brain Registry** (`platform/registries/brains/`) and the dependency order; a test fails if a Brain references another Brain's non-`contracts/` path.
* Versioning: semver in the schema `$id`; breaking change = new major, dual publish for one cycle (Publisher validates both).

## 6. Schema strategy

| Class | Home |
|---|---|
| Platform (envelope, control, lineage, score block, freshness) | `contracts/schemas/` |
| Brain-published state & artifacts | `brains/<id>/contracts/` |
| Brain-private (bundle manifests, catalogs, internal ledgers) | `brains/<id>/runtime/schemas/` (or beside the module) |
| Customer API (`ConditionsResponse` etc.) | `engine/` — add a generated JSON schema for clients (today: Swift DTO only) |
| Runtime state at rest (RTDB shape) | derived from `contracts/` + Publisher `paths`; `TARGET_SECTOR_BRAIN_SCHEMA` stays the governance reference |

Undocumented implicit schemas (every non-Fish Brain today) get a published contract at that Brain's certification; this is part of the Brain package's mandatory set.

## 6a. Registry model and the Lake dataset (RA-5)

Three different things, never one "registry":

| Concept | Location | Owner | What it is |
|---|---|---|---|
| Brain Registry | `platform/registries/brains/` | Platform; **generated** from `brains/*/brain.json` | registered specialist Brains, machine edges, path families, job manifest, dependency order |
| Lake Registry | `platform/registries/lakes/` | Platform | canonical **lake identity** |
| Species Registry | `platform/registries/species/` | Platform (CERT-8) | canonical **species identity** |
| (Provider catalog) | `providers/PROVIDERS.json` | Platform | provider ownership/consumers; not an entity registry |

Identity vs intelligence: Species Registry → *canonical species identity*; Fish Brain → *intelligence about fish*. Lake Registry → *canonical lake identity*; Lake Brain → *intelligence about lakes*. Wind, Clarity, Water Temperature, Fish and Lake Brain all consume the **Lake Registry contract**; none is required to depend on Lake Brain merely to resolve a lake.

* **Lake Registry owns:** `lakeId`, canonical display name, aliases, stable identity and key derivation (`lake_key`), waterbody classification, basic geographic identity, canonical geometry/boundary **reference**, registry membership, stable registry metadata.
* **Lake Brain owns:** lake hydrology intelligence, operating-pool and water-level interpretation, lake-specific source bindings, lake condition intelligence, lake-specific species presence, lake-specific validation, lake-domain state.
* Do not confuse the Brain Registry with the Lake or Species Registry. Not implemented in this pass.

**Git vs canonical versioned release storage (621-lake dataset; initial rule):**

| Content | Where | Why |
|---|---|---|
| Registry schema, generator, key-derivation conformance fixtures, build recipe | Git (`platform/registries/lakes/`, `contracts/`) | how it works |
| Small identity source table (id, name, aliases, state, classification, centroid) | Git, if it stays well under the ≥1 MB policy; otherwise a registry release with its hash/version recorded in a Git manifest | reviewable, needed for build |
| Generated Swift/JSON consumed at build (`LakeDirectory` ≈190 KB) | Git **only with** source + generator + version/provenance + rebuild instructions in a header/manifest (RA-15); otherwise produced at build from the release | generated runtime data |
| Boundary/geometry polygons (`polygons.geojson.gz` 7.5 MB, fetch tables) | canonical versioned release storage; Git holds the **manifest** (URI/version/hash) | large, regenerable, Lake Registry-owned reference material (not Wind truth, not Clarity truth) |
| Lake Brain source bindings (≈425 KB generated Swift, 760 KB proposed JSON) | Lake Brain: small reviewed sets in Git per RA-15, bulk proposals in release storage | Brain-owned, not registry |
| Per-lake species presence | private canonical storage only (never public Git) | private research data |
| Hydrology evidence (12 MB, Clarity) | release storage or recorded exception; Clarity phase | Clarity-owned |

Exact thresholds and the final cut are fixed in the Lake phase; Phase 1A creates only schemas and READMEs.

## 7. Test strategy

* Tests live with their owner: `engine/Tests`, `providers/*/tests`, `platform/*/tests`, `brains/<id>/tests`. Cross-cutting in `tests/`.
* Swift: split the single `SectorEngineTests` into per-target test targets (`EngineTests`, `ProvidersTests`, `PlatformSwiftTests`, `LakeBrainTests`, `WaterTempBrainTests`, `ClarityTests`); Python: every dir has `pytest.ini`, **no loose `test_*.py` beside scripts**.
* `brain.json` declares `tests: [paths]` and CI **derives Brain coverage from the Brain Registry** (replacing the hand-written directory list). Non-Brain infrastructure (platform, providers, customer Engine, cross-cutting integration) is enrolled **explicitly** and never depends on `brain.json` to run; an unregistered test dir is reported by an architecture test.
* Add Swift build+test to CI (or a scheduled workflow) so the Brain Swift targets are covered.
* Golden response test for the customer Engine before any move touching `engine/`.
* Network tests are `-m network`, deselected offline (already the Wind convention).

| Current test | Owner (target) |
|---|---|
| Aggregator, Factor, ConfigOverrides, ForecastRain*, FullPool | `engine/` |
| USGSWaterDataTests + USGS fixtures | `providers/` |
| BrainPlatformConformanceTests | `platform/swift` |
| Lake* (7) | `brains/lake` |
| LakeDirectoryAPITests, registry identity/key tests | `platform/registries/lakes` (endpoint-shape cases stay with `engine/`) |
| WaterTemp* / WaterTemperatureBrain* (8) | `brains/water-temperature` |
| Clarity*, HydrologyGraph | `brains/water-clarity` |
| `brain_platform/tests` (9) | `platform/python` |
| `brain-orchestrator/tests` (4), `brain-scores` (4 loose) | `platform/orchestrator`, `platform/scoring` |
| Wind 8 / Fish 1 / Intelligence 2 / Clarity 1 / TVA archive 1 | their Brain / provider |
| Lake Python (validation, bindings, ledger, review) 6, lake-geometry 1 | `brains/lake` (and add to CI) |

## 7a. Architecture invariants (REPORT-ONLY in Phase 1B; enforced per Brain at its migration phase)

Legacy violations are **not** enforced until the corresponding migration phase establishes compliance.
1. every registered Brain has a valid `brain.json`; 2. `brainId` unique; 3. machine id stable (never renamed); 4. every registered Brain has an operating contract with all 19 sections; 5. declared contracts exist; 6. declared runtime and tests exist; 7. no unauthorized Brain-to-Brain private import; 8. no runtime dependency on `docs/`; 9. no absolute Desktop/user path in runtime code; 10. no direct specialist production writer after that Brain's Publisher cutover; 11. no customer database dependency unless explicitly authorized; 12. every provider dependency is registered in `PROVIDERS.json` and the consumer is authorized; 13. a Brain consumes another Brain only through a declared contract/state; 14. Platform never imports a specialist Brain implementation; 15. large/generated tracked files (≥1 MB) require a policy exception with source/generator/version/rebuild info; 16. research metadata directories contain no raw research data.

## 8. Scoring strategy

* `platform/scoring/`: scorer, beta, score publisher, shared rubric mechanics and the two platform rubrics (engine aggregate, beta readiness).
* `brains/<id>/scoring/rubric.json` (+ short `README`): the Brain's `ENGINE_READINESS_SCORE` definition. `frozen-scores.json` lives in `platform/scoring/` and is replaced Brain-by-Brain as rubrics land. **Scores do not change in any migration phase** (before/after check).
* Naming enforced by `brain.json`: `score.type = ENGINE_READINESS_SCORE`, `score.path = /scores/{brainId}`.
* Candidate/science scores (Wind bowfishing score, validation scoreboards) are named `*_candidate` / `validation/` and never published at `/scores`.
* Customer `CONDITIONS_SCORE` stays in `engine/`; its docs say it is not a readiness score.

## 9. Research boundary and public/private rules

Rule of thumb: **GitHub holds how the Brain works and the metadata that governs research; the workspace holds evidence.**

| MUST be in Sector_Engine | Normally stays OUTSIDE (workspace / private storage) |
|---|---|
| `BRAIN_OPERATING_CONTRACT.md`, `brain.json`, README | raw datasets, provider dumps, corpora, literature PDFs |
| runtime code, artifact builder, validators | private observations, field logs, customer data |
| published contracts, schemas, config defaults | sensitive security findings, private IAM detail, credentials, tokens |
| scoring rubric, validation protocols & prereg (text), small golden fixtures | large/binary model artifacts, private validation archives, RTDB exports |
| tests, deploy scripts without secrets | per-lake species presence and other licensed/private research data |
| provider clients, `PROVIDERS.json` | generated bulk data that can be rebuilt from a recorded recipe |
| architecture docs, decision records | working handoffs (private Desktop handoff folder) |
| research **metadata**: `research/GAPS.json`, `research/MANIFEST.json` (workspace id, artifact hashes, locations as logical names) | the research artifacts themselves |

Conservative public-repo rules: no service-account emails, project numbers beyond what is already public, UIDs, or live job snapshots in `docs/`; size budget (suggested: files > 1 MB or > 5 MB per directory need an exception recorded in `brain.json` `dataBudget`); build-time embedded data (registry, bindings, hydrology) must be **generated from a recorded recipe** and either small or stored as a release artifact; generated files carry a header with source hash.

**Code and `brain.json` must not hard-code the workspace path.** `brain.json` carries a logical workspace id; tools take `SECTOR_RESEARCH_ROOT` (env) + a Brain workspace id (`wind-brain`, `fish-brain`, …); the absolute path exists only in `docs/architecture/certification/BRAIN_RESEARCH_WORKSPACE_V1.md` and local config.

## 10. Source-of-truth model (locked) and canonical-release boundary

| Layer | Is | Includes |
|---|---|---|
| **GitHub** | how the Brain works | code, operating contract, schemas/contracts, tests, score definition, validation protocol, research rules/metadata, deploy/config declarations, reproducibility tooling suitable for source control |
| **Research workspace** | evidence and working research | raw research, datasets, analysis, exploratory outputs, private/large evidence |
| **Canonical versioned storage** | durable accepted Brain knowledge | canonical releases, publication artifacts, durable validation/history that is not appropriate for public Git |
| **`sector-brain` RTDB** | compact current operational published state | Publisher-written current state only |
| **Customer Engine / customer data** | separate product-serving layer | `engine/`, customer database; reached by Brain output only via an approved integration mode |

**No layer impersonates another** (e.g. a research CSV is not a canonical release; RTDB is not a research archive; the customer database is not Brain state; Git is not a data lake).

Flow: `research workspace → (Brain canonicalization, evidence-gated) → canonical release (versioned, private bucket; CERT-3/4) → artifact builder → Publisher → sector-brain`. The repo records the schema, validator and rule for a canonical release (`brains/<id>/contracts`, `validation/`, operating contract §CANONICALIZATION), never a private release payload.

**Research artifact classification (RA-17), applied at each Brain's certification/migration, never in bulk:** every meaningful research-branch artifact is assigned one destination:
GITHUB: operating rules, durable Brain specification, canonical decision records, preregistration/protocols, accepted validation methodology, schemas, small fixtures, research-gap metadata, reproducibility tooling that supports published claims.
RESEARCH WORKSPACE: raw evidence, exploratory research, large datasets, provider dumps, working analyses, private observations, bulky derived outputs, research notes not part of the permanent contract.
CANONICAL VERSIONED STORAGE: accepted durable releases, publication artifacts, validation/history that must be durable but is unsuitable for public Git.
No copy-and-forget; no duplicating evidence merely because a branch exists; use manifest/reference/hash.

## 11. Cross-Brain, import, and publication rules (normative once approved)

1. **Import:** `brains/A` may import `providers`, `platform` (including the Lake and Species Registry contracts), and `brains/B/contracts` only. No `brains/B/runtime|artifact|research` imports, no `engine/` imports.
2. **Data:** a Brain never reads another Brain's research workspace; it reads published state/contracts (RTDB or release). Entity identity (lake, species) comes from the platform registries, not from a Brain.
3. **Customer:** only `engine/` serves customers. Brain output reaches customers only via an approved `customerIntegrationMode` (`embedded` library or `published` contract) and a versioned cutover; never Brain → customer Engine.
4. **Writes:** specialist Brains produce versioned artifacts; only the Publisher writes `sector-brain` (target; the repo structure must not add new direct writers). New direct-writer code is rejected by the architecture test after Publisher cutover.
5. **Providers:** acquisition only through `providers/`; authorized consumers per `PROVIDERS.json`.
6. **Scores:** one `ENGINE_READINESS_SCORE` per Brain at `/scores/{brainId}`; Ops never computes.
7. **Platform duplication:** a Brain may not re-implement envelope/keys/freshness/health/ownership/lineage.
8. **Unknown is not zero**: schemas must allow explicit `UNKNOWN`/absent; builder tests assert it.
9. **Research is bounded**: Research Gaps (below) are the only reason to start research work.

## 12. Alternatives considered

| Alternative | Why not |
|---|---|
| "Everything under `brains/`" | Puts providers, platform and the customer Engine under Brains or leaves them orphaned; customer Engine is not a Brain; fails shared-provider goal |
| Keep `jobs/` as primary (one dir per runtime job) | Runtime units ≠ ownership (Lake spans 3 jobs; Fish/Intelligence are in-process); this is today's confusion |
| Language-first (`swift/`, `python/`) | Splits each Brain across the tree (the current problem) |
| Separate repos per Brain | Platform contracts, Publisher and Orchestrator need atomic cross-Brain changes; public-repo + one CI is simpler at this scale. Revisit only if a Brain becomes independently maintained |
| Monorepo with Python workspace tool (uv/poetry) | Not needed yet; plain `pyproject.toml` per package keeps stdlib-only constraint |
