# Fish Brain (`biological-state`) — Structural Gap Audit V1

**Written before any implementation.** Brain #2 of the certification program (Wind was #1). Scope: STRUCTURE, CONTRACTS, OWNERSHIP, LINEAGE, HEALTH, PUBLISHER COMPATIBILITY. Not a research campaign; no species fact is added, changed or removed.

- Engine `main` at start: `3aa39d58cf1438b6665311dd5c8f176e64c2b3e7` (PR #23 merged). Worktree `Sector_Engine-fish-cert-v1`, branch `cert/fish-brain-architecture-v1` (created from that SHA).
- Human name **Fish Brain**; machine id **`biological-state`** (never renamed). Vocabulary: Species Intelligence, Species Intelligence Profile, Knowledge Coverage, Research Gaps.

## 0. Where Fish actually lives (three tiers of history)

| Ref | State | Contents |
|---|---|---|
| `origin/main` `jobs/biological-brain/` | **species-knowledge publisher only** (≈790 lines, 29 tests) | `biological_brain.py` (bundle load + hash verify + fail-closed validation + RTDB payload builders), `orchestration.py` (descriptor/`plan()`), `run.py` (`--plan/--dry-run/--write`), `brain_platform.py` shim, 4 JSON schemas. Already instrumented with `ConsumptionRecorder` for Brain-RTDB GETs (PR #22). |
| `feat/biological-brain-adoption` (`a7f17cdc`, pushed to origin; 19 commits ahead of / 96 behind main; **never merged, no PR**) | the **real Fish Brain**: machine rules, condition features, response bands, derived Biological State pilot, movement outlook, validation foundation (frozen rule register + prediction log), Species Intelligence Profile v1 generator, review/adoption tooling, 32 docs + coverage matrix, 17 new test files (≈21k lines) | Everything the program means by "existing Fish knowledge, spawn rules, movement logic, scoring weights, validation conclusions". `git merge-tree` against current main: **one trivial conflict** (`jobs/brain_platform/tests/test_scoring.py`). |
| `brain/biological` (`99c18f78`, 0 ahead / 141 behind main), `docs/biological-brain-research` (`84df8f1d`, 2 docs commits), `feat/biological-score-v2` (`c562d9cb`, isolated rubric-v2 proposal, **not wired**) | historical / research / proposal | Inventoried, **not touched, not deleted**. Score v2 is a *global scoring* change and is out of scope here. |

Other worktrees: `Sector_Engine-biological`, `-biological-adoption`, `-biological-research`. None modified.

**Decision A (made, flagged for review):** the cert branch **merges** `feat/biological-brain-adoption` (real merge commit, history of all 19 commits preserved, no rebase, no force). Certifying only the 790-line v0 publisher would certify a container that excludes the Brain's actual behaviour, and the later Fish Research session would then have to move code into it. The merge is a separate first commit so reviewers can review the cert commits independently of the adoption content. The two early adoption commits that once carried per-lake presence labels are **already on origin** (memory: scrubbed in the working tree, guarded by `test_no_per_lake_species_presence_labels…`); merging adds no new exposure and no history rewrite is attempted.

## 1. The 20 questions

1. **Where does Fish code live today?** `jobs/biological-brain/` (main); the full Brain only on the adoption branch. Plus platform-side facts: `jobs/brain_platform/.../scoring.py::score_biological`, `keys.py`, `ownership.py` (`/species/*` owner), `jobs.py` (`biological-brain` job record), `control_manifest.json` (`biological-state` execution entry), `jobs/brain-orchestrator/orchestrate.py` (`EXECUTORS["biological-state"].dir`), `jobs/brain-orchestrator/deploy-job.sh` (stages `jobs/biological-brain`), `docs/brains/scoring/biological-state-score-v1.json`.
2. **Canonical `brains/` location?** Yes, by established convention: **`brains/fish/`** (`brains/README.md`: "`brains/fish` has `brainId` `biological-state`"; `tools/architecture/stable_brain_ids.json` `"fish": "biological-state"`; `test_foundation.py` asserts directory `fish` ↔ id `biological-state`). The mission's "`brains/biological-state/`" is the *expected conceptual* path; the repository's recorded convention wins (mission: "unless the repository's current conventions establish another canonical path"). Directory ≠ machine id by design. Nothing exists there yet.
3. **What remains under `jobs/biological-brain`?** Everything (it is the only implementation). `tools/architecture/ownership_map.json` already assigns it to "Fish Brain, Phase 4 (Fish migration)".
4. **Formally registered?** **No.** `biological-state` is an identity in `keys.BRAINS` and the legacy `control_manifest.json`, but not a registered Brain (`report.py`: "registered Brains scanned: 1" = Wind).
5. **`brain.json`?** None.
6. **Schemas/contracts?** `jobs/biological-brain/schemas/*.schema.json` (bundle shapes: latest pointer, manifest, species summary, species profile; adoption adds rule, condition features, observation, prediction, response band, species-response-bands, species profile v1). No Brain `contracts/` declaration, no Publisher registry entry, no `publishes[]`.
7. **Inputs?** (a) the PRIVATE canonical knowledge bundle `gs://sector-biology-private/biology/v1` (`latest.json` pointer → manifest → hash-verified species/rules/cards) — this is the Brain's **own knowledge release**, not another party's state; (b) the Brain RTDB: its own nodes (`/brains/biological-state`, `/species`) for `plan()`; (c) *pilot only* (`run_state.py`/`bio_state.py`, internal, local-file output, GET-only): published Water Temp / Clarity / Wind / Lake / (Depth, Vegetation shapes) states and Lake-Brain species presence.
8. **Other Brains consumed?** In the orchestrated species-knowledge runtime: **none**. In the internal Biological State pilot: Water Temp, Water Clarity, Wind, Lake Brain (+ provisional Depth/Vegetation input contracts). The pilot is `NOT_STARTED`/`PILOT_INTERNAL`, not scheduled, publishes nothing.
9. **Providers/registries/private bundles?** Providers: none. Registries: none read at runtime (species identity currently travels *inside* the Fish bundle — see gap G-6). Private bundle: yes (7a).
10. **Formally declared?** Only in the platform-authored legacy `control_manifest.json`: 4 *provisional, OPTIONAL* Brain edges (`wind`, `water-temp`, `water-clarity`, `lake-brain`) — **none of which the orchestrated runtime reads**. They are not Brain-owned declarations and misrepresent the real architecture (health plane shows them as 4 UNKNOWN rows: `sample_health_state_live_dryrun_2026-10-17.json`). The bundle is declared nowhere.
11. **Recorded in `consumed[]`?** Only own-RTDB GETs through `BrainRtdb(recorder=…)` (own nodes are excluded by the recorder ⇒ typically an empty list). The private bundle is read through a raw `urllib` GCS reader in `run.py` — **outside the recorder** (acknowledged in `ACTUAL_CONSUMPTION_LINEAGE_V1.md` §7 gap 3). `run_state.py` builds a `BrainRtdb` **without** a recorder.
12. **Outputs?** Today: one atomic multi-path RTDB update — `/species/{id}`, `/brains/biological-state`, `/validation/biological-state`, `/health/brains/biological-state`, `/activity/{event}`. Adoption adds: Species Intelligence Profile v1 documents (`biological-species-profile-v1`), profile bundle, evaluated view, movement outlook — all dry-run/local, "no publication". No versioned Publisher artifact exists.
13. **Direct production RTDB write?** Yes, one place: `run.py --write` → `rtdb.update(updates)` (`BrainRtdb`, ownership-checked by `ownership.assert_owned`, atomic). Classification: **LEGACY** (canonical-platform client, but it is a specialist-owned production write rather than the Publisher door) → `RETIREMENT_CANDIDATE` at Publisher cutover. Nothing else writes (all `open(..,"w")` are local tool outputs; no REST PATCH/PUT/POST anywhere else).
14. **Platform RTDB clients consistently?** Yes for RTDB (`brain_platform.py` shim → `sector_brain_platform`). The GCS reader is a bespoke `urllib` helper (bundle storage is not an RTDB concern; it is the knowledge-release door — see G-2).
15. **Bypasses the recorder?** Bundle reads (not a classified dependency type; belongs in artifact release identity — G-2) and `run_state.py` GETs (G-3).
16. **healthV1 today?** `control/healthV1` already renders `biological-state` from the *legacy manifest*: process HEALTHY, dependencies/freshness/publish **UNKNOWN**, 4 legacy OPTIONAL rows, `consumptionRecorded: false`. No Brain-owned declaration, so no `brain.json` source.
17. **Score/readiness?** `/scores/biological-state`, `biological-state-score-v1` (rubric sha in `score_baseline.json`), **computed from live published RTDB facts** by `score_biological` (species coverage/depth/maturity, per-lake state status, Intelligence connection). Last verified live value **4.0** (gate-capped: per-lake state NOT_STARTED ⇒ ≤4.0; no species VALIDATED ⇒ ≤6.0). `scoreType` is not stamped on the node (concept label assigned by the baseline: `ENGINE_READINESS_SCORE`). **Mixes architecture with science** (knowledgeDepth, evidenceQuality are domain facts) — documented, not redesigned (scope rule).
18. **Lifecycle actually?** Legacy manifest: `PROFILED`; registry node `status: PROFILED`. Species knowledge `RESEARCH` maturity; Biological State `NOT_STARTED` (pilot internal). Customer integration: none.
19. **Scientific/validation state?** `NOT_VALIDATED` (`/validation/biological-state`). No species `VALIDATED`; preregistered validation (hash-pinned, adoption branch) has not produced results; Intelligence consumes species summaries read-only.
20. **What prevents architecture certification today?** See §2 (blockers B1–B9).

## 2. Structural blockers (all FISH STRUCTURE or generic-platform-reuse items; none is SCIENCE)

| # | Blocker | Class | Resolution in this phase |
|---|---|---|---|
| B1 | Real Fish Brain unmerged (only on `feat/biological-brain-adoption`) | FISH STRUCTURE / HUMAN decision A | merge (history-preserving) |
| B2 | No canonical package, `brain.json`, operating contract, `contracts/` | FISH STRUCTURE | create `brains/fish/` |
| B3 | Legacy fake dependency declarations (4 OPTIONAL edges never consumed) | FISH STRUCTURE (drift) | Brain-owned `consumes: []`; manifest edges → `[]` (Wind precedent) |
| B4 | No versioned Publisher-compatible artifact / no Publisher registry entry for `biological-state` | FISH STRUCTURE (uses generic Publisher infrastructure) | register Fish schemas/bundle (generic registry, no platform change) |
| B5 | Direct specialist production write (`run.py --write`) with no Publisher path | FISH STRUCTURE | classify LEGACY; add artifact-only `--artifact` path; do **not** enable cutover |
| B6 | Private-bundle read outside lineage | FISH STRUCTURE | record the knowledge release in artifact lineage (`knowledgeRelease/manifestRef/manifestSha256`), no fabricated consumed entry |
| B7 | `run_state.py` GETs unrecorded | FISH STRUCTURE | attach recorder |
| B8 | Research workspace (`Sector Research/fish-brain`) exists but is empty/unstructured | FISH STRUCTURE | create manifest/layout only |
| B9 | No certification tests / evidence | FISH STRUCTURE | build |

## 3. Known structural gaps that are NOT fixed here (documented)
- **G-1** Species identity currently ships inside the Fish bundle and `/species/{id}` (identity + summary mixed; `RTDB_PATH_OWNERSHIP_MATRIX` row 32). Species Registry owns identity (CERT-8) but has no data yet. Fish code is unchanged; boundary documented; no `registry:species` dependency declared because Fish does **not** read the Species Registry.
- **G-2** The private research bundle is the Brain's own *knowledge release*; the platform has no "knowledge release" dependency type and needs none: it is identity-in-lineage (`knowledgeRelease`, `manifestRef`, `manifestSha256`).
- **G-3** The Biological State pilot's upstream inputs (Water Temp, Clarity, Wind, Lake, Depth, Vegetation) are **not declared** because that component is not part of any orchestrated execution. Declaring them is a one-line `brain.json` change when the pilot graduates (HUMAN/DECISION D-1).
- **G-4** Score system mixes architecture and domain science; `biological-state-score-v2` is a separate isolated proposal (branch `feat/biological-score-v2`). Not touched.
- **G-5** Local `species-intelligence` docs remain under `docs/brains/biological-adoption/` (not moved: doc churn without structural value; referenced from the package README).
- **G-6** Signals: Fish consumes none from the Signal Registry today ⇒ declared none (no `pressure-trend`, `moon-phase`, … fabrication).

## 4. Method constraints honoured
No production write, no deploy, no scheduler, no provider polling, no Publisher production enablement, no customer-visible change, no research campaign, no Sector Ops change, no global score redesign.
