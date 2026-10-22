# Sector Engine — all eight Brains operational readiness — Session Record

```text
Standards: Rehtac Cortex 2.3.0 @ 8955840 (clean), pack sector/engine
Repository: Sector-Bowfishing/Sector_Engine · main @ 1d05a8cc (start) · Date: 2026-10-22
```

**Scope.** All eight Brains. Production inspection was read-only. Pilots ran as dry-runs only: no production writes, and the Wind GCS store is refused without its approval variable. No knowledge release was promoted, no score changed, and no Brain schedule was enabled.

## 1. Acceptance criteria applied (mission §10)

**OPERATIONALLY READY** requires all eight of:
1. runtime tested;
2. input and knowledge contracts satisfied (an **approved** knowledge release, BR-11);
3. outputs pass scientific validation;
4. runs in the intended infrastructure;
5. an approved publication path;
6. scheduling and monitoring verified;
7. correct Ops representation;
8. passing pilot end-to-end evidence.

**PRODUCTION ACTIVE** is separate: the Brain is publishing in production now.

## 2. Readiness matrix (evidence: live read-only checks + Guntersville pilots at `1d05a8cc`)

| Brain | Runtime (pilot) | Knowledge release | Scientific validation | Production activity (live) | Health / freshness (live) | Pilot output (Guntersville) | Blockers to OPERATIONALLY READY |
|---|---|---|---|---|---|---|---|
| Fish `biological-state` | PASS: `run.py --dry-run`, 29 species profiles, valid artifact | packaged, approval NOT_RECORDED (M-3) | NOT_VALIDATED: response bands PROPOSED, RESEARCH tier | published 2026-10-19 in-process; orchestrator PAUSED, so not refreshing | HEALTHY, not stale (VERSION model) | species knowledge: response bands, movement, water domains. No per-lake state in the production path | M-3 approval; field validation; per-lake biological state is not on the production path |
| Wind `wind` | PASS in production (hourly) | packaged in main; the deployed image predates verify-on-load; approval NOT_RECORDED | PARTIAL | **ACTIVE**: wind-hourly ENABLED, image `e6a5026f`, last run 2026-10-22T02:07Z | HEALTHY, fresh | analysis: sustained/gust, shoreline exposure 0 % exposed / 100 % protected. A physical description, explicitly **not** a fishing recommendation | M-3; validation PARTIAL (failed gates recorded); A-2 redeploy to the release-verifying image |
| Water Clarity `water-clarity` | PASS: `run.py --dry-run`, 1 lake | packaged, approval NOT_RECORDED | PARTIAL (VALIDATED_NO_GATE; candidate promotion pending) | **NOT ACTIVE**: no `water-clarity-brain` job deployed; satellite and hydrology schedulers PAUSED; last publication 2026-10-12 | STALE (age policy) | 4.0 ft modeled, range given, `uncalibratedModel:rain-decay-v0`; satellite median 4.83 ft (2.1–16 ft) from a 13-day-old scene | M-3; validation (CLARITY-VAL-001); job deploy + activation approval; M-5, M-6, D-E |
| Lake `lake-brain` | PASS: `LakeBrainJob --dry-run` (main build), 3 s | compiled bindings; presence release FNV fingerprint (M-7) | NOT_VALIDATED (prospective ledger running) | **ACTIVE (daily ledger)**: `lake-brain-ledger-daily` ENABLED; image `a6622f99` is off main | WARNING (recorded); Brain-level fresh under the 26 h policy | OBSERVED 593.90 ft, IN_ZONE, STABLE, hist NORMAL, baseline 7,416 days, BETA, presence 10; flags `trend24hFallback`, `noOperatorFloodPoolThreshold` | field validation; reconcile the off-main image with main (Lake owner); M-7; D-C |
| Water Temp `water-temp` | PASS: `WaterTempBrainJob --dry-run` (main build) | compiled model (NOT_APPLICABLE) | PARTIAL (GLOBAL_HOLDOUT_ONLY) | **NOT ACTIVE**: no schedule; last publication 2026-10-14 | STALE | 70.2 °F modeled, −0.5 °F/24 h, 3-day forecast to 68.6 °F, `forecastModelOnly:notSeparatelyValidated` | per-lake validation; activation approval; D-C |
| Intelligence `sector-intelligence` | PASS: `run.py --dry-run` | packaged, approval NOT_RECORDED | NOT_VALIDATED | **NOT ACTIVE**: in-process, orchestrator PAUSED, last 2026-10-14 | HEALTHY (recorded); no own age rule | EVALUATED_PILOT: 2 of 5 inputs fresh; stale inputs named. **No fishing judgment**: input assembly only, by design | recommendation synthesis does not exist (a gated product decision + science); outcome validation; M-3 |
| Depth `depth` | PASS as refusal: exit 2 `BLOCKED_AWAITING_APPROVED_RELEASE`; with a local `--allow-unapproved-release` 5 pilots, all DEGRADED | CANDIDATE, unapproved (G-1) | NOT_VALIDATED (DEPTH-VAL-001, DEPTH-DAT-001) | not activated (by design) | — | none publishable | G-1 + field validation + datum coverage |
| Vegetation `vegetation` | PASS as refusal: exit 2; locally 51 lakes, 0 observed, 51 unavailable | CANDIDATE, unapproved (G-1) | FAIL (gates failed; fresh truth needed) | not activated; no RTDB records (INACTIVE_EXPECTED) | — | **no Guntersville coverage** (regional limit, not a runtime defect) | fresh independent truth + holdout (VEG-VAL-001); G-1; V-1 |

**Missing- and stale-data behaviour verified in the pilots:**
- Depth and Vegetation refuse unapproved knowledge.
- Intelligence marks 3 of 5 inputs STALE and degrades rather than inventing.
- Clarity carries `uncalibratedModel` and a range.
- Water Temp flags its unvalidated forecast.
- Wind refusal on missing memory is covered by tests (exit 2, `a1e709ce`).

**Coordinated pipeline:** Intelligence consumed the live published outputs of Lake, Water Temp, Clarity, Wind and Fish, with provenance. The freshness verdicts match the control plane.

## 3. Counts

- **Operationally ready (all criteria): 0 / 8.** Criterion 3 (scientific validation) fails or is unrecorded for every Brain, and criterion 2 fails because no knowledge release has a recorded approval (M-3, G-1).
- **Runtime ready** (pilot passes in the intended code; refusal where required): **8 / 8**. Depth and Vegetation are runtime-ready in the sense that they correctly refuse.
- **Production active:** 2 / 8: Wind (hourly) and Lake (daily ledger, off-main image).

These counts are not inflated. The gap to 8/8 is scientific evidence and owner approvals, not code.

## 4. Changes in this session

- **Cortex 2.3.0 @ `8955840` adopted:** `CLAUDE.md` pin, plus the status report's standards fields.
- **Engineering-status layers:** `operationalReadiness` and `productionActivation` for all eight Brains now carry today's live and pilot evidence instead of "not checked". Repository evidence is never PASS for these layers (test rule): the maximum is PARTIAL, and live truth stays in the control plane. This is what Sector Ops shows.
- **Standing checks:**
  - `rules-check` on the live rules: 0 findings.
  - `data-check` v2: 177 findings (99 bare-root UNREGISTERED_PATH, 67 UNDECLARED_ACCESS, 9 UNDECLARED_READ for orchestrator, scorer and Kit reader declarations, 2 PRIVATE_DATA_READ that are the Publisher contract declaring the Lake presence family, not a read). No runtime defect; recorded for the registry.
  - Standing memory checks: not triggered (no runtime, loader, release or deploy file changed).
  - Security (SEC): no trigger (no rules, consumer, cache or public build change).

## 5. Implementation results (2026-10-22, continued)

| PR | Merge commit | Change |
|---|---|---|
| #45 | `acd32ac1` | live and pilot evidence in the status layers; Cortex 2.3.0 @ `8955840` adopted |
| #46 | `640ae422` | Lake provider requirements. History-only (`iem-hads`, `usgs-nwis-dv`) and fleet/candidate-scope (`usace-access2water`, `usbr-rise`, `nws-nwps`) providers are OPTIONAL; the pilot primaries stay REQUIRED. A test ties the requirements to `jobs.MANIFEST` roles |
| #47 | `817d2f90` | re-collected certification after #46 |

**Incident (process):** #46 was merged with 3 failing checks.
- **Cause:** the merge gate compared check text instead of the `gh pr checks` exit code. The failures came from collecting certification while a new test file was untracked; the source digest hashes only tracked files.
- **Impact:** `main` CI red for one commit. No deploy or runtime impact (the orchestrator stayed on `acd32ac1` until the fix was merged).
- **Fix:** #47 restored green CI on `main`. Merges are now gated on the `gh pr checks` exit code.

**Orchestrator deployments** (each: lineage and stale-score guards passed; scheduler PAUSED; no Brain executed):

| Commit | Image | Args |
|---|---|---|
| `acd32ac1eca3` | `sha256:387d36fc…` | `--publish-engineering-status --publish-health` |
| `817d2f909b69` (current) | `sha256:202e4a08c82e9952da16fa8c6d3a412590d06096b982c1dda4cd3d01041c887e` | same |

**Health plane `/control/healthV1`:**
- Refreshed for the first time since 2026-10-17. It is now part of every orchestrator run (`--publish-health`).
- Current aggregate: HEALTHY 4 (Fish, Wind, Clarity, Intelligence), DEGRADED 2, UNKNOWN 2 (Depth and Vegetation, not configured).
- **Lake DEGRADED:** primary provider health records come from the daily ledger run, which is older than the providers' freshness thresholds. This is genuine, and it was a false FAILED before #46.
- **Water Temp DEGRADED:** stale inputs. Genuine.

**Engineering status `/control/engineeringStatusV1`:** AVAILABLE @ `817d2f909b69`, carrying the readiness layers of §2.

**Scores:** unchanged. **Schedulers:** unchanged (wind-hourly and lake-brain-ledger-daily ENABLED; all others PAUSED).

## 6. Approvals that would move Brains toward OPERATIONALLY READY (owner decisions; none taken here)

| # | Approval | Brains | Unblocks |
|---|---|---|---|
| 1 | **M-3:** a named approver and a recorded approval for each packaged knowledge release | Fish, Wind, Clarity, Intelligence | criterion 2 |
| 2 | **Scientific validation acceptance** of the recorded evidence (the validation status stays honest until then) | all | criterion 3 |
| 3 | **A-2 Wind redeploy** to the release-verifying image (after M-3) | Wind | running verified knowledge |
| 4 | **Activation:** Clarity job deploy + schedules (clarity-current-hourly, hydrology-hourly, lake-surface-*); Water Temp schedule; orchestrator scheduler (in-process Fish and Intelligence) | Clarity, Water Temp, Fish, Intelligence | criterion 6 / PRODUCTION ACTIVE |
| 5 | **Lake:** reconcile the off-main `a6622f99` image with main (Lake owner) | Lake | criterion 4 on main code |
| 6 | **G-1** (after field validation DEPTH-VAL-001 / DEPTH-DAT-001 and VEG-VAL-001 with fresh independent truth) and **V-1** | Depth, Vegetation | criteria 2–3 |
| 7 | **Intelligence recommendation synthesis:** a gated product decision plus a validation design; today it is input assembly only | Intelligence | bowfishing recommendations |
