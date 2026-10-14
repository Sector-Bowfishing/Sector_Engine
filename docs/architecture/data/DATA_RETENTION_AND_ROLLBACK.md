# Data Retention and Rollback

## 1. Retention policy

| Data | Store | Class | Retention | Bounded today? | Action |
|---|---|---|---|---|---|
| Raw research, sources | research repo + `sector-research-private` | IMMUTABLE / APPEND | forever | n/a — **not backed up** | C1 backup |
| Knowledge releases | release buckets | IMMUTABLE | forever (all releases) | yes (Biological: 2 releases) | keep; no lifecycle delete |
| Prediction ledgers, preregistrations | `gs://sector-lake-brain/predictions`, release `validation/` | IMMUTABLE | forever | yes ("keep everything") | keep |
| Field observations | `gs://sector-observations` (create on first observation) | IMMUTABLE | forever | none exist yet (Biological 0 observations) | create with versioning, no delete rule |
| Review ledger, dispositions | release / research repo | APPEND | forever | yes | keep |
| Handoffs | `Sector Handoffs/` | APPEND | per Michael's folder rules | yes | unchanged |
| Publish manifests, score history | `gs://sector-brain-history` | APPEND | forever (tiny) | **does not exist** | C3 |
| RTDB exports (backups) | `gs://sector-brain-history/rtdb-exports/` | IMMUTABLE | daily × 30, monthly × 12 (lifecycle rule **on this prefix only**) | **none** | C1 |
| RTDB runtime (`/lakes`, `/species`, `/scores`, …) | `sector-brain` | DERIVED | current only | yes (overwrite) | — |
| `/activity` | `sector-brain` | HIST | ≤ 80 events per Brain and ≤ 30 days | partly: Biological & Intelligence never prune; orchestrator global sweep unimplemented | C2: prune by key range; all writers |
| Orchestrator ledgers | `/control/orchestratorV1/{executions,decisions,requests}` | HIST | 60 / 120 / 30 | yes | keep |
| `/jobs` | `sector-brain` | CTRL | current; retired jobs removed | no (never removed) | C6 |
| `/requests/*` | `sector-brain` | APPEND | 90 days, then archived to history bucket | n/a | C5 |
| `/control/fleet`, `/control/beta` orphans | `sector-brain` | DERIVED | current fleet only | no (orphans) | prune in scorer |
| Lake baselines | `gs://sector-lake-brain/baselines` | MUT pointer + IMM archive | archive forever | yes (lifecycle on non-archive) | keep |
| Wind / hydrology / dispatch ledgers | GCS | DERIVED | 90 days | **no lifecycle** | C6 add lifecycle (after confirming DERIVED class) |
| Artifact Registry images | AR | — | keep images referenced by any rollback doc + last 10 | **no policy** (5 GB) | C6 cleanup policy with keep-list |
| Clarity research archive | `gs://sector-clarity-candidate` (29 GB) | RESEARCH | forever unless Michael classifies parts as rebuildable | — | classify; do not delete |

## 2. Rollback strategy (prefer reproducibility over Firebase editing)

| Artifact | Detect a bad publish | Restore | What's retained to make it possible |
|---|---|---|---|
| Knowledge-derived outputs (species registry, profiles, Depth, Vegetation) | Ops/validator sees wrong content; `publication.outputFingerprint` diff vs previous; profile validator | **Repoint `latest.json` to previous release (Michael) → rebuild → republish.** Verify `outputFingerprint` equals the earlier publish manifest's. | all releases (immutable) + publish manifests (history) + builder code at `codeCommit` |
| Builder/code regression (same release, new code) | same | redeploy previous image (or run builder at previous `codeCommit`) → republish | AR image keep-list; manifests name `codeCommit` |
| Observation-Brain state (Wind, Water Temp, Clarity, Lake level) | health/validation alarms, fleet anomalies | redeploy prior image; state self-heals on next run (no prior state restore — inputs were live) | image keep-list, deploy packages (e.g. Wind `413bbbae`) |
| Scores | stale-score guard (exists); score history diff | republish prior score record from `gs://sector-brain-history/scores/` (or recompute at prior commit) | score history (new) |
| Control plane | Ops; orchestrator health | redeploy prior orchestrator (`5fd727ef` documented), `--legacy-execution`, or remove `/control/orchestratorV1` per its runbook | existing runbook |
| Whole-database accident (bad script, console mistake) | anomaly / Michael | restore affected **subtree** from latest RTDB export with a reviewed PATCH (never whole-DB import while writers run); then republish affected Brains from canonical | daily RTDB exports (new) |
| Research store accident | — | bucket object versioning / git history | versioning (new) |

**Runtime versions retained in RTDB: none.** One current version per path. History lives in GCS where it is cheap, immutable and does not affect read shapes. Copying old RTDB JSON back is a last resort only for the whole-database case; for everything else the canonical rollback is *republish from a canonical revision*.

## 3. RTDB export (backup) requirement
Before **any** structural change (and from now on, daily): `GET /.json?format=export` per top-level path (or a full export) with the Engine identity → `gs://sector-brain-history/rtdb-exports/{YYYY-MM-DD}/{path}.json` + `INDEX.json` (path, bytes, child counts, sha256). Read-only for the database; ≈ 10 MB/day. This bucket prefix is private and is excluded from the public repo; exports contain per-lake presence.
