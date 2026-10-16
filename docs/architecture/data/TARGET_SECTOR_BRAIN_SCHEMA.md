# Target `sector-brain` Schema (proposed — nothing changed live)

> **Superseded in part by Brain Certification V1 (`docs/architecture/certification/`, 2026-10-14).** Where they differ, Certification V1 wins:
> (1) the **Orchestrator Publisher is the only steady-state writer** to `sector-brain`; specialist Brains produce artifacts and do not write production (this document had Brains publishing through a shared `publish()` with their own identity);
> (2) **Ops sends requests through an authenticated Engine/Orchestrator API**, not by creating `/requests/*` nodes in RTDB;
> (3) **species identity is owned by the Species Registry (Engine Platform)**, not by the Fish Brain (`biological-state`); Fish Brain owns species intelligence;
> (4) **no path changes** (including `/speciesProfiles`) are approved by this document; they are decided per Brain during certification.
> In the target-schema and source-of-truth tables, "writer" means the **producing Brain**; the physical writer is the Publisher.


Machine-readable: `TARGET_SECTOR_BRAIN_SCHEMA.json` (path, owner, writers, readers, read pattern, max size, status vs today).
**Role (D1):** production serving + control database for Engine internals, Ops and downstream Brains. Compact, derived, lineage-stamped, bounded. Customer apps reach Engine truth through the Engine API, never by reading this database.

```
/access/opsUsers/{uid}: true                       ACL      Michael (scripted)            unchanged
/opsPreferences/{uid}                              ACL      Ops user                      unchanged

/brains/{brainId}                                  REG      that Brain                    unchanged (registry, Model v1 fields)
/brains/{brainId}/publication                      CTRL     that Brain (via publish())    NEW  latest publish manifest
                                                                                          (discrepancy/research text REMOVED from biological-state)

/species/{speciesId}                               REG      Biological                    SLIMMED (≤ 2 KB each, ≈ 60 KB total)
    speciesId, commonName, scientificName, aliases[], group, taxonomyStatus
    environments{freshwater,brackish,marine}       PRIMARY | USES | (absent = not used)
    primaryEnvironment
    intelligenceScope{freshwater,brackish,marine}  IN_SCOPE | OUT_OF_SCOPE | PLANNED
    knowledge{score, coverage, researchMaturity, openGapCount, openDiscrepancyCount, knowledgeRelease, profileFingerprint}
    policy{…}                                      owned by Policy layer (when D5-policy lands); Biological never writes it
    lineage{…}
/speciesIndexes/{freshwater|brackish|marine}/{speciesId}: "PRIMARY"|"USES"   DERIVED by Biological   NEW
/speciesProfiles/{speciesId}                       SERVE    Biological                    NEW  biological-species-profile-v1 (17–56 KB), LEAF_ONLY reads
                                                                                          (absorbs responseBands; evidenceSummary carries source id/publisher/title/strength/verification level only)

/lakes/{lakeKey}/brain                             SERVE    Lake                          unchanged
/lakes/{lakeKey}/states/{slot}                     SERVE    slot owner                    unchanged (+ lineage.publishId/outputFingerprint)
/lakes/{lakeKey}/profiles/{slot}                   SERVE    slot owner                    unchanged (Clarity map-layer metadata moves here from state)
/lakes/{lakeKey}/validation/{brainId}              OBS-SUM  that Brain                    unchanged (no null-on-miss)
/lakes/{lakeKey}/speciesPresence                   SERVE    Lake                          unchanged (explicit NONE marker instead of null)
/lakes/{lakeKey}/states/biology                    SERVE    Biological                    FUTURE (current movement outlook)

/lakeFleet/{lakeKey}                               SERVE    per-slot owners               unchanged
/lakeFleet/{lakeKey}/rollup                        SERVE    platform                      NEW  (absorbs /control/fleet/{k})

/scores/{brainId|engine}                           SERVE    platform                      unchanged (canonical; + lineage)
/validation/{brainId}                              OBS-SUM  that Brain                    unchanged (summaries only; Wind scores removed)
/sources/{sourceId}                                REG      owning Brain (1 per id)       unchanged (data-feed registry only)
/health/brains/{brainId}                           SERVE    that Brain                    unchanged
/health/sources/{sourceId}                         SERVE    owning Brain                  unchanged

/control/overview                                  CTRL     platform                      unchanged
/control/beta/{lakeKey}                            CTRL     platform                      unchanged (+ orphan pruning)
/control/orchestratorV1/*                          CTRL     orchestrator                  unchanged
/jobs/{jobId}                                      CTRL     orchestrator                  unchanged (absorbs /health/jobs; retired jobs pruned)

/requests/control/{requestId}                      CTRL     Ops (create-only)             NEW  (replaces dead /controlRequests/pending)
/requests/review/{requestId}                       CTRL     Ops (create-only)             NEW
/requests/research/{requestId}                     CTRL     Ops (create-only)             NEW
/requests/{kind}/{requestId}/outcome               CTRL     Engine consumer only          NEW
/activity/{epochMs}-{brainId}-{seq}                HIST     each writer (own events)      unchanged, one key format, bounded

/schemaVersion                                     CTRL     platform                      populate once (so the writers' schema gate works) — or drop the gate (decision)
```

**Retired after their readers move (Stage 6, explicit approval):** `/snapshots` (→ `/lakes/{k}/states`), `/control/fleet` (→ `/lakeFleet/{k}/rollup`), `/engine` (→ `/scores/engine`), `/control/orchestrator` (→ `orchestratorV1`), `/health/jobs` (→ `/jobs`), `/controlRequests` (never had data), `/validationOps` (rules-only, never had data).

**Explicitly NOT in `sector-brain`:** research packets, source text, agent verification workflow, rejected claims, discrepancy decision prose, private bucket paths, prediction ledgers, raw field observations, history of prior values (→ `gs://sector-brain-history`), anything licensed.

## Size and cost model (target)

| Read shape | Who | Today | Target |
|---|---|---|---|
| `/species` whole | Ops (Biological tab, Diagnostics), Intelligence | 117 KB | ≈ 60 KB (slim) — and **not** 1.2 MB as it would be with nested profiles |
| one `/speciesProfiles/{id}` | Ops per species, Intelligence per target species | — | 17–56 KB |
| `/lakeFleet` whole (persistent) | Ops | 484 KB | ≈ 600 KB with `rollup` (but `/control/fleet` 173 KB listener disappears) |
| per-lake states | Ops lake page | `snapshots/{k}/latest` ≈ 5.5 KB | `lakes/{k}/states` ≈ same |
| Ops session cold start (Overview + Fleet + Brains) | Ops | ≈ 1 MB | ≈ 0.9 MB |
| Diagnostics | Ops | ≈ 450 KB, 12 listeners | ≈ 400 KB |
| whole `/activity` to prune | 4 Brains | 13 KB (grows with Brains) | key-range query (`endAt(cutoff)`) |

| Write shape | Today | Target |
|---|---|---|
| Wind hourly | ≥ 6 PATCHes, 621 fleet rows + states + snapshot copies | 1 PATCH, no snapshot copies (≈ half the bytes) |
| Intelligence republish | ≈ 0.95 MB / run | ≈ 0.7 MB (no snapshot copies), skipped when fingerprint equal |
| Biological publish | ≈ 0.15 MB | ≈ 1.2 MB with profiles, **only on a new release** (rare) |
| Storage total | 10.1 MB | ≈ 7 MB (−3.2 MB duplicates, + 1.05 MB profiles) |
| History growth | none kept | `gs://sector-brain-history`: ≈ 2–10 KB per publish → < 50 MB/year |

At Ops's scale (2 allowlisted users) RTDB download and storage cost is negligible either way; the model exists to stop **structural** hazards: (1) a wholesale listener on a collection that grows ×10 (`/species` + profiles), (2) whole-collection listeners that each Wind run re-delivers deltas to, (3) unbounded append nodes, and (4) any future customer read path — 1,000+ app users reading RTDB directly would turn each of these into a real bill, which is why the Engine API stays the customer boundary.
