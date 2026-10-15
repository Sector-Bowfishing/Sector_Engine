# Wind Certification Entry Checklist (Brain Certification #1)

For the next session: **WIND BRAIN — ARCHITECTURE CERTIFICATION V1**. Start only after Michael approves the foundation (`BRAIN_CERTIFICATION_V1.md`). Complete §A–§L **read-only** before proposing any change. Record results in `docs/architecture/certification/records/wind.md` (public-safe). Security evidence goes in the private Wind handoff folder (`Sector Handoffs/Sector Engine/Wind Brain/`).

## 0. Session entry gates
- [x] Foundation approved by Michael on 2026-10-14, with CERT-1 to CERT-9 (see `README.md`). Cite this in the record.
- [ ] `git fetch`; identify the newest safe shared lineage (currently `feat/brain-platform-model-v1` or successor). Confirm it contains the deployed orchestrator commit and the Wind durability commit (`f7b6b066`). Create the certification branch from it. Specialist work is **additive only**: no edits to shared platform files without a platform-lane decision.
- [ ] Read the newest Wind handoff in `Sector Handoffs/Sector Engine/Wind Brain/` and the Wind decision queue (D7–D9).

## A. Baseline freeze (step 1)
- [ ] `brainId = wind`, display name, lifecycle (registry: CALIBRATION/shadow candidate), `customerPublication` (expected false).
- [ ] Fleet distribution from live data: expected ≈ 547 DISCOVERED / 70 PROFILED / 4 CALIBRATION; 74 profiles; 4 lake states; 4 lake-local validation records; 4 snapshot copies.
- [ ] Customer exposure: confirm that customer `/conditions` wind uses its own provider/path (Open-Meteo in-process) and does **not** read Wind Brain state. This boundary must survive certification unchanged.
- [ ] Validation status (`/validation/wind`, field acceptance evaluator state, 30-day reliability gate).

## B. Score baseline (step 1 / exit H)
- [ ] Record every Wind score-like value with its location: `/scores/wind` (≈ 3.3), other Wind metadata (≈ 3.1), BWIS 5.4, `/brains/wind.scores`, `/validation/wind` scores, `frozen-scores.json` entry, `check_score_artifacts.py` result.
- [ ] Assign each a `scoreType` (`ENGINE_READINESS_SCORE` / `BWIS` / …) and identify the single authoritative `ENGINE_READINESS_SCORE` and its `scoreVersion`. **Do not change any value.** The 3.3 vs 3.1 difference is explained, not "fixed" by picking one.
- [ ] Capture BEFORE with the scoring definition/version used; AFTER must use the same.

## C. Local research inventory (step 2)
Search the whole development root, then compare with the new workspace:
- [ ] `/Users/mcather/Desktop/Development/Sector Research/wind-brain` (canonical LOCAL Wind workspace going forward; **empty** at 2026-10-14).
- [ ] `/Users/mcather/Desktop/Development/Sector Research/shared` (empty at 2026-10-14). Note anything Wind-owned that should live there (e.g. provider docs), but do not move yet.
- [ ] `Development/Sector_Research_Data/wind-brain` (≈ 52 MB: `cycles/`, `live-meta/`, `live-meta-mirror/`, `out/`, `registry/`, pickled row sets, ATL13 raw manifest).
- [ ] Engine worktrees: `Sector_Engine-wind`, `Sector_Engine-wind-adoption`, `Sector_Engine-wind-research`, `Sector_Engine-wind-deploy` (untracked/ignored artifacts included).
- [ ] Engine branches: `docs/wind-brain-research`, `feat/wind-brain-adoption` (`c6f6232e`), `deploy/wind-internal-validation` (`413bbbae`), `brain/wind`, `feat/orchestrator-wind-score-durability`, `intelligence/wind`; repo dirs `research/wind-brain`, `jobs/wind-hourly/research`, `jobs/wind-hourly/sector_wind`.
- [ ] iOS: `iOS/sector-wind` (`scripts/wind/build_fetch_tables.py` fetch-table generator, `tools/wind-candidate-tests`), `iOS/sector-wind-prodfix`, `WindSurfacePhysics.swift` (Swift mirror of Wind physics).
- [ ] Ops: `Sector_Ops/src/components/windBrain.tsx` (consumer, not research).
- [ ] Handoffs mentioning Wind; any Wind PDFs/provider docs anywhere under `Development/`.
- [ ] For every artifact: classification, owner, used-by, canonical?, duplicate-of, rebuildable?, backup location, licence, proposed action (`BRAIN_DATA_CLASSIFICATION_V1.md`). Byte, dataset, source and release counts.

## D. Remote storage (step 3, read-only)
- [ ] `gs://sector-wind-candidate/wind/v1/*` (≈ 50 MB): structure, versioning, lifecycle, what is CANONICAL vs DERIVED vs HISTORY.
- [ ] `brain/wind/last_publish.json` (Wind's private publish memory): document it as a **second source of truth** to be replaced by the Publisher's publication record.
- [ ] Fetch-table geometry copied to GCS from the iOS generator: owner (Lake Registry geometry vs Wind derived), provenance, versioning.
- [ ] Artifact Registry images referenced by the Wind rollback package (`deploy/wind-internal-validation`); confirm they are retained.
- [ ] Verify hashes/manifests where they exist; note where none exist.

## E. RTDB paths (step 4)
For each path, record owner, writer, readers, classification, canonical/duplicate/legacy, lifecycle, action:
- [ ] `/brains/wind` (registry; carries `scores{}`: a score duplicate)
- [ ] `/lakes/{k}/states/wind`, `/lakes/{k}/profiles/wind`, `/lakes/{k}/validation/wind`
- [ ] `/lakeFleet/{k}/slots/wind`, `readiness/wind`, `modelVersions/wind` (all 621 rows)
- [ ] `/snapshots/{k}/latest/wind` (**duplicate**; consumers still declare `/snapshots`; status expected `LEGACY_READER_PRESENT`)
- [ ] `/validation/wind`, `/health/brains/wind`, `/health/jobs/wind-hourly` vs `/jobs/wind-hourly`
- [ ] `/sources/{noaa-nbm-v5, noaa-rtma-ru, iem-metar-wind}` and `/health/sources/*`: set `acquisitionOwnerBrainId = wind`, list authorized consumers
- [ ] `/scores/wind`, `/control/fleet/{k}` and `/control/overview` Wind projections
- [ ] Wind `/activity` events and pruning
- [ ] Known defects to confirm in code: `validation/wind` is deleted when evidence lookup misses (null-on-miss); state and fleet slot are written in **separate** PATCHes (≥ 6 per run; partial-publish risk)

## F. Code trace (step 5)
- [ ] Writers: `jobs/wind-hourly/main.py`, `sector_wind/brain/publish.py`, `writer.py`, `__main__.py` (CLI `publish --rtdb`), the GCS store (`store.py`). Gates: env var `SECTOR_WIND_BRAIN_RTDB_URL`, `--rtdb`/`--dry-run`, `SECTOR_WIND_GCS_APPROVED`.
- [ ] Readers of Wind output: Ops (`windBrain.tsx`, BrainPage, fleet, diagnostics), Sector Intelligence (dependency registry + snapshot), score publisher, orchestrator, `research/run_cycle.py` (GET `/scores/wind`).
- [ ] Scheduler: **`wind-hourly` (`5 * * * *` UTC) is ENABLED** and is the only hourly production writer. Do **not** pause or resume it without approval. Record the deploy script, image, labels (the build label hard-codes `main@`; note it), and the credential identity **class** used.
- [ ] Wind branch edits to shared platform files (e.g. `jobs/brain_platform/tests/test_scoring.py`): list them as lineage issues.
- [ ] Do not trust `/jobs` declarations; confirm every declared path against code.

## G. Canonical truth (step 6)
- [ ] What is Wind's CANONICAL release? (Model v1 code + config + candidate store contents?) Decide `knowledgeRelease` format (e.g. `wind-model-v1@<commit>`) and where its manifest lives.
- [ ] Which Wind data is irreplaceable (field observations, acceptance evidence, reliability-gate history)? Confirm a private versioned backup exists; if not, that is a **blocker for exit B**.

## H. Publish artifact contract (step 7, design only until approved)
- [ ] Artifact schema(s): per-lake state/profile/validation, fleet slot projection, registry, validation summary, sources.
- [ ] Lineage block, volatile-field list, `outputFingerprint` definition, material-change semantics (hourly provider data: what counts as material?).
- [ ] Authorized path families (`BRAIN_PATH_OWNERSHIP_V1.md` §1, `wind` row).

## I. Publisher migration plan (step 8; Wind is the first Brain, so the Publisher may not exist yet)
- [ ] Per **CERT-2 (approved)**, Publisher V1 is a **separate shadow-only platform task**, not part of this session. Wind runs steps 1–7 (read-only inventory through artifact-contract design). Until Publisher V1 exists, the best possible Wind status is `PARTIAL` or `BLOCKED: publisher`.
- [ ] Shadow plan: Wind produces artifacts; the Publisher runs in dry-run and diffs against what `wind-hourly` actually wrote; zero diff required before cutover.
- [ ] Cutover plan: one atomic publish per run; `/snapshots/{k}/latest/wind` still written in the same atomic publish while readers remain; `wind-hourly`'s direct write is removed only after the Publisher path is proven; a rollback package exists.

## J. Security / IAM (step 9; findings private)
- [ ] The identity actually used by `wind-hourly` and by local Wind CLIs; its database capabilities (rules **and** IAM, Admin SDK/REST).
- [ ] Target: Wind identity has no production `sector-brain` write; it can write only its artifact prefix and its private storage. The Publisher identity can write the Wind path families. A cross-domain write from Wind is denied. Ops cannot write Wind paths.
- [ ] Record evidence privately; record pass/fail publicly.

## K. Downstream and Ops consumers (steps 10–11)
- [ ] Ops Wind views and fleet views: list the exact listeners and grains; the reader migration plan for any legacy path.
- [ ] Sector Intelligence: does it read Wind via `/snapshots` or via `/lakes/{k}/states/wind`? Migration order.
- [ ] Score publisher and orchestrator dependency on Wind fields (`usesFields`, fingerprint ingredients).
- [ ] Customer path: demonstrate that `/conditions` output is unchanged (diff before/after).

## L. Rollback (exit G)
- [ ] Existing: `deploy/wind-internal-validation` @ `413bbbae` (exact command, prior image digest), never exercised.
- [ ] Target: restore the prior Publisher-published Wind artifact from history; redeploy the prior Wind image; verify the output fingerprint.
- [ ] Rollback is exercised in shadow before any cutover.

## M. Stop conditions (stop and return to Michael if any occurs)
- Any step would change a score value, customer behaviour, or a scheduler state without explicit approval.
- Irreplaceable Wind data has no private versioned backup and creating one needs approval.
- The Publisher does not exist and building it is not approved for this session.
- A required change touches shared platform files on a non-shared lineage.
- A security finding needs an IAM or rules change (record privately; do not change live).
- Unexpected writers or readers of Wind paths are found (untraced writer = automatic `BLOCKED`).
- The shared standard turns out to be wrong for Wind: stop and propose a standard revision (`FAILED` / `ADJUST`).

## N. Exit
Produce exit evidence A–J (`BRAIN_CERTIFICATION_V1.md` §6) and a status. **Do not begin Fish certification in the same session.**
