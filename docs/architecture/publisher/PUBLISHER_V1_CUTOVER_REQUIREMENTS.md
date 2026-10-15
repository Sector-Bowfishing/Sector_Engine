# Publisher V1: what must happen before any production use

**Status:** requirements only. Publisher V1 exists in SHADOW mode. **Nothing below is authorised or done.** Each item needs its own explicit approval from Michael (`../certification/README.md`: "Approval of these decisions authorizes no implementation by itself"). Public-safe: target shapes only; concrete service-account names, IAM bindings and current-state security findings are kept in the private handoff.

## 1. Remaining before a production Publisher
| # | Work | Notes |
|---|---|---|
| P1 | Live sink + live mode | A new `LiveSink`/mode in a **separate module** that only the Publisher service imports; the shadow package must keep passing its import lint. Requires a new reviewed change; there is no flag to flip. |
| P2 | Artifact/history bucket adapter | GCS `ObjectStore` implementing the existing contract (`if_generation_match`, generations). **Bucket creation needs approval (CERT-3 approved the design only).** Versioning on; no delete rights for the Publisher identity; lifecycle rules only on classes named in `BRAIN_DATA_CLASSIFICATION_V1` rule 5. |
| P3 | Atomic live update + manifest-last | Send `UpdatePlan.updates` as ONE multi-location update including `brains/{id}/publication`; implement `PARTIAL → COMPLETE` manifest-last for artifacts above `max_bytes` (Wind fleet-scale artifacts). Record `COMPLETE` / `PARTIAL` (the shadow-only status `SHADOW` goes away in live). |
| P4 | Baseline reconciliation | The shadow baseline is the last `SHADOW_READY`, not live. Before the first live publish per scope, read live (GET only), compute the fingerprint of what is live, seed the head, and diff; the first publish after that must be a *deliberate* change, never an accidental full rewrite. |
| P5 | Rollback execution | `rollback_reference` identifies the previous artifact; add a reviewed, request-driven rollback that republishes it (needs an explicit "rollback" path through the validator, since older artifacts are otherwise rejected). Test end to end (exit evidence G). |
| P6 | Release resolver | Implement `release_resolver` against private release storage so `knowledgeRelease`/`manifestRef`/`manifestSha256` are verified, not just well-formed. |
| P7 | Orchestrator API service | Deployable authenticated service: Firebase ID-token verification (`Authenticator`), the allowlist (no user identifiers in the public repo), a real `Dispatcher` onto `orchestration.evaluate_request` and the Brains' review/research queues, request/outcome records written through the Publisher. Only after the API exists may Ops stop writing control state directly. |
| P8 | Artifact handoff from Brains | Brains write `artifacts/{brainId}/{artifactId}.json` (own prefix, `ifGenerationMatch=0`) and signal completion; the Publisher uses `evaluate_stored`. Decide the signal channel (Orchestrator execution record vs API publish request). |
| P9 | Schema registrations | One reviewed registration per Brain schema (Fish, Lake, Water Temp, …). Each Brain's volatile fields (`volatile_extra`), lifecycle policy and freshness requirement are declared there, by that Brain's certification. |
| P10 | Certification record write | `/brains/{id}/certification` is reserved and Publisher/Orchestrator-owned; writing it is a later feature. |
| P11 | Monitoring and cost | Metrics for SKIP rate, rejects by code, plan bytes; confirm no recurring-cost regression (Publisher runs inside the existing hourly Orchestrator wake-up; no new scheduler is required by this design, none was created). |

## 2. Wind-specific cutover items (Wind certification)
1. Wind's real output must be re-expressed as `wind-lake-state-v1` / `wind-registry-v1` / `wind-source-registry-v1` artifacts: **the `brains/wind` registry as child nodes** (see architecture §10.1), no nulls/empty containers (existing Wind writer behaviour must be audited for null-on-miss), UNKNOWN as a value.
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
Described **privately** (`~/Desktop/Sector Handoffs/…`), per CERT-9. Public summary of the target only: specialist identities hold no database write capability; only the Publisher identity holds database write; Ops has none; Brain identities cannot reach customer app databases; the Publisher identity has no delete on the history bucket; local development runs default to dry-run. Verified per Brain against the identity actually used, never assumed.

## 5. Resources still needing Michael's approval (none created)
GCS artifact/history bucket (CERT-3) · research-backup bucket (CERT-4; separate task, not Publisher) · Publisher/API Cloud Run service · Publisher service account and any IAM binding · RTDB rules deploy · any Scheduler entry · secrets · customer-facing changes.

## 6. Can Wind proceed to cutover testing?
**Not to cutover.** Wind may proceed with its certification work that does not need a live Publisher: inventory, canonical truth, artifact contract (step 7), and **shadow-mode** publication tests (step 8 in shadow) against `ShadowPublisher` using real `wind-hourly` output read-only. Exit evidence F (security) and G (live atomic publish, rollback end to end) cannot pass until P1-P5 and the security work in §3-4 exist and are approved; Wind stays `PARTIAL`/`BLOCKED` on those items. Current direct writers (`wind-hourly` and all other Brains) are unchanged.

## 7. Unresolved decisions / risks
* Artifact handoff signal (P8) and API deployment shape (P7) are open design choices inside CERT-1.
* `SHADOW` as a record status is an addition to the lineage doc's status set; confirm or rename.
* The `ARTIFACT_OLDER_THAN_BASELINE` rule is a Publisher-side safety addition (not in the foundation docs); keep or drop at P5.
* The decision to reject (not coerce) nested nulls and empty containers is stricter than today's writers; the Wind and other Brain writers will need changes to comply.
* Manifest-last chunking is unimplemented; an oversize artifact is simply rejected.
