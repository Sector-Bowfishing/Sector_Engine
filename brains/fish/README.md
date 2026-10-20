# Fish Brain (`brainId: biological-state`)

**What it is.** The Fish Brain answers: *what does Sector know about this fish, and what is it likely doing?* Today it publishes **Species Intelligence** (evidence-completeness scores, Knowledge Coverage, Research Gaps, machine rules, response bands, movement knowledge) from the private canonical bundle (`gs://sector-biology-private/biology/v1`) as lightweight species summaries. The per-lake Biological State is an **internal pilot** (nothing published per lake). Lifecycle `PROFILED`, science `NOT_VALIDATED`; no customer path reads it.

Rules for every session: **[`BRAIN_OPERATING_CONTRACT.md`](BRAIN_OPERATING_CONTRACT.md)**. Identity and edges: [`brain.json`](brain.json). Published contract: [`contracts/fish-publication-v1.json`](contracts/fish-publication-v1.json). Certification record: `docs/architecture/certification/fish/`. Species-intelligence specs and decisions: `docs/brains/biological-adoption/`, `docs/brains/BIOLOGICAL_BRAIN_INTEGRATION.md`.

| Path | Holds |
|---|---|
| `runtime/` | production package (flat modules, stdlib only): `biological_brain.py` (bundle load + hash verify + fail-closed validation + RTDB payload builders), `publish_artifact.py` (Publisher `fish-publication-v1` builder, **shadow only**), `run.py` (`--plan/--dry-run/--write`), `orchestration.py` (descriptor + `plan()`), rules / features / bands / bio_state / movement_outlook / capability / validation_log / species_profile (Species Intelligence Profile) modules, `run_state.py` (internal pilot runner), `brain_platform.py` (platform shim), `schemas/`, `tools/` (bundle tooling that runs against the private workspace) |
| `runtime/` capability V2 | `biological_assessment.py` (Intelligence-facing `fish-biological-assessment-v1`: biology under supplied conditions, no locations/rankings), `capability_eval.py` (Layer 3: executes the runtime per species and emits capability **evidence**, no points), `capability_run.py` (local deterministic entry point for developers / Sector Pulse; points come from the shared scorer `sector_brain_platform.fish_capability`). See `docs/brains/scoring/FISH_BIOLOGICAL_CAPABILITY_V2.md` |
| `contracts/` | `fish-publication-v1.json` (derived from the Publisher registry by `describe_contract.py --check`) |
| `tests/` | stdlib/pytest, **synthetic species only** (this repository is public) |
| `research/` | research rules (README) and `GAPS.json`. Never data |

```bash
cd brains/fish && python3 -m pytest -q                       # Fish suite (pytest.ini sets import roots)
cd brains/fish/runtime && python3 run.py --dry-run --offline --bundle /path/to/biology/v1 --out out/   # artifact.json + SHADOW Publisher verdict; writes nothing remote
PYTHONPATH=jobs/brain_platform python3 brains/fish/contracts/describe_contract.py --check
python3 brains/fish/runtime/capability_run.py --bundle /path/to/private/release --out out/   # Biological Capability V2 (candidate; local files only)
```

The Cloud Run / in-process job id `biological-brain` is unchanged; the orchestrator image stages `brains/fish/runtime` under the legacy `jobs/biological-brain/` layout (`jobs/brain-orchestrator/deploy-job.sh`). `jobs/biological-brain/` is a retirement pointer only. Nothing here is deployed by the repository migration; nothing publishes to a customer.

**Never commit proprietary biology here.** Detailed profiles, rules, evidence, packets and per-lake species presence live only in the private bucket and the private research workspace.
