# Current Data Inventory (Stage 0, read-only)

**Measured:** 2026-10-14 (UTC evening). **Method:** authenticated HTTP GET of every `sector-brain` subtree (no writes); code audit of Engine @ `f6cec529` (`feat/brain-platform-model-v1`, the newest shared lineage; the deployed orchestrator is `5fd727ef`, an ancestor) plus 10 unmerged Brain branches; Sector Ops `main` @ `7564672` and `feat/canvas-orchestrator-control-v1` @ `768e63d`; iOS `sector/app-updates`; Android `feat/ios-visual-parity`.
**Nothing was migrated, written, deleted, renamed or deployed.**

> Public-repo rule: this file deliberately omits per-lake species pairings, user identifiers, credential/IAM details and security findings. Those are in the private handoff (`Sector Handoffs/Sector Engine/`).

## 1. Storage that exists today

| Store | What it actually is | Size | Who uses it |
|---|---|---|---|
| RTDB `sector-brain` | Engine Brain serving + control database. Read **only** by Sector Ops (allowlisted users) and by Engine jobs. No customer app reads it. | **10.11 MB**, 14 top-level paths | Brains, platform score/control publisher, Orchestrator, Ops |
| RTDB `sector-9393c-default-rtdb` | **Production customer app database** (users, guides, tournaments, regulations, presence…). Name says "default"; content and subscription row say Production. | ≈1.9 MB, 46 keys | iOS, Android, Sector-Web |
| RTDB `sector-dev-1f4d0` | **Development/sandbox app database.** A copy of prod taken ≈July 2026 (contains real user records); rules are a superset of prod's. | — | iOS/Android dev builds via `DatabaseProvider` |
| Firestore `(default)` | Exists (native, nam5). Not used by any Engine or Ops code found. | not inspected | — |
| GCS `sector-biology-private` | Biological canonical knowledge releases (`latest.json` → `releases/{researchVersion}/manifest.json` → hash-pinned files). Versioned, public access blocked. | 0.8 MB | Biological publisher |
| GCS `sector-lake-brain` | Lake presence, baselines (`latest.json` + immutable archive), history, **prediction ledger (immutable)**. Versioned. | 8 MB | Lake Brain |
| GCS `sector-lake-registry` | Lake registry + geometry. | 9.6 MB | Engine, Lake, Wind |
| GCS `sector-lake-surface` | Clarity map layers, hydrology. | not measured | Engine serving (`ClarityStateLoader`), `/lakes` map-layer links |
| GCS `sector-wind-candidate` | Wind store + `last_publish.json` (Wind's publish memory). | 50 MB | Wind |
| GCS `sector-water-temp-archive` | TVA water-temp archive (merge-only). | 2 MB | Water Temp |
| GCS `sector-clarity-candidate` | Clarity research archive, ACOLITE, shadow. | 29 GB | Clarity research |
| Local `~/…/Development/Sector_Research_Data` | **All Brains' raw research.** Not a git repo, no remote, no backup found. | **3.6 GB** (depth 1.4G, lake 1.0G, water-temp 578M, vegetation 522M, wind 52M, biological 13M) | Research sessions |
| Engine repo (PUBLIC) | Code, contracts, docs, some research ledgers (`docs/research/*` on research branches), **Depth canonical data** (`jobs/depth-brain/depth_brain/data/`), frozen scores (`docs/brains/scoring/frozen-scores.json`) | — | everyone |
| Handoffs folder (local) | Session handoffs; also a third copy of Biological profiles (Ops Species Profile Package). | — | Michael |

## 2. `sector-brain` top-level paths (measured)

| Path | Bytes | Children | What it holds | Writers (code) | Bounded? |
|---|---:|---:|---|---|---|
| `/lakes` | 5,711,763 | 621 | Per lake: `states/{slot}`, `profiles/{slot}`, `validation/{brainId}`; pilots also `brain`, `speciesPresence`. Clarity states alone 2.63 MB (≈1.17 MB of it map-layer/satellite/gauge metadata). | Lake, Water Temp, Clarity, Wind, Intelligence (all 621), Depth (branch) | yes (overwrite in place) |
| `/snapshots` | 3,403,154 | 621 | `{k}/latest` = **byte-identical copies** of `lakes/{k}/states/*` (+ `brainVersions`). `generatedAt` lags its content. | Lake, Water Temp, Clarity, Wind, Intelligence | yes |
| `/lakeFleet` | 483,885 | 621 | Compact fleet row per lake (`slots/*`, `readiness/*`, `modelVersions/*`, `riverSystem`). | every lake-scoped Brain | yes |
| `/control` | 256,042 | 5 | `fleet` 173 KB (**duplicates `/lakeFleet` rollups**), `orchestratorV1` 53 KB (14 sections, capped ledgers 60/120/30), `overview` 16 KB, `beta` 11 KB, `orchestrator` 3 KB (legacy, rewritten every live cycle) | `score_brains.py`; orchestrator | mostly; orphans when a lake leaves the fleet |
| `/species` | 117,165 | 29 | Biological species records: ids, names, taxonomy, version fields, 8-domain knowledge score + history, `profileRef` (private `gs://` path + sha256), `responseBands`, **research workflow metadata** (evidence-verification labels naming agents, open discrepancy titles, research gaps, a private report path), one `policyNote` that names a lake. | Biological only (may replace whole root; deletes species absent from bundle) | yes |
| `/brains` | 57,958 | 7 | Registry per Brain (contract §registry, Model v1 additive fields). `biological-state` also carries open discrepancies with decision text. | each Brain writes its own node **whole**; score publisher deletes `/brains/*/score` | yes |
| `/jobs` | 29,427 | 21 | Job records incl. 5 non-Brain functions (admin/app notification jobs). | orchestrator | records never removed |
| `/activity` | 12,726 | 51 | Event feed; two key formats (`{epochMs}-…` and `YYYYMMDDT…`). | every writer, own events | per-Brain cap 80/30 d — **except Biological & Intelligence (never prune)** |
| `/validation` | 12,473 | 7 | Compact per-Brain validation summary (Wind also carries scores). | each Brain | yes |
| `/scores` | 11,350 | 7 | Canonical score per Brain + `engine`. | `score_brains.py` only | yes |
| `/sources` | 6,013 | 12 | **Data-feed** registry (NBM, RTMA, USGS, CWMS…), not literature. Unowned ids are last-writer-wins. | Lake, Water Temp, Clarity, Wind | yes |
| `/health` | 5,520 | 3 | `brains/*` (dup of `/brains/*.health`), `jobs/*` (overlaps `/jobs`), `sources/*` | each Brain | yes |
| `/engine` | 1,581 | 1 | `score` — **alias of `/scores/engine`** | `score_brains.py` | yes |
| `/access` | 86 | 1 | `opsUsers/{uid}: true` (2 entries). Ops read allowlist. | **no code** — hand-maintained (console) | yes |
| *(rules-only)* `/opsPreferences`, `/validationOps`, `/schemaVersion` | 0 | — | declared in rules, no data | none | — |

**Duplication:** ≈3.2 MB (32 %) of `sector-brain` is duplicated data (`/snapshots` ⊂ `/lakes`, `/control/fleet` ≈ `/lakeFleet` rollups, `/engine/score` = `/scores/engine`; readiness stored 3×; health stored 2×; Wind score in 4 places).

## 3. Readers (who reads what, at what grain)

| Reader | Reads | Grain | Notes |
|---|---|---|---|
| **Sector Ops** (only client of `sector-brain`) | `/species` (117 KB, BrainPage Biological tab + Diagnostics), `/lakeFleet` (484 KB), `/control/fleet` (173 KB), `/brains`, `/jobs`, `/validation`, `/scores`, `/sources`, `/control/beta`, `/control/overview` + `/health` (every page), `/activity` (`orderByChild('at')`, last 50), `/control/orchestratorV1/*` (12 section listeners; branch `768e63d` reads whole) | **whole collections** via persistent `onValue`, shared per path, IndexedDB cache; per lake: `lakes/{k}/brain`, `lakes/{k}/speciesPresence`, `snapshots/{k}/latest`, `control/fleet/{k}`, `lakeFleet/{k}` | Never reads `/lakes` or `/snapshots` whole. Diagnostics opens 12 whole-node listeners (≈450 KB). |
| iOS / Android / Sector-Web | **nothing in `sector-brain`** | — | Engine data comes over Cloud Run HTTP. They read/write the app databases. |
| `score_brains.py` | 12 whole top-level nodes + per-lake `brain`/`states/lake` for profiled lakes + ≤50 Intelligence states | whole + per lake | |
| Orchestrator | `/brains`, `/health/brains`, `/jobs`, `/scores`, `/control/*`, `/controlRequests/pending` (does not exist; nothing can write it) | whole | |
| Sector Intelligence | 6 dependency registries, `/species` (whole), `/lakeFleet` (whole), pilot `snapshots/{k}/latest` + `speciesPresence` | whole + per lake | reads specialists through the snapshot duplicate |
| Biological | `brains/biological-state`, `species?shallow`; pilot runner (branch) reads `snapshots/{k}/latest` (water temp etc.), presence, species | leaf / per lake | reads Water Temp, never republishes it ✔ |
| Clarity | `brains/water-clarity`, `/lakeFleet` whole, `/activity` whole | whole | |
| Lake, Water Temp, Wind | own registry, per-lake own state, `/activity` whole (to prune) | leaf + whole | |
| Depth (branch) | `/lakeFleet` whole, `lakes/{k}/states/lake`, own registry | whole + per lake | |
| Engine serving (`/conditions`) | **no RTDB**; GCS `sector-lake-surface`, registry URL | — | customer path is independent of Brain state today |

## 4. Writers (summary — full table in `RTDB_PATH_OWNERSHIP_MATRIX.md` and `SECTOR_DATA_OWNERSHIP_ARCHITECTURE.md` §4)
- **Two write clients only:** Python `BrainRtdb` (`jobs/brain_platform/sector_brain_platform/rtdb.py`) and Swift `RTDBRestStore` (`Sources/SectorEngine/Brain/BrainRTDBStore.swift`). Every write is a root multi-location `PATCH` (`print=silent`); `null` deletes. No PUT, push, Admin SDK or Firestore writes anywhere.
- **Fence:** URL must contain `sector-brain` and must not name an app database. Ownership check runs only when `brain_id` is set. `/schemaVersion` gate never fires (path absent).
- **Scheduled live writers right now:** `wind-hourly` (`5 * * * *`) and `lake-brain-ledger-daily` (`0 12 * * *`, created by hand, not in repo). Orchestrator and everything it drives are **paused**.
- **Manual live writers:** orchestrator default mode, `score_brains.py --write`, Biological/Intelligence `run.py --write`, **Clarity `run.py` with no flag**, Lake/Water Temp Swift jobs with `--rtdb` **or just the env var `SECTOR_BRAIN_RTDB_URL`**, Wind CLI `--rtdb`, Depth branch with its shadow approval.
- **Sector Ops writes nothing** (all branches). The mobile apps write nothing to `sector-brain`.
- **Tests are safe:** injected transports, `DryRunStore`, monkeypatching; Wind network tests deselected.

## 5. Research / canonical / published / ledger locations per Brain (as found)

| Brain | Raw research | Canonical knowledge | Published runtime | Validation / ledgers |
|---|---|---|---|---|
| Biological | `Sector_Research_Data/biological-brain` (unversioned) | `gs://sector-biology-private` release (`2026-10-14.4` live; `2026-10-14.7` staged locally only) | `/species/*`, `/brains/biological-state`, `/validation/biological-state` | bundle `validation/*.jsonl` (82 frozen rules, 21 predictions, 0 observations) |
| Lake | `Sector_Research_Data/lake-brain` (1 GB, `MANIFEST.jsonl`) | `gs://sector-lake-brain/{presence,baselines,history}`, `gs://sector-lake-registry` | `/lakes/{k}/{brain,states/lake,speciesPresence}`, `/lakeFleet` | `gs://sector-lake-brain/predictions` (immutable); research ledgers (append-only JSONL) on public research branch |
| Wind | `Sector_Research_Data/wind-brain` | `gs://sector-wind-candidate/wind/v1` | `/lakes/{k}/*/wind`, `/brains/wind` | `/validation/wind`, fieldops tooling |
| Water Temp | `Sector_Research_Data/water-temp-brain` (578 MB); some data committed publicly under `docs/research/water-temp` | code constants + `gs://sector-water-temp-archive` | `/lakes/{k}/{states,profiles}/waterTemp` | prediction log local files only |
| Water Clarity | local unpushed branch `research/clarity-candidate` (~200 MB committed artifacts) + `gs://sector-clarity-candidate` | code + candidate bucket | `/lakes/{k}/{states,profiles}/waterClarity` | `/validation/water-clarity` |
| Depth | `Sector_Research_Data/depth-brain` (1.4 GB) | **committed in the public repo** (`jobs/depth-brain/depth_brain/data/`, 1 MB candidates) | `/brains/depth` (shadow) | none |
| Vegetation | `Sector_Research_Data/vegetation-brain` (522 MB) | frozen gates in code | nothing (dry-run writer only) | sealed holdout registry (branch) |
| Intelligence | research branch docs | evidence catalog in code | `/lakes/{k}/states/intelligence` (621 lakes, ≈1 MB per republish) | `/validation/sector-intelligence` |

## 6. Observed live issues (not structural, recorded for completeness)
- Water Clarity last published 2026-10-12T06:52Z (≈2.6 days old at measurement); health shows the publisher `MANUAL_RUN_NOT_DEPLOYED`.
- `usace-cwms-pool` source FAILED; Lake Brain WARNING; `clarity-candidate-shadow` PAUSED after 17 failed tasks.
- With the orchestrator paused, `/scores` and `/control/*` are not refreshed while Wind (hourly) and Lake (daily) keep changing state, so `/control/overview` drifts.
