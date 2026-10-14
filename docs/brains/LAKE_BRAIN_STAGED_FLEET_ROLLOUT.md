# Lake Brain: staged fleet rollout (offline pre-seed, batches A to D, per-batch checklist, STOP and rollback, score projection)

Status: PLAN, prepared 2026-10-13, ready for the moment Michael's binding review produces `jobs/lake-brain/data/accepted_batch.json`.
**Nothing in this document has been executed against production.** No lifecycle change, no REVIEWED binding, no validation claim, no cloud mutation. The only
network use was read-only GETs of public data (smoke and throughput measurement, local files) and read-only GETs of the Brain RTDB / Cloud Run / Monitoring.
Lake Brain validation stays `NOT_VALIDATED`. Numbers marked **measured** were measured on 2026-10-13; **model** = computed from measurements; **assumption** = not measured.

Code and data (all under `jobs/lake-brain/history/`, tests in `tests/`, 117 tests):

| File | What it is |
|---|---|
| `preseed_fleet.py` | The offline history pre-seed. Input: an `accepted_batch.json` as `ingest_review_result.py` writes it. Output: `history/<lakeKey>/daily.csv` files (local), a manifest, structured logs. Dry run by default. |
| `rollout_plan.py` | Batch selection by declared rules, per-batch call/time cost, score projection through the real `score_lake`, staged accepted-file emitter. No network. |
| `verify_batch.py` | Read-only post-run verifier (profiles, states, health, validation, score, ledger). |
| `measured_throughput.json`, `rollout_plan.v1.json` | The measurement and the plan derived from it (re-derive with the commands in section 7). |
| `tests/fixtures/fixture_batch/` | FIXTURE ONLY: 8 fake lakes written by the real ingest from a synthetic pack. Refused by the pre-seed without `--allow-fixture`, always refused with `--gcs-prefix`. |

## 1. Findings that change how the rollout is run

1. **Staging is not possible with the current generator.** `scripts/generate-lake-bindings.py` embeds every id of `jobs/lake-brain/data/accepted_batch.json` as REVIEWED, so the
   full accepted batch would flip all lakes at once. A staged rollout needs the generator to read a cumulative subset. The smallest change is one line, **not applied here**
   (it edits a script outside this task): `ACCEPTED = os.environ.get("LAKE_ACCEPTED_BATCH", os.path.join(DATA, "accepted_batch.json"))`.
   `rollout_plan.py --emit-stage X` then writes a *derived* subset (dict form, `lakeIds`, `stagedFromAcceptedBatchSha256`) that the generator already understands. The real
   `accepted_batch.json` is never edited.
2. **The job already pulls full history when a lake has none** (`existing.isEmpty -> since = nil` in `LakeBrainRunner.evaluateLake`). Without the pre-seed, the first run of a new
   lake does that inside the 15 minute job: 20 lakes have a HADS history source, each needs 4 to 6 three-year chunks (about 22 s each, **measured**) behind a 15 s global gate, so roughly
   80 to 120 requests and at least 20 minutes for the HADS lakes alone; 99 lakes have CWMS history (hundreds of requests each for the irregular series, Cave Run Lake 309 calls = 309 s). That is why the pre-seed exists and why
   every batch has an entry criterion "history objects present for every lake of the batch".
3. **`--scope pilots` already means "all REVIEWED lakes"** (`LakeBrainRunner.run`: `.pilots` filters `reviewedBinding`). No scope change is needed in `deploy-job.sh`; the batch lakes
   join the run as soon as the deployed image's table marks them REVIEWED.
4. **The binding table understates history for CWMS lakes whose research window was 2018.** `historyCompleteYears` / `historyFirstYear` for 40 lakes is the research window: Branched Oak Lake
   binding 8 complete years, the real series gave 40 (hourly series since 1984); Cave Run Lake binding 8, real 22. The other 7 measured lakes that have a binding count matched it exactly. Consequence:
   some lakes will be better seeded than the table says (never worse), and the cost model below is a lower bound for the 20 CWMS series that are not in the research catalog.
5. **Memory is not measurable from Cloud Monitoring for this job.** `run.googleapis.com/container/memory/utilizations` returned a single sample (2.0 % of 1 GiB at the end of the 16:52 run) and nothing
   for the other four. The checklist therefore asks for a peak-RSS line in the job log (a small Swift change, section 10) before batch C.
6. **The scorer reads at most 200 profiled lakes** (`score_brains.fetch_facts`: `sorted(profiled)[:200]`). Fleet maximum here is 196, so coverage is not truncated; the cap matters if the fleet grows.
7. **The ledger `provider` field is the prefix of `sourceId`** (a2w, rise, nwps appear after rollout); the ledger doc lists only tva/cwms/usgs. `score_predictions.py` slices by `provider` as a string, so it works, but the table in `LAKE_BRAIN_PREDICTION_LEDGER.md` needs the new values.
8. **The existing Swift User-Agent contains the owner's email** (`LakeFeedHTTP.userAgent` in `LakeLevelFeedsFleet.swift`). The pre-seed uses the brief's UA (`Sector-LakeBrain/1.0 (io.sector.co; Rehtac Labs; read-only public data)`, optional `SECTOR_CONTACT`). A role mailbox from Michael is still needed.
9. **The ingest writes no hash that binds `accepted_batch.json` to `binding_review_result.json`.** The pre-seed checks everything the two files let it check (section 2) and records both sha256 in its state; a GCS write additionally needs `--confirm-batch-sha`. Recommended small ingest change: add `acceptedBatchSha256` to the result (the pre-seed already verifies it when present).

## 2. The pre-seed utility

`preseed_fleet.py` (header = the pre-registration and the safety contract; commit `7ef7b6de` fixed the thresholds before any test or run and they were not changed afterwards).

* **Refuses anything that is not a legitimately formed accepted batch**: sorted unique id list; `binding_review_result.json` beside it with `criteriaVersion binding-review-v1`, `ruleMet true`, `verdict ACCEPT_BATCH`, `rejected <= maxErrors`, every row decided, `acceptedBatchCount == len(batch)`, a 64-hex `reviewCsvSha256`, `packId LBR-SAMPLE-*`; no id in `heldBackLakes`, `rejectedIds`, `flagged57`, the repository hold lists (`held_lakes.py`, includes the 14 series-mismatch lakes) or a `fullReviewStrata` stratum; every id a MACHINE_VERIFIED row of the bindings table. 14 malformed variants are tested.
* **Providers**: CWMS (also behind Access2Water and NWPS lakes), USGS (dv and iv, gage height only with a datum offset), RISE, HADS, TVA guide; the live reads for the continuity check cover Access2Water, CWMS, USGS, NWPS, RISE and TVA. Same reductions as the Swift job (source ids, lake-local day medians per request window, 0.0 RISE placeholders and modeled values dropped, `-999999` dropped, `%.2f`, later source wins a date).
* **Rate limits** (one gate per host, process wide): HADS 15 s between requests and 429 backoff 60/120/240 s; CWMS, USGS, RISE, NWPS 1 s; Access2Water, TVA 2 s. Only HADS publishes a number; the others are politeness gaps. One worker per history host runs in parallel (`--no-parallel` for serial).
* **Checkpointed and resumable**: atomic state file plus a hash-checked cache of every fetched step (CWMS window, HADS chunk, RISE page, USGS year). Tested with in-process crashes at 5 points, a real `os._exit(137)` subprocess kill, corrupt cache entries, stale tmp files, stale and live locks, an input-bound state. **Deterministic**: same inputs give byte-identical `daily.csv` and manifest (3 runs, serial and parallel; golden hashes pinned).
* **Continuity check** (pre-registered): live series of the binding vs the history on the overlapping lake-local days; median difference > 2.0 ft rejects (`REJECT_DATUM`); no overlap falls back to the runtime's 15 ft rule (`PASS_COARSE`, flagged); no live reading defers. The 14 known mismatch lakes are rejected in a canned test (offsets 15.5 to 28.5 ft, both overlap and latest-only modes, and through the whole Runner with nothing staged or published). `PASS_COARSE` cannot see an offset between 2 and 15 ft: every such lake is listed in the manifest.
* **Writes**: dry run writes only `--work-dir`. `--write-dir` adds local `history/<key>/daily.csv`. `--gcs-prefix gs://sector-lake-brain/history` needs `--write-dir` and `--confirm-batch-sha`, is create-only (`--if-generation-match=0`, an existing object is skipped) and `--overwrite-existing` first copies the live generation to `history_backup/`. The REVIEWED pilots are always skipped (they keep their deep composite). The tests never use the flag. No promotion to REVIEWED, no change to bindings, no RTDB.

## 3. Evidence: live smoke and throughput measurement (read-only, local files only)

Smoke on two REVIEWED pilots, then one lake per provider shape (`--measure`, 8 lakes, scope exceeds "1 to 2 pilots" on purpose: the pilots only cover CWMS-daily and TVA; the measurement is not a pre-seed and its output is not publishable).

| Lake | Shape | Calls | Wall (s) | Downloaded | Rows | Complete years (binding) | Continuity |
|---|---|---|---|---|---|---|---|
| Lake Hartwell\|SC (pilot) | CWMS daily 1962- | 17 | 17 | 0.9 MB | 23,662 | 64 (64) | PASS_OVERLAP 30 d, +0.015 ft |
| Guntersville\|AL (pilot) | TVA guide | 2 | 2 | 0.05 MB | 651 | n/a | PASS_OVERLAP 3 d, -0.055 ft |
| Bankhead\|AL | CWMS daily 1963- | 17 | 17 | 0.8 MB | 23,072 | 62 (62) | PASS_OVERLAP 31 d |
| Branched Oak Lake\|NE | CWMS hourly 1984- | 84 | 105 | 14.4 MB | 15,181 | **40 (8)** | PASS_OVERLAP 31 d |
| Alum Creek Lake\|OH | CWMS 15 min 2020- | 88 | 101 | 7.4 MB | 2,250 | 5 (5) | PASS_OVERLAP 2 d |
| Cave Run Lake\|KY | CWMS irregular, 0.25 y windows | 309 | 309 | 1.6 MB | 8,432 | **22 (8)** | PASS_OVERLAP 2 d |
| Eagle Creek Reservoir\|IN | USGS dv 1989- | 2 | 2 | 1.2 MB | 12,910 | 33 (33) | PASS_OVERLAP 30 d |
| Buckeye Lake\|OH | USGS iv 2019- | 11 | 21 | 21.5 MB | 2,766 | 6 (6) | PASS_OVERLAP 31 d |
| Box Butte Reservoir\|NE | RISE 1991- | 7 | 20 | 4.4 MB | 11,742 | 28 (28) | PASS_OVERLAP 30 d |
| Lewis and Clark Lake\|SD | HADS 2019- | 5 | 89 | 5.1 MB | 2,565 | 6 (6) | PASS_OVERLAP 31 d |

**Fidelity (measured): the pre-seeded Hartwell file is byte-identical to the production object the Swift job wrote** (`gs://sector-lake-brain/history/Lake_Hartwell_SC/daily.csv`, sha256 `ab21abc3becdedaeab404b7d12c86fed5122116f1b75273b91db943cc3874b8f`, 23,662 rows). Guntersville: all 651 rows equal the bucket's (the bucket has 7,408, the rest is the deep RVDHUN/HADS composite the pre-seed deliberately does not touch). A recorded-response replay of the smoke reproduced files and manifest byte for byte.

Seconds per call, **measured** (`measured_throughput.json`; net = time inside the HTTP call, the gap is added by the plan):

| Host | Calls | Net s/call | Bytes/call | Gap used | Binding constraint |
|---|---|---|---|---|---|
| cwms | 512 | 0.57 | 47 KB | 1 s | the 1 s gap (irregular series: 309 calls = 309 s) |
| usgs | 14 | 1.44 | 1.6 MB | 1 s | payload size (iv years are 2 to 5 MB) |
| rise | 7 | 2.80 | 0.6 MB | 1 s | response time |
| hads | 4 | **21.9** | 1.2 MB | 15 s | response time of a 3-year chunk, not the gate (a 21-day request took 0.4 s, 54 KB) |
| a2w / nwps / tva | 2 / 1 / 2 | 0.62 / 0.40 / 0.58 | 295 / 107 / 27 KB | 2 / 1 / 2 s | n/a |

Cost model (`preseed_fleet.plan_lake`, calls per host) against the 10 measured lakes: exact (0 %) for 7, +15 % (Alum Creek), +29 % (Box Butte, 9 vs 7), and **-61 % for Branched Oak** (33 vs 84) because its series is absent from the research catalog and the binding's first year is wrong. 20 of the 99 CWMS history series have no catalog entry, so the CWMS number is a lower bound for them.

## 4. Whole-fleet pre-seed estimate (all 196 table lakes, model)

| | Calls | Downloaded | Wall |
|---|---|---|---|
| cwms | 9,998 | about 0.5 GB | 9,998 s at the 1 s gap |
| hads | 137 | 0.17 GB | 2,999 s (137 x 21.9 s) |
| rise | 302 | 0.19 GB | 846 s |
| usgs | 113 | 0.19 GB | 163 s |
| a2w / nwps / tva | 75 / 21 / 22 | small | 150 / 21 / 44 s |
| **Total** | **10,668** | **about 1.05 GB** | **serial 14,221 s (3.9 h); hosts in parallel 9,998 s (2.8 h, CWMS-bound)** |

The 5 pilots are skipped, so a real run is 191 lakes and 10,643 calls. Range: 7,638 calls if the binding years were right (no catalog), up to about 11.7k if all 20 uncatalogued CWMS series behave like Branched Oak. Whole-fleet = roughly one working afternoon, unattended and resumable. Output about 1.75 M rows, about 120 MB of CSV (70 bytes per row).

## 5. The Cloud Run job today (read-only `gcloud run jobs describe/executions list lake-brain`)

| | |
|---|---|
| Job | `lake-brain`, image `brain-jobs:98c8871798c5`, service account `brain-writer`, args `--rtdb ... --archive gs://sector-lake-brain --scope pilots` |
| Resources | 1 vCPU, **memory limit 1 GiB**, task timeout **900 s**, 1 task, 0 retries (`deploy-job.sh`) |
| Executions (5, all succeeded) | 70.3 s, 148.0 s, 108.4 s, 82.5 s, 71.0 s wall (start 05:33, 08:51, 12:51, 16:52, 18:52 UTC on 2026-10-13) |
| Lake work in the last run | `durationMs 5034` for 5 lakes (concurrency 3, two groups), `HEALTHY`, 0 errors, 1 ledger object |
| Peak memory | not measurable (finding 5); the one sample was 2.0 % of 1 GiB |

Runtime model for N reviewed lakes with the history pre-seeded (**model**, constants: 70 to 148 s fixed per execution = measured wall minus lake work; 2.5 s per group of 3 lakes from the 5,034 ms for 2 groups; a HADS lake holds its group for the 15 s global gate):
`T = 70..148 + 2.5 x ceil(N/3) + 12.5 x (HADS lakes)`.

| After batch | Reviewed N | HADS lakes | Job wall (s) | % of 900 s |
|---|---|---|---|---|
| A | 14 | 1 | 95 to 173 | up to 19 % |
| B | 73 | 1 | 145 to 223 | up to 25 % |
| C | 122 | 15 | 360 to 438 | up to 49 % |
| D | 196 | 20 | 485 to 563 | up to 63 % |

The 2.5 s per group figure comes from TVA and CWMS pilots; the first run of batch A measures it for a2w/usgs/rise/nwps. Memory (**assumption**, not measured): the largest history file is 46k rows (Lake Winnebago, about 3 MB); three lakes in flight plus the 2.65 MB presence bundle should stay well below 300 MB of the 1 GiB. Treat as unverified until RSS is logged.

## 6. Batches

Rules are constants in `rollout_plan.py` and the sizes are an output of them (`rollout_plan.v1.json`, built from the 191 non-pilot table lakes; rebuild with `--accepted` once the real batch exists, lakes Michael rejects drop out and the sizes shrink).

| Batch | Rule | Lakes | Pre-seed calls | Pre-seed wall (parallel hosts / serial) |
|---|---|---|---|---|
| **A** canary | one lake per (live provider, history kind) among B-eligible lakes (strict plan evidence first, cheapest first) plus the cheapest HADS lake | 9 | 83 | 153 s (HADS) / 293 s |
| **B** high confidence, well seeded | history SUFFICIENT with >= 15 complete years, single history source, not slow (HADS / USGS iv / CWMS > 60 calls / > 120 s), research probe age <= the binding's own lag + 6 h | 59 | 584 | 683 s (RISE) / 1,060 s |
| **C** slower history providers | history SUFFICIENT, single source, slow: 33 sub-daily CWMS (up to 947 calls each), 14 HADS, 2 USGS iv | 49 | 8,271 | 8,113 s (CWMS) / 10,293 s |
| **D** remaining accepted | everything else: 45 SUFFICIENT but < 15 years, 7 stale probe, 7 TVA guide-only, 6 LIMITED, 6 composite, 3 without a history source | 74 | 1,705 | 1,552 s / 2,541 s |

Batch A (canary):

| Lake | Live | History | Years | Est. calls | Est. s | Plan / flood level |
|---|---|---|---|---|---|---|
| Abiquiu Lake\|NM | a2w | cwmsDaily | 15 | 17 | 18 | yes / yes |
| Allatoona\|GA | a2w | usgsDaily dv | 20 | 2 | 3 | yes / yes |
| Arkabutla Lake\|MS | cwms | cwmsDaily | 27 | 17 | 17 | yes / yes |
| Canton Lake\|OK | nwps | hadsDaily | 15 | 8 | 154 | yes / yes |
| Cheney Reservoir\|KS | rise | riseDaily | 33 | 9 | 25 | yes / yes |
| Clarks Hill / J.S. Thurmond\|GA | usgs | usgsDaily dv | 68 | 2 | 3 | no / no |
| Hungry Horse Reservoir\|MT | a2w | riseDaily | 74 | 15 | 41 | no / yes |
| Possum Kingdom Lake\|TX | cwms | usgsDaily dv | 35 | 2 | 2 | no / yes |
| Pueblo Reservoir\|CO | cwms | riseDaily | 48 | 11 | 29 | yes / yes |

Three canary lakes have no plan or flood level on purpose (the sparse cases). The composition above is computed from the table of 2026-10-13 and will be re-derived from the real accepted batch.

**Entry criteria (every batch)**
1. Previous batch passed its checklist (section 7) and its STOP criteria (section 8) did not fire.
2. `preseed_fleet.py` dry run over exactly the batch lakes ended with every lake `PASS`; `REJECT_DATUM`, `REJECT_EMPTY`, `FAILED` and `DEFERRED` lakes are removed from the stage file (they wait for a decision), never forced. The manifest lists `PASS_COARSE` lakes: review those by hand.
3. The pre-seeded `completeYears` per lake agrees with or exceeds the binding (a lake that comes out lower is held).
4. History objects for all batch lakes exist in `gs://sector-lake-brain/history/` (published with `--gcs-prefix`, or by hand from the local output).
5. Batch A only: a role mailbox is set in `SECTOR_CONTACT` (or Michael decides to run without), and the generator staging change (finding 1) is in.
6. Batch C and D only: task timeout raised (section 8) and peak-RSS logging in the image (section 10).
7. Batch D only: batches B and C produced no `historyLiveMismatch` and no unexplained `FAILED`/`DEGRADED`.

## 7. Checklist after each batch (run in this order; X = A, B, C, D)

```
# 0. plan from the REAL accepted batch (rebuilds sizes; lists lakes)
python3 jobs/lake-brain/history/rollout_plan.py --accepted jobs/lake-brain/data/accepted_batch.json \
  --catalog /Users/mcather/Desktop/Development/Sector_Research_Data/lake-brain/binding/catalog_usgs_cwms.jsonl \
  --throughput jobs/lake-brain/history/measured_throughput.json --out /tmp/rollout_plan.json
LAKES="$(python3 -c "import json;print(','.join(json.load(open('/tmp/rollout_plan.json'))['batches']['X']['lakes']))")"
```
1. **Pre-seed** (dry run first, then publish):
   `python3 jobs/lake-brain/history/preseed_fleet.py --batch jobs/lake-brain/data/accepted_batch.json --work-dir $LB/X/work --lakes "$LAKES"`
   then re-run the same command with `--write-dir $LB/X/out`; after reading `preseed_manifest.json` (counts, `PASS_COARSE`, warnings) and the lead's go: add
   `--gcs-prefix gs://sector-lake-brain/history --confirm-batch-sha $(shasum -a 256 jobs/lake-brain/data/accepted_batch.json | cut -c1-12)` (create-only). Check `gcloud storage ls gs://sector-lake-brain/history/ | wc -l` rose by the PASS count.
2. **Generate bindings (staged)**: `python3 jobs/lake-brain/history/rollout_plan.py --accepted jobs/lake-brain/data/accepted_batch.json --emit-stage X --out /tmp/stage_X.json`, drop the rejected/deferred lakes from `lakeIds`, then `LAKE_ACCEPTED_BATCH=/tmp/stage_X.json python3 scripts/generate-lake-bindings.py` (needs the one-line generator change). Commit the regenerated `LakeSourceBindingsGenerated.swift`.
3. **Tests**: `swift test` (baseline 270/270; the bindings tests check count and ids), `python3 -m pytest jobs/lake-brain/history jobs/lake-brain/bindings jobs/lake-brain/review jobs/lake-brain/validation jobs/lake-brain/ledger jobs/brain-scores jobs/brain_platform -q`.
4. **Build internal image**: `./jobs/brain-image-build.sh` (prints `IMAGE=...:<commit>`; never touches the serving service).
5. **Deploy internal job**: `IMAGE=<that> ./jobs/lake-brain/deploy-job.sh`. Record the previous image (`brain-jobs:98c8871798c5` today) for rollback.
6. **Run through the orchestrator**: `gcloud run jobs execute brain-orchestrator --region us-central1 --project sector-9393c --args=--dry-run` shows whether the plan starts the Lake Brain (it is TIME driven, `staleAfterHours 3`); then without `--args` (or wait for the hourly run). If it will not start soon enough, `gcloud run jobs execute lake-brain --region us-central1 --wait` is the same job.
7. **Verify profiles and states**: write the batch lakes (cumulative, plus pilots) to `lakes.txt`, then
   `python3 jobs/lake-brain/history/verify_batch.py --lakes-file lakes.txt --manifest $LB/X/out/preseed_manifest.json --expect-profiled <N> --ledger-day $(date -u +%Y/%m/%d)`.
   It checks REVIEWED, readiness, baseline status against the pre-seed, observation count >= pre-seeded rows, state OBSERVED, no `historyLiveMismatch`, health, validation still `NOT_VALIDATED`, profiled count. (Run live on the 5 pilots on 2026-10-13: 0 hard failures, health HEALTHY, score 3.0 / uncapped 6.3.)
8. **Verify the prediction ledger**: the same command reports the newest `predictions/yyyy/MM/dd/*.jsonl` object, its record count, the lakes of the batch that appear, and the `provider` values (new: a2w, rise, nwps). Objects are immutable; a missing object after a run that published is a defect.
9. **Canonical scorer**: `python3 jobs/brain-scores/score_brains.py` (dry run prints every score); the orchestrator's own cycle publishes with `--write --if-changed`. Compare with the projection (section 9).
10. **Verify score publication**: `curl -H "Authorization: Bearer $(gcloud auth print-access-token)" https://sector-brain.firebaseio.com/scores/lake-brain.json` - `value`, `uncapped`, `scoreUpdatedAt` newer than the run.
11. **Verify Ops-readable state**: `/control/overview` (lake-brain row: health, score, stale), `/control/fleet/<lakeKey>` for 2 batch lakes, `/health/brains/lake-brain`, `/brains/lake-brain` registry counts. Ops only reads these; it never computes.
12. **Measure and write down**: job wall time from `gcloud run jobs executions list lake-brain --limit 3`, `health.durationMs`, `errorCount`, `staleLakeCount`, peak RSS (once logged), source failures per provider (job log `errors`, `primarySourceStale`, `fallbackSource` flags in the states), GCS history object count and bytes, noncurrent versions of `history/` (hygiene doc).

## 8. STOP and rollback

**STOP (do not start the next batch, investigate) when any of these holds after a batch**
* a `historyLiveMismatch` flag on any batch lake, or `REJECT_DATUM` that is not explained by the lake's own datum story;
* `/health/brains/lake-brain` is `FAILED`, or `DEGRADED` (more than 25 % of reviewed lakes unavailable), or `errorCount` rose and the errors are not one named provider outage;
* more than 10 % of the batch lakes are `DEGRADED`/`UNAVAILABLE` state or `stale`, or more than 3 lakes run on a fallback source that the research probe did not predict;
* a job execution longer than **600 s** (67 % of the timeout), or any execution that hits 900 s, or a failed/killed execution; per-group time above 5 s (twice the model);
* peak memory above 600 MiB (60 % of the limit) once measured; any OOM;
* the validation status is anything but `NOT_VALIDATED`, a lifecycle or readiness value other than CALIBRATION/BETA appears, or a customer-facing surface changes (it must not);
* the prediction ledger object is missing after a publishing run, or a ledger record has a provider or lake not in the batch;
* the displayed score differs from the projection by more than 0.1 without an explanation (section 9 states the assumptions);
* a pre-seed step: any `REJECT_DATUM` outside the expected held set, a `FAILED` lake that is not a plain outage, a rows/complete-years shortfall, a source answering HTTP 429 after the backoff, or any sign the provider asked us to stop.

**Rollback (cloud mutations, lead only, in this order; stop after the step that fixes the problem)**
1. *Stop the bleeding, bindings*: redeploy the previous image, which carries the previous table.
   `gcloud run jobs update lake-brain --image us-central1-docker.pkg.dev/sector-9393c/cloud-run-source-deploy/brain-jobs:98c8871798c5 --region us-central1 --project sector-9393c`
   (use the tag recorded in checklist step 5 for later batches), and revert the generated Swift commit in git.
2. *Remove the batch lakes' published nodes*, because a job that no longer reviews them will not touch them again (scope `pilots` processes reviewed lakes only, so their last state would sit there stale). For each lake key `K` of the batch (`python3 -c 'import re,sys;print(re.sub(r"[^A-Za-z0-9]+","_",sys.argv[1]))' "<lake id>"`), with `T=$(gcloud auth print-access-token)`:
   `for p in lakes/$K/brain lakes/$K/states/lake lakes/$K/speciesPresence lakeFleet/$K snapshots/$K/latest/lakeState; do curl -s -X DELETE -H "Authorization: Bearer $T" "https://sector-brain.firebaseio.com/$p.json"; done`
   Only the Brain RTDB `sector-brain`; never a customer RTDB. Then run `python3 jobs/brain-scores/score_brains.py --write --if-changed` (or let the orchestrator cycle) so `/scores/lake-brain` and `/control` reflect it.
3. *Bad pre-seed data only*: the history objects are create-only inputs and harmless once the lake is not reviewed. If one is wrong: `gcloud storage rm gs://sector-lake-brain/history/<K>/daily.csv` (the bucket is versioned with 7-day soft delete; the previous generation, if any, is recoverable) and re-run the pre-seed for that lake. Never delete anything under `predictions/` (immutable audit trail), `history_backup/` or `baselines*/`.
4. A timeout-only problem is not a rollback: `gcloud run jobs update lake-brain --task-timeout 1800 --region us-central1 --project sector-9393c` (and put the same value in `deploy-job.sh`).

## 9. Expected score movement (PROJECTION ONLY)

Computed by `rollout_plan.py` with the real `score_lake` (the function `score_brains.py` calls) and the real rubric `docs/brains/scoring/lake-brain-score-v1.json`; cross-check: with the 5 pilots it returns the published block exactly (value 3.0, uncapped 6.3, coverage 1.0, floodDroughtContext 2.0), tested.
**Assumptions**: every accepted lake of the batch becomes REVIEWED and profiled (directory 621); validation stays `NOT_VALIDATED` (validation dimension 0, the 5.0 gate stays); health HEALTHY; baseline SUFFICIENT iff the binding says >= 5 complete years (TVA guide-only lakes INSUFFICIENT); operatorPlan = guide or zone in the binding; flood known iff the binding has a flood-pool level; every state observed (the 90 % row marks the lakes with the stalest research probe unobserved); pilots as published. The batches are the 191 table lakes, i.e. the case where Michael accepts every non-held lake; a smaller accepted batch lowers `Profiled` and the coverage points.

| After | Profiled | Displayed | Uncapped | Gates | Source / plan / history / baseline / trend / flood / validation / coverage |
|---|---|---|---|---|---|
| today (5 pilots, published) | 5 | **3.0** | 6.3 | coverage, validation | 10 / 10 / 10 / 10 / 10 / 2.0 / 0 / 1 |
| batch A | 14 | 3.0 | 6.3 | coverage, validation | 10 / 7.9 / 10 / 10 / 10 / 6.4 / 0 / 1 |
| batch B | 73 | **5.0** | 6.3 | validation | 10 / 4.0 / 10 / 10 / 10 / 5.1 / 0 / 3 |
| batch C | 122 | 5.0 | 6.3 | validation | 10 / 3.7 / 10 / 10 / 10 / 5.8 / 0 / 3 |
| batch D | 196 | 5.0 | 6.5 | validation | 10 / 4.3 / 9.2 / 9.5 / 10 / 5.7 / 0 / 5 |

With 90 % of states observed the displayed values are identical and the uncapped values 6.3, 6.2, 6.1, 6.1, 6.4.

What the projection says, in plain words:
* **The displayed score moves exactly once, at the batch that takes profiled lakes to 63 (10 % of 621): the coverage gate (cap 3.0) lifts and the validation gate (cap 5.0) takes over.** Here that is batch B (73 lakes). A alone (14) cannot move it. Everything after B moves only the uncapped value.
* **Uncapped does not rise monotonically**: it dips (6.3 to 6.1) while the share of lakes with an operator plan falls (pilots 100 %, whole fleet 43 %: plan dimension 10 to 3.7) and recovers as the coverage ladder steps (1 point below 5 % of the directory, 3 from 10 %, 5 from 25 %, weight 20). Final uncapped is 6.5.
* **The ceiling without validation is 5.0 displayed.** Only the validation dimension (weight 15, 0 today) and a PARTIAL or VALIDATED status lift it; this rollout does not and must not touch that.

## 10. Open items for the lead (nothing here was done)

1. Apply the one-line generator change (finding 1) and decide whether the stage file may carry rejected lakes' removal by hand (recommended: the pre-seed manifest decides).
2. Raise the job task timeout to 1800 s before batch C (the model says 438 s at C and 563 s at D against 900 s; the margin shrinks if the 2.5 s per group figure is wrong for a2w/usgs/rise).
3. Add a peak-RSS line (`VmHWM` from `/proc/self/status`) to the `LakeBrainJob` summary line so memory can be measured; until then memory is an assumption.
4. Michael: a role mailbox for `SECTOR_CONTACT`, and the Swift User-Agent (finding 8).
5. Decide the `history/` noncurrent-version lifecycle rule (hygiene doc section 3): 196 lakes rewrite their history object each run.
6. Add `acceptedBatchSha256` to `binding_review_result.json` in the ingest (finding 9); update the ledger doc provider list (finding 7).
7. CWMS gap: 1 s is a politeness choice (no published limit); halving it would halve the 2.8 h whole-fleet wall. Not done without the data owner's terms.
