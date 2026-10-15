# Wind research (rules and tooling only — no data)

Research rules are in [`../BRAIN_OPERATING_CONTRACT.md`](../BRAIN_OPERATING_CONTRACT.md) §8–§12. The evidence itself lives in the private research workspace **`wind-brain`** (logical id; physical root never recorded in this public repo) and its private backup. This directory holds only code.

| Path | Holds |
|---|---|
| `tools/*.py` | 28 research scripts (evaluations, fetchers, physics experiments). Run from `tools/`; they add `../../runtime` to `sys.path` to reach the production package |
| `tools/check-live.sh` | mirror the private candidate archive and run the milestone/validation checks on the mirror |
| `tools/sector_wind_research/` | research-only modules moved out of the production package in Repository Phase 2 (code unchanged): `provider_bakeoff`, `rrfs`, `evidence`, `scoreboard`, `fieldops`, `field`, `field_qa`, `field_run`, `exemplars`, `overwater`, `bowfishing_score`, `bowfishing_assets` |
| `tools/tests/` | tests of the research modules (run by `brains/wind/pytest.ini`) |
| `tools/requirements.txt` | research-tool extras (shapely, pyproj); production deps are `../runtime/requirements.txt` |

Commands (`python -m sector_wind_research.<module> …`, from `research/tools` with `PYTHONPATH=../../runtime`):

| Command | What it answers |
|---|---|
| `evidence status\|harvest --store local:$MIRROR` | archive health, skill by lead, event contingency; upcoming wind windows |
| `fieldops opportunities\|packet …` | where/when to collect; one blind field session packet |
| `field_qa ingest\|verify\|qa`, `field_run gaps\|calstatus\|diagnostics`, `exemplars add\|review\|status` | field record intake/QA, scoring status, human photo exemplars |
| `overwater import\|compare`, `scoreboard …`, `provider_bakeoff collect\|status\|parity\|loop`, `rrfs discover\|collect` | over-water stations, the Candidate scoreboard, the provider bake-off, RRFS archive |

None of these change the Candidate, the fetch method, thresholds or the rubric, and none read sealed holdout accuracy.

**Deferred (recorded, not done in the migration):**
- Research defaults still point at pre-migration local locations (the local research cache, the legacy research data directory, the app checkout for fetch-table assets and evidence). They are research-only and not production; repointing them to the `wind-brain` workspace needs Michael's approval and must not happen while the provider bake-off collector runs (it runs from a separate, older worktree with its own interpreter and is untouched).
- `GAPS.json` and a public `MANIFEST.json` are not written: gaps come from the Wind research lane, and the workspace manifest is private.
- Per-script classification (keep in Git vs move to the workspace) per STANDARD_BRAIN_PACKAGE_V1 §3a is a Wind certification item; all 28 scripts stay in Git until then.

**Provider licence notes** (from the research preservation plan): NOAA NBM/RTMA/MADIS and IEM are public data; Open-Meteo (research comparisons only) is free-tier non-commercial; NASA Earthdata requires a login. Nothing restricted is committed.
