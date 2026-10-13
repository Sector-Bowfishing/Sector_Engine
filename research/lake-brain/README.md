# Lake Brain research campaign — conventions (started 2026-10-13)

Base: `feat/cost-efficient-scheduling` @ `48168baa323897681219f81480ad4accba08ef07` (not yet merged into `main`).
Branch: `docs/lake-brain-research`. Research-only: no deploy, no Scheduler/Cloud Run change, no lifecycle change,
no rubric edit, no customer behavior change. Production code is untouched; this directory holds research tooling.

## Where things live
| What | Where | In Git? |
|---|---|---|
| Public-safe findings (the 9 required docs + per-track notes) | `docs/research/lake-brain/` | yes |
| Source ledger / blocker queue / Michael actions / score history (machine-readable) | `docs/research/lake-brain/ledger/*.jsonl` | yes (small) |
| Research scripts | `research/lake-brain/` | yes |
| Downloaded / generated data (bulk, GIS, history series) | `~/Desktop/Development/Sector_Research_Data/lake-brain/<track>/` | **never** |
| Per-dataset retention manifest (for Sweep) | `~/Desktop/Development/Sector_Research_Data/lake-brain/MANIFEST.jsonl` and a copy of its schema in `docs/research/lake-brain/ledger/` | manifest only |

Never commit: raw datasets, GIS bulk, credentials, tokens, private Clarity research. Never write to any RTDB or bucket.
Production reads are GET-only (`gcloud auth print-access-token` + `https://sector-brain.firebaseio.com/<path>.json`).

## Ledger records (one JSON object per line; append only; each thread writes its own file `ledger/<thread>.jsonl`)
`source`:  `{"kind":"source","id":"S-<thread>-NNN","question","name","org","url","accessed":"2026-10-13","dataType","geoCoverage","lakeCoverage","timeCoverage","cadence","machineReadable":true,"access":"api|bulk|portal|pdf","license","authority":1-7,"supports","scoreDimensions":["coverage"],"decision":"ACCEPTED|REJECTED|LEAD|DEAD_END","reason","localPath","checksum","notes"}`
`blocker`: `{"kind":"blocker","id":"B-<thread>-NNN","question","missing","why","scoreDimension","impact":"+0.0..","attempted":[],"proxy","michaelAction":true|false,"priority":"high|medium|low","status":"OPEN|WORKED_AROUND|CLOSED"}`
`action`:  `{"kind":"action","id":"M-NN","what","impact","priority","relatedBlocker"}`
`dataset`: `{"kind":"dataset","path","bytes","sha256","track","retention":"KEEP|ARCHIVE_FIRST|REBUILDABLE|SAFE_TO_REMOVE|REVIEW_REQUIRED","rebuild":"command or url","note"}`
`score`:   `{"kind":"score","step","previous","candidate","dimensions":{},"evidence","confidence","remaining"}`
Authority scale (source quality): 1 federal/operator/state authoritative · 2 peer-reviewed · 3 gov/university report ·
4 documented public GIS portal · 5 scientific DB · 6 secondary · 7 community/lead only.

## Scoring honesty
`jobs/brain_platform/sector_brain_platform/scoring.py::score_lake` is the rubric and is not edited. A "research score" is that
function run over research-built profile/state facts (`research/lake-brain/tools/research_score.py`). A binding counts
only if it meets the pre-registered review criteria recorded in `LAKE_BRAIN_VALIDATION_STRATEGY.md`; automated
candidates that did not pass stay CANDIDATE and do not count (rubric `cannotCount`).
