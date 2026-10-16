# Sector Engine — Jobs, Schedules & Cloud Cost Audit (2026-10-13)

**Mode:** READ-ONLY. Nothing was deployed, scheduled, paused, configured, written to Firebase, committed or
pushed. This file is an uncommitted working-tree document. Project `sector-9393c`, region `us-central1`.
Evidence sources: Cloud Scheduler / Cloud Run / Artifact Registry / GCS via `gcloud` (describe/list only),
Cloud Monitoring time series (last 7 / 14 / 30 days), the BigQuery billing export, the Brain RTDB
(`sector-brain`, GET only), the Sector repos, and job code on `main` (tag `consolidation/2026-10-12`).
Cost figures are **ESTIMATES = measured usage × Google list prices** unless marked ACTUAL.

---

## EXECUTIVE SUMMARY

| | |
|---|---|
| Total workloads inventoried | **18**: 6 Cloud Run jobs, 8 Cloud Run services (2 Engine, 5 Cloud Functions, 1 read service), 4 manual Brain publishers (no cloud job) — plus the platform publisher (manual) |
| Scheduled (Cloud Scheduler, ENABLED) | **5**: `wind-hourly`, `clarity-current-hourly`, `hydrology-hourly`, `water-temp-tva-archive` (hourly), `lake-surface-daily` (daily) |
| Paused | **1**: `clarity-candidate-shadow` |
| Manual | **6**: `lake-brain`, `water-temp-brain` (job defined in code, never deployed), `water-clarity-brain`, `biological-state`, `sector-intelligence`, `brain-scores` (platform publisher) |
| Event-driven | 5 Cloud Functions (`conditions`, `playnotifications` (Pub/Sub), `appstorenotifications`, `adminlistusers`, `tournamentpage`) + `wind-candidate-read` (HTTP, master-only) |
| PRODUCTION | `sector-engine` service, the 5 Cloud Functions |
| INTERNAL | `water-temp-tva-archive`, all 6 Brain publishers, `brain-scores`, `wind-candidate-read` |
| RESEARCH | `clarity-current-hourly`, `hydrology-hourly`, `lake-surface-daily` (Clarity Fusion Stage 3–5 pipeline; nothing a customer sees reads their output), Wind candidate ingestion |
| SHADOW | `clarity-candidate-shadow` (paused) |
| **Measured recent cloud cost** | **Unavailable.** The BigQuery billing export (`billing.gcp_billing_export_*`) **stopped on 2026-09-09**; its last 30 exported days show Cloud Run $0.33 (fully credited by the free tier) — before min-instances, jobs and the Clarity Fusion deploys existed. Budget API not enabled. |
| **Estimated current monthly run-rate** | **~$55–75 / month after the 10-12 change; it was ~$110–140 / month from 09-29 to 10-11** (Cloud Run only; everything else is at or near $0). Detail in COST ANALYSIS. |
| **Top 5 cost drivers** (measured usage) | 1) `sector-engine` **idle minimum instances on 0 %-traffic tagged revisions** (`00044-b6m`/`fusion`, `00071-cuw`/`clarity`): ~315 of the last 7 days' 446 instance-hours; 2) `sector-engine` serving revision min instance + request CPU (p50 latency **8.5 s**, ~4,700 req/day); 3) `lake-surface-daily` (8 tasks × 4 vCPU / 16 GiB daily: 67 vCPU-h + 271 GiB-h per week); 4) `hydrology-hourly`; 5) `wind-hourly` (≈ $0.80 / month — **not** the cost driver). |
| **Top 5 scheduling inefficiencies** | 1) `clarity-current-hourly` rebuilds a Stage-5 "world" every hour that no customer path reads; 2) `lake-surface-daily` boots 8 × 4 vCPU / 16 GiB tasks daily although Sentinel-2 revisits a lake only every 2–3 days and the job already knows (`newest_pass_date`) when nothing is new; 3) `hydrology-hourly` runs hourly for a single lake feeding an endpoint iOS never calls; 4) `wind-hourly` polls RTMA-RU/METAR hourly although it only ever publishes the newest NBM cycle (hourly) — fine on cadence, but it carries no "no new cycle → stop" short-circuit; 5) two Brains that matter to freshness (Lake, Water Temp) have **no schedule at all** while research pipelines run hourly. |
| **Biggest unexplained cost — now explained** | The Ops "446.9 server-hours" = the 7-day sum of `sector-engine` billable instance time (measured 445.8 h). Three revisions with `minScale: 1` were simultaneously warm from 10-08 to 10-11 (72 h/day): the serving revision plus two tagged 0 %-traffic revisions. Before 10-07: two warm revisions (48 h/day). Since the 10-12 redeploy only one warm revision remains (52.4 h on the partial day; ~30 h/day expected). |

---

## REAL CLOUD STATE (verified 2026-10-13 ~04:10 UTC)

**Is `wind-hourly` actually paused? — NO.** Cloud Scheduler `wind-hourly` is **ENABLED**, cron `5 * * * *` UTC, last attempt **2026-10-13T04:05:03Z**, next `scheduleTime` 05:05Z. The Cloud Run job executed at 04:05Z (199 s, success) and every hour before it (148/148 executions successful since 10-07). Michael's intended pause **did not take effect** (or was applied to something else). The RTDB (`/health/jobs/wind-hourly`, `/brains/wind.publishMode = scheduled`) says SCHEDULED/HEALTHY — which is currently *accurate*. **Not changed.**

**What is actually ENABLED:** `wind-hourly` (hourly), `clarity-current-hourly` (hourly :40), `hydrology-hourly` (hourly :15), `water-temp-tva-archive` (hourly :20), `lake-surface-daily` (daily 03:00 America/Chicago). **PAUSED:** `clarity-candidate-shadow` (daily 07:00 CT, paused 2026-10-02). No Cloud Scheduler jobs exist in any other region.

**Cloud Run services that cannot scale to zero:** only **`sector-engine`** — service template `minScale: 1` (2 vCPU / 1 GiB, concurrency 1, timeout 60 s, CPU throttled outside requests = request-based billing, startup-cpu-boost). Every other service (`wind-candidate-read`, the 5 functions) has no min instances and scales to zero.

**Minimum instances that exist:** `sector-engine` serving revision `00080-wes` (minScale 1). Historical revisions `00077`, `00072`, `00071`, `00070`, `00067`, `00066`, `00051`, `00050`, `00044` all carry `minScale: 1` in their annotations; a revision's min instance is only kept while the revision is routable (traffic % or a tag).

**Tagged revisions that consumed resources:** until the 10-12 redeploy the tags were `fusion` → `00044-b6m` (4 vCPU / 2 GiB, minScale 1) and `clarity` → `00071-cuw` (4 vCPU / 2 GiB, minScale 1). Monitoring shows `00071-cuw` **idle 1.00 instance for 11 straight days** and `00044-b6m` idle ~1.0 after it stopped serving on 10-07 — 157.8 h + 157.4 h billable in the last 7 days with ~0 and 4.5 vCPU-h of actual CPU allocation. Today the tags point to `00078-kuv` (`clarity`) and `00079-zab` (`fusion`), **which have no minScale annotation** → they now consume nothing while idle (instance_count 0.67 on 10-12 only, from the deploy's probing). Both remain **publicly invokable** (`allUsers`) at their tag URLs.

**What caused the server-hours:** `minScale: 1` × (number of routable revisions). Daily billable hours: 48.0–48.3 h/day 09-29→10-06 (2 warm), 56.6 h on 10-07 (3 from 19:50Z), **72.1–72.3 h/day 10-08→10-11 (3 warm)**, 52.4 h on 10-12 (back to 1 after the redeploy re-tagged). Request traffic (36,427 requests / 7 d, p50 8.5 s) accounts for only ~27 vCPU-h of CPU in 7 days; the rest is idle warm time.

---

## MATRIX A — CURRENT EXECUTION

| Workload | Owner | Class | Purpose | Mode | Current cadence | Enabled? | Last run (UTC) | Avg runtime (MEASURED) | Source cadence | Freshness requirement | Runtime type | Scale-to-zero? | Est. monthly run (runs) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `wind-hourly` (job) | Wind | RESEARCH (candidate ingest) + INTERNAL (WindBrain publish) | fetch NBM/RTMA-RU/METAR → `gs://sector-wind-candidate`; publish WindBrain to RTDB | SCHEDULED | hourly :05 | **YES (ENABLED)** | 10-13 04:05 | 223 s (148 runs, 0 fail) | NBM hourly cycles (qmd at 00/06/12/18Z); RTMA-RU 15 min; METAR hourly | Brain `staleAfterHours` 1.5; forecast cycle ≤ 3 h | Cloud Run job 1 vCPU / 2 GiB | n/a (job) | 720 |
| `clarity-current-hourly` (job) | Water Clarity | RESEARCH (Stage 5) | ClarityPrecompute: prepared clarity "world" per lake → `gs://sector-lake-surface/clarity/current/*` | SCHEDULED | hourly :40 | YES | 10-13 03:40 | 140 s (200/200 ok) | derived from `hydrology-hourly` (hourly) + lake-surface passes (days) | none customer-facing; read only by fusion-lineage server code / iOS feature worktrees | job 2 vCPU / 2 GiB | n/a | 720 |
| `hydrology-hourly` (job) | Water Clarity (hydrology) | RESEARCH/INTERNAL | MRMS Pass-2 rain per arm + USGS flows + TVA for **Guntersville only** → `hydrology/<slug>/hourly/<date>.json` | SCHEDULED | hourly :15 | YES | 10-13 03:15 | 196 s (200/200 ok) | MRMS Pass 2 hourly (~2 h lag); USGS IV 15–60 min; TVA hourly | feeds prod `/clarity/state` (iOS never calls it) and Stage-5 | job 1 vCPU / 2 GiB | n/a | 720 |
| `water-temp-tva-archive` (job) | Water Temp / Lake | INTERNAL | archive TVA observed/predicted discharge for 4 dams (TVA keeps only today) → `gs://sector-water-temp-archive` | SCHEDULED | hourly :20 | YES | 10-13 03:20 | 131 s (144/145 ok) | TVA hourly rows; API retains ~24 h | archive must not miss a day; Lake Brain reads it | job 1 vCPU / 512 MiB | n/a | 720 |
| `lake-surface-daily` (job) | Water Clarity (satellite) | RESEARCH/INTERNAL | Sentinel-2 L2A clarity products for 599 lakes (+ Stage-4 cells/anchors/NDCI for Guntersville) → `gs://sector-lake-surface/lakes/*` | SCHEDULED | daily 03:00 CT | YES | 10-12 08:00 | **74–87 min wall** (8 parallel tasks; 19 ok / 4 failed of 21) | Sentinel-2 revisit 2–3 days per lake; STAC query first | Clarity Brain satellite evidence (manual); `staleThresholdHours` 336 | job **8 × 4 vCPU / 16 GiB** | n/a | 30 |
| `clarity-candidate-shadow` (job) | Water Clarity (private research) | SHADOW | frozen Stage 16/17 shadow on new passes → `gs://sector-clarity-candidate` | **DISABLED (paused)** | daily 07:00 CT | NO | 10-02 (1 run, **failed 17/17**) | 719 s | passes | none | job 17 × 2 vCPU / 8 GiB | n/a | 0 |
| `sector-engine` (service) | Shared / Conditions Score | **PRODUCTION** | `/conditions`, `/conditions/batch`, `/lakes`, `/health` for iOS+Android | EVENT_DRIVEN (HTTP) | continuous | YES | serving | p50 8.5 s, p95 18.8 s; ~4,700 req/day (8,101 on 10-12) | Open-Meteo/USGS/TVA/CWMS per request | customer: live render | service 2 vCPU / 1 GiB, **minScale 1**, max 30, conc 1 | **NO** | — |
| `wind-candidate-read` (service) | Wind | INTERNAL (master-only) | serve `latest/<lake>.json.gz` to 3 master UIDs | EVENT_DRIVEN | on request | YES | 4 req / 7 d | — | — | — | 1 vCPU / 512 MiB, max 2 | yes | — |
| `conditions`, `appstorenotifications`, `adminlistusers`, `tournamentpage` (functions) | Other (app backend) | PRODUCTION | Firebase Functions (Node) | EVENT_DRIVEN | on request | YES | 2–8 req / 7 d | — | — | — | 1 vCPU / 256 MiB | yes | — |
| `playnotifications` (function) | Other | PRODUCTION | Pub/Sub trigger | EVENT_DRIVEN | on message | YES | — | — | — | — | 1 vCPU / 256 MiB | yes | — |
| `lake-brain` (manual) | Lake | INTERNAL | 5 pilot lakes: level state/profile/presence → RTDB + `gs://sector-lake-brain` | MANUAL | none | — | 10-12 23:46 (7.8 s) | 7.8 s (RTDB health) | TVA/CWMS/USGS hourly | `staleAfterHours` 3 → **stale now** | local `swift run LakeBrainJob` | — | 0 |
| `water-temp-brain` (manual; job script exists, not deployed) | Water Temp | INTERNAL | 621-lake water-temp states → RTDB | MANUAL (ran once) | none (`deploy-job.sh` would be every 3 h at :25) | — | 10-12 06:40 (261 s) | 261 s | USGS/CWMS sensors 15–60 min; Open-Meteo hourly | `staleAfterHours` 6 → **stale now** | would run from the serving image | — | 0 |
| `water-clarity-brain` (manual) | Water Clarity | INTERNAL | mirror `/conditions` clarity for 621 lakes → RTDB (**621 production `/conditions` calls, concurrency 2**) | MANUAL (ran once) | none | — | 10-12 06:52 (**27.3 min**) | 1,640 s | its own inputs are hourly/daily | `staleAfterHours` 26 | local Python | — | 0 |
| `biological-state` (manual) | Biological | INTERNAL | species knowledge bundle → `/species` | MANUAL | version-driven | — | 10-13 03:56 (7.6 s) | 7.6 s | research releases | VERSION (never by age) | local Python | — | 0 |
| `sector-intelligence` (manual) | Sector Intelligence | INTERNAL | registry/dependencies + 5 pilot evaluations | MANUAL | fingerprint-driven | — | 10-13 03:56 (6.4 s) | 6.4 s | upstream Brain publishes | FINGERPRINT | local Python | — | 0 |
| `brain-scores` (manual) | Shared Platform | INTERNAL | scores, Engine score, `/control/*` | MANUAL | none | — | 10-13 03:58 | ~10 s | published Brain facts | n/a | local Python | — | 0 |

Scheduler run arithmetic (reporting only): hourly = 24/day, 168/week, ~720/month; daily = 1/7/30.

---

## MATRIX B — DEPENDENCY / VALUE

| Workload | Input | Output | Upstream | Downstream | Customer-facing? | Brain publisher? | Required? | Duplicate? | Can detect source change? |
|---|---|---|---|---|---|---|---|---|---|
| `wind-hourly` | NOAA NBM (NODD S3), RTMA-RU, IEM METAR, fetch tables in `gs://sector-wind-candidate/fetch` | `wind/v1/*` archive + ledger; RTDB wind slot for 4 lakes | — (Lake geometry generated in the iOS repo, static) | WindBrain → Intelligence pilot; `wind-candidate-read` | **no** (production wind = Open-Meteo inside `/conditions`) | yes | for the candidate research + WindBrain state only | fetches Open-Meteo? no; but **production `/conditions` fetches wind separately per request** (two wind sources by design) | **yes** — NBM objects are keyed by cycle init; the run ledger records completed cycles (catch-up logic exists) |
| `hydrology-hourly` | MRMS Pass-2 accumulations, USGS IV flows, TVA 48 h (Guntersville) | `hydrology/Guntersville_AL/hourly/*`, `rain/*/catchments.json` | `scripts/hydrology` graph + weights (deploy-copied) | `clarity-current-hourly`; prod `ClarityStateLoader` (`/clarity/state`, **not called by iOS**) | no | no | only for Stage 3–5 research | **TVA observed-data is fetched by this job, by `water-temp-tva-archive`, by Lake Brain and by production** (4 fetchers of the same endpoint) | yes (MRMS hourly product timestamps) |
| `clarity-current-hourly` | hydrology outputs, lake-surface arms/cells, Engine Stage-5 code (image `03937913`) | `clarity/current/<slug>/{world,composite,changes}` | `hydrology-hourly`, `lake-surface-daily` | fusion-lineage server routes (0 % traffic), iOS `feat/clarity-*` worktrees | no | no | **no** (research/shadow) | recomputes every hour even when hydrology hasn't changed? it runs whether or not inputs changed | partially (inputs are hourly files; no change check) |
| `lake-surface-daily` | Earth Search STAC (Sentinel-2 L2A), lake polygons | `lakes/<slug>/clarity/*` (latest, history, PNGs, cells/arms for Guntersville) | — | Water Clarity Brain satellite evidence; `clarity-current-hourly`; prod reads `arms/latest.json` **which nothing writes** | no | no | for Clarity Brain satellite evidence (manual) | — | **yes** — `newest_pass_date()` STAC query per lake before any heavy read; lakes "up to date" are skipped (but the 8 tasks still boot) |
| `water-temp-tva-archive` | TVA RestApi observed/predicted (4 dams) | `water-temp/tva/*` daily records | — | Lake Brain history (shared, read-only) | no | no | yes (TVA discards history) | TVA endpoint also fetched by hydrology, Lake Brain, production | yes (hour keys; idempotent, never overwrites) |
| `sector-engine` `/conditions` | Open-Meteo, USGS IV, TVA, CWMS, SWPA, APC, NWS alerts, MRMS/IEM rain, lake-surface hydrology | render JSON | — | customers | **YES** | no (reads no Brain) | yes | computes level/temp/clarity/wind itself (documented adapters) | n/a (per request) |
| `lake-brain` | TVA, CWMS, USGS (reviewed bindings), `gs://sector-water-temp-archive`, presence bundle | `lakes/{k}/brain|states/lake|speciesPresence`, fleet row, history/baselines | `water-temp-tva-archive` | Intelligence pilot; Ops | no | yes | yes (freshness blocker for beta) | own TVA/CWMS/USGS fetchers (duplicate of production's) | yes (`sourceObservationAt`, `nextCheckAt`, `plan()`) |
| `water-temp-brain` | production fetchers (USGS/CWMS sensors, Open-Meteo) | `lakes/{k}/states/waterTemp`, fleet | — | Intelligence pilot; Ops | no (customers get the same numbers from `/conditions`) | yes | yes (freshness blocker) | **recomputes the same resolver production already runs per request** | partial (sensor timestamps yes; model forcing = Open-Meteo hourly) |
| `water-clarity-brain` | production `/conditions` ×621, lake-surface `latest.json`+meta | `lakes/{k}/states/waterClarity`, sources, registry | `lake-surface-daily` | Intelligence pilot; Ops | no | yes | yes | **621 production renders per publish** (load on the customer service) | partial (lake-surface run records yes; `/conditions` no) |
| `biological-state` | private bundle `gs://sector-biology-private` | `/species/*`, registry | — | Intelligence pilot; Ops | no | yes | yes | — | yes (bundle sha/version; `plan()`) |
| `sector-intelligence` | `/brains`, `/health`, `/validation`, `/lakeFleet`, pilot snapshots, `/species`, presence, Cloud Run describe, Engine `/lakes` | registry, 621 states (5 evaluated), fleet slots | all 5 Brains | Ops; (future customers) | no | yes | yes | — | yes (fingerprint) |
| `brain-scores` | all of the above (RTDB) | `/scores/*`, `/control/*` | all Brains | Ops | no | platform | yes | — | n/a |

**Duplicate fetches:** TVA observed-data (4 fetchers: production per request, `hydrology-hourly`, `water-temp-tva-archive`, Lake Brain); USGS IV (production per request, Lake Brain, Water Temp Brain, hydrology); Open-Meteo (production per request ×4,700/day, Water Temp Brain, Wind candidate's bake-off). **Duplicate computation:** Water Temp Brain re-runs the production resolver for 621 lakes; Clarity Brain re-renders 621 production `/conditions`. **Duplicate storage:** none significant (buckets: lake-surface 0.35 GB, wind 0.04 GB, clarity-candidate 29 GB research, run-sources 0.84 GB, Artifact Registry **5.0 GB** of old images). **Unnecessary cascades:** `hydrology-hourly → clarity-current-hourly` every hour for a product nobody reads.

---

## MATRIX C — COST RISK

Rates used (us-central1 Tier 1 list prices, **ESTIMATE**; confirm in the console): services request-based CPU $0.000024 / vCPU-s, memory $0.0000025 / GiB-s; idle min-instance CPU $0.0000025 / vCPU-s, memory $0.00000025 / GiB-s; jobs CPU $0.000018 / vCPU-s, memory $0.000002 / GiB-s; Cloud Scheduler 3 jobs free then $0.10 / job-month; free tier 180k vCPU-s + 360k GiB-s / month (not applied below).

| Workload | Service/job | CPU | Memory | Min inst. | Runs/month | Runtime/month (MEASURED basis) | Measured cost | Estimated monthly cost | Risk | Reason |
|---|---|---|---|---|---|---|---|---|---|---|
| `sector-engine` idle warm revisions (pre-10-12) | service | 4 | 2 GiB | 1 each × 2–3 revisions | continuous | ~1,900 idle instance-h/month (48–72 h/day measured) | n/a (export stale) | **~$70–75** idle (CPU $0.036/h + mem $0.0018/h per 4-vCPU instance) | **CRITICAL (historical)** | `minScale: 1` kept on 0 %-traffic tagged revisions; resolved by the 10-12 re-tag, **not by any explicit decision** — will recur the next time a revision with minScale is tagged |
| `sector-engine` serving (post-10-12) | service | 2 | 1 GiB | 1 | continuous | ~720 idle instance-h + ~55 active vCPU-h/month (27 vCPU-h / 7 d measured at 4 vCPU; halves at 2 vCPU) | n/a | **~$14 idle + ~$6 CPU + ~$6 memory ≈ $25–30** | MEDIUM | min instance is a deliberate latency choice (p50 is already 8.5 s); concurrency 1 means every concurrent render is an extra instance |
| `lake-surface-daily` | job | 4 × 8 tasks | 16 GiB × 8 | — | 30 | 67.4 vCPU-h + 270.7 GiB-h per 7 d measured → ~290 vCPU-h + 1,160 GiB-h / month | n/a | **~$27** (CPU $19 + mem $8) | **HIGH** | research pipeline; 16 GiB × 8 daily for a source that changes every 2–3 days; 4 of 21 executions failed |
| `hydrology-hourly` | job | 1 | 2 GiB | — | 720 | 1.9 vCPU-h + 3.9 GiB-h / 7 d → ~8 + 17 / month | n/a | ~$0.60 | LOW (cost) / MEDIUM (purpose) | cheap, but feeds nothing customer-visible |
| `wind-hourly` | job | 1 | 2 GiB | — | 720 | 2.5 vCPU-h + 5.3 GiB-h / 7 d → ~11 + 23 / month | n/a | **~$0.80** | LOW | **not the cost problem**; still running although believed paused |
| `clarity-current-hourly` | job | 2 | 2 GiB | — | 720 | 1.7 vCPU-h + 1.7 GiB-h / 7 d → ~7 + 7 / month | n/a | ~$0.50 | LOW (cost) / HIGH (purpose) | hourly compute for an unread product |
| `water-temp-tva-archive` | job | 1 | 512 MiB | — | 720 | 0.5 vCPU-h / 7 d → ~2 / month | n/a | ~$0.15 | LOW | justified by TVA's retention |
| `clarity-candidate-shadow` | job | 2 × 17 tasks | 8 GiB × 17 | — | 0 (paused) | 0 | n/a | $0 while paused; **~$2–3 per run** if resumed (17 × 2 vCPU × 12 min) | MEDIUM if resumed | its only execution failed 17/17 |
| `wind-candidate-read` + 5 functions | services | 1 | 256–512 MiB | 0 | on request | negligible (≤ 8 req / 7 d) | n/a | ~$0 | LOW | scale to zero |
| Cloud Scheduler | — | — | — | — | 6 jobs | — | n/a | ~$0.30 (3 free) | LOW | |
| Artifact Registry | 5.0 GB images | — | — | — | — | — | n/a | ~$0.50 | LOW | 50+ old `sector-engine` images retained |
| Cloud Storage | 31 GB (29 GB private Clarity research) | — | — | — | — | — | n/a | ~$0.70 | LOW | |
| Firebase RTDB (`sector-brain`) | — | — | — | — | — | ~1 MB per Intelligence publish; 622-path control writes | n/a (Sept export: $0.00) | ~$0 at current volume | LOW | Ops subscriptions are the only reads |
| Manual Brain publishers | local | — | — | — | 0 | — | — | $0 (run on Michael's machine) | LOW | the Clarity publish loads production with 621 renders |

**Estimated totals:** 09-29 → 10-11 ≈ **$110–140 / month run-rate** (dominated by idle warm revisions); since 10-12 ≈ **$55–75 / month** (serving min instance + request CPU ≈ $30, jobs ≈ $30, storage/registry/scheduler ≈ $2). Free-tier credits (worth up to ~$2.1 CPU + $0.9 memory / month) and any committed discounts are not applied. **No actual invoice data for this period is available to this audit.**

---

## BRAIN-BY-BRAIN

### Lake Brain
- **Current schedule:** none (manual `swift run LakeBrainJob`); last run 10-12 23:46; `staleAfterHours` 3 → **stale**; registry lacks `schedule`/`stalenessModel`/`dependsOn` until republished (on `main` they are set: TIME, manual, []).
- **Supporting jobs:** `water-temp-tva-archive` (shared TVA history, read-only); its own GCS history/baselines.
- **Source cadence:** TVA observed-data-48-hours hourly (lag ~60 min; midnight guide daily), CWMS hourly (Hartwell; lag ~120 min; feed was silent 10-08), USGS IV 15–60 min. Bindings record `cadenceMin`/`lagMin` per source.
- **Freshness:** per-state envelope with `freshUntil` (+3 h), `nextCheckAt` (e.g. "scheduled: stable lake, 2 h"), `sourceObservationAt`; `plan()` says PUBLISH when `nextCheckAt` reached, state stale, binding/version changed.
- **Dependencies:** upstream none (reads the TVA archive opportunistically); downstream Intelligence pilot, beta readiness (blocker today), Ops.
- **Average runtime:** 7.8 s for 5 lakes (RTDB health).
- **Cost characteristics:** negligible compute; would need a Cloud Run job (no image/job exists; LakeBrainJob is not built into the serving image).
- **Scheduling constraints:** TVA hourly rows arrive ~1 h late; the brain's own `nextCheckAt` adapts (stable lake → 2 h). Single-flight exists in-process.
- **Optimization category:** candidate for **conditional refresh driven by `nextCheckAt`** (the brain already computes it) rather than a fixed cron; source-change detection = TVA `lastObservationAt`.

### Water Temperature Brain
- **Current schedule:** none; ran once (10-12 06:40, 261 s for 621 lakes); `staleAfterHours` 6 → **stale**. The job script targets every 3 h at :25 UTC — never deployed (D9).
- **Supporting jobs:** none required (uses production fetchers in-process); the TVA archive is not an input.
- **Source cadence:** USGS/CWMS lake sensors 15–60 min; Open-Meteo forcing refreshes hourly (model), the brain's value is a lake-local **daily** model value plus a sensor when ≤ 6 h old.
- **Freshness:** TIME, 6 h; `evidenceStale` when a configured sensor has no fresh reading; no `nextCheckAt` published yet (on `main` the descriptor says "sensor newer reading / state older than 6 h").
- **Dependencies:** none upstream; downstream Intelligence pilot, beta (blocker), Ops.
- **Cost characteristics:** ~4.4 min of 2 vCPU per run (ESTIMATE from the one run) ≈ $0.01 / run; at every 3 h ≈ **$2–3 / month**; the external fetch fan-out (621 lakes × USGS/CWMS/Open-Meteo) is the real constraint, not cloud cost.
- **Scheduling constraints:** production already computes the same resolver per customer request — the Brain's publication is for Ops/Intelligence, not customers.
- **Optimization category:** **duplicate computation** of production; candidate for sensor-timestamp-driven refresh (only lakes whose sensor posted a newer reading, plus a daily model pass).

### Water Clarity Brain
- **Current schedule:** none; ran once (10-12 06:52, **27.3 min**, 621 production `/conditions` calls at concurrency 2); `staleAfterHours` 26.
- **Supporting jobs:** `lake-surface-daily` (satellite evidence, daily), `hydrology-hourly` + `clarity-current-hourly` (Stage 3–5 research; the Brain does not read `clarity/current`).
- **Source cadence:** production clarity inputs change hourly (rain decay, USGS turbidity); Sentinel-2 every 2–3 days per lake (`staleThresholdHours` 336 = 14 d).
- **Freshness:** TIME 26 h; satellite freshness 14 d; `stale_carry` for missed lakes.
- **Dependencies:** upstream `lake-surface-daily` (and production `/conditions`); downstream Intelligence pilot, Ops.
- **Cost characteristics:** the publish itself is free (local) but **puts 621 cold renders on the production service** (each ~8 s at concurrency 1 → spins instances; this is customer-facing capacity).
- **Scheduling constraints:** must never run during customer peak; must not be hourly.
- **Optimization category:** **mirror, not source** — candidate for publishing clarity from inside the Engine (the render already computes it) instead of re-rendering 621 lakes; satellite evidence should follow `lake-surface-daily` run records (event-driven).

### Wind Brain
- **Current schedule:** hourly (`wind-hourly`, **ENABLED**), 223 s avg, 1 vCPU / 2 GiB ≈ **$0.80 / month**; `staleAfterHours` 1.5; `publishMode: scheduled`.
- **Supporting jobs:** none; `wind-candidate-read` serves the archive to 3 master UIDs (4 requests / week).
- **Source cadence (from `ingest.py`):** NBM publishes a cycle **every hour** (v5.0 since 2026-05-05; `qmd` percentiles only at 00/06/12/18Z); RTMA-RU every 15 min; METAR hourly via the IEM archive. The job ingests the newest cycle and the last hour of RTMA-RU + METAR; a ledger records completed cycles and a catch-up path fills gaps.
- **Freshness:** TIME 1.5 h (state) and forecast cycle ≤ 3 h; `stale`/`staleReasons` published.
- **Dependencies:** upstream none (frozen fetch geometry generated in the iOS repo, copied to GCS); downstream Intelligence pilot, Ops.
- **Cost characteristics:** cheap; the perceived "Wind cost" was the warm `sector-engine` revisions, not this job.
- **Scheduling constraints:** 4 live lakes only; production wind is unaffected either way.
- **Optimization category:** cadence matches the hourly NBM cycle; candidate for a **"no new cycle → exit early" check** (the S3 object name encodes the cycle) and for skipping RTMA-RU/METAR when no consumer needs sub-hourly values.

### Biological Brain
- **Current schedule:** none; version-driven (`stalenessModel: VERSION`); last publish 10-13 03:56 (7.6 s).
- **Source cadence:** research releases (`biology/v1/latest.json` pointer + sha). **No recurring compute is needed**: `plan()` already says SKIP unless the bundle version/manifest changes.
- **Dependencies:** none upstream; downstream Intelligence (presence ∩ knowledge), Ops.
- **Optimization category:** **should never need a timer** — republish on bundle change (a GCS object-change notification or a manual run after research).

### Sector Intelligence
- **Current schedule:** none; fingerprint-driven; last publish 10-13 03:56 (6.4 s; 5 pilot evaluations, ~1 MB write).
- **Source cadence:** upstream Brain publishes (any of 5) + serving revision + catalog.
- **Freshness:** FINGERPRINT (inputs' `generatedAt`/status); per-lake evaluations carry degraded inputs honestly.
- **Dependencies:** all 5 Brains upstream (`dependsOn` published); downstream Ops, beta readiness.
- **Optimization category:** **reactive, not cron** — run when the fingerprint changes (today that means after any Brain publish); the Orchestrator plan() already expresses this.

---

## SUPPORTING JOBS (non-Brain)

| Job | Verdict |
|---|---|
| `hydrology-hourly` | Single-lake (Guntersville) hourly MRMS/USGS/TVA record. Its consumer in production is `/clarity/state`, which iOS does not call; its other consumer is Stage-5 research. Cadence matches MRMS (hourly, 2 h lag). Cheap ($0.60/mo). Purpose should be decided with D4. |
| `clarity-current-hourly` | Rebuilds the Stage-5 clarity world hourly from `03937913` (not on `main`); nobody customer-facing reads `clarity/current/*`. Cheap ($0.50/mo) but pure research compute on a schedule. Candidate for manual/event-driven or retirement (D4). |
| `lake-surface-daily` | The dominant job cost (~$27/mo) and the only job with failures (4/21). Already checks `newest_pass_date` per lake before heavy work; the fixed cost is booting 8 × 4 vCPU / 16 GiB tasks daily. Sentinel-2 revisit is 2–3 days; a pass-availability-driven trigger (Earth Search STAC) would cut boots roughly by half or more. Its outputs feed only the Clarity Brain's satellite evidence (manual) and the unread `arms/latest.json`. |
| `water-temp-tva-archive` | Justified: TVA discards history; hourly polling guards the ~24 h retention window with margin. Could be 2–4×/day safely if the retention claim ("only today's hours") holds — the archiver never overwrites, so sparser polling only risks gaps, not corruption. |
| `clarity-candidate-shadow` | Paused since 10-02 after a 17/17-task failure. If resumed as configured: 17 tasks × 2 vCPU / 8 GiB. Private research. Leave paused unless the Clarity research decision (D4) revives it. |
| `wind-candidate-read` | Scale-to-zero service; 4 requests/week; costs ~$0. |
| Cloud Functions (5) | App backend; scale-to-zero; negligible traffic. |

---

## DEPENDENCY GRAPH (source → job → Brain → Intelligence)

```
NOAA NBM (hourly cycles) ─┐
RTMA-RU (15 min) ─────────┼─ wind-hourly (hourly, ENABLED) ──► gs://sector-wind-candidate ──► WindBrain (in-job) ──┐
IEM METAR (hourly) ───────┘                                                      └──► wind-candidate-read (masters) │
                                                                                                                      │
MRMS Pass-2 (hourly, ~2 h lag) ─┐                                                                                     │
USGS IV flows (15–60 min) ──────┼─ hydrology-hourly (hourly) ──► hydrology/Guntersville_AL/* ─┬─► clarity-current-hourly (hourly) ─► clarity/current/* (unread)
TVA observed (hourly) ──────────┘                                                              └─► prod /clarity/state (iOS never calls)
                                                                                                                      │
Sentinel-2 L2A via Earth Search (2–3 d revisit) ─ lake-surface-daily (daily, 8×4 vCPU) ─► lakes/<slug>/clarity/* ─┬─► Water Clarity Brain (manual) ──┤
                                                                                                                  └─► clarity-current-hourly         │
prod /conditions ×621 (manual, 27 min) ──────────────────────────────────────────────────────────► Water Clarity Brain ───────────────────────────────┤
                                                                                                                      │
TVA observed/predicted (hourly; ~24 h retention) ─ water-temp-tva-archive (hourly) ─► gs://sector-water-temp-archive ─► Lake Brain (manual) ───────┤
TVA/CWMS/USGS pools (hourly) ──────────────────────────────────────────────────────────────────────► Lake Brain ─► speciesPresence ─┐             │
                                                                                                                                     ├─► Sector Intelligence (manual, fingerprint) ─► /control, beta readiness ─► Ops
USGS/CWMS lake sensors + Open-Meteo (hourly) ──────────────────────────────────────────────────────► Water Temp Brain (manual) ──────┤
Research bundle (gs://sector-biology-private, on release) ─────────────────────────────────────────► Biological Brain (manual) ──────┘

Customers: iOS/Android ─► sector-engine /conditions (per request: Open-Meteo, USGS, TVA, CWMS, SWPA, APC, NWS, MRMS/IEM) — reads NO Brain.
```

---

## COST ANALYSIS — measured vs estimated

**Measured (Cloud Monitoring):**
- `sector-engine` billable instance time: last 7 d **445.8 h** (`00044-b6m` 157.8, `00071-cuw` 157.4, `00072-way` 120.1, `00080-wes` 10.4, `00077-diw` 0.1); last 30 d ≈ 1,145 h. Daily: 48 h/day (09-29→10-06), 56.6 (10-07), 72 h/day (10-08→10-11), 52.4 (10-12).
- `sector-engine` CPU allocation (actual CPU time billed at the active rate): **27 vCPU-h / 7 d**, 121 vCPU-h / 30 d; memory 251 GiB-h / 7 d. Requests 36,427 / 7 d; p50 8.5 s, p95 18.8 s.
- Jobs CPU allocation / 7 d: `lake-surface-daily` 67.4 vCPU-h + 270.7 GiB-h; `wind-hourly` 2.5 + 5.3; `hydrology-hourly` 1.9 + 3.9; `clarity-current-hourly` 1.7 + 1.7; `water-temp-tva-archive` 0.5 + 0.3.
- Instance counts: `00071-cuw` idle 1.00 for 11 days; `00044-b6m` idle 0.57 / active 0.64 (14-day means); `00072-way` active 1.09 / idle 0.38 while serving.

**Actual billing:** the export's last row is 2026-09-09 (Cloud Run $0.33, credited). **The expensive period (09-27 onward) is not in the export.** This audit cannot state an invoiced number; the console Billing report is the source of truth and should be compared with the estimates above.

**Assumptions:** list prices as stated in Matrix C; idle min-instance hours ≈ billable instance hours − active instance hours (active ≈ CPU allocation ÷ vCPU per instance); jobs are billed for allocated CPU/memory for the whole task duration; free tier and credits ignored; no network egress (Cloud Run egress to the apps was ~31 MB in the Sept window).

---

## OPS CONTRACT GAPS (`/jobs/{jobId}` — target contract)

`/jobs` does not exist in the RTDB; Ops reads `/health/jobs`. Fields present per record today (✓) vs target:

| Field | wind-hourly | clarity-current-hourly | hydrology-hourly | lake-surface-daily | water-temp-tva-archive | clarity-candidate-shadow | lake-brain | water-temp-brain | water-clarity-brain | biological-state | sector-intelligence | brain-scores |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| record exists | ✓ | ✓ | ✓ | ✓ | **✗** (live job, no RTDB record) | ✓ | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| jobId / displayName | ✓ | ✓ | ✓ | ✓ | — | ✓ | ✓ | ✓ | ✓ | — | — | — |
| owner (`brainId`) | ✗ | ✓ | ✓ | ✓ | — | ✓ | ✗ | ✗ | ✓ | — | — | — |
| purpose, environment, classification, executionMode | ✗ | ✗ | ✗ | ✗ | — | ✗ | ✗ | ✗ | ✗ | — | — | — |
| schedule (free text) / cron / timezone / enabled | text only / ✗ / ✗ / ✗ | text / ✗ / ✗ / ✗ | same | same | — | same | ✗ | text (never deployed) | ✗ | — | — | — |
| runtimeStatus (`status`) | ✓ | ✓ | ✓ | ✓ | — | ✓ | ✓ | ✓ | ✓ | — | — | — |
| lastStartedAt / lastCompletedAt / lastSuccessfulAt / lastFailedAt | lastRun+lastSuccess only | same | same | same | — | lastRun | same | same | same | — | — | — |
| nextScheduledAt | ✗ | ✗ | ✗ | ✗ | — | ✗ | ✗ | ✗ | ✗ | — | — | — |
| durationMs | ✓ | ✓ | ✓ | ✓ | — | ✗ | ✓ | ✓ | ✓ | — | — | — |
| service / revision / sourceVersion / modelVersion / deploymentStatus | ✗ | ✗ | ✗ | ✗ | — | ✗ | ✗ | ✗ | deploymentStatus only | — | — | — |
| brainPublishInJob | ✓ | ✗ | ✗ | ✗ | — | ✗ | ✗ | ✗ | ✗ | — | — | — |
| inputs / outputs / brainDependencies / statePaths | ✗ | ✗ | ✗ | ✗ | — | ✗ | ✗ | ✗ | ✗ | — | — | — |
| retryPolicy / freshnessPolicy | ✗ | ✗ | ✗ | ✗ | — | ✗ | ✗ | ✗ | ✗ | — | — | — |
| lastError / lastErrorAt / failureCount | latestError only | ✗ | ✗ | ✗ | — | latestError | ✗ | ✗ | ✗ | — | — | — |
| running | ✓ | ✓ | ✓ | ✓ | — | ✓ | ✓ | ✓ | ✓ | — | — | — |

Observations: the Clarity Brain writes job records for jobs it does not own (`hydrology-hourly`, `lake-surface-daily`, `clarity-current-hourly`, `clarity-candidate-shadow`) by reading the Cloud Run API, so those records are **stale when the Brain hasn't run** (they show 10-11/10-12 last runs while the jobs ran at 03:xx today). The `wind-hourly` record is written by the job itself and is current. `enabled`/`cron`/`nextScheduledAt` exist nowhere — the RTDB cannot tell Ops that a scheduler is paused (which is exactly the confusion in this incident).

---

## ORCHESTRATOR READINESS (planning inputs available today)

| Brain | stale Brain | dependency changed | source changed | nextCheckAt | recompute needed (own `plan()`) | do nothing | Verdict |
|---|---|---|---|---|---|---|---|
| Lake | yes (TIME 3 h; registry lacks `stalenessModel` until republish) | n/a (no upstream) | yes (`sourceObservationAt`, TVA/CWMS timestamps) | **yes** (published per state) | yes (`LakeBrainPlanner`) | yes | **READY** once it republishes the `main` registry fields (and has a runtime to execute) |
| Water Temp | yes (6 h) | n/a | partial (sensor timestamps; Open-Meteo forcing has no version) | no | no `plan()` (TIME only) | by age only | **PARTIAL** |
| Water Clarity | yes (26 h) | yes (lake-surface run records) | partial (`/conditions` has no version; `engineRevision` recorded) | no | no `plan()` | by age only | **PARTIAL** |
| Wind | yes (1.5 h) | n/a | yes (NBM cycle id in the ledger) | no (forecastGeneratedAt only) | no `plan()`; the job is the cron | by age only | **PARTIAL** |
| Biological | VERSION (never by age) | n/a | yes (bundle version/sha) | n/a | yes (`orchestration.plan`) | yes | **READY** |
| Sector Intelligence | FINGERPRINT | yes (dependency statuses, versions) | yes (inputs fingerprint) | n/a | yes (`plan`) | yes | **READY** |

The planning core (`sector_brain_platform.orchestrator.plan`) can already produce a correct plan from these inputs; what is missing is (a) the four Brains republishing `schedule`/`stalenessModel`/`dependsOn`, (b) `plan()` hooks for Water Temp / Clarity / Wind, (c) an executor — **not deployed (D10)**.

---

## WHAT SHOULD NEVER NEED A TIMER (categories, not decisions)

- **Biological knowledge:** version-driven already; a timer adds nothing. Trigger = research release.
- **Sector Intelligence:** fingerprint-driven; should react to upstream Brain publishes (or run as the last step of an orchestrated pass), never hourly.
- **Satellite Clarity (`lake-surface-daily`):** pass-availability-driven — Earth Search exposes acquisition dates; a cheap daily STAC check (seconds) could decide whether to boot the heavy tasks at all, instead of booting 8 × 4 vCPU / 16 GiB unconditionally.
- **Clarity Brain publish:** should follow `lake-surface-daily` run records for satellite evidence and should stop re-rendering 621 production lakes (publish from inside the render instead).
- **`clarity-current-hourly` / `hydrology-hourly`:** only exist for Stage-5 research; manual or event-driven if kept (D4).
- **Wind:** the hourly NBM cycle justifies hourly *checks*, but a "cycle already ingested → exit" guard would make missed/duplicate runs free.
- **Lake Brain:** its own `nextCheckAt` (2 h for a stable lake, sooner when moving) is a better clock than a cron.
- **Water Temp:** sensor-timestamp-driven per lake plus one daily model pass; the per-request production path already serves customers.

---

## GITHUB ACTIONS AUDIT

**No `.github/workflows` directory exists in any of the four repos** (`Sector_Engine` public, `iOS_Sector`, `Sector_Ops`, `Android_Sector` private) and no workflow runs exist. Nothing recurring on GitHub, nothing duplicating GCP work.

**Potential (not moved):** the pure, network-free work could run on free GitHub runners if ever desired — Swift/Python test suites on push, the conformance fixtures, `score_brains.py --dry-run`-style validations against exported snapshots, rubric/doc checks. Anything that fetches NOAA/USGS/Sentinel data or writes the Brain RTDB should stay in GCP (credentials, data volume, write ownership). The public repo must never hold the Brain writer credential.

---

## QUESTIONS / DECISIONS FOR MICHAEL

1. **`wind-hourly` is still ENABLED** — confirm whether you intended to pause it; this audit did not touch it.
2. **Billing export stopped 2026-09-09** — re-enable/verify the BigQuery export (and consider the Budget API) so the next audit can use actual invoices.
3. **`minScale: 1` on tagged revisions** — decide a rule: tags on revisions without min instances only (what the 10-12 deploy did by accident), or no tags on the production service at all (D6 also covers their public reachability).
4. **`sector-engine` min instance** — keep the one warm instance (≈ $14/month idle) for cold-start latency, or allow scale-to-zero (customers would see a cold start of several seconds on first use after idle; p50 is already 8.5 s).
5. **D4 (Clarity Stage 3–5 jobs)** — now also a cost/scheduling question: `lake-surface-daily` is the largest job cost and `clarity-current-hourly` + `hydrology-hourly` run hourly for research outputs.
6. **D9 / D10** remain open (scheduling Lake + Water Temp; the Orchestrator executor). This audit gives the inputs; it does not decide.
7. **Artifact Registry** holds 5 GB of old `sector-engine` images (50+): a retention policy is cheap but deletes images — your call.

---

## NEXT STEP

Michael + ChatGPT design the execution schedule from this audit. The facts that matter most: the Wind job costs ~$0.80/month and is still running; the server-hours came from warm 0 %-traffic revisions; the only expensive job is the daily satellite pipeline; the Brains that affect freshness (Lake, Water Temp) have no schedule; the billing export is stale.

**No scheduling, deployment, Cloud Run, Cloud Scheduler, Brain state, or production changes were made during this audit.**
