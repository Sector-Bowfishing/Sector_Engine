# Publisher V1: shadow architecture

**Status:** implemented in SHADOW ONLY mode on branch `feat/publisher-v1-shadow` (local; not pushed). **Success state: `PUBLISHER_V1_SHADOW_READY`.** This is *not* `PRODUCTION_PUBLISHER_DEPLOYED`, `WIND_CUT_OVER` or `SPECIALIST_WRITERS_DISABLED`.
**Design closeout (Michael, follow-up session):** the decisions in §0 are LOCKED; the P7/P8 design questions (artifact handoff signal, API shape) are closed. Closing them authorises no deployment.
**Implements:** CERT-1 (Publisher is a platform library in the Orchestrator platform; small authenticated API shares its identity) and CERT-2 (separate shadow-only task) from `../certification/README.md`. Standards followed: `BRAIN_IDENTITY_AND_LINEAGE_V1.md`, `BRAIN_READ_WRITE_SECURITY_V1.md` §2-4, `BRAIN_PATH_OWNERSHIP_V1.md`.
**Code:** `jobs/brain_platform/sector_brain_platform/publisher/` (stdlib-only; not imported by `sector_brain_platform/__init__.py`, so no production job loads it). **Tests:** `jobs/brain_platform/tests/test_publisher_*.py`.

## 0. Locked decisions (summary; details in the numbered sections)
| # | Decision | Where |
|---|---|---|
| 1 | `SHADOW` stays the shadow-only record status; `SHADOW_READY` the shadow result. Shadow never claims a publication; there is no `PUBLISHED` member anywhere. | §8 |
| 2 | `ARTIFACT_OLDER_THAN_BASELINE` stays, with one exact comparison rule that fails closed when order cannot be established. | §5 |
| 3 | Specialist artifacts never replace `/brains/{brainId}`; child-level mutations only; `/brains/{brainId}/publication` (and `certification`) are Publisher-owned. | §4a |
| 4 | Handoff: Brain → private artifact storage → authenticated API signal (a reference) → Orchestrator loads → Publisher validates → SHADOW (production mode later, separately approved). Production RTDB is never an artifact queue; Ops never writes an RTDB request node. | §9a |
| 5 | The API is workflow-oriented and bounded; no `write(path, json)`, no arbitrary PATCH, no caller-supplied JSON to publish. | §9 |
| 6 | Logical private storage layout defined (no bucket created). | §8 |
| 7 | P7/P8 closed: Orchestrator platform library + small authenticated API service + dedicated Publisher identity (future). Not deployed. | §9, cutover doc |
| 8 | Wind shadow-integration contract is stable and tested. | §11 |

## 1. What it is
```
specialist Brain ──► publish artifact (envelope + lineage + mutations)
                          │
                 ShadowPublisher.evaluate(artifact, producer=<authenticated brainId>)
                          │  stage 0  shape                        → FAILED_VALIDATION
                          │  stage 1  brainId registered + equals the submitter     → REJECTED
                          │  stage 2  artifactSchema registered for that brain      → REJECTED
                          │  stage 3  every path in an authorised family; cross-domain; reserved; delete policy; overlap
                          │  stage 4  lineage complete / well-formed / release triplet
                          │  stage 5  lifecycle policy, review/validation semantics, freshness
                          │  stage 5b values: no null, no empty container, no NaN, legal keys, value type
                          │  stage 6  size bound; outputFingerprint RECOMPUTED and compared with the declared one
                          │  stage 7  compare with the scope's baseline (history head)
                          ▼
     SKIP (equal)  |  SHADOW_READY (changed)  |  REJECTED  |  FAILED_VALIDATION
                          │
          ONE deterministic atomic update plan  ──►  ShadowSink (memory only)
          + publication record  ──►  history store (local/test)
```
In front of stage 0 the production handoff adds a reference step (§9a): the API signal names an artifact; the Publisher loads it from private storage, checks the namespace, the declared hash of the exact stored bytes and the request/artifact bindings, and then runs the **same** stages 0-7 (`evaluate_reference` and the local convenience `evaluate` share `_run`).
The Publisher knows structure and authorization. It never reads, recomputes or "fixes" a domain value, and nothing in the package mentions any Brain's science. The only Brain-specific content is *registration data* (`registry.wind_specs()`).

## 2. Modules
| Module | Responsibility |
|---|---|
| `canonical.py` | canonical JSON, `sha256:<hex>`, volatile-field stripping, `output_fingerprint` |
| `paths.py` | path normalisation, exact-depth `PathFamily`, reserved Publisher-owned children, forbidden roots, cross-domain naming (reuses `ownership.path_allowed`) |
| `registry.py` | `SchemaSpec` / `Registry` (brainId → schema → path families), Wind registration |
| `validate.py` | the validation stages above |
| `plan.py` | `build_update_plan`: one atomic `{rtdb key → value}` dict + publication record; asserts no `None` without an explicit DELETE |
| `sinks.py` | `ShadowSink` (the only sink) and `require_shadow_sink` |
| `publisher.py` | `ShadowPublisher`, `PublishResult` |
| `storage.py` | `ObjectStore` (GCS-style generations), `MemoryObjectStore`, `LocalDirObjectStore`, `PublishHistory` |
| `refs.py` | `ArtifactRef` (the only thing the API signal carries about an artifact), artifact location layout, reference validation |
| `handoff.py` | Brain-side `ArtifactWriter` (create-only, own prefix), `seal_artifact`, `ShadowDispatcher` (API → `evaluate_reference`), `local_shadow_stack` for Brain shadow-integration tests |
| `api.py` | Orchestrator API contract + shadow handler (CONTROL / REVIEW / RESEARCH / ARTIFACT) |
| `model.py` | `PublisherMode`, `Result`, reason-code table, `Violation`/`Rejected` |

## 3. Artifact envelope (`publish-artifact-v1`)
```jsonc
{ "envelope": "publish-artifact-v1",
  "lineage":  { /* brain-lineage-v1 exactly as BRAIN_IDENTITY_AND_LINEAGE_V1 §2: schema, brainId, artifactSchema, knowledgeRelease,
                   manifestRef, manifestSha256, codeVersion, executionId, inputFingerprint, outputFingerprint, [artifactId],
                   generatedAt, lifecycle, reviewStatus, validationStatus */ },
  "scope": "default",                       // optional; baseline key within (brainId, artifactSchema)
  "freshness": { "freshnessStatus": "FRESH|STALE|EXPIRED|UNAVAILABLE|UNKNOWN", "evidenceObservedAt": "…", "inputGeneratedAt": "…", "staleAfter": "…", "expiresAt": "…" },
  "approvalRef": "…",                       // needed for PRODUCTION / PRODUCTION_READY
  "mutations": [ {"op":"SET","path":"/lakes/{k}/states/wind","value":{…}},
                 {"op":"DELETE","path":"…","reason":"…"} ] }
```
Unknown envelope/lineage/mutation keys are rejected. `executionId` and (if present) `artifactId` are UUIDv4 (or `sha256:`); `brainId` stays a readable kebab-case id. The Publisher adds `publishId`, the evaluation time and the publisher identity *class* (`orchestrator-publisher`) in the publication record, never to the artifact.

**Mutations, not a free-form map.** Payload is a list of explicit `SET`/`DELETE` operations on normalised absolute paths; a plan is built only from those, so the Publisher can never be asked to write a path nobody authorised, and a `None` in the plan exists only where a `DELETE` was requested and permitted.

## 4. Path authorization (fail closed)
* `PathFamily` is an **exact-depth pattern**: `{k}` matches exactly one segment, optionally constrained (`lake key`, `owned source ids`, `not a reserved child`). No `**`, no prefix wildcards, so a family never silently covers a deeper or shallower path.
* A path is authorised only if a family of **the artifact's own schema** (per `SchemaSpec.families`, or `delete_families` for DELETE) matches. One schema cannot borrow another schema's paths (`wind-lake-state-v1` cannot write `/health/brains/wind`).
* Roots `access control jobs scores engine schemaVersion controlRequests` can never be declared in any schema (registration fails).
* `/brains/{id}/publication` and `/brains/{id}/certification` (and anything under them) are **reserved** for the Publisher/Orchestrator (`RESERVED_PATH`); `/brains` and `/brains/{id}`, whose whole-node SET would erase them, are `BRAIN_NODE_REPLACEMENT`. See §4a.
* A rejected path is classified `CROSS_DOMAIN_PATH` when another owner legitimately owns it (species identity/policy, another Brain's slot/registry/score, platform roots; uses the live `ownership.path_allowed` table plus protected roots), else `PATH_NOT_AUTHORIZED`.
* **Brain node ownership (§4a)** is enforced on top of the families.
* **Wind** (`registry.wind_specs()`), three schemas so no schema is broader than its job:

| Schema | Families |
|---|---|
| `wind-lake-state-v1` (freshness required) | `/lakes/{k}/states/wind`, `/lakes/{k}/profiles/wind`, `/lakes/{k}/validation/wind`, `/lakeFleet/{k}/{slots,readiness,modelVersions}/wind` (DERIVED_PROJECTION), `/snapshots/{k}/latest/wind` (LEGACY_READER_PRESENT; same atomic publish) |
| `wind-registry-v1` | `/brains/wind/{child}` for the approved children in `WIND_REGISTRY_CHILDREN` only (§4a), `/validation/wind`, `/health/brains/wind`, `/activity/{event}` (own events only) |
| `wind-source-registry-v1` | `/sources/{id}`, `/health/sources/{id}` for sources whose acquisition owner is `wind` (derived from `ownership.SOURCE_OWNERS`) |

  Lifecycles Wind artifacts may carry: RESEARCH, PROFILED, SHADOW, CALIBRATION. `PRODUCTION*` needs both schema permission and an `approvalRef`; Wind has neither. A test asserts every Wind family is also allowed by the existing writer-side `ownership.path_allowed`.
* Every other Brain id is registered as an identity with **no schema**: their artifacts reject `UNKNOWN_SCHEMA` until their own certification registers one.

## 4a. `/brains/{brainId}` ownership model
Whole-node replacement is not acceptable in the target. A specialist artifact may only mutate **approved child paths** of its own Brain node; a multi-location update at child level is a merge by construction (siblings, including Publisher-owned ones, are untouched; tested by applying a plan to a store double).

| Child of `/brains/wind` | Owner | Notes |
|---|---|---|
| `brainId displayName domain question platform` (group `identity`) | Wind | |
| `version schemaVersion stalenessModel dependsOn descriptor versions activeProductionModel researchCandidate scores readinessDefinitions stateKinds` (group `model`) | Wind | `scores` here is Wind's own labelled score content; the authoritative `ENGINE_READINESS_SCORE` stays at Platform-owned `/scores/wind` (score reconciliation is a Wind certification item) |
| `schedule enabled health status supportedLakeCount profiledLakeCount readinessCounts staleLakeCount staleAfterHours staleRule lastSuccessfulRun lastError deploymentVersion breakdowns runsPerMinute updatedAt publishMode` (group `status`) | Wind | |
| `publication` | **Publisher** | latest publication record, written in the same atomic update; reserved |
| `certification` | **Orchestrator/Publisher** | reserved; written by a later feature |
| anything else | nobody | `PATH_NOT_AUTHORIZED` until a schema registers it |

Each child is replaced as a unit (exact-depth families: `/brains/wind/status/health` is rejected). The child list follows the registry fields `wind-hourly` writes today; a Brain's certification may add children by registering them. Rejection codes: `/brains` and `/brains/{id}` → `BRAIN_NODE_REPLACEMENT`; `publication`/`certification` (and anything under them), for any Brain → `RESERVED_PATH`; another Brain's child → `CROSS_DOMAIN_PATH`. Consequence for the existing Wind registry: fields that are `None` today (`lastError`, version `date`) must be omitted, not published as null (a child with no value is simply not in the artifact; a stale child needs an explicit permitted DELETE).

## 5. Fingerprints, SKIP and ARTIFACT_OLDER_THAN_BASELINE
`outputFingerprint = sha256(canonical JSON of {brainId, artifactSchema, mutations sorted by path})` with volatile keys removed at any depth (shared default `generatedAt publishedAt checkedAt ageHours durationMs` + `SchemaSpec.volatile_extra`) and floats rounded to 9 places (the platform's existing noise tolerance). The Publisher recomputes it and rejects `FINGERPRINT_MISMATCH` if it differs from the declared value; Brain-supplied fingerprints are never trusted. The scope's baseline is the history head pointer (§8). Equal → `SKIP`: no plan, no sink call; only a history record (this is checked first, so identical content never needs an ordering decision).

**Ordering rule (exact, fail closed).** Evaluated only when the content differs from the scope's baseline (baseline = history head for `(brainId, artifactSchema, scope)`):
| Condition | Result |
|---|---|
| artifact `lineage.generatedAt` **>** baseline `generatedAt` | accepted (continues to SHADOW_READY) |
| artifact `generatedAt` **≤** baseline `generatedAt` | `REJECTED ARTIFACT_OLDER_THAN_BASELINE` (equal time + different content is ambiguous order, so it is rejected too); detail names the baseline `publishId` |
| baseline or artifact `generatedAt` missing / not ISO-8601 UTC | `REJECTED BASELINE_ORDER_UNKNOWN` (never guess) |
| artifact `generatedAt` more than 5 minutes after the Publisher clock | `REJECTED ARTIFACT_FROM_FUTURE` (a future-dated artifact would otherwise block every later honest one) |
Both timestamps are the Brain's validated lineage values at full sub-second precision; wall-clock arrival order is never used; the comparison is per scope. A rejection never moves the baseline and is recorded in history with its diagnostic. An older artifact is republished only by an explicit rollback, a separate later approved mechanism (cutover P5).

## 6. Null / delete semantics
* `SET` with a missing/`null` value, a nested `null`, or an empty object/array is **rejected** (`NULL_VALUE`, `NULL_IN_VALUE`, `EMPTY_VALUE`): RTDB deletes a null node and drops empty containers, so each would be an implicit delete. UNKNOWN is encoded as the string `UNKNOWN`.
* Data absent from a newer artifact is simply absent from the plan; nothing is deleted. `plan.deletes` and every `None` in `plan.updates` correspond one-to-one to explicit `DELETE` mutations; `build_update_plan` re-asserts this itself.
* `DELETE` needs `delete_families` on the schema (Wind: none), a non-empty `reason`, and no value.

## 7. Shadow-only guarantee (not a comment)
1. `PublisherMode` has two members, `SHADOW` and `DRY_RUN`. **There is no live member** to select.
2. `Result` has no `PUBLISHED`. Records carry `status: SHADOW`, `live: false` and no `publishedAt`.
3. `ShadowPublisher` accepts only a `ShadowSink` that exposes no write-shaped method; a `DryRunStore`, `BrainRtdb`, a duck-typed object or a subclass adding `update`/`patch`/… raises `LiveCapabilityRefused`.
4. The package imports no network, process, credential or cloud-start module and no platform module that can write live (`rtdb`, `gcp`, `jobs`, `orchestration`, …). `test_publisher_boundary.py` lints this with an AST scan and a source scan, runs the whole flow with sockets/`urlopen`/`subprocess` monkeypatched to fail, and proves environment variables cannot change behaviour.
5. `sector_brain_platform/__init__.py` is untouched; production jobs never import the package.
6. `DRY_RUN` additionally writes no history and never calls the sink.

## 8. Plan, record, history
* **Plan** (`UpdatePlan`): one dict keyed by root-relative RTDB path, sorted, containing every artifact path **plus** `brains/{id}/publication` (the record, RTDB-safe: no nulls/empties). Built entirely in memory first; if building or validation fails nothing is handed to the sink or persisted except a rejection record. Order in `SHADOW`: persist artifact → `sink.submit` → append record → advance head, so a sink failure leaves no record and no head change.
* **Record**: `publishId, previousPublishId, brainId, artifactId, executionId, artifactSchema, scope, result, status, evaluatedAt, publisher, mode, trigger, requestId, knowledgeRelease, codeVersion, input/outputFingerprint, generatedAt, lifecycle, reviewStatus, validationStatus, paths{count,bytes}, pathSha256{}, artifactPatchSha256, updateSha256, removed[]`, plus `violations[]` on rejections. **SHADOW semantics (locked).** `status` is `SHADOW | SKIPPED_UNCHANGED | REJECTED`; `result` is `SKIP | SHADOW_READY | REJECTED | FAILED_VALIDATION`. A `SHADOW` record means "validated, changed, and the atomic plan was rendered to the ShadowSink"; it carries `live: false`, `mode: SHADOW`, `evaluatedAt` and **no `publishedAt`**. The lineage doc's `COMPLETE`/`PARTIAL` (and a `PUBLISHED` result) exist only for live publication and are unreachable in this code. The shadow baseline advances on `SHADOW_READY` only, and is never mistaken for live state. In the RTDB-shaped publication node the history-only fields (`pathSha256`, `violations`, `headGeneration`) are omitted: path-keyed hashes are not legal node keys.
* **Private storage contract** (CERT-3; logical layout only, **no bucket exists**):
  `artifacts/{brainId}/{artifactId}/artifact.json` immutable · `publishes/{brainId}/{publishId}/record.json` immutable · `publishes/{brainId}/_heads/{artifactSchema}/{scope}.json` versioned baseline pointer (optimistic concurrency) · `scores/{brainId}/…`, `exports/…` reserved (not written by Publisher V1). A `sha256:` artifactId is stored as `sha256-<hex>`.
  | Principal (target) | artifacts/ | publishes/ | scores/ exports/ |
  |---|---|---|---|
  | specialist Brain, own `{brainId}` | **create-only** (`ifGenerationMatch=0`), read own | none | none |
  | any other Brain's prefix | none | none | none |
  | Publisher | **read** | **create** records, move heads (generation-matched) | none in V1 |
  | anyone | **no delete** of immutable history | | |
  Implemented in code as `ScopedObjectStore` views (`brain_view`, `publisher_view`) with no delete method at all; this is defence in depth, **IAM enforces the same model at cutover**. `ObjectStore` mirrors GCS generations. Shipped: `MemoryObjectStore`, `LocalDirObjectStore`. Not shipped: any GCS adapter.
* **Rollback metadata**: `PublishHistory.rollback_reference(brain, publishId)` → previous baseline `publishId`, its immutable `artifactId`/key and fingerprint (`None` for a first publication). Executing a rollback is out of scope for V1.
* SKIP and REJECTED are recorded in history only; on the local direct-evaluate path a rejected artifact is stored under `rejected-{publishId}`; on the reference path the Brain's artifact is already stored and the record points at it (the Publisher never writes `artifacts/`).

## 9. Orchestrator API contract (`api.py`)
`authenticate → coarse allowlist → request schema → fine authorization (caller, kind, action, Brain) → Orchestrator workflow`. Request: `apiVersion, requestId (UUIDv4), requestKind, brainId, action, params, [confirm]`, nothing else (unknown fields rejected).
| Kind | Actions | Notes |
|---|---|---|
| `ARTIFACT` | `SUBMIT_ARTIFACT` | params: `artifactId artifactRef artifactSha256 executionId expectedSchema`; a reference, never content (§9a) |
| `CONTROL` | `RUN_NOW(scope) PAUSE RESUME SET_MANUAL`; protected: `CHANGE_PROTECTED_SCHEDULE DISABLE_VALIDATION_CAPTURE` | `RUN_NOW` is the design's "RUN_BRAIN" (existing orchestration action name kept; no second spelling). Protected actions need `confirm.by == caller` and the exact phrase |
| `REVIEW` | `SUBMIT_REVIEW ACCEPT_RULE REJECT_RULE` | |
| `RESEARCH` | `RESEARCH_GAP` | |
`SET_ENGINE_MODE ACTIVATE_PRODUCTION PUBLISH_CUSTOMER PROMOTE_LIFECYCLE` are never grantable (rejected before authorization; an allowlist cannot even be constructed with them). Grants are per kind and action, and may be pinned to one Brain (`SUBMIT_ARTIFACT@wind`). Params are closed per action, scalar only (str/int), length-bounded, pattern/enum-checked.

**Hard rule: no arbitrary path/write API.** There is no request, field or param that carries a database path, a value, an update map, a mutation list, or JSON to publish; unknown fields and params are rejected (`UNKNOWN_FIELD` / `UNKNOWN_PARAM`) and a test enumerates the schema for path/payload-looking names. The handler holds no database client; it passes a validated `ApiRequest` to an injected `Dispatcher`. The `ARTIFACT` response is a summary only (`result, publishId, codes, live, mode`): no plan, path or value leaves the Publisher through the API. No Firebase token verification or HTTP server exists yet; `Authenticator` is a protocol (cutover P7).

## 9a. Artifact handoff (locked)
```
specialist Brain ─(create-only, own prefix)─► private artifact storage  artifacts/{brainId}/{artifactId}/artifact.json
        │ returns ArtifactRef {brainId, artifactId, location, sha256 of the exact stored bytes, executionId, expected schema}
        ▼
authenticated API signal  SUBMIT_ARTIFACT (the reference, requestId)          ── identifies the artifact; carries no mutations
        ▼
Orchestrator ─► Publisher.evaluate_reference(ref)
        │ 1 reference well-formed; location is exactly artifacts/{ref.brainId}/{artifactId}/artifact.json   else NAMESPACE_VIOLATION / ARTIFACT_REF_INVALID
        │ 2 artifact exists                                                                                 else ARTIFACT_NOT_FOUND
        │ 3 sha256(stored bytes) == declared hash                                                           else ARTIFACT_HASH_MISMATCH
        │ 4 artifact's lineage artifactId / executionId / artifactSchema agree with the request            else ARTIFACT_BINDING_MISMATCH
        │ 5 the SAME stages 0-7 as any artifact (identity, schema, paths, lineage, lifecycle, values, recomputed fingerprint, baseline ordering)
        ▼
SHADOW now (SHADOW_READY / SKIP / REJECTED / FAILED_VALIDATION) · production publication only in a later, separately approved mode
```
The caller never chooses a production path: paths come only from the stored artifact and are authorised by the schema registry. The same caller identity that may submit for Brain X is checked against X's namespace twice (API validation and Publisher), so Wind cannot reference Fish's namespace and Wind's identity cannot submit as Fish. Production RTDB is not an artifact queue and not a request inbox; Ops reaches the Orchestrator only through this API. The signal channel (P8) is therefore: **authenticated API call**; the Orchestrator's own execution records remain an additional trigger for artifacts of Brains it starts itself.

## 10. Architecture notes found while implementing (refinements, not conflicts)
1. **RESOLVED (decision 3):** whole-node `/brains/{id}` writes are rejected; Wind's registry is published as approved child nodes (§4a). Wind's live writer still writes the whole node today and must change before cutover.
1a. **Bug found and fixed in this follow-up:** the first version put a path-keyed hash map (`pathSha256`) inside the plan's publication node; `/` is not a legal RTDB node key, so a live write would have failed. Plans are now validated with the platform's `check_update` and tests apply plans to the platform's store double.
2. RTDB's null/empty semantics make "UNKNOWN as null" unsafe; artifacts must encode UNKNOWN as a value (already the lineage standard).
3. Oversize artifacts (> `SchemaSpec.max_bytes`, default 8 MiB) are rejected. Manifest-last chunking (security doc §3.7) is **not** in V1; fleet-wide Wind artifacts may need it or per-lake scoping.
4. Wind-specific volatile fields beyond the shared default must be listed by the Wind certification (`volatile_extra`) or they will cause needless `SHADOW_READY` results.
5. The shadow baseline is the last `SHADOW_READY` record, not live state. The first live publish after cutover must reconcile it (see the cutover requirements).
6. Not verified, deliberately: any live system (RTDB rules, IAM, schedulers, buckets). Nothing live was read or changed.

## 11. Wind shadow-integration contract (stable surface for the Wind certification session)
Use `local_shadow_stack(root=None | dir)` for a complete local pipeline, `seal_artifact(...)` to build an envelope with a correct fingerprint, `stack.writer("wind").write(artifact)` for the Brain-side write, and either `stack.publisher.evaluate_reference(ref)` or the API (`OrchestratorApi` + `stack.dispatcher`) for the signal. Schemas: `wind-lake-state-v1`, `wind-registry-v1`, `wind-source-registry-v1`. Everything below is covered by `tests/test_publisher_wind_integration.py` and `test_publisher_handoff.py`:
accepted artifact · reference/hash validated · schema accepted · lineage accepted · output fingerprint verified · unchanged → SKIP · changed → SHADOW · authorized Wind paths accepted · unauthorized/cross-domain paths rejected · `/brains/wind/publication` protected · whole-node `/brains/wind` rejected · null-on-miss cannot delete · one deterministic atomic plan · no live mutation. Wind must supply its own `volatile_extra`, register any additional registry children, and keep `wind-hourly` untouched until its own approved cutover.
