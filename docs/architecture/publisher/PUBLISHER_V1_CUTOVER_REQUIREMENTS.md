# Publisher V1: what must happen before any production use

**Status:** requirements only. Publisher V1 exists in SHADOW mode. The P7/P8 design questions were **closed** in the design-closeout follow-up (below); closing a design question deploys nothing. **Nothing below is authorised or done.** Each item needs its own explicit approval from Michael (`../certification/README.md`: "Approval of these decisions authorizes no implementation by itself"). Public-safe: target shapes only; concrete service-account names, IAM bindings and current-state security findings are kept in the private handoff.

## 0. Gate P status (Wind / Publisher contract hardening)
**`PUBLISHER_GATE_P_SHADOW_READY`** (F-1..F-9 resolved at the shadow-contract level; matrix in architecture §12). **`PRODUCTION_WRITE_SECURITY_GATE_OPEN`**: production cutover remains blocked on a bounded Publisher write model (detail private). Not production deployed; no IAM approved; Wind not cut over; no specialist write removed; no live change; Wind architecture not certified; customer publication not enabled.

### Changes the Wind artifact builder must make to meet the hardened contract (Wind lane, not done here)
1. Emit ONE `publish-artifact-v2` artifact per run (bundle `wind-publication-v1`, sections = the three Wind schemas, lake-state split into scopes if desired) instead of five artifacts. `seal_bundle` builds it; fingerprints use `artifact.section_fingerprint` (schema volatile contract applied).
2. Stop authoring `/snapshots/{k}/latest/wind` and `brainVersions/wind` (Publisher-derived), `/lakeFleet/{k}/lakeId`, `/snapshots/{k}/latest/lakeId`, `/health/jobs/*`, and the health process fields; author only `/health/brains/wind/{status,staleLakeCount}` child-level.
3. Unchanged by this pass and still governed by the Wind certification: the registry `scores` mirror, the freshness inputs and the `lastError` content. For stale optional children use an explicit `DELETE` with a declared reason (never null).
4. Re-run the equivalence evaluator (§12.8) against a PRIVATE read-only live capture and keep the JSON as certification evidence.

### Platform items created by Gate P (not Wind, not Publisher)
| # | Item | Owner | Needed before |
|---|---|---|---|
| G1 | Orchestrator-owned execution/job health representation (compatibility records for `/health/jobs/wind-hourly` and the `/health/brains/wind` process fields, from `/jobs` + execution ledger). **Future Orchestrator/platform work; not a blocker for Wind Repository Phase 2** | Orchestrator | live cutover review item (Ops would otherwise lose them) |
| G2 | Dependency / execution freshness from Orchestrator records instead of forcing a Brain republish (replaces reading `/brains/wind/lastSuccessfulRun`). **Future Orchestrator/platform work; not a blocker for Wind Repository Phase 2** | Orchestrator | live cutover review item; until then a SKIP leaves the transitional child stale |
| G3 | Activity retention job (bounded ring over `/activity`) | Platform maintenance | Wind cutover (Wind artifacts never prune) |
| G4 | Platform Lake Registry publisher for `lakeId` identity fields | Platform | a new lake appears after Wind stops writing them |
| G5 | **CLOSED (Michael): `NO_REPUBLISH_HEARTBEAT — PLATFORM_EXECUTION_FRESHNESS_SEPARATE`.** Unchanged domain truth stays SKIP; execution freshness is advanced separately by the Orchestrator/platform (future task, see G1/G2) | closed | n/a |
| G6 | **CLOSED:** lineage doc §7 records `SHADOW`, the implemented ordering rule and algorithm id `sector-semantic-fingerprint-v2` | closed | n/a |

## 1. Remaining before a production Publisher
| # | Work | Notes |
|---|---|---|
| P1 | Live sink + live mode | A new `LiveSink`/mode in a **separate module** that only the Publisher service imports; the shadow package must keep passing its import lint. Requires a new reviewed change; there is no flag to flip. |
| P2 | Artifact/history bucket adapter | GCS `ObjectStore` implementing the existing contract (`if_generation_match`, generations). **Bucket creation needs approval (CERT-3 approved the design only).** Versioning on; no delete rights for the Publisher identity; lifecycle rules only on classes named in `BRAIN_DATA_CLASSIFICATION_V1` rule 5. |
| P3 | Atomic live update + manifest-last | Send `UpdatePlan.updates` as ONE multi-location update including `brains/{id}/publication`; implement `PARTIAL → COMPLETE` manifest-last for artifacts above `max_bytes` (Wind fleet-scale artifacts). Record `COMPLETE` / `PARTIAL` (the shadow-only status `SHADOW` goes away in live). |
| P4 | Baseline reconciliation (the Gate P equivalence evaluator is the comparison tool; reconcile heads from a PRIVATE live capture) | The shadow baseline is the last `SHADOW_READY`, not live. Before the first live publish per scope, read live (GET only), compute the fingerprint of what is live, seed the head, and diff; the first publish after that must be a *deliberate* change, never an accidental full rewrite. |
| P5 | Rollback execution | `rollback_reference` identifies the previous artifact; add a reviewed, request-driven rollback that republishes it (needs an explicit "rollback" path through the validator, since older artifacts are otherwise rejected). Test end to end (exit evidence G). |
| P6 | Release resolver | Implement `release_resolver` against private release storage so `knowledgeRelease`/`manifestRef`/`manifestSha256` are verified, not just well-formed. |
| P7 | Orchestrator API service | **Design CLOSED:** Orchestrator platform library + small authenticated API service + dedicated Publisher identity (all future; nothing deployed). Remaining (implementation, needs approval): Firebase ID-token verification behind `Authenticator`, the real allowlist (no user identifiers in the public repo), real `Dispatcher` onto `orchestration.evaluate_request` and the review/research queues, request/outcome records written through the Publisher, deployment. Only after the API exists may Ops stop writing control state directly. |
| P8 | Artifact handoff from Brains | **Design CLOSED:** Brain writes create-only to its own `artifacts/{brainId}/` prefix → authenticated `SUBMIT_ARTIFACT` signal carrying a reference (id, location, hash, executionId, expected schema) → Orchestrator → `Publisher.evaluate_reference`. Production RTDB is never a queue; Ops never writes an RTDB request node. Remaining: the GCS adapter (P2), Brain-side adoption of `ArtifactWriter` semantics, IAM per-prefix create-only grants. |
| P9 | Schema registrations | One reviewed registration per Brain schema (Fish, Lake, Water Temp, …). Each Brain's volatile fields (`volatile_extra`), lifecycle policy and freshness requirement are declared there, by that Brain's certification. |
| P10 | Certification record write | `/brains/{id}/certification` is reserved and Publisher/Orchestrator-owned; writing it is a later feature. |
| P11 | Monitoring and cost | Metrics for SKIP rate, rejects by code, plan bytes; confirm no recurring-cost regression (Publisher runs inside the existing hourly Orchestrator wake-up; no new scheduler is required by this design, none was created). |
| P12 | Transactional baseline | Replace sequential per-section head advancement by one transactional baseline index per artifact so a lost race cannot leave a mixed baseline (shadow behaviour documented in architecture §12.11) |

## 2. Wind-specific cutover items (Wind certification)
1. Wind's real output must be re-expressed as `wind-lake-state-v1` / `wind-registry-v1` / `wind-source-registry-v1` artifacts: **the `brains/wind` registry as the approved child nodes** (architecture §4a; whole-node writes are rejected), no nulls/empty containers, UNKNOWN as a value. Known today from reading the writer (not run): the registry object contains `None` values (`lastError`, version `date`) and the writer sets `brains/wind` as one node, so both must change in the Wind artifact builder.
2. Wind's `volatile_extra` and the `/snapshots/{k}/latest/wind` legacy copy (kept in the same atomic publish until its readers move; retirement is the 14-step procedure).
3. Decide the artifact granularity (per lake / per fleet) against `max_bytes` and the 621-lake fleet.
4. Resolve the Wind score identity reconciliation in `BRAIN_IDENTITY_AND_LINEAGE_V1.md` §5.4; the score path `/scores/wind` is Platform-owned and is deliberately **not** a Wind family.
5. Parallel run: Publisher in SHADOW against real `wind-hourly` output (read-only, off the live path) and compare plan vs actually written paths before any cutover. `wind-hourly` direct writes stay until then.

## 3. RTDB rules changes required later (target shape only)
Live rules were **not** inspected or changed; the rules file is not in this repo. The target (`BRAIN_READ_WRITE_SECURITY_V1.md` §5) is:
* `.write` is `false` for every client principal on every domain path (all of `/lakes /lakeFleet /snapshots /brains /validation /health /sources /activity /species /speciesProfiles /scores /control /jobs /engine`); client writes allowed only on a separate per-user preferences node outside domain paths (CERT-7).
* `.read` limited to Ops-visible paths for the allowlisted Ops principals; **no** customer-client read on Brain database paths.
* No rule is relied on to constrain Admin SDK/service identities (rules do not bind them); see §4.
Each change is applied one tested step at a time, with Ops regression checks, only after the Ops write calls are removed (P7).

## 4. IAM / service identity changes required later
Described **privately** (in the private handoff folder, not in this repository), per CERT-9. Public summary of the target only: specialist identities hold no database write capability; only the Publisher identity holds database write; Ops has none; Brain identities cannot reach customer app databases; the Publisher identity has no delete on the history bucket; local development runs default to dry-run. Verified per Brain against the identity actually used, never assumed.

## 5. Resources still needing Michael's approval (none created)
GCS artifact/history bucket (CERT-3) · research-backup bucket (CERT-4; separate task, not Publisher) · Publisher/API Cloud Run service · Publisher service account and any IAM binding · RTDB rules deploy · any Scheduler entry · secrets · customer-facing changes.

## 6. Can Wind proceed to cutover testing?
**Publisher shadow integration: YES (contract stable, tested).** **Cutover: NOT YET.** Wind may proceed with its certification work that does not need a live Publisher: inventory, canonical truth, artifact contract (step 7), and **shadow-mode** publication tests (step 8 in shadow) against `ShadowPublisher` using real `wind-hourly` output read-only. Exit evidence F (security) and G (live atomic publish, rollback end to end) cannot pass until P1-P5 and the security work in §3-4 exist and are approved; Wind stays `PARTIAL`/`BLOCKED` on those items. Current direct writers (`wind-hourly` and all other Brains) are unchanged.

## 7. Unresolved decisions / risks
* **Decided (Michael):** `SHADOW` status kept; `ARTIFACT_OLDER_THAN_BASELINE` kept (exact rule in architecture §5, fail closed); `/brains/{id}` child-level ownership with Publisher-owned `publication`; handoff by authenticated reference; no arbitrary write API. Still to be reflected in the lineage doc: `SHADOW` as a record status and the ordering rule (documentation follow-up in `../certification/`, not done here).
* Additions of mine inside the locked decisions, for confirmation: `BASELINE_ORDER_UNKNOWN` and `ARTIFACT_FROM_FUTURE` (5 min skew) ordering codes; per-Brain API grants (`SUBMIT_ARTIFACT@wind`); the initial list of approved `/brains/wind` children (taken from the fields `wind-hourly` writes today).
* The decision to reject (not coerce) nested nulls and empty containers is stricter than today's writers; the Wind and other Brain writers will need changes to comply.
* Manifest-last chunking is unimplemented; an oversize artifact is simply rejected.
* **Requires Michael's approval before any live cutover** (none given): the bucket, the Publisher/API service and identity, every IAM change, rules deploy, Wind's writer change, enabling any non-shadow mode, and removing any direct writer.
