# Publisher V1: shadow architecture

**Status:** implemented in SHADOW ONLY mode on branch `feat/publisher-v1-shadow` (local; not pushed). **Success state: `PUBLISHER_V1_SHADOW_READY`.** This is *not* `PRODUCTION_PUBLISHER_DEPLOYED`, `WIND_CUT_OVER` or `SPECIALIST_WRITERS_DISABLED`.
**Gate P (Wind / Publisher contract hardening):** F-1..F-9 resolved at the shadow-contract level; see §12. Status `PUBLISHER_GATE_P_SHADOW_READY`. `PRODUCTION_WRITE_SECURITY_GATE_OPEN` (§12.9): this blocks production cutover, not shadow work.
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
| `canonical.py` | canonical JSON, `sha256:<hex>`, volatile key/path stripping, `output_fingerprint`, `bundle_fingerprint`, algorithm id |
| `artifact.py` | parse + validate ONE logical artifact (v1 one section / v2 several) into `Parsed`, or reject the whole thing |
| `compat.py` | machine-readable legacy path table (classification, owner, source, retirement gate) |
| `equivalence.py` | Wind shadow equivalence evaluator (live vs Publisher-produced target) |
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

## 3. Artifact envelope (`publish-artifact-v1` one section, `publish-artifact-v2` several sections)
**v2** (Gate P): `{"envelope":"publish-artifact-v2","lineage":{…,"artifactSchema":"<bundle id>"},"sections":[{"artifactSchema","scope?","freshness?","mutations"}],"approvalRef?"}`. The bundle (`wind-publication-v1`) names which section schemas one logical artifact may contain; `lineage.outputFingerprint` is the bundle fingerprint over the sections' semantic fingerprints. v1 and v2 never mix. Details of the transaction semantics: §12.1.

### v1 shape
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
| `wind-lake-state-v1` (freshness required) | `/lakes/{k}/states/wind`, `/lakes/{k}/profiles/wind`, `/lakes/{k}/validation/wind`, `/lakeFleet/{k}/{slots,readiness,modelVersions}/wind` (DERIVED_PROJECTION). Explicit DELETE of the same nodes (reasons `LAKE_LEFT_FLEET`, `EVIDENCE_REMOVED`). **`/snapshots/{k}/latest/wind` and `brainVersions/wind` are no longer authorable: the Publisher derives them (§12.5).** |
| `wind-registry-v1` | `/brains/wind/{child}` for the approved children in `WIND_REGISTRY_CHILDREN` only (§4a), `/validation/wind`, `/health/brains/wind/{status,staleLakeCount}` (domain health facts only; process/job health is Orchestrator-owned, §12.6), `/activity/{event}` (own events only). Explicit DELETE of `/brains/wind/lastError` (reason `OPTIONAL_CHILD_CLEARED`). |
| `wind-source-registry-v1` | `/sources/{id}`, `/health/sources/{id}` for sources whose acquisition owner is `wind` (derived from `ownership.SOURCE_OWNERS`) |

  Bundle `wind-publication-v1` = these three schemas as sections of ONE artifact. Lifecycles Wind artifacts may carry: RESEARCH, PROFILED, SHADOW, CALIBRATION. `PRODUCTION*` needs both schema permission and an `approvalRef`; Wind has neither. A test asserts every Wind family is also allowed by the existing writer-side `ownership.path_allowed`.
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
`outputFingerprint` is the **semantic** fingerprint, algorithm `sector-semantic-fingerprint-v2`: sha256 of the canonical JSON of `{algorithm, brainId, artifactSchema, mutations sorted by path}` with (a) volatile KEYS removed at any depth inside values and (b) SET mutations whose PATH matches a volatile path family left out, both governed by the schema's `VolatileContract` on top of the shared defaults (§12.2); floats rounded to 9 places (the platform's existing noise tolerance). The Publisher recomputes it and rejects `FINGERPRINT_MISMATCH` if it differs from the declared value; Brain-supplied fingerprints are never trusted. The scope's baseline is the history head pointer (§8). Equal → `SKIP`: no plan, no sink call; only a history record (this is checked first, so identical content never needs an ordering decision).

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
* `DELETE` needs `delete_families` on the schema, a `reason` from the schema's **closed** `delete_reasons` vocabulary, and no value. Full semantics (typed op, exact-node scope, conflicts, derived deletes): §12.4.

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
4. **RESOLVED (F-8):** Wind's volatile contract is registered as `wind-volatile-v1` (§12.2), minimal and inspectable.
5. The shadow baseline is the last `SHADOW_READY` record, not live state. The first live publish after cutover must reconcile it (see the cutover requirements).
6. Not verified, deliberately: any live system (RTDB rules, IAM, schedulers, buckets). Nothing live was read or changed.

## 11. Wind shadow-integration contract (stable surface for the Wind certification session)
Use `local_shadow_stack(root=None | dir)` for a complete local pipeline, `seal_artifact(...)` to build an envelope with a correct fingerprint, `stack.writer("wind").write(artifact)` for the Brain-side write, and either `stack.publisher.evaluate_reference(ref)` or the API (`OrchestratorApi` + `stack.dispatcher`) for the signal. Schemas: `wind-lake-state-v1`, `wind-registry-v1`, `wind-source-registry-v1`. Everything below is covered by `tests/test_publisher_wind_integration.py` and `test_publisher_handoff.py`:
accepted artifact · reference/hash validated · schema accepted · lineage accepted · output fingerprint verified · unchanged → SKIP · changed → SHADOW · authorized Wind paths accepted · unauthorized/cross-domain paths rejected · `/brains/wind/publication` protected · whole-node `/brains/wind` rejected · null-on-miss cannot delete · one deterministic atomic plan · no live mutation. Wind must supply its own `volatile_extra`, register any additional registry children, and keep `wind-hourly` untouched until its own approved cutover.

## 12. Gate P resolution (F-1 .. F-9)
### 12.0 Resolution matrix
| ID | Finding (Wind shadow integration) | Resolution | Evidence |
|---|---|---|---|
| F-1 | volatile scalar children addressed by path were never stripped, so unchanged artifacts did not SKIP | generic `VolatileContract`: volatile **keys** (any depth) + volatile **path families** (exact-depth), per schema, shared defaults always on; three distinct hashes documented (§12.2) | `test_volatile_scalar_children_do_not_force_a_republish`, `…material_change…not_hidden`, `…three_hashes…`, `…never_hide_a_delete` |
| F-2 | one run produced several plans | envelope **v2**: ONE logical artifact with sections → ONE validation, ONE plan, ONE publication record, ONE sink call; whole-artifact rejection; per-section baselines (§12.1) | `test_one_multi_section_artifact_yields_one_plan…`, `…one_bad_mutation_in_any_section_rejects_the_whole_artifact…` (7 cases), `…order_independent` |
| F-3 | publication record overwritten once per plan | Publisher writes exactly one `brains/{id}/publication` per accepted artifact, stable `publishId`; reserved against specialists incl. delete; SKIP writes none (§12.3) | `test_publication_metadata_is_written_once…`, `test_a_specialist_cannot_author_or_delete_publication_state…`, `test_skip_does_not_fabricate_a_publication` |
| F-4 | stale optional children could not be removed | typed `DELETE` op + per-schema delete families + closed reason vocabulary; exact-node scope, no subtree/whole-node/foreign/reserved deletes; SET+DELETE conflict code (§12.4) | `test_allowed_optional_child_delete…`, `test_unauthorized_deletes_are_rejected…` (12), `test_set_and_delete_of_the_same_path_conflict…`, `test_delete_reasons_are_a_closed_vocabulary` |
| F-5 | legacy paths Wind writes but is not authorised for | every path classified into exactly one of four categories in `compat.LEGACY_PATH_TABLE`; Wind ownership **not** widened; snapshot paths become Publisher-derived projections (§12.5) | `test_every_row_has_exactly_one_valid_classification…`, `test_platform_owned_and_derived_rows_are_not_authorable_by_wind`, `test_snapshot_copy_and_brainversion_are_publisher_derived_and_explicit` |
| F-6 | Wind owns Ops job-health representation | split: Wind authors domain health facts only; execution/job health is Orchestrator-owned with a declared compatibility path (§12.6) | `test_wind_cannot_author_platform_owned_or_derived_legacy_paths`, `test_wind_domain_health_children_and_events_remain_authorable` |
| F-7 | activity pruning / failure health inside Wind | retention = Platform maintenance; failure execution state = Orchestrator; Brain emits only append-only domain events (§12.7) | legacy table rows `activity-retention`, `health-brains-wind-process`, `registry-lasterror` |
| F-8 | Wind volatile list not in the Publisher | `wind-volatile-v1` (named, versioned, annotated, minimal) registered on all three Wind schemas; no hidden list in Publisher code (§12.2) | `test_wind_volatile_contract_is_inspectable_named_versioned_and_fully_explained` |
| F-9 | shadow baseline vs live state | `equivalence.evaluate_equivalence`: six-class, machine-readable, digest-only evidence; unknowns never normalised away (§12.8) | `tests/test_publisher_equivalence.py` (13) |

### 12.1 Atomic publication model (F-2)
```
one logical artifact (v1: 1 section | v2: n sections of an allowed bundle)
   → A.parse: shape → identity → schema/bundle → paths (ALL sections, all violations) → global overlap/conflict → lineage → lifecycle (every section's schema must allow it)
              → freshness (per section) → values → sizes → recomputed fingerprints (per section, then the bundle)       ── any failure rejects the WHOLE artifact
   → per-section baseline comparison:  identical → that section SKIPs (contributes nothing) ; changed → part of the plan
        all sections identical → result SKIP, no plan, no sink call, no head move
        any changed section older than its baseline / unorderable / future-dated → whole artifact REJECTED
   → derive Publisher-owned compatibility projections from the CHANGED sections (§12.5)
   → ONE UpdatePlan = authored mutations (all changed sections) + derived + the ONE publication record, checked with the platform's check_update
   → SHADOW: persist artifact (if direct) → ONE sink.submit → append the ONE record → advance each changed section's head
```
No plan exists before the whole artifact is validated, so no partial plan can survive a rejection. Unchanged sections are not republished: their live content is by definition identical to their baseline (that is the SKIP condition), so the plan plus the untouched sections form a coherent whole. Mutation and section order never affect the output (sorted by path / (schema, scope)). Baseline heads advance sequentially after the sink call with generation-matched writes (single writer per Brain is guaranteed by the Orchestrator's single-flight; a lost race raises rather than overwriting). The record carries `sections[]` (schema, scope, section fingerprint, SKIP|SHADOW, previous publish) and `derived[]`.

### 12.2 Semantic fingerprint, volatile contract, the three hashes (F-1, F-8)
| Concept | Covers | Excludes | Used for |
|---|---|---|---|
| **Input artifact integrity hash** (`artifactSha256` in the API reference) | the exact stored bytes of the artifact (everything: lineage, ids, times, freshness, volatile fields) | nothing | proving the Publisher loaded the artifact the Brain wrote (`ARTIFACT_HASH_MISMATCH`) |
| **Semantic output fingerprint** (`lineage.outputFingerprint`, per section and bundle) | brainId, artifactSchema, every mutation `(op, path, value)` | lineage (generatedAt, executionId, artifactId, codeVersion, release, input fingerprint), freshness block, Publisher metadata, shared + schema volatile keys at any depth, SET mutations at volatile paths; DELETE operations are **never** excluded | SKIP / change decision; recomputed by the Publisher, never trusted |
| **Publication metadata** (`publication` record) | publishId, evaluatedAt, publisher identity, mode/status, fingerprints, section results, derived rules, path counts | not part of any fingerprint | audit, rollback reference, the single `brains/{id}/publication` node |
The shared volatile keys (`generatedAt publishedAt checkedAt ageHours durationMs`) always apply; a schema's `VolatileContract` can only ADD (id, version, keys, path families, and a rationale/retirement note for every entry). **Wind: `wind-volatile-v1`** = keys `inputAgeHours lastFetchAt latencyMs`; paths `/brains/wind/updatedAt`, `/brains/wind/lastSuccessfulRun` (both transitional, with retirement gates in the legacy table). Deliberately minimal: a missing entry only costs an extra `SHADOW_READY`; a wrong entry could hide a domain change. Evidence times (`observationTime`, `forecastGeneratedAt`, `latestObservationAt`, `latestIssuedAt`) stay **material**. Dropped from the first-round Wind list because those fields are no longer Wind-authored: `lastUpdatedAt lastRun lastSuccess` (process fields, §12.6). A baseline recorded under a different algorithm id is never treated as equal. Known, accepted consequence: while `lastSuccessfulRun`/`updatedAt` are volatile, a SKIP leaves them unrefreshed; execution freshness comes from the Orchestrator's own execution records, not from Brain publication (legacy rows `registry-lastsuccessfulrun`, `registry-updatedat`). There is **no republish heartbeat** (decision G5, §12.10): unchanged domain truth stays `SKIP`.

### 12.3 Publication metadata ownership (F-3)
Publisher-owned: `brains/{id}/publication` and `…/certification` (reserved for every Brain; a specialist `SET`, nested `SET` or `DELETE` is `RESERVED_PATH`; `/brains` or `/brains/{id}` is `BRAIN_NODE_REPLACEMENT`). The record is attached exactly once, inside the final plan, with one `publishId` that is identical in the plan node, the sink record and the history record. It is not specialist semantic truth (never in a fingerprint, never authored). SKIP produces a history-only `SKIPPED_UNCHANGED` record: no plan, no node, no head move.

### 12.4 Explicit delete semantics (F-4)
* Representation: a typed mutation `{"op":"DELETE","path","reason"}`. JSON `null`, an empty container or an absent field never delete (`NULL_VALUE`, `NULL_IN_VALUE`, `EMPTY_VALUE`; absence = nothing happens).
* Authorization: the path must match a `delete_families` entry of the schema (exact-depth, so a delete removes exactly the named child node, never a parent: `/lakes/{k}/states`, `/lakes/{k}`, `/lakeFleet/{k}`, `/brains/wind`, `/brains` are all rejected); the `reason` must be in the schema's closed `delete_reasons` (a schema cannot declare deletes without that vocabulary). Foreign paths → `CROSS_DOMAIN_PATH`; `publication`/`certification` → `RESERVED_PATH`; an undeclared delete on an owned path → `DELETE_NOT_PERMITTED`.
* Wind registrations: registry `lastError` (`OPTIONAL_CHILD_CLEARED`); lake nodes `states profiles validation slots readiness modelVersions` (`LAKE_LEFT_FLEET`, `EVIDENCE_REMOVED`). Nothing else.
* Conflicts: SET and DELETE on the same or overlapping paths anywhere in the artifact, across sections, are `SET_DELETE_CONFLICT`; same-op overlaps are `OVERLAPPING_PATHS`.
* A volatile contract can never hide a DELETE. Deletes are atomic with the other mutations (they are `None` entries of the same single plan; `plan.deletes` lists them; the builder re-asserts that every `None` is an explicit delete).
* Deleting a source of a compatibility projection deletes its derived target in the same plan (§12.5). The next normal artifact will differ from the post-delete baseline once and republish; that is expected.

### 12.5 Compatibility projection ownership (F-5)
A `CompatibilityProjection` is declared on a schema, computed by the Publisher from an accepted source mutation in the same plan, listed separately (`plan.derived_keys`, `record.derived`), owned by the Publisher, and carries a retirement gate. A Brain cannot author a projection target (`PLATFORM_DERIVED_PATH`). Wind: `wind-snapshot-copy-v1` (`/snapshots/{k}/latest/wind` = `/lakes/{k}/states/wind`) and `wind-snapshot-brainversion-v1` (`…/brainVersions/wind` = `/brains/wind/version` when the artifact carries it; never invented). Byte equality with the source is by construction. Limitation: a projection fires with its source section, so a version bump with an unchanged lake state refreshes `brainVersions` on the next state change (the equivalence evaluator would show it).

Legacy path migration table (authoritative machine form: `compat.LEGACY_PATH_TABLE`, tested):
| Legacy path | Current writer | Current reader(s) | Class | Target owner | Target source | Compat needed? | Mechanism | Retirement gate |
|---|---|---|---|---|---|---|---|---|
| `/lakeFleet/{k}/lakeId` | wind-hourly (field open to every Brain) | Ops fleet, Sector Intelligence | PLATFORM_OWNED | Platform Lake Registry | canonical lake directory | no (rows persist; Wind stops writing) | STOP_WRITING | registry publisher owns identity; Wind writer count 0 |
| `/snapshots/{k}/latest/lakeId` | wind-hourly (every Brain) | Ops snapshot row, SI | PLATFORM_OWNED | Platform Lake Registry | canonical lake directory | no | STOP_WRITING | as above; retires with the snapshot row |
| `/snapshots/{k}/latest/wind` | wind-hourly | Ops (row listener), SI (parked) | DERIVED_COMPATIBILITY_PROJECTION | Publisher | `/lakes/{k}/states/wind` | **yes** | PUBLISHER_DERIVED | Wind snapshot migration plan S2-S7 + Michael |
| `/snapshots/{k}/latest/brainVersions/wind` | wind-hourly | snapshot-row consumers (field use unverified) | DERIVED_COMPATIBILITY_PROJECTION | Publisher | `/brains/wind/version` | **yes** | PUBLISHER_DERIVED | with `snapshot-wind` |
| `/health/jobs/wind-hourly` | wind-hourly | Ops | PLATFORM_OWNED | Orchestrator | `/jobs/wind-hourly` + execution ledger | **yes** | ORCHESTRATOR_DERIVED | Ops reads `/jobs`; zero readers; Wind writer 0 |
| `/health/brains/wind/{lastRun,lastSuccess,durationMs,errorCount,latestError,deployedVersion,publishMode}` | wind-hourly | Ops, SI, score publisher | LEGACY_READER_DEPENDENCY | Orchestrator | execution ledger + deploy label | **yes** | ORCHESTRATOR_DERIVED | readers move; Wind stops authoring |
| `/health/brains/wind/{status,staleLakeCount}` | wind-hourly | Ops, SI | WIND_DOMAIN_TRUTH | Wind | Wind's own evidence evaluation | no | WIND_AUTHORED | none |
| `/brains/wind/updatedAt` | wind-hourly | Ops | LEGACY_READER_DEPENDENCY | Publisher (`publication.evaluatedAt`) | publication record | **yes** | WIND_AUTHORED_TRANSITIONAL | Ops reads publication |
| `/brains/wind/lastSuccessfulRun` | wind-hourly | Orchestrator (dependency freshness), Ops, score publisher | LEGACY_READER_DEPENDENCY | Orchestrator | execution ledger | **yes** | WIND_AUTHORED_TRANSITIONAL | Orchestrator uses its own records |
| `/brains/wind/lastError` | wind-hourly | Ops | LEGACY_READER_DEPENDENCY | Orchestrator | execution ledger | **yes** | WIND_AUTHORED_TRANSITIONAL | failures surfaced by the Orchestrator; cleared via explicit DELETE meanwhile |
| `/activity` pruning (deletes) | wind-hourly | Ops (last 50) | PLATFORM_OWNED | Platform maintenance / Orchestrator retention | bounded-ring retention job | no | STOP_WRITING | retention job exists; Wind artifacts never prune |
| `/activity/{event}` containing `-wind-` | wind-hourly | Ops | WIND_DOMAIN_TRUTH | Wind | readiness / version change facts | no | WIND_AUTHORED | none |
`WIND_DOMAIN_TRUTH` is deliberately limited to the two domain rows above (health facts, own events) plus what Wind already owns by contract (states, profiles, validation, fleet slots/readiness/modelVersions, sources, registry domain children): lake identity, job health, process facts and snapshot duplicates are not Wind truth.

### 12.6 Ops health / job representation (F-6)
Target contract: **Brain domain health** (`/health/brains/wind/{status,staleLakeCount}`: what Wind knows about its own evidence) is Wind-authored and child-level; **execution / job / deployment health** (when it ran, how long, errors, deployed label, publish mode, job status) is Orchestrator-owned, derived from its execution ledger and `/jobs`. Current Ops reads both under `/health/…`, so the Orchestrator (not the Publisher, not Wind) owns a temporary compatibility representation (rows `health-jobs-wind-hourly`, `health-brains-wind-process`), written separately from any Brain-authored mutation, until Ops reads `/jobs`/execution state. The Publisher enforces only the negative: Wind cannot author the process fields or `/health/jobs/*`. The equivalence evaluator reports them as `LEGACY_ONLY` (open compatibility rules) so the cutover cannot silently drop them. Nothing was changed in Ops or the live job.

### 12.7 Activity pruning and failure health (F-7)
| Behaviour | Owner (target) | Migration |
|---|---|---|
| append-only domain events (`readiness.changed`, `brain.version`) | Wind (event facts) | stay in the artifact as `/activity/{event}` SETs |
| pruning old events (reads the whole `/activity` node, deletes by age) | Platform maintenance (Orchestrator retention job) | Wind's artifact never prunes; retention job needed before cutover; until then the legacy writer keeps pruning |
| failure-path health writes (`status`, `lastRun`, `latestError` when the lake directory is unavailable) | Orchestrator (execution failure state) | a run that cannot produce an artifact produces none; the Orchestrator's execution ledger records the failure; no Wind failure artifact |
| `lastError` | transitional Wind child → Orchestrator | explicit DELETE clears it after recovery |
Not blindly preserved: none of this moves into Wind's future package.

### 12.8 Wind shadow equivalence evaluation (F-9)
`render_target(artifact, registry)` produces what the Publisher would publish against an empty baseline (DRY_RUN; nothing persisted). `evaluate_equivalence(live_tree, target_updates, registry=…, derived_keys=…)` compares leaf by leaf over the Wind scope (all Wind families, projection targets, legacy table paths, `/brains/wind`, `/health/brains/wind`; other Brains' content is out of scope). Classes: `EXPECTED_MIGRATION_DIFF` (Publisher metadata, explicit delete, retired STOP_WRITING rows, append-only history), `SEMANTIC_MISMATCH` (values differ outside volatile; a unit replacement drops a live key; Wind domain truth missing from the target), `LEGACY_ONLY` (live has it, a compat-needed row says something else must still produce it), `TARGET_ONLY` (new content; derived projections are explained, anything else blocks), `VOLATILE_ONLY`, `UNKNOWN` (live content no family or row accounts for). Verdict `EQUIVALENT_WITH_EXPECTED_DIFFS` only if no `SEMANTIC_MISMATCH`, no `UNKNOWN`, no unexplained `TARGET_ONLY`; `openCompatibilityRules` lists what the platform must still provide at cutover. Output is JSON, sorted, deterministic, contains SHA-256 digests of compared values and never the values. Live data may be fed only from an already-authorised read-only capture kept PRIVATE; public tests use synthetic fixtures. The evaluator itself performs no I/O.

### 12.9 Remaining production security gate
**`PRODUCTION_WRITE_SECURITY_GATE_OPEN`.** Moving a broad production database role from a specialist identity to the Publisher is not acceptable hardening; the Publisher's production identity needs a bounded write model (the per-prefix/per-path model in the foundation security doc). This pass changed no IAM, rules or identities; detail is private. It blocks production cutover, not shadow semantics.

### 12.10 Decisions closed after Gate P (documentation closeout)
* **G5 closed: `NO_REPUBLISH_HEARTBEAT — PLATFORM_EXECUTION_FRESHNESS_SEPARATE`.** The Publisher has no generic heartbeat and never republishes identical domain truth to refresh freshness. Separation: Brain semantic state unchanged → Publisher `SKIP`; Brain/job execution succeeds → Orchestrator/platform execution freshness advances separately (future Orchestrator task, **not implemented here**); semantic state changes → normal publication. `lastSuccessfulRun`/`updatedAt` remain transitional, volatile-excluded Wind children until readers move (legacy table rows `registry-lastsuccessfulrun`, `registry-updatedat`).
* **G1 / G2 retained as future Orchestrator/platform work** (execution/job health representation; dependency and execution freshness from Orchestrator records). They are **not** blockers for Wind Repository Phase 2; they remain blockers/review items for eventual live cutover where a reader still depends on the legacy fields.
* **G6 closed:** the lineage standard now records `SHADOW`, the implemented ordering rule and the algorithm id `sector-semantic-fingerprint-v2` in `docs/architecture/certification/BRAIN_IDENTITY_AND_LINEAGE_V1.md` §7.
* **`PRODUCTION_WRITE_SECURITY_GATE_OPEN` is unchanged.** Production cutover stays blocked until the Publisher has an acceptably bounded production write model; no private detail is recorded in public documents.
