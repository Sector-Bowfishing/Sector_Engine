# Sector Intelligence (`brainId: sector-intelligence`)

**What it is.** The synthesis Brain. Its target question is *what does everything Sector knows mean for the bowfisher?*: it is the only Brain allowed to combine specialist assessments into bowfishing opportunities, explanations and recommendations. **Today** it publishes the inventory of what constitutes Sector Intelligence (implementation catalog), the truth about each upstream Brain's availability and consumption, and, for the five pilot lakes, a normalized evaluation (`intelligence-eval-v1`) that restates specialist Brain states with provenance. It produces **no rating, score or recommendation**, no customer consumes it, and it never calls `/conditions`: the customer path is the Engine Conditions Score. Lifecycle `CALIBRATION`, activity PARKED, `NOT_VALIDATED`.

Rules for every session: **[`BRAIN_OPERATING_CONTRACT.md`](BRAIN_OPERATING_CONTRACT.md)**. Identity and edges: [`brain.json`](brain.json). Published contract (SHADOW): [`contracts/sector-intelligence-publication-v1.json`](contracts/sector-intelligence-publication-v1.json). Evaluation contract: [`contracts/intelligence-evaluation-v1.schema.json`](contracts/intelligence-evaluation-v1.schema.json). Integration contract: `docs/brains/SECTOR_INTELLIGENCE_BRAIN_INTEGRATION.md` (read its "Current state on main" note first).

| Path | Holds |
|---|---|
| `runtime/` | stdlib Python: `run.py` (`--plan` / `--dry-run` / `--write`), `sector_intelligence_brain.py` (registry, dependency truth, per-lake inputs), `evaluation.py` (pilot evaluation), `orchestration.py` (descriptor + `plan()`), `catalog.json` (hand-reviewed implementation catalog), `publish_artifact.py` (Publisher V2 builder, **shadow only**), `brain_platform.py` (platform shim) |
| `contracts/` | `sector-intelligence-publication-v1.json` (derived from the Publisher registry by `describe_contract.py --check`); `intelligence-evaluation-v1.schema.json` |
| `tests/` | dependency truth, degrade/abstain, pilot evaluation, evaluation contract, specialist boundary, Brain Certification Kit V1 adapter (synthetic data, no network) |
| `research/` | research rules (README). Never data |

```bash
cd brains/sector-intelligence && python -m pytest -q          # every suite (pytest.ini sets import roots)
cd brains/sector-intelligence/runtime && python run.py --plan  # is a publish warranted? (GET only)
python run.py --dry-run --out out/                             # build everything from live reads, write out/updates.json, no writes
PYTHONPATH=jobs/brain_platform python3 brains/sector-intelligence/contracts/describe_contract.py --check
```

The orchestrator runs it in-process (`control_manifest.json` `sector-intelligence`; FINGERPRINT trigger; the Brain is PARKED); its image stages `runtime/` under the legacy layout `jobs/sector-intelligence-brain/` (`jobs/brain-orchestrator/deploy-job.sh`), and the in-process executor id `sector-intelligence-brain` is unchanged. Nothing here activates recommendations for customers (approval-gated).
