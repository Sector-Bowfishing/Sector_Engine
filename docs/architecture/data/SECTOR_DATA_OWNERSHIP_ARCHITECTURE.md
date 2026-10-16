# Sector Data Ownership, Storage & Publishing Architecture (v1)

> **Superseded in part by Brain Certification V1 (`docs/architecture/certification/`, 2026-10-14).** Where they differ, Certification V1 wins:
> (1) the **Orchestrator Publisher is the only steady-state writer** to `sector-brain`; specialist Brains produce artifacts and do not write production (this document had Brains publishing through a shared `publish()` with their own identity);
> (2) **Ops sends requests through an authenticated Engine/Orchestrator API**, not by creating `/requests/*` nodes in RTDB;
> (3) **species identity is owned by the Species Registry (Engine Platform)**, not by the Fish Brain (`biological-state`); Fish Brain owns species intelligence;
> (4) **no path changes** (including `/speciesProfiles`) are approved by this document; they are decided per Brain during certification.
> In the target-schema and source-of-truth tables, "writer" means the **producing Brain**; the physical writer is the Publisher.


**Status:** PROPOSED — for Michael's review. 2026-10-14. Branch `feat/data-ownership-architecture-v1` (from `feat/brain-platform-model-v1` @ `f6cec529`). **Documentation only — no runtime code, live data, rules or deployments changed.**
**Builds on (does not replace):** `docs/brains/OWNERSHIP_MATRIX.md` (science ownership), `BRAIN_PLATFORM_CONTRACT.md` (RTDB envelopes), `platform/SECTOR_BRAIN_MODEL_V1.md` (claims, lifecycle, execution, scores), `OPS_CONTROL_PLANE_CONTRACT.md`. Those say *who owns which science*; this says *where each piece of data lives, who may write it, how it becomes production and how it is versioned and rolled back*.

Companion documents (same folder): `CURRENT_DATA_INVENTORY.md` · `RTDB_PATH_OWNERSHIP_MATRIX.md` (+`.json`) · `SOURCE_OF_TRUTH_MATRIX.md` (+`.json`) · `BRAIN_DATA_CONTRACT_V1.md` · `PUBLISHING_AND_PROMOTION_MODEL.md` · `TARGET_SECTOR_BRAIN_SCHEMA.md` (+`.json`) · `RESEARCH_AND_EVIDENCE_STORAGE.md` · `ENVIRONMENT_AND_SPECIES_CLASSIFICATION.md` · `DATA_RETENTION_AND_ROLLBACK.md` · `DATA_MIGRATION_PLAN.md` · `DATA_ARCHITECTURE_DECISION_QUEUE.md`.

---

## 1. The architecture in one page

```
 RESEARCH / EVIDENCE            CANONICAL KNOWLEDGE              RUNTIME SERVING                 CONSUMERS
 (private, versioned)           (immutable releases)             (sector-brain RTDB)
 ───────────────────            ────────────────────             ───────────────────             ─────────
 Sector_Research (private git)  gs://<brain bucket>/             /species  /speciesProfiles      Sector Ops (read)
 gs://sector-research-private     latest.json ──► releases/{v}/  /lakes/{k}/states|profiles      Intelligence
   raw sources, packets,            manifest.json (sha256 pins)  /lakeFleet  /brains /scores     downstream Brains
   cards, candidates,          ▲   review_ledger.jsonl           /validation (summaries)         Engine API → apps
   rejected claims             │   rules, registry, sources                 ▲
            │                  │                                            │
            └── adoption ──────┘── release (Michael-approved) ── deterministic build ── publish (fingerprint, manifest-last)
                                                                            │
 OBSERVATION / VALIDATION (append-only buckets: field obs, prediction ledgers) ──► validators ──► /validation summaries
 CONTROL PLANE (sector-brain /control /jobs /requests /health /activity) — Orchestrator decides WHEN and WHO
 HISTORY (gs://sector-brain-history: every publish manifest + score history, append-only, tiny)
```

**The rules, stated once:**
1. **One owner, one canonical home per data type** (`SOURCE_OF_TRUTH_MATRIX.md`).
2. **The plane *is* the state.** Research lives in the research store; knowledge becomes canonical only by being in a released, hash-pinned bundle; runtime state is only ever *built from* a release (plus live provider inputs). Nothing is promoted by editing a field in place.
3. **`sector-brain` is the production serving + control database. It is not the attic.** It holds compact, rebuildable, lineage-stamped outputs and control state, nothing that cannot be rebuilt or that is research workflow (D1).
4. **Ops reads truth and submits requests. It never mutates domain truth** (§7).
5. **Every published artifact carries a lineage block, and every publish leaves a manifest in append-only history** (`PUBLISHING_AND_PROMOTION_MODEL.md`).
6. **Rollback = republish from a prior canonical release, never hand-editing Firebase** (`DATA_RETENTION_AND_ROLLBACK.md`).
7. **Irreplaceable truth (observations, ledgers, reviews, releases, research) is immutable or append-only, and no cleanup policy may touch it.**
8. **Customer apps never read `sector-brain` directly.** The Engine API is the customer boundary (this is already true and should stay true).

What this deliberately does **not** add: no new database, no Firestore, no event bus, no warehouse, no new scheduler. It adds two small private buckets (`sector-research-private`, `sector-brain-history`) plus, when the first field observation exists, `sector-observations`, a create-only `/requests` root, a `/speciesProfiles` root, a `/speciesIndexes` root and a `publication` child per Brain. Everything else is moving data to where it already conceptually belongs.

---

## 2. Current-state findings (evidence in `CURRENT_DATA_INVENTORY.md`)

**What already works well (keep — D18):**
- Exactly two write clients and one write method (root multi-location PATCH).
- **Ops writes nothing** to `sector-brain` (verified on all Ops branches); rules make every Brain path write-false for clients and read only for allowlisted Ops users.
- **No customer app reads `sector-brain`**; the customer path (`/conditions`) does not read RTDB at all.
- Biological's **immutable, hash-pinned release bundle** with a `latest.json` pointer in a versioned private bucket — the right pattern; generalise it.
- Lake's **immutable prediction ledger** and baseline archive in a versioned bucket.
- Orchestrator V1's **content-aware control writes** (idle plane writes nothing but a 6 h heartbeat) and capped ledgers.
- Per-lake `/lakes/{k}/states/{slot}` layout with one owner per slot; `/lakeFleet` as a compact fleet index.
- Tests cannot write production (injected transports / `DryRunStore`).

**What is wrong (ranked in §10):**
1. **The research store is not version-controlled or backed up** (3.6 GB, all Brains), and docs point to a "private research repository" that does not exist.
2. **Several writers go live by default or from an env var alone** (Clarity `run.py` with no flag; Lake / Water Temp Swift jobs when `SECTOR_BRAIN_RTDB_URL` is set).
3. **The score publisher writes into six other Brains' nodes with the ownership check disabled** (`score_brains.py:226`) and ignores `--db`.
4. **Writer identity and credential scope have not been reviewed against the target model** (assessment kept in the private handoff; certification step 9 reviews it per Brain).
5. **Nothing records what was published before.** RTDB holds only the latest value; there is no publish manifest, no output fingerprint on states/profiles, and no score history outside a capped activity feed.
6. **Research workflow metadata is served from production** (`/species` evidence-verification labels naming agents, discrepancy titles, a private report path; `/brains/biological-state` discrepancy decision text; a per-lake note inside `/species`).
7. **32 % of `sector-brain` is duplicated data** (`/snapshots`, `/control/fleet`, `/engine/score`, readiness ×3, health ×2, Wind score ×4).
8. **Partial publishes are possible**: Wind (≥ 6 PATCHes, state and fleet slot separately), Clarity (25-lake batches, continues after failure), score publisher (4 units), Lake (per-lake then registry).
9. **No request path exists.** `/controlRequests/pending` is read by the orchestrator but nothing can write it; accepted RUN_NOW is never executed; there is no review or research request path at all.
10. **Structural read hazards:** Ops reads `/species` wholesale; nesting profiles there would take it from 117 KB to ≈1.2 MB. Ops also holds whole-collection listeners on `/lakeFleet` (484 KB) and `/control/fleet` (173 KB).
11. **Null semantics leak:** RTDB drops nulls; Wind deletes `validation/wind` on a lookup miss; Lake nulls `speciesPresence` when empty; Ops renders an absent `issueCount` as 0.
12. The customer app databases are outside Engine scope; their review is recorded privately.

---

## 3. The five data planes

| Plane | Holds | Physical home | Mutability | Production? |
|---|---|---|---|---|
| **A. Research / evidence** | raw sources, extracts, PDFs, packets, research cards, verification workflow, candidate & rejected claims, notes, bulk rebuildable datasets, licensed text | **Private** git repo `Sector_Research` (text/JSON/scripts) + versioned private bucket `gs://sector-research-private` (bulk binaries) | captured sources immutable; notes append-only via git | **Never** |
| **B. Canonical domain knowledge** | what a Brain has *adopted*: accepted rules, species knowledge, seasonal movement, confidence, provenance refs, review ledger, source identity, registry | each Brain's **release bucket**: `gs://<bucket>/{latest.json, releases/{releaseId}/manifest.json + files}` | each release immutable; only the `latest.json` pointer moves | It is the *source* of production, not served directly |
| **C. Runtime / serving** | compact current state, registries, compiled profiles, current outlooks, scores, health, validation summaries | RTDB **`sector-brain`** | overwrite in place; always derived; always lineage-stamped | **Yes** |
| **D. Control** | orchestrator state, jobs, schedules, decisions, requests, activity, health, execution history | RTDB `sector-brain` (`/control`, `/jobs`, `/requests`, `/health`, `/activity`) + Cloud Scheduler | capped/bounded | Yes (internal) |
| **E. Observation / validation** | field observations, trip observations, preregistrations, prediction ledgers, validation outcomes | append-only buckets (`gs://sector-lake-brain/predictions` today; `gs://sector-observations` when the first field observation exists); release `validation/*.jsonl` for frozen registers | **immutable / append-only**; never overwritten by derived state | Only summaries are served (`/validation`) |

**Physical vs logical separation of E:** physically separate (its own bucket/prefix with object versioning and no lifecycle-delete rule). Reason: it is the only plane whose loss cannot be recomputed, and it must not share a delete policy or a writer identity with derived state.

Plus one supporting store: **`gs://sector-brain-history`** (append-only): every publish manifest and score history. Bytes per day ≈ KB; it is what lets anyone answer "what changed, when, from what".

---

## 4. Writer map — who can change production truth today

All writes go through `BrainRtdb` (Python) or `RTDBRestStore` (Swift); method is always root multi-location `PATCH`.

| Writer | Trigger today | Writes | Guard today | Cross-owner? |
|---|---|---|---|---|
| **Wind** (`jobs/wind-hourly`) | **Scheduler `wind-hourly` 5 * * * * — ENABLED** | `/lakes/{k}/{states,profiles,validation}/wind`, `/snapshots`, `/lakeFleet` (621), `/brains/wind`, `/validation/wind`, `/sources/{3}`, `/health/*`, `/activity` | env `SECTOR_WIND_BRAIN_RTDB_URL` present | no; but ≥ 6 PATCHes (partial-publish risk) and null-deletes `validation/wind` on a miss |
| **Lake Brain** (`LakeBrainJob`) | **Scheduler `lake-brain-ledger-daily` 0 12 * * * — ENABLED, created by hand, not in repo** | `/lakes/{k}/{brain,states/lake,speciesPresence}`, snapshots, `/lakeFleet`, `/brains/lake-brain`, `/validation`, `/health`, `/sources/{6}` (3 unowned), `/activity` | `--rtdb` **or env var alone** | writes 3 unowned source ids |
| Water Temp (`WaterTempBrainJob`) | orchestrator (paused) / manual | `waterTemp` slots, snapshots, fleet, registry, validation, sources | `--rtdb` **or env var alone** | no |
| **Water Clarity** (`run.py`) | manual (deploy script would create an ENABLED daily scheduler) | `waterClarity` slots for 621 lakes, registry, sources | **none — bare `python run.py` publishes live** | no |
| Biological (`run.py`) | orchestrator in-process (paused) / manual | `/species/*` (may replace root; deletes absent species), `/brains/biological-state`, `/validation`, `/health`, `/activity` | `--write` + plan | permitted to replace whole `/species` |
| Intelligence (`run.py`) | orchestrator in-process (paused) / manual | `/lakes/{k}/states/intelligence` (621, ≈1 MB single PATCH), fleet slot, registry | `--write` + fingerprint plan | no |
| **Score/control publisher** (`score_brains.py`) | orchestrator subprocess (paused) / manual | `/scores/*`, `/engine/score`, `/control/{overview,fleet,beta}`, `/activity`, **deletes `/brains/*/score` for 6 Brains** | `--write`, stale-score guard | **yes — ownership check disabled; ignores `--db`** |
| Orchestrator | **paused** | `/jobs`, `/control/orchestrator`, `/control/orchestratorV1/*`; starts Lake/WT jobs, runs Bio/Intel/scores | **default mode is a live write cycle** | ships Bio/Intel code from whatever branch the platform deploys |
| Depth (branch) | manual | `depth` slots, `/brains/depth` | two different approval guards | branch edits shared orchestrator files |
| Michael (Firebase console) | manual | `/access` | none | — |
| Sector Ops, iOS, Android, Web, tests | — | **nothing** | rules / design | — |
| GCS-side | various | `gs://sector-lake-registry/registry/lakes.v1.json` **replaced** by `build_geometry --upload`; `ops/setup_alerting.py` applies Monitoring changes at import | flags / none | — |

**Answer:** today production truth in `sector-brain` can be changed by (a) two enabled schedulers (Wind hourly, Lake daily), (b) manual runs of any of nine entry points — four of which go live without an explicit write flag — and (c) manual console edits. Ops cannot.

## 5. Reader map (summary — detail in `CURRENT_DATA_INVENTORY.md` §3)
- **Ops** is the only client; all reads are persistent listeners; whole-collection on `/species`, `/lakeFleet`, `/control/fleet`, `/brains`, `/jobs`, `/validation`, `/scores`, `/sources`, `/control/beta`, `/control/overview`, `/health`; per-lake on `lakes/{k}/brain`, `speciesPresence`, `snapshots/{k}/latest`.
- **Brains/platform** read whole `/activity` just to prune it (four Brains), whole `/lakeFleet` (Clarity, Depth, Intelligence), whole `/species` (Intelligence), and 12 whole nodes (scorer).
- **Hazards:** (1) `/species` wholesale (profile nesting → ×10); (2) two whole-fleet listeners (`/lakeFleet` + `/control/fleet`) carrying overlapping data; (3) whole-`/activity` reads for pruning (grows with Brains; replace by `orderByChild('at').endAt(cutoff)` / key range); (4) Diagnostics opens 12 whole-node listeners; (5) any future whole `/speciesProfiles` or `/lakes` listener — forbidden by contract (§`BRAIN_DATA_CONTRACT_V1.md` cost class).

---

## 6. Ownership matrix (domains)

| Domain | Owner | Canonical home | Serves at | Duplication violations found |
|---|---|---|---|---|
| Lake identity, registry, geometry | **Lake Registry (Lake Brain)** | `gs://sector-lake-registry` | Engine `GET /lakes`; `lakeKey` | Android bundled directory; iOS `LakeRegistry.swift` (existing EXCEPTION); Ops `lakeKey.ts` (fixture-tested ADAPTER) |
| Lake level/state, bindings, baselines | **Lake Brain** | `gs://sector-lake-brain` | `/lakes/{k}/{brain,states/lake}` | production `/conditions` level path (ADAPTER) |
| Lake → species presence | **Lake Brain** (ratify O-24) | `gs://sector-lake-brain/presence` | `/lakes/{k}/speciesPresence` | **`/species/*/policyNote` names a lake (Biological node)**; Biological discrepancy text asserts per-lake facts; iOS presence models |
| Species identity & environments | **Biological Brain** | release `registry.json` | `/species/{id}` | **app `speciesCatalog` (different ids, coarser groups)**; bundled `SpeciesCatalog.swift`; Android BAA species list |
| Species behaviour, seasonal movement, response rules | **Biological Brain** | release | `/speciesProfiles/{id}`, `/species/{id}/knowledge` | **iOS `SpeciesKnowledgeBase.swift` + `SpeciesStateModels.swift`, Android `fishintel/biology/*`**; Engine `SpeciesDatabase.swift` (ADAPTER) |
| Species policy (legality, invasive, conservation) | **Policy layer** (D5) | Engine `Config/`→`Policy/` | `/species/{id}/policy` (owned child) | app `/regulations` (reference data in app DB) |
| Water temperature | **Water Temp Brain** | providers + code (+ archive) | `waterTemp` slots | client `k = 0.20` (existing EXCEPTION) |
| Water clarity | **Water Clarity Brain** | providers + code | `waterClarity` slots | Android `ClarityModel.kt` (EXCEPTION) |
| Wind | **Wind Brain** | `gs://sector-wind-candidate` | `wind` slots | iOS `WindSurfacePhysics.swift` mirror; Wind score in 4 places; `last_publish.json` as private memory |
| Depth | **Depth Brain** | release (to create) | `depth` slot | canonical data committed in public repo |
| Vegetation | **Vegetation Brain** | release (to create) | `vegetation` slot | — |
| Synthesis | **Sector Intelligence** | code + evidence catalog | `intelligence` slot | must not copy specialist facts (today it reads them through `/snapshots`, a duplicate) |
| Brain scores | **Platform** (calc) | computed + frozen | `/scores` | `/engine/score`, `/brains/wind.scores`, `/validation/wind` scores |
| Execution policy / schedules | **Orchestrator** | control manifest + Cloud Scheduler | `/control/orchestratorV1`, `/jobs` | `/health/jobs`; legacy `/control/orchestrator`; a scheduler (`lake-brain-ledger-daily`) not represented in repo |
| Presentation | **Sector Ops** | Ops repo | — | Ops still computes some rollups in the browser (existing OPEN) |
| Ops access | **Michael** | `/access` | — | platform writer is permitted to replace it |

## 7. Sector Ops write policy (D10–D12)

**Ops reads truth. Ops submits requests or human decisions. Ops never directly mutates domain truth, control state, scores or registries.**

Ops may write exactly:
| Path | What | Rule |
|---|---|---|
| `/opsPreferences/{uid}` | per-user UI preferences | owner only (exists today) |
| `/requests/control/{requestId}` | RUN_NOW / PAUSE / RESUME / SET_MANUAL (existing orchestrator schema) | create-only; `requestedBy == auth.uid`; allowlisted; no update/delete |
| `/requests/review/{requestId}` | ACCEPT / REJECT / NEEDS_MORE_EVIDENCE on a claim/rule id, with note | create-only; uid-bound; carries `brainId`, `subjectId`, `subjectRevision` (the release the reviewer saw) |
| `/requests/research/{requestId}` | "research X for brain Y" with scope text | create-only; uid-bound |

Outcomes are written by the consumer, never by Ops: control outcomes to `/control/orchestratorV1/requests` (exists), review and research outcomes to `/requests/{kind}/{requestId}/outcome` **written only by the Engine identity** (rules: Ops cannot write `outcome`). Three kinds, three consumers, three schemas — one rules block. Flow:

```
Ops click ─► /requests/{kind}/{id} (create-only, uid-bound)
          ─► consumer: control → Orchestrator · review → owning Brain's review tool · research → research queue
          ─► policy/authorization (allowlist, confirm phrase for protected actions, Michael-only for releases)
          ─► canonical change (control state | review ledger in next release | research store only)
          ─► derived rebuild ─► fingerprint ─► publish (manifest-last) ─► Ops observes the new state
```
No path in this flow lets a UI click become production truth without passing the owning Brain's validators and, for knowledge, a release.

## 8. Orchestrator and Intelligence boundaries (preserved)
- **Orchestrator decides WHEN and WHO; Brain decides HOW; Intelligence decides WHAT IT MEANS.** The orchestrator owns `/control/orchestratorV1`, `/jobs`, execution ledgers, request *outcomes* for control requests and the decision to run a Brain after a material change. It owns no science, no knowledge release, no lake truth. It must not author `/brains/{id}` content (today it does not).
- **Intelligence** reads specialist **published runtime outputs** (states, profiles, presence) and writes only `states/intelligence`. It must not keep its own species knowledge, clarity model, wind model, lake state or depth truth. Target: read `/lakes/{k}/states/*` (not `/snapshots`) and `/speciesProfiles/{id}` per species (not whole `/species`).
- **A Brain must not maintain a second copy of upstream truth.** Biological reads current water temperature from the Water Temp slot at run time and records the input fingerprint; it never republishes water temperature.

## 9. Reality tests

### 9.1 "Biological researches Common Carp tonight; tomorrow Michael opens Ops and sees new Common Carp knowledge"
| Question | Answer |
|---|---|
| Where did the raw research go? | `Sector_Research/biological-brain/…` (private git: packets, cards, verification, dispositions incl. rejected claims) and any PDFs/extracts to `gs://sector-research-private/biological-brain/…`. **Nothing to RTDB.** |
| Where did the accepted knowledge go? | Into the authoring rules directory in the private repo as DRAFT → RECONCILED, then — after review — into a **new release** `gs://sector-biology-private/releases/{releaseId}/` whose manifest pins every file by sha256. |
| Who decided it was accepted? | A non-author reviewer (Michael or external) via a `/requests/review/{id}` submission (or `tools/review.py` directly), recorded in `rules/review_ledger.jsonl` with reviewer uid and requestId. **Michael approves the release pointer move** (`latest.json`), as today (Biological Decision #1). Agents may draft; agents may not accept. |
| What file/record is canonical? | `gs://sector-biology-private/latest.json` → `releases/{releaseId}/manifest.json` and the files it pins. |
| What got published to Firebase? | `/speciesProfiles/common_carp` (compiled profile, with lineage), `/species/common_carp` (slim identity + `knowledge` summary), `/brains/biological-state` (+`publication` manifest), `/validation/biological-state` summary, one `/activity` event. |
| Who published it? | The Biological publisher (`run.py --write`, run by the orchestrator after a material-change decision or manually), recorded in `publication.publishedBy` and `codeCommit`. |
| What path? | Above; one atomic multi-location PATCH, manifest included in the same PATCH (≈ 1.2 MB, within one write). |
| What does Ops read? | `/species` (slim, whole — stays ≈ 60 KB), then `/speciesProfiles/common_carp` **one species at a time** when the Biological tab opens, and `/brains/biological-state/publication` to show "release X, published Y by Z". |
| What does Intelligence read? | `/speciesProfiles/{id}` for the target species of the lakes it evaluates, plus `/lakes/{k}/speciesPresence` from Lake Brain; it records the profile's `outputFingerprint` in its own input fingerprint. |
| How can we tell what revision created it? | `/speciesProfiles/common_carp/lineage` = `{knowledgeRelease, knowledgeManifestSha256, builder: biological-species-profile-v1, codeCommit, inputFingerprint, outputFingerprint, publishId}`; the full manifest of that publish is in `gs://sector-brain-history/biological-state/publishes/{publishId}.json`, which names the previous publishId. "Why did carp change yesterday?" = diff the two releases' manifests (file hashes) and the two publish manifests' fingerprints. |
| How do we roll it back? | Repoint `latest.json` to the previous release (Michael-approved), rebuild deterministically, republish. The previous profile is reproduced byte-for-byte (same builder version) — verified by matching `outputFingerprint` to the old publish manifest. No Firebase hand-editing. |
| What if the research was wrong? | Reviewer submits REJECT / supersede against the rule id; the rule moves to RETIRED or `supersededBy` in a new release; the bad source gets a retraction entry in the research store; republish. The wrong research stays in history (append-only) with its rejection — it is not deleted. |
**Gaps to close for this to be fully true** (Stage 1–3 work): private research repo + bucket; `/speciesProfiles` root + ownership entry; profile `outputFingerprint`; publication manifest + history bucket; `/requests/review`; `run.py` flag to publish profiles. All are in `DATA_MIGRATION_PLAN.md`.

### 9.2 "Saltwater intelligence two years from now; a species uses freshwater, brackish and marine waters"
| Question | Answer |
|---|---|
| One species ID? | **Yes.** `/species/{speciesId}` is environment-neutral identity. |
| How classified? | `environments: {freshwater: "PRIMARY"|"USES"|null, brackish: …, marine: …}` + `intelligenceScope: {freshwater: "IN_SCOPE", brackish: "OUT_OF_SCOPE", marine: "OUT_OF_SCOPE"}`; derived indexes `/speciesIndexes/{environment}/{speciesId}`. |
| Which Brain owns its behaviour? | **Biological Brain** for all environments. Knowledge records (rules, movement claims) carry `environment` applicability; one Brain, environment-scoped knowledge (no duplicate "Marine Biological Brain" re-owning the same species). |
| How does freshwater scoring avoid marine-only knowledge? | The freshwater target set is `intelligenceScope.freshwater == IN_SCOPE`; coverage scoring counts only claims whose `environments` include `freshwater` (target-scoped score v2 already scopes by target set). Marine-only claims are invisible to the freshwater denominator and numerator. |
| How does Ops filter? | Read `/speciesIndexes/freshwater` (keys only) or filter the slim `/species` on `environments`. |
| Data model migration? | **No.** Adding marine scope = new index entries + new knowledge in a new release + `intelligenceScope.marine` flip. Lake-side, a waterbody gets an `environment` attribute in the Lake registry (freshwater / brackish / marine); presence stays Lake-owned. Details: `ENVIRONMENT_AND_SPECIES_CLASSIFICATION.md`. |

### 9.3 "Michael clicks *Research Bigmouth Buffalo Night Behavior* in Ops"
```
OPS REQUEST            /requests/research/{id} = {kind:research, brainId:biological-state, subject:"bigmouth_buffalo",
                        topic:"night behavior", requestedBy:<uid>, requestedAt}           (create-only, rules-enforced)
CONTROL/RESEARCH REQ   Research queue (a research session lists open /requests/research — GET only)
AUTHORIZATION          requestedBy ∈ /access/opsUsers (rules); research requests need no confirm phrase (no production effect)
RESEARCH               packets/cards/sources → Sector_Research (private git) + bucket. Profile gap keeps
                        researchStatus RESEARCH_NOT_AUTHORIZED → becomes RESEARCH_REQUESTED by referencing the requestId
CANDIDATE KNOWLEDGE    DRAFT rules in the authoring dir (private repo); verification READ-FULL/ABSTRACT recorded
REVIEW/RECONCILIATION  author reconciles (RECONCILED); reviewer submits /requests/review → APPROVED / REJECTED in review ledger
CANONICAL KNOWLEDGE    stage_bundle → new release → Michael approves latest.json move
PROFILE REBUILD        deterministic build_profile from the release; outputFingerprint computed
MATERIAL CHANGE        fingerprint ≠ last publication.outputFingerprint → Orchestrator decision RUN (or manual --write)
PUBLISH                one PATCH: /speciesProfiles/bigmouth_buffalo, /species/bigmouth_buffalo, /brains/biological-state(+publication), activity
                        → manifest appended to gs://sector-brain-history
OPS UPDATED            Ops listener on /speciesProfiles/bigmouth_buffalo updates; request outcome = {status: PUBLISHED, publishId}
```
The Engine writes the request `outcome` at each milestone (ACKNOWLEDGED → IN_RESEARCH → CANDIDATE → RELEASED → PUBLISHED / DECLINED). There is no step at which the click, the research session, or the reviewer touches `/speciesProfiles` or `/species` directly.

---

## 10. Priorities

| P | Problem | Why | Fix (campaign) |
|---|---|---|---|
| **P0** | Research store unversioned, un-backed-up (3.6 GB) | irreplaceable; single laptop | Back up to versioned private bucket now; private git repo for text (C1) |
| **P0** | No RTDB backup exists before any structural change | rollback impossible | Scheduled RTDB export to `gs://sector-brain-history/rtdb-exports/` (daily, 30 d) (C1) |
| **P0** | Live-by-default writers (Clarity no flag; Swift env-var-only) | an innocent command or env var publishes 621 lakes | require explicit `--write`/`--rtdb`, refuse env-only (C2) |
| **P0** | Score publisher cross-owner deletes with ownership off, ignores `--db` | silent cross-Brain mutation | declared platform exception path, honour `--db` (C2) |
| **P1** | Research workflow metadata + per-lake text served in `/species`, `/brains/biological-state` | research ≠ production; presence ownership | slim `/species`; move to release (C4) |
| **P1** | No publish manifest / history / output fingerprints | cannot answer "why did X change", cannot verify rollback | `publication` + history bucket + lineage block (C3) |
| **P1** | Writer credentials not yet bounded to the publishing door | enforcement must not rely on code convention | certification step 9 (private review) |
| **P2** | Side doors: `/access` editable by platform writer; Depth/score-v2 branches edit shared files; console edits | ownership erosion | ownership table; lineage preflight (C2) |
| **P2** | Partial publishes (Wind, Clarity, scorer, Lake) | inconsistent reads | manifest-last + per-Brain single PATCH where ≤ 2 MB (C3) |
| **P2** | No request path (control/review/research) | UI pressure to add side doors | `/requests` + rules + consumers (C5) |
| **P3** | `/species` wholesale read; duplicated `/snapshots`, `/control/fleet`; whole-`/activity` reads | cost/shape | `/speciesProfiles`; retire duplicates after readers move (C4, C6) |
| **P3** | Null/unknown leaks (`?? 0`, null-deletes) | UNKNOWN = UNKNOWN | contract + Ops fixes (C2/C6) |
| **P4** | Naming drift (two activity key formats, three `executionMode` vocabularies, two job manifests, stale docs) | confusion | conventions (§11), doc fixes |
| **P5** | Cosmetic | — | — |

## 11. Naming conventions (preserve existing ids; no gratuitous renames)
| Thing | Convention | Notes |
|---|---|---|
| Brain id | existing kebab-case ids are **frozen**: `lake-brain`, `water-temp`, `water-clarity`, `wind`, `biological-state`, `sector-intelligence`, `depth`, `vegetation` | inconsistent `-brain` suffix is accepted; renaming costs more than it saves |
| Lake slot key | existing camelCase: `lake`, `waterTemp`, `waterClarity`, `wind`, `intelligence`, `depth`, `vegetation`, `biology` | map brainId↔slot in the platform registry (exists) |
| Species id | `snake_case` common name (`common_carp`); group ids end `_group` | never environment-prefixed |
| Lake key | `BrainPlatform.lakeKey` / `sector_brain_platform.lake_key` (`Name_ST`) | conformance fixtures pin it |
| Path segments | camelCase for fields, ids as above; no environment or version in a path except `releases/{releaseId}` in buckets | |
| Schema names | `<artifact>-v<N>` (`biological-species-profile-v1`, `brain-lineage-v1`); existing integer `schemaVersion` kept alongside | |
| Timestamps | ISO-8601 UTC with `Z` (`2026-10-14T21:30:00Z`); epoch-ms only inside keys | |
| Release ids | `YYYY-MM-DD.N` (Biological today) | per Brain |
| Publish ids | `{brainId}:{YYYYMMDDTHHMMSSZ}:{first 8 of outputFingerprint}` | |
| Fingerprints | content: `sha256:<64 hex>` over canonical JSON (sorted keys, no volatile fields); orchestrator decision fingerprints keep their 16-hex form | |
| Activity keys | `{epochMs}-{brainId}-{seq3}` (one format) | |
| UNKNOWN | see §12 | |

## 12. UNKNOWN semantics in RTDB
RTDB deletes `null`. Therefore:
1. **Absent means unknown, never zero.** Readers must render `—` for an absent value. `?? 0` on a count or score is a defect (Ops `issueCount ?? 0`, `slotsPublished ?? 0` must change).
2. **Enum/state fields that a consumer depends on are written explicitly as `"UNKNOWN"`** (never omitted) — e.g. `status`, `presenceState`, `maturity`, `coverage`.
3. **Numeric values whose unknown-ness matters carry a sibling status**: `{value: 12.4, status: "OBSERVED"}` or `{status: "UNKNOWN"}` (no value). Never `value: 0` as a placeholder.
4. **"Checked and found nothing" ≠ "not checked"**: write an explicit empty marker (`{checkedAt, items: "NONE"}`) instead of nulling the node (Lake `speciesPresence`, Wind `validation/wind`).
5. **A publish must not delete a node because a lookup missed.** Deletion is only for retirement, recorded in the publish manifest's `removed[]`.

## 13. Security boundary (target; current-state assessment is private)
- `sector-brain` clients: Ops read-only. No client writes domain truth. Rules ownership stays with the Ops repo; add a rules test and a "rules file == live" check before any rules deploy.
- **Never in `sector-brain`:** raw/licensed source text, private research notes, agent workflow labels, private bucket paths, secrets/tokens, user PII, rejected claims.
- **Never in the public Engine repo:** per-lake species presence, `/access` contents, live RTDB dumps, service-account e-mails, licensed text, the private research store.
- Writer identities: target is a single bounded publisher identity (see `BRAIN_READ_WRITE_SECURITY_V1.md`); enforcement must be verified in IAM as well as in rules and code.
- Emergency console access remains (Michael), but any console edit to `sector-brain` must be followed by a republish from canonical state; console edits are not a workflow.

## 14. Side-door prohibitions
| Side door | Protection |
|---|---|
| Ops mutating Brain output | rules: everything write-false except `/requests` (create-only) and `/opsPreferences` |
| Brain writing another Brain's canonical data | ownership check **always on** (`brain_id` required by `BrainRtdb`); the platform score/control writer gets an explicit, enumerated exception list instead of `brain_id=None` |
| Manual scripts bypassing validators | all publishes go through the platform `publish()` (validate → build → fingerprint → manifest); no direct `patch()` outside it (lint test) |
| Research tools writing production | research code has no write client import (test); research reads use GET-only helpers |
| Tests pointing at production | existing injected-transport pattern; add a guard that refuses a real URL when `PYTEST_CURRENT_TEST`/XCTest is set |
| Live by default | every writer requires an explicit flag; env vars may *configure* the URL but never *enable* writing |
| Console edits as workflow | `/access` managed by a logged script; console edits to Brain paths followed by republish; activity event `manual.edit` recorded |
| Specialist branch editing shared platform files | lineage preflight + additive-only rule (existing memory rule) + CODEOWNERS-style check in preflight |
| Schedulers outside the repo | every scheduler represented in the control manifest; drift check compares Cloud Scheduler to manifest |

## 15. Decisions D1–D18 (recommendations)
Full RECOMMENDED / ALTERNATIVE / WHY NOT for each in `DATA_ARCHITECTURE_DECISION_QUEUE.md`.

| # | Decision | Recommendation |
|---|---|---|
| D1 | Role of `sector-brain` | Production **serving + control** DB for Engine internals, Ops and downstream Brains. Compact, derived, lineage-stamped. Not research, not history, not customer-facing directly. |
| D2 | Raw/private research | Private git repo `Sector-Bowfishing/Sector_Research` (text/JSON/scripts, < 100 MB per Brain) + versioned private bucket `gs://sector-research-private` for bulk/binary. Back up `Sector_Research_Data` to the bucket immediately. |
| D3 | Canonical Brain knowledge | Each Brain's immutable, hash-pinned **release bundle in a private versioned GCS bucket** with a `latest.json` pointer (Biological pattern), authored from the private repo. Not Firestore, not RTDB. |
| D4 | Compiled runtime outputs | `sector-brain` RTDB, built deterministically from a release, with lineage. |
| D5 | Biological profiles path | **`/speciesProfiles/{speciesId}`.** Not `/species/{id}/profile`. |
| D6 | Owner of `/species` | Biological Brain (identity + knowledge summary). Policy layer owns a `policy` child when D5-policy lands. |
| D7 | Freshwater/brackish/saltwater | One species id; `environments` + `intelligenceScope` maps on the identity record; derived `/speciesIndexes/{env}`; knowledge scoped by environment; freshwater scoring counts freshwater-applicable knowledge only. |
| D8 | `/sources` | Data-feed source registry + health only (owner per id). Literature source identity lives in the release and appears in production only inside profile `evidenceSummary` (id, publisher, title, strength, verification level). |
| D9 | `/validation` | Compact per-Brain validation summaries only. Raw observations/ledgers in append-only buckets. |
| D10 | Ops writes | `/opsPreferences/{uid}` and create-only `/requests/{control,review,research}/{id}`. Nothing else. |
| D11 | Review decisions | `/requests/review/{id}` → owning Brain's review tool → review ledger in the next release → republish. |
| D12 | Research requests | `/requests/research/{id}` → research queue → research store only; outcome written back by Engine. |
| D13 | Promotion to production | DISCOVERED → SUPPORTED → RECONCILED → REVIEWED (APPROVED) → RELEASED (Michael pointer move) → PUBLISHED (deterministic build + fingerprint + manifest). VALIDATED is claim maturity, orthogonal. |
| D14 | Mandatory lineage | `lineage` block on every published artifact + `publication` manifest per Brain + append-only history (`PUBLISHING_AND_PROMOTION_MODEL.md` §3). |
| D15 | Misplaced live paths | `/snapshots`, `/control/fleet`, `/engine/score`, `/control/orchestrator`, `/health/jobs`, research metadata in `/species` and `/brains/biological-state`, per-lake text in `/species`, Wind scores in `/brains/wind` + `/validation/wind`, `/controlRequests` (dead). |
| D16 | Dangerous writes | Clarity live-by-default; Swift env-var-live; score publisher cross-owner deletes / ignores `--db`; Biological whole-`/species` replace + delete-absent; Wind null-delete on miss; multi-PATCH partial publishes; unguarded `ops/setup_alerting.py`; `build_geometry --upload` replacing the public registry index; Clarity deploy creating an enabled scheduler; hand-made scheduler not in repo; local runs with Michael's credentials. |
| D17 | Migrate first | (1) back up research store + RTDB export; (2) close live-by-default + cross-owner writes; (3) lineage/publication/history; (4) `/speciesProfiles` + slim `/species`; then requests; then retire duplicates. |
| D18 | Do not change | the two write clients; Ops read-only + allowlist rules; Biological release pattern; Lake ledger; Orchestrator V1 content-aware writes and capped ledgers; per-lake slot layout; `/lakeFleet`; apps via Engine HTTP; injected-transport tests; existing ids. |

## 16. What we should stop doing immediately
1. Running any writer without an explicit write flag, and setting `SECTOR_BRAIN_RTDB_URL` in a shell that runs Swift jobs.
2. Adding research/workflow fields (agent names, verification workflow, discrepancy decisions, file paths, per-lake notes) to anything published to `sector-brain`.
3. Keeping research only on the laptop (`Sector_Research_Data`) without a backup.
4. Adding new top-level RTDB roots, or nesting large derived blobs under a collection Ops reads wholesale, without a row in `RTDB_PATH_OWNERSHIP_MATRIX.md`.
5. Writing with `BrainRtdb(brain_id=None)`.
6. Creating schedulers by hand that are not in the control manifest.
7. Editing Brain data in the Firebase console as a fix (republish instead).
8. Specialist branches editing shared platform files.
9. Deploying `database.rules.json` from any Ops branch other than the one matching live.

## 17. What is safe to keep doing
- Running Wind hourly and the Lake ledger daily as they are.
- Running any Brain with `--dry-run` / `DryRunStore`, any GET-only research read of production.
- Biological staging bundles locally and Michael approving uploads.
- Ops reading as it does today (until `/speciesProfiles` exists — do not nest profiles under `/species`).
- Lake appending to its prediction ledger; research ledgers as append-only JSONL.
- Orchestrator control-only / dry-run evaluations.
