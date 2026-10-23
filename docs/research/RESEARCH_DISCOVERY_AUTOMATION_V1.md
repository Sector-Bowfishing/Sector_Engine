# Automatic research discovery V1 (2026-10-23)

The owner's directive: the research flow must run on its own. It finds the gaps, searches public sources, downloads and validates evidence, packages candidate knowledge, evaluates score impact, keeps investigating weak areas and cleans up. Nobody should have to prepare evidence or repair inputs before a campaign.

This document covers the discovery layer added to the existing coordinator, `tools/research/campaign.py`. It is not a second orchestrator.

Cloud Brain execution stays PAUSED. Nothing is approved or published: every candidate carries approval `NOT_RECORDED`, and gates M-3 and G-1 still apply.

## Flow per Brain

```
discover ─► acquire ─► research ─► validate ─► candidate ─► score ─► followup ─┬─► cleanup ─► report
   ▲                                                                             │
   └──────────── weak areas re-open acquire..followup (wider search) ◄───────────┘  (≤ maxIterations)
```

| Step | Automatic behaviour | Never stops the campaign because… |
|---|---|---|
| Gaps | Reads the Engine `brains/<dir>/research/GAPS.json`. If it is missing, gaps are **reconstructed** from three sources: frozen score blockers, the latest research closeout's Blockers section, and candidate blockers. The result goes to `<folder>/research/GAPS.generated.json` in the research home. | …a missing GAPS.json triggers reconstruction |
| Inputs | Each Brain's declared inputs (`discovery.json` `inputs`) end up in one of three states. A present input is used. A missing one is reconstructed with `git show <research branch>:<path>` and registered as RECONSTRUCTABLE. If that is impossible, it is recorded as a **limitation**. | …a missing input becomes a reconstruction or a recorded limitation |
| Acquire | Connectors download public evidence (table below) from five **allowlisted** HTTPS hosts. Requests get 3 retries with backoff, a per-host rate limit and a 50 MB cap. Downloads land in `<folder>/sources/<campaign>/` with `PROVENANCE.json` (URL, sha256, bytes, retrievedAt, licence) and are registered in `manifest.json` as RECONSTRUCTABLE. A read-only (protected) `sources/` is never modified: evidence goes to `research/discovery-sources/<campaign>/` instead. | …a failed request is recorded per file; a source that does not answer at all is an external-data limitation |
| Research | The Brain's existing adapter runs; an adapter BLOCKED on a missing external input is recorded, not fatal. Then the **offline** analysis of the saved evidence generates findings. Their thresholds are pre-declared in `discovery.json` before any download. | …a blocked adapter is recorded |
| Validate | Each finding is checked for schema and for evidence whose sha256 matches. The analysis is **re-run offline** from the hashed evidence. If its metrics differ from the research run, every discovery finding is REJECTED. Thresholds are then applied. | — |
| Candidate | Validated findings only. Packaged as `knowledge_release` with approval `NOT_RECORDED`. | — |
| Score | The Brain's candidate score (non-authoritative) plus the analysis' score impact. The authoritative score files must stay byte-identical. | — |
| Followup | Weak areas get a second, wider iteration. Weak areas are rejected findings, unmatched targets, sites without data, and too few records or leads. The wider iteration means a larger search radius excluding sites already used, a longer year range, broader literature queries, or the next batch of lakes. Whatever stays weak is reported. | …the loop is bounded by `maxIterations` |
| Cleanup | Only the campaign-owned workspace is deleted. Evidence and candidates are kept and registered. | — |

The `acquire` stage is the only place with network access. Brain adapters still run with network, gcloud and Firebase blocked.

## Connectors (allowlisted, public, legitimate)

| Brain | Connector | Source | What the analysis produces |
|---|---|---|---|
| Water Temp | `water-temp-sensors` | USGS NWIS site + daily values (00010), Open-Meteo archive | Independent **out-of-sample** validation of production M0. M0 is re-implemented and first checked against the stored production values. Sensors come from name-matched USGS lake sites, excluding the M0 calibration set. Per-lake RMSE ≤ 2.0 °C; pooled ≤ 2.5 °C. |
| Water Temp | `wqp-activity-metadata` | WQP Activity (metadata only) | Status of the Level-4 protected-truth gap. Counting casts with the frozen rule reads protected values, so it is reported as **owner approval required** and never done automatically. |
| Lake | `lake-levels` | USGS NWIS daily lake/reservoir elevation | An independent daily level source per fleet lake, with 30-day coverage of at least 90%: redundancy when CWMS fetches fail. |
| Clarity | `wqp-secchi` | WQP narrowResult Secchi depth | New Secchi observations, unit-normalised and range-screened, as input to the next re-certification. |
| Fish | `gbif-species` | GBIF occurrence search (month facet) | National observation-season profiles for the 13 bowfishing species. Aggregates only: no locations and no per-lake presence. |
| Wind, Depth, Vegetation | `literature` | Crossref works (metadata, CC0) | Peer-reviewed literature **leads** per open gap, as DOIs for a reviewer. They are not adopted knowledge. |
| Intelligence | `upstream` | this campaign's specialist candidates (its `dependsOn` only) | The integration input. It never invents specialist outputs. |

New connectors are reviewed code. They are registered in `discovery.py` (`acquire_*` and `analyze_*`) and `discovery.json`.

## Commands

```
python3 tools/research/campaign.py init   --campaign C [--home DIR]
python3 tools/research/campaign.py run    --campaign C [--home DIR] [--parallel 3] [--retry-failed] [--offline]
python3 tools/research/campaign.py report --campaign C
```

- `run` resumes from the checkpoint.
- `--retry-failed` re-opens only FAILED stages after a fix. Finished stages, including downloads, are kept.
- `--offline` disables acquisition: every request fails and is recorded.

## Boundaries (unchanged)

- No Cloud Scheduler, orchestrator or Firebase use.
- No approval and no write into the Engine.
- No sealed or protected holdout values.
- No per-lake species presence in this public repository.
- Raw evidence lives only in the private research home.
