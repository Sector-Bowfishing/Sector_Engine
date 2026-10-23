# Sector — automatic eight-Brain research discovery — Session Record

```text
Standards: Rehtac Cortex 2.7.0 @ ebc7fb9 (clean), pack sector/engine
Repository: Sector-Bowfishing/Sector_Engine · main @ 1d6a41db (start) · Branch: cortex/research-discovery-2026-10-23 · Date: 2026-10-23
```

**Mission (owner).** The whole research flow runs automatically. It has to:

- discover gaps;
- search the internet;
- download and validate legitimate evidence;
- package candidate knowledge and evaluate the score impact;
- keep investigating weak areas;
- clean up.

Missing caches, datasets or GAPS.json files must trigger discovery or reconstruction, never stop the campaign. It uses the existing coordinator. Cloud stays PAUSED, and nothing is approved or published.

## Added

- **`tools/research/discovery.py`** provides:
  - an allowlisted fetcher: 5 public HTTPS hosts, retries, a per-host rate limit, a 50 MB cap, and 404 treated as "no data";
  - an evidence store: `PROVENANCE.json` (URL, sha256, bytes, retrievedAt, licence), manifest registration as RECONSTRUCTABLE, and resume on restart. A write-protected `sources/` is never modified; evidence goes to `research/discovery-sources/` instead;
  - gap loading, or reconstruction to `GAPS.generated.json`;
  - input reconstruction (`git show`) or a recorded limitation;
  - five connector and analyzer pairs (Water Temp sensors and protected-lake metadata, Lake levels, Clarity Secchi, Fish GBIF, Crossref literature), plus the Intelligence upstream integration.
- **`tools/research/discovery.json`** holds the per-Brain connectors, the thresholds (pre-declared), `maxIterations` = 2, and the declared inputs.
- **`campaign.py`** gains:
  - new `acquire` and `followup` stages;
  - gaps and inputs handled in `discover`;
  - a BLOCKED adapter (rc 2) recorded instead of being fatal;
  - an offline re-run of the analysis at `validate`: if it is not reproducible, the discovery findings are REJECTED;
  - the score impact;
  - `run --retry-failed` and `--offline`;
  - report sections for gaps, inputs and limitations;
  - Intelligence reading only its `dependsOn` Brains (fixes a race with sibling tracks).
- **Docs:** `docs/research/RESEARCH_DISCOVERY_AUTOMATION_V1.md`; the stage table in `RESEARCH_CAMPAIGN_AUTOMATION_V1.md`.
- **Cortex gaps:** CG-2.7-3 (automated acquisition standard) and CG-2.7-4 (GAPS.json is not a required package file).

## Verification evidence

**Tests.** 21 tests pass offline: the 12 existing tests plus 9 new ones. The new tests use a fake source server and cover:

- the full discovery → validate → package → follow-up cycle;
- tampered evidence being rejected;
- an unreproducible re-run being rejected;
- all eight Brains completing with every source down and every adapter blocked;
- the allowlist;
- input reconstruction and limitations;
- gap reconstruction;
- a read-only `sources/` left untouched;
- `--retry-failed` resuming with no re-download.

**Mutations caught (5).** Each mutation below makes the suite fail:

- allowlist removed;
- offline re-validation bypassed;
- follow-up loop disabled;
- station name-matching removed;
- blocked adapter made fatal again.

**Live campaign 1, `auto-discovery-2026-10-23`.** This was the real research home with real sources. Two defects surfaced and were fixed:

- Wind's `sources/` is write-protected, so acquisition hit `PermissionError`. Fixed by the protected-sources fallback.
- Lake's validate adapter was not idempotent when re-run in a follow-up iteration. Fixed by clearing the stage directories.

After the fixes, `run --retry-failed` re-ran only the failed stages: Lake validate, and Wind from acquire onward. Downloads that were already DONE were not repeated. The campaign completed 8/8.

Review then found a third defect: a continued follow-up left the `followup` stage DONE, so iteration 2 skipped its own evaluation. It is fixed and tested.

**Final live campaign, `auto-discovery-2026-10-23-final`.**

- Overall:
  - 8/8 DONE;
  - 145 evidence files, 2.3 MB, all with provenance and registered in the manifests;
  - offline re-validation reproducible on every Brain;
  - authoritative scores byte-identical;
  - 8 candidates with approval NOT_RECORDED;
  - all workspaces deleted;
  - 8/8 closeouts pass `research-check --closeout` with 0 findings.
- **Water Temp** (real out-of-sample cycle):
  - The re-implemented production M0 reproduces the stored production values (max |diff| 0.0 °C over 3000 lake-days).
  - Name-matched USGS continuous lake sensors outside the M0 calibration set were tested against Open-Meteo forcing. Results by lake:

    | Lake | RMSE (°C) | Days | Verdict |
    |---|---|---|---|
    | Lake Murray SC | 1.69 | 422 | VALIDATED |
    | West Okoboji IA | 1.07 | 302 | VALIDATED |
    | Lake Monona WI | 2.38 | — | REJECTED (> 2.0) |
    | Lake Anna VA | 2.24 | — | REJECTED; power-plant cooling lake, model about 2 °C cold |

  - Pooled equal-lake RMSE is 1.91 °C (≤ 2.5), which is better than the fleet grab-sample reference of 2.27: VALIDATED.
  - Five matched sites have no daily data since 2023. Iteration 2 widened the radius and found a second Lake Anna site.
  - The Level-4 protected-truth gap has 0 new WQP casts at Wheeler or Wilson since 2026-07-01. That count comes from metadata only. Re-counting under the frozen rule would open protected values, so it is reported as OWNER APPROVAL REQUIRED.
  - The frozen score stays 3.0.
- **Lake:** 31 lakes matched to USGS level sites. 18 have at least 90% of the last 30 days and form the CWMS redundancy evidence. 13 stayed weak after iteration 2 and are reported.
- **Clarity:** 832 screened 2026 Secchi observations at 8 fleet lakes.
- **Fish:** 13 GBIF national season profiles. Ictiobus niger was weak at 2015–2026, so iteration 2 widened the window to 2000–2026 and it validated.
- **Literature leads (Crossref):** Wind 4/4 gaps, Vegetation 3/3, Depth 2/3. Depth's DEPTH-VAL-001 query hit HTTP 429 on all three attempts; this was isolated and recorded.
- **Intelligence:** integrated the 5 specialist candidates from its dependencies.

**Cloud.** 9/9 Cloud Scheduler jobs PAUSED; `/control/executionControlV1/state` = PAUSED (read-only check); nothing deployed.

**Repository check.** Cortex `research-check` reports 84 `MAC_LOCAL_RUNTIME_PATH`, all in pre-existing files outside `tools/research`; none were added.

## Limitations (genuine)

- **External private data:** Wind stage3a `rows.pkl` and Clarity `stage_r31/cache` live in private repositories. The certification re-runs are recorded as limitations. Discovery still ran for both Brains.
- **Approval:** Water Temp Level-4 (protected truth) and any promotion of candidates (M-3, G-1) require the owner.
- **Data:** Wilson has no public casts after May 2026, so the gap needs a prospective network (D3). Five USGS lake sensors were discontinued. Thirteen fleet lakes have no fresh USGS level series. Crossref rate limits apply.
- **Not done:** reviewing the generated GAPS files for Lake, Water Temp and Intelligence before copying them into the Engine (CG-2.7-4).
