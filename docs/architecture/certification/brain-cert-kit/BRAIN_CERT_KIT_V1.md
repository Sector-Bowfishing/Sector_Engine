# BRAIN_CERT_KIT_V1 — the shared structural-certification kit (D-7b)

**Status:** `BRAIN_CERT_KIT_V1_READY_FOR_REVIEW`. Test/platform tooling only: **no runtime Brain, platform, Publisher, Orchestrator, customer, Ops or scheduler behaviour changed.** Existing certifications (Wind, Fish, Water Clarity = `STRUCTURALLY_CERTIFIED_V1`) are unchanged and were not re-graded.

## What it is
The kit encodes **how** a Brain is structurally certified (Brain Factory V1 §7), not **what** a Brain knows. A Brain supplies a declarative `BrainCertSpec` (data) and one small artifact factory; the kit supplies the 19 proofs, a mutation suite and one shared contract descriptor.

```
tools/brain_certification/
  brain_cert_kit/    spec.py (BrainCertSpec, Rejection)   proofs.py (P01–P19)   suite.py (make_certification_tests)
                     env.py (repo access, local SHADOW rig, sealed probes, AST scanners)
                     contract.py (ContractSpec, describe_contract, run_describe_cli)   mutations.py
  tests/             hygiene guards · unit tests · proofs on a SYNTHETIC Brain
  pytest.ini
```
Location: `tools/` is the established home of repository tooling (`tools/architecture`); `platform/` is structure-only today and its name would shadow the stdlib `platform` module if the repo root were ever on `sys.path`. The kit is **test-only** and is never vendored into a deploy image (it is not inside `sector_brain_platform`).

## The 19 proofs
P01 location & identity map · P02 one implementation (+ retirement pointer) · P03 identity / lifecycle / Publisher state / consumers (brain.json == control manifest == artifact lineage) · P04 operating contract (19 sections, required statements) · P05 published contract derived from the registry · P06 declared dependencies exact, resolvable, drift-free, no fabricated signals · P07 artifact valid and deterministic · P08 fingerprint stable, SKIP on unchanged, changes on real change · P09 lineage truthful, never optimistic · P10 healthV1 from engine truth, UNKNOWN honest · P11 Publisher SHADOW only, end-to-end, plan roots · P12 Publisher rejections (cross-Brain, reserved, node replacement, section-crossing, foreign writer, production lifecycle, release/freshness) · P13 typed deletes, null ≠ delete · P14 direct-write sites AST-pinned · P15 artifact builder cannot write · P16 runtime isolation paths · P17 research separate from runtime · P18 architecture gates (NEW 0, carried baseline) · P19 score / lifecycle unchanged.
Plus, per Brain: a mutation test for every proof (≈ 30): perturb ONE declared truth (or the artifact) and require the matching proof to **fail**; a spec-validity test; a completeness test (`every proof has a mutation that defeats it`).

## The spec (parameters)
| Group | Fields |
|---|---|
| identity | `brain_id`, `directory`, `repo_root` |
| declared truth | `lifecycle`, `cutover_status`, `workspace_id`, `authorized_consumers`, `consumes` (exact), `providers` (exact), `customer_integration_mode`, `runtime_kind`, `providers_match_registry_sources` |
| package shape | `required_files`, `unique_module_basenames`, `legacy_pointer_dir`, `runtime_dir`, `allowed_runtime_ext`, `research_files`, `contract_tokens` / required / forbidden terms |
| Publisher | `bundle_id`, `contract_file`, `registry_schema_id`, `registry_probe_child`, `job_id`, `plan_root_prefixes`, `extra_rejections` |
| write isolation | `write_call_suffixes`, `allowed_write_sites` (== the direct-write audit table), `forbidden_imports`, `builder_module`, `builder_forbidden_*`, `local_path_regex`, `local_path_exempt_markers` |
| gates | `arch_findings`, `baseline_entry_basenames`, `baseline_carried_from_required`, `score_baseline_substring` |
| artifact | `artifact_factory(n, generated_at, consumed, rerun)`, `changed_artifact_factory`, `release_lineage` (`NONE`×3 or `None` = a real release), `expected_review_status`, `expected_validation_status`, `consumed_absent_when_unknown` |
| declared non-applicability | `not_applicable {proof id: reason}` — skipped **visibly** with the reason; a reason shorter than four words is rejected |

## Constraints that prevent domain leakage (enforced by `tests/test_kit_hygiene.py`)
No Brain name, no domain term, no per-Brain conditional (`if brain_id == …`) in the shared code; only stdlib + `sector_brain_platform` + `tools/architecture` + pytest imports; no absolute or private paths. Brain-specific truth is data in the spec; a Brain-specific *behaviour* belongs in that Brain's own tests. The kit cannot import or read a Brain's science.

## How Brain #4 adopts the kit (minimum)
1. Follow the Factory checklist up to Phase 6 (brain.json, contract, artifact builder, Publisher registration in `registry.py`, runtime in `brains/<dir>/runtime`).
2. `brains/<dir>/pytest.ini`: add `../../tools/brain_certification` (and `../../jobs/brain_platform`) to `pythonpath`.
3. `brains/<dir>/tests/<brain>_cert_spec.py`: build `SPEC = BrainCertSpec(...)` and an `artifact_factory` (≈ 50 lines; copy the nearest existing spec).
4. `brains/<dir>/tests/test_<brain>_kit_certification.py`: `globals().update(make_certification_tests(SPEC))` (6 lines).
5. `brains/<dir>/contracts/describe_contract.py`: a `ContractSpec` + `run_describe_cli` (≈ 35 lines); `--write` then `--check`.
6. Write only the **domain** tests locally: science golden, domain freshness, input truth, write-set classification, staged-layout run, private-marker scan.
7. Mandatory: every mutation test and every proof green; any proof that cannot apply gets `not_applicable[...] = "<real reason>"` and a line in the certification report.
Do **not** copy a Brain's certification suite again.

## Migration notes for the existing Brains
- Water Clarity: 21 generic tests replaced by the kit (44 → 27 local `def test_`; 52 kit tests added). Fish: 17 replaced (33 → 18; 2 domain remainders added). Wind: 3 package tests replaced (9 → 6) and the 19 proofs now also run for Wind (Wind gains P06–P15, P17–P19 coverage it never had, including the AST write-site pin that closes **D-8**).
- Wind's clean-copy production gate now excludes the kit certification module (the kit needs the whole repository).
- Contract JSONs are unchanged byte for byte (sha256 recorded in the report).
