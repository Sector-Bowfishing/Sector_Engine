# Wind Brain: live cutover plan (PREPARED, NOT EXECUTED)

> **Update (Publisher V2):** step 4 now produces ONE `publish-artifact-v2` bundle per run (not five artifacts). Step 6's parallel run is what supplies the time-aligned equivalence; the real-state structural equivalence is already `EQUIVALENT_WITH_EXPECTED_DIFFS` (`WIND_PUBLISHER_V2_ADOPTION_REPORT.md` §8). Added gates before step 8: Orchestrator execution/job health compatibility (13 `LEGACY_ONLY` rows) and the Orchestrator reading its own execution records instead of `/brains/wind/lastSuccessfulRun`. Production write security (`PRODUCTION_WRITE_SECURITY_GATE_OPEN`) and Publisher P1-P12 still gate steps 3 and 9.

Each live step needs Michael's explicit approval. **This session performed none of them.** Exact identities, bindings and commands are private (IAM delta in the private handoff). Public version states targets and gates only.

| # | Step | Prerequisite / approval | Evidence required | Rollback |
|--:|---|---|---|---|
| 1 | **Protect and back up** Wind research/history (preservation plan): research-backup bucket, `sector-wind-candidate` versioning/copy, collector decision, verified hashes | Michael: bucket creation, collector decision | remote hashes = recorded hashes; manifest backups[] filled | delete only the new copies (never sources) |
| 2 | **Approve/create artifact + history storage** (CERT-3 bucket, versioned, no-delete for the Publisher identity) | Michael: resource creation | create-only grant to the Wind prefix proven by an attempted overwrite failing | none needed (empty) |
| 3 | **Approve/deploy the Publisher service and identity** (Publisher V1 production mode is a separate reviewed change P1-P11; it does not exist) | Michael; Publisher lane | Publisher deployed in SHADOW-only first | undeploy; no Wind change yet |
| 4 | **Wind produces artifacts for real** in parallel with its direct writer: `wind-hourly` writes the 5 artifacts to its own artifact prefix after the existing publish (additive, `publish()` never raises, no exit-code change), signals the Orchestrator | Michael: Wind job change + deploy; builder wired; F-1..F-8 resolved or accepted | artifacts appear hourly; hash verified | revert the job image to `e6a5026f5d0f` (digest recorded privately) |
| 5 | **Publisher evaluates the real artifacts in deployed SHADOW** | deployed shadow Publisher | records in history, `SHADOW_READY`/`SKIP` rates sane | stop signalling |
| 6 | **Compare the Publisher shadow plan with Wind's actual live output**, hourly for ≥ 7 days: for each path, plan value vs value stored by `wind-hourly` in the same run (modulo the 4 reported unauthorised paths, RTDB null/empty normalisation, and the two scalar volatile children) | step 5 | zero unexplained diffs; intentional diffs listed (scope split, no `lakeId`, no `health/jobs`, no `brainVersions`) | n/a (read-only) |
| 7 | **Approve Wind cutover** | Michael, with F-1..F-8 decisions, Ops owner informed | signed-off diff report | — |
| 8 | **Wind producer becomes artifact-only**: remove the direct `publish()` writer from the job (the artifact path stays); `last_publish.json` retired in favour of the Publisher's publication record; reconcile the Publisher baseline against live (P4) first | step 7 | first live publish is a deliberate change, not a full rewrite | redeploy prior image; the old direct writer returns (its write grant is still in place until step 13) |
| 9 | **Publisher becomes the production writer for Wind** (live mode, atomic, history) | Publisher production mode approved | one atomic plan per artifact (or group) applied; publication record `COMPLETE` | republish previous artifact from history (explicit rollback, P5); or step 8 rollback |
| 10 | **Verify live output**: field-level equality of the Wind paths vs the pre-cutover export; `lastSuccessfulRun`, freshness fields, readiness counts; no unexpected writes | step 9 | export diff = intentional only | as 9 |
| 11 | **Verify Ops and dependents**: Ops Wind views, fleet, Brain page, jobs/health cards (F-6), score tile (3.3 unchanged), Sector Intelligence snapshot read; customer `/conditions` output diff = none | step 9 | screenshots/diffs; `/conditions` before/after identical | feature switches; step 9 rollback |
| 12 | **Preserve rollback**: previous image digest, last pre-cutover export, last N artifacts, Publisher history retained | — | rollback exercised once end to end in a non-production rehearsal first | — |
| 13 | **ONLY THEN remove the Wind specialist's direct production DB write capability** (IAM change; replace with read-only + create-only artifact grants) | steps 8-12 complete and stable; Michael | — | restore the previous binding (recorded privately) |
| 14 | **Verify the specialist cannot write `sector-brain`** (attempted write by the Wind identity is denied; attempted cross-domain write by the Publisher is rejected; Ops write denied) | step 13 | tested denials (pass/fail public; detail private) | — |
| 15 | **Certify Wind**: exit evidence A-J complete, Michael reviews, record `ARCHITECTURE_CERTIFIED_V1` | all above | evidence pack | — |

## Exit-evidence mapping
A done · B after step 1 · C after step 1 + hash verification of the bucket manifests · D, E done · F steps 13-14 · G steps 5-9 + rollback rehearsal · H score BEFORE 3.3 / AFTER same type, version, scope (see score reconciliation) · I step 11 · J step 15.

## Non-negotiables during cutover
No score change; no customer behaviour change; `wind-hourly` schedule/ENABLED state untouched except by an explicit approved step; H2 stays sealed; no direct production write is restored as a final design; steps 13-14 happen strictly last.
