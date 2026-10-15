# Publisher V1: shadow architecture

**Status:** implemented in SHADOW ONLY mode on branch `feat/publisher-v1-shadow` (local; not pushed). **Success state: `PUBLISHER_V1_SHADOW_READY`.** This is *not* `PRODUCTION_PUBLISHER_DEPLOYED`, `WIND_CUT_OVER` or `SPECIALIST_WRITERS_DISABLED`.
**Implements:** CERT-1 (Publisher is a platform library in the Orchestrator platform; small authenticated API shares its identity) and CERT-2 (separate shadow-only task) from `../certification/README.md`. Standards followed: `BRAIN_IDENTITY_AND_LINEAGE_V1.md`, `BRAIN_READ_WRITE_SECURITY_V1.md` §2-4, `BRAIN_PATH_OWNERSHIP_V1.md`.
**Code:** `jobs/brain_platform/sector_brain_platform/publisher/` (stdlib-only; not imported by `sector_brain_platform/__init__.py`, so no production job loads it). **Tests:** `jobs/brain_platform/tests/test_publisher_*.py`.

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
| `api.py` | Orchestrator API contract + shadow handler (CONTROL / REVIEW / RESEARCH) |
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
* `/brains/{id}/publication` and `/brains/{id}/certification` (and `/brains`, `/brains/{id}`, whose whole-node SET would erase them) are **reserved** for the Publisher/Orchestrator and rejected `RESERVED_PATH` for every artifact.
* A rejected path is classified `CROSS_DOMAIN_PATH` when another owner legitimately owns it (species identity/policy, another Brain's slot/registry/score, platform roots; uses the live `ownership.path_allowed` table plus protected roots), else `PATH_NOT_AUTHORIZED`.
* **Wind** (`registry.wind_specs()`), three schemas so no schema is broader than its job:

| Schema | Families |
|---|---|
| `wind-lake-state-v1` (freshness required) | `/lakes/{k}/states/wind`, `/lakes/{k}/profiles/wind`, `/lakes/{k}/validation/wind`, `/lakeFleet/{k}/{slots,readiness,modelVersions}/wind` (DERIVED_PROJECTION), `/snapshots/{k}/latest/wind` (LEGACY_READER_PRESENT; same atomic publish) |
| `wind-registry-v1` | `/brains/wind/{child}` (child ≠ publication/certification), `/validation/wind`, `/health/brains/wind`, `/activity/{event}` (own events only) |
| `wind-source-registry-v1` | `/sources/{id}`, `/health/sources/{id}` for sources whose acquisition owner is `wind` (derived from `ownership.SOURCE_OWNERS`) |

  Lifecycles Wind artifacts may carry: RESEARCH, PROFILED, SHADOW, CALIBRATION. `PRODUCTION*` needs both schema permission and an `approvalRef`; Wind has neither. A test asserts every Wind family is also allowed by the existing writer-side `ownership.path_allowed`.
* Every other Brain id is registered as an identity with **no schema**: their artifacts reject `UNKNOWN_SCHEMA` until their own certification registers one.

## 5. Fingerprints and SKIP
`outputFingerprint = sha256(canonical JSON of {brainId, artifactSchema, mutations sorted by path})` with volatile keys removed at any depth (shared default `generatedAt publishedAt checkedAt ageHours durationMs` + `SchemaSpec.volatile_extra`) and floats rounded to 9 places (the platform's existing noise tolerance). The Publisher recomputes it and rejects `FINGERPRINT_MISMATCH` if it differs from the declared value; Brain-supplied fingerprints are never trusted. The scope's baseline is the history head pointer (§8). Equal → `SKIP`: no plan, no sink call; only a history record. Not-newer `generatedAt` with different content → `REJECTED ARTIFACT_OLDER_THAN_BASELINE` (an old artifact is replayed only by an explicit rollback, which is a later feature).

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
* **Record**: `publishId, previousPublishId, brainId, artifactId, executionId, artifactSchema, scope, result, status, evaluatedAt, publisher, mode, trigger, requestId, knowledgeRelease, codeVersion, input/outputFingerprint, generatedAt, lifecycle, reviewStatus, validationStatus, paths{count,bytes}, pathSha256{}, artifactPatchSha256, updateSha256, removed[]`, plus `violations[]` on rejections. `status` is `SHADOW | SKIPPED_UNCHANGED | REJECTED` (the lineage doc's `COMPLETE`/`PARTIAL` are reserved for live publication; `SHADOW` is the one addition and is shadow-only).
* **History layout** (CERT-3, documented, **no bucket exists**):
  `artifacts/{brainId}/{artifactId}.json` immutable · `publishes/{brainId}/{publishId}.json` immutable · `publishes/{brainId}/_heads/{artifactSchema}/{scope}.json` versioned head pointer (optimistic concurrency) · `scores/`, `exports/` reserved.
  `ObjectStore` mirrors GCS generations (`if_generation_match=0` create-only). Shipped: `MemoryObjectStore`, `LocalDirObjectStore`. Not shipped: any GCS adapter.
* **Rollback metadata**: `PublishHistory.rollback_reference(brain, publishId)` → previous baseline `publishId`, its immutable `artifactId`/key and fingerprint (`None` for a first publication). Executing a rollback is out of scope for V1.
* SKIP and REJECTED are recorded in history only; a rejected artifact is stored with its record under `rejected-{publishId}`.

## 9. Orchestrator API contract (`api.py`)
`authenticate → coarse allowlist → request schema → fine authorization (caller, kind, action) → Orchestrator workflow`. Request: `apiVersion, requestId (UUIDv4), requestKind, brainId, action, params, [confirm]`, nothing else (unknown fields rejected). `CONTROL`: `RUN_NOW(scope) PAUSE RESUME SET_MANUAL` + protected `CHANGE_PROTECTED_SCHEDULE DISABLE_VALIDATION_CAPTURE` (exact confirm phrase by the same caller). `REVIEW`: `SUBMIT_REVIEW ACCEPT_RULE REJECT_RULE`. `RESEARCH`: `RESEARCH_GAP`. `SET_ENGINE_MODE ACTIVATE_PRODUCTION PUBLISH_CUSTOMER PROMOTE_LIFECYCLE` are never grantable (rejected before authorization; an allowlist cannot even be constructed with them). Params are closed per action, scalar only (str/int), length-bounded, pattern/enum-checked. **No field carries a path, value, update map or mutation, and the handler holds no database client**: it can only pass a validated `ApiRequest` to an injected `Dispatcher`. No Firebase token verification or HTTP server exists yet; `Authenticator` is a protocol.

## 10. Architecture notes found while implementing (refinements, not conflicts)
1. **Whole-node `/brains/{id}` SET conflicts with the Publisher-owned `publication`/`certification` children.** Wind today writes the registry as one `brains/wind` object. In the target, the Wind registry artifact is published as child nodes (`/brains/wind/{child}`); stale children must then be removed by an explicit permitted DELETE.
2. RTDB's null/empty semantics make "UNKNOWN as null" unsafe; artifacts must encode UNKNOWN as a value (already the lineage standard).
3. Oversize artifacts (> `SchemaSpec.max_bytes`, default 8 MiB) are rejected. Manifest-last chunking (security doc §3.7) is **not** in V1; fleet-wide Wind artifacts may need it or per-lake scoping.
4. Wind-specific volatile fields beyond the shared default must be listed by the Wind certification (`volatile_extra`) or they will cause needless `SHADOW_READY` results.
5. The shadow baseline is the last `SHADOW_READY` record, not live state. The first live publish after cutover must reconcile it (see the cutover requirements).
6. Not verified, deliberately: any live system (RTDB rules, IAM, schedulers, buckets). Nothing live was read or changed.
