# Wind Brain: Repository Phase 2 physical migration V1

**Status: `WIND_REPOSITORY_PHASE_2_COMPLETE`** (2026-10-16). Wind is **structurally migrated** into its permanent home `brains/wind/`. This is **not** `ARCHITECTURE_CERTIFIED_V1`, not production cutover, not scientific validation, not Publisher production readiness; **`PRODUCTION_WRITE_SECURITY_GATE_OPEN`** is unchanged. No live system was changed, nothing was deployed.

## 1. Entry gate and lineage
- Repository Foundation real GitHub Actions run green on PR #18 (draft, not merged) at foundation `988d6745`: `foundation-verification / foundation`, `swift-tests / swift` (274 tests, Swift 6.1.2), `python-jobs-tests / platform`, `brains` (incl. the legacy Wind suite), `lake-geometry`.
- Branch `migrate/wind-brain-v1` from `988d6745`; one `--no-ff` merge of `cert/wind-architecture-v1` @ `87714527` (no conflicts; the lineages touch disjoint files), preserving Publisher Gate P `7ebfca1c`, its merge `0355d4e3`, Wind Publisher V2 adoption `7111e241` and the research preservation/workspace docs. Nothing cherry-picked or copied by hand.

## 2. Permanent location and package
```
brains/wind/
  README.md  BRAIN_OPERATING_CONTRACT.md (19 sections, v1.0.0)  brain.json  pytest.ini  .gitignore
  runtime/     main.py  lakes.json  requirements.txt  sector_wind/{ingest,grib,store,sample,interp,validate,monitor,live,bowfishing}.py
               sector_wind/brain/{contract,lakes,profile,state,publish,writer,artifact,__main__}.py + validation_evidence.json
  contracts/   wind-publication-v1.json (+ describe_contract.py: derived from the Publisher registry, --check)
  tests/       production tests + fixtures/golden_stage1.json
  research/    README.md  tools/{28 research scripts, check-live.sh, requirements.txt, sector_wind_research/ (11 moved modules + bowfishing_assets), tests/}
  deploy/      Dockerfile  .gcloudignore  deploy-job.sh (stages the image context; --stage-only)  read_service/
  docs/        WIND_BRAIN_DESIGN_V1.md (was BRAIN.md)  history/SESSION_CLOSEOUT_2026-10-12.md
```
No ceremonial directories: `artifact/` (builder stays in `sector_wind.brain.artifact` until it is wired at cutover), `scoring/` (rubric lives on the Wind adoption lineage), `validation/` and `config/` are not created.
- **`brain.json`**: `brainId wind` (unchanged), domain `condition`, lifecycle CALIBRATION, publishes `wind-publication-v1` (12 path families, equal to the Publisher registry), consumes the Lake Registry contract, providers `noaa-nbm-v5`/`noaa-rtma-ru`/`iem-metar-wind` (Wind = domain interpreter), research workspace **logical id `wind-brain`**, score `ENGINE_READINESS_SCORE` at `/scores/wind`, `customerIntegrationMode none`, Publisher required, cutover **SHADOW**, consumers Ops / Sector Intelligence / Fish Brain. No physical path.
- **Operating contract**: written from the certification record, adds no policy; bowfisher decision explicit (where the surface is calm enough to see and shoot).

## 3. Source → destination
| From `jobs/wind-hourly/` | To `brains/wind/` | Class |
|---|---|---|
| `main.py`, `lakes.json`, `requirements.txt`, `sector_wind/` (main.py import closure) | `runtime/` | WIND_RUNTIME / WIND_DOMAIN |
| `sector_wind/brain/artifact.py` | `runtime/sector_wind/brain/artifact.py` | WIND_ARTIFACT (Publisher V2 builder) |
| `sector_wind/{bowfishing_score,evidence,exemplars,field,field_qa,field_run,fieldops,overwater,provider_bakeoff,rrfs,scoreboard}.py` | `research/tools/sector_wind_research/` | WIND_RESEARCH_TOOL (never imported by main.py) |
| `bowfishing.load_lake` + the latent Desktop `ASSETS` constant | `research/tools/sector_wind_research/bowfishing_assets.py` (verbatim) | WIND_RESEARCH_TOOL |
| `research/*.py` (28), `check-live.sh` | `research/tools/` | WIND_RESEARCH_TOOL |
| `tests/` (conftest + 6 test files + `golden_stage1.json`) | `tests/` | WIND_TEST |
| `tests/test_stage3a.py`, `tests/test_store_field.py`, `fixtures/overwater_SYNTHETIC.jsonl` | `research/tools/tests/` | WIND_TEST (research tools) |
| `Dockerfile`, `deploy-job.sh`, `.gcloudignore`, `read_service/` | `deploy/` | DEPLOY (Brain-owned) |
| `BRAIN.md`, `SESSION_CLOSEOUT.md` | `docs/` | docs |
| `pytest.ini`, `.gitignore`, `tests/conftest.py` | rewritten in place (import roots declared; shims removed) | WIND_TEST |
All moves by `git mv` (rename history kept). No Platform/Publisher code moved into Wind; shared provider infrastructure untouched.

## 4. `jobs/wind-hourly`: **RETIRED**
Only a moved-notice `README.md` remains: no code, no entrypoint, no deploy file, no second implementation (gate: exactly one tracked `sector_wind` package, under `brains/wind/runtime/`). The Cloud Run job **name** `wind-hourly`, its schedule and the deployed image are unchanged; job-name references in the Platform (`jobs.py`, control manifest, RTDB `/jobs/wind-hourly`, `/health/jobs/wind-hourly`) are names, not paths, and stay. Pointer retires in Repository Phase 7.

## 5. Boundaries established
- **Production vs research:** research depends on runtime, never the reverse (AST gate). The production package contains no Mac path, cache path, research-workspace path or app-checkout path (gate over all runtime files); every shipped module is reachable from an entrypoint (no orphan research code in the image). The 11 research modules and the latent `ASSETS` constant are no longer in the image.
- **Research paths:** research tools keep their pre-migration local defaults (research-only). They are **not** repointed: that needs Michael's approval and must not happen while the provider bake-off collector runs (it runs from an older worktree with its own interpreter, untouched). No `SECTOR_WIND_RESEARCH_ROOT` was introduced; production never reads any research location.
- **Import shims:** `writer.py`'s repo-only `sys.path` hook and the test `conftest` shim are removed; `brains/wind/pytest.ini` declares the import roots (`runtime/`, `research/tools/`, `../../jobs/brain_platform`). Remaining legacy coupling: the shared platform package's legacy location `jobs/brain_platform` (test import root and image vendoring source) until the platform package migrates. Research scripts keep a `sys.path` line pointing at `../../runtime` (research-only).
- **Providers:** the three Wind-exclusive sources are registered in `providers/PROVIDERS.json` (acquisition and health owner `wind`, sole consumer); the client code stays in `runtime/sector_wind/ingest.py` (single-consumer, movable). No consolidation, no Open-Meteo or TVA change.
- **Deploy:** `deploy-job.sh` stages exactly `Dockerfile .gcloudignore requirements.txt lakes.json main.py sector_wind/ sector_brain_platform/` into a temp directory (no vendoring into the tree). The staged context equals the pre-migration image context except: `writer.py` (shim removed, inert in the image), an `artifact.py` comment, the `brain/__init__.py` docstring, and the removal of the unused research modules. Not executed; still refuses without approval.

## 6. Publisher V2 contract (unchanged, verified)
One `publish-artifact-v2` per execution, bundle `wind-publication-v1`, sections `wind-lake-state-v1` (scopes `lake-live`, `lake-static`, `fleet-readiness`), `wind-registry-v1`, `wind-source-registry-v1`; `wind-volatile-v1`; `sector-semantic-fingerprint-v2`; typed DELETE only; Publisher-owned publication metadata; Publisher-derived snapshot compatibility copies; Lake Registry identity and Orchestrator job/process health not authored by Wind. The Publisher V2 builder suite (`tests/test_publish_artifact.py`, 48 cases incl. the 18 required Wind proofs) passes from the new location; `contracts/wind-publication-v1.json` is checked against the Publisher registry.

## 7. Verification (2026-10-16, local)
| Suite | Result |
|---|---|
| Wind production tests (`brains/wind/tests`) | PASS 77 (16 network-marked NOT_RUN by design) |
| Wind research-tool tests | PASS 29 (6 skip when the app checkout is absent) |
| Wind total | PASS 106, identical to pre-migration |
| Wind package gates (`verification/integration/test_wind_package.py`) | PASS 9; mutation-checked (research import, Mac path, orphan module, contract drift each fail) |
| Production tests in a clean copy without the research package | PASS 77 |
| Production tests under a sandbox denying all research/app/handoff/cache paths | PASS 77; staged image `main.py --help` PASS |
| Foundation + verification | PASS 85 |
| brain_platform / orchestrator / brain-scores | PASS 452 / 24 / 21 |
| Other job suites (lake-brain ×4, lake-geometry, clarity, biological, intelligence, dispatch, tva-archive) | PASS (unchanged) |
| Score baseline | PASS (wind 3.3/10 unchanged; no score recomputed) |
| Architecture report `--legacy --baseline` | 0 NEW; 1 RESOLVED (`jobs/wind-hourly` writer path); 2 Wind published-label entries carried with a retirement condition |
| New CI job `registered-brains` | NOT_RUN on GitHub (branch not pushed) |

## 8. Remaining (certification, not migration)
1. Production write security gate; Publisher P1–P12; G1/G2 (Orchestrator execution health, freshness source); G4 Lake Registry identity publisher.
2. Builder wiring + artifact store + deployed Publisher (cutover steps 2–5); `removals`; `expiresAt`; Wind release manifest.
3. `research/GAPS.json` (Wind research lane); research path repointing (approval; collector decision); per-script Git-vs-workspace classification.
4. Two published provenance labels (`PLATFORM.contract`, `definitionRef`) reference doc paths; replacing them is an output change.
5. Lake Registry contract (Wind still uses the interim `lakes.json` copy); platform package migration (removes the `jobs/brain_platform` import root).
6. Push + real CI run of `migrate/wind-brain-v1`; Architecture Audit #1.
