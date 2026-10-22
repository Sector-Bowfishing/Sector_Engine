# Water Clarity Brain (`brainId: water-clarity`)

**What it is.** The Water Clarity Brain (component **C1**) answers *what does the water look like?* It restates the production clarity estimate and the newest usable satellite evidence for every lake as Brain state in the Brain RTDB. **Bowfisher decision (clarity part):** whether the water is likely clear enough to see fish under lights (and, only as a hint, which part of a lake looks better); Sector Intelligence makes the bowfishing recommendation (contract §3). Consumers: Sector Ops and Sector Intelligence read published Clarity state. Lifecycle `CALIBRATION`; the customer number is **not validated**; a certified research candidate exists and is **not deployed**. No schedule (execution is MANUAL by decision). Nothing here is deployed by the repository migration.

Rules for every session: **[`BRAIN_OPERATING_CONTRACT.md`](BRAIN_OPERATING_CONTRACT.md)**. Identity and edges: [`brain.json`](brain.json). Published contract: [`contracts/clarity-publication-v1.json`](contracts/clarity-publication-v1.json). Real inputs: [`contracts/INPUTS_V1.json`](contracts/INPUTS_V1.json). Certification record: `docs/architecture/certification/water-clarity/`. Design, schemas and field map: `docs/brains/WATER_CLARITY_BRAIN_INTEGRATION.md`, `docs/brains/WATER_CLARITY_BRAIN_MAPPING.md`.

| Path | Holds |
|---|---|
| `runtime/` | production package (flat modules, stdlib only): `clarity_brain.py` (builders), `run.py` (`--dry-run` / publish), `publish_artifact.py` (Publisher `clarity-publication-v1` builder, **shadow only**), `brain_platform.py` (platform shim), `catalog.json` (public-safe catalog; detail comes from a private overlay) |
| `contracts/` | `clarity-publication-v1.json` (derived from the Publisher registry by `describe_contract.py --check`), `INPUTS_V1.json` |
| `deploy/` | `deploy-job.sh` (approval-gated; `--stage-only DIR` assembles the build context, no gcloud) and `Dockerfile`. Never run by the repository |
| `tests/` | stdlib/pytest, synthetic fixtures only; `golden/` holds the science-preservation baseline from the pre-move tree |
| `research/` | rules and `GAPS.json`. Never data |

```bash
cd brains/water-clarity && python3 -m pytest -q                         # Water Clarity suite (pytest.ini sets import roots)
cd brains/water-clarity/runtime && python3 run.py --dry-run --out /tmp/wcb --lakes "Guntersville|AL"   # payload.json + artifact.json + SHADOW verdict; writes nothing remote
PYTHONPATH=jobs/brain_platform python3 brains/water-clarity/contracts/describe_contract.py --check
```

`jobs/water-clarity-brain/` is a retirement pointer only. **Private detail:** research results never enter this package; set `CLARITY_PRIVATE_CATALOG` to a private overlay at run time.
