"""Mutation tests: for a Brain's spec, perturb ONE declared truth (or the artifact it builds) and require the matching proof to FAIL.
A proof that cannot fail is not a proof; running this for every adopting Brain shows the kit is sensitive on that Brain's real files, with no Brain-specific code."""
from __future__ import annotations

import copy
import dataclasses
import json
import random

from . import proofs as P
from .env import Env, imported_roots
from .spec import Rejection


def _a_builder_import(spec):
    """A module the Brain's builder really imports (sorted, first), declared forbidden: P15 must then fail. Brain-agnostic (no assumption that a builder
    imports any particular module); falls back to "json" when the builder cannot be read."""
    import os
    try:
        roots = sorted(imported_roots(os.path.join(spec.brain_dir, spec.builder_module)) - {"__future__"})
    except (OSError, SyntaxError):
        roots = []
    return (roots[0],) if roots else ("json",)


def _tamper_fingerprint(factory):
    def f(n, gen, consumed, rerun):
        a = factory(n, gen, consumed, rerun)
        a = copy.deepcopy(a)
        a["lineage"]["outputFingerprint"] = "sha256:" + "0" * 64
        return a
    return f


def _nondeterministic(factory):
    def f(n, gen, consumed, rerun):
        a = copy.deepcopy(factory(n, gen, consumed, rerun))
        a["lineage"]["codeVersion"] = f"{a['lineage']['codeVersion']}-{random.random()}"
        return a
    return f


def _optimistic_validation(factory):
    def f(n, gen, consumed, rerun):
        a = copy.deepcopy(factory(n, gen, consumed, rerun))
        a["lineage"]["validationStatus"] = "VALIDATED"
        return a
    return f


def _leaky_consumed(factory):
    def f(n, gen, consumed, rerun):
        a = copy.deepcopy(factory(n, gen, consumed, rerun))
        a.setdefault("consumed", [])
        return a
    return f


def _score_writer(factory):
    def f(n, gen, consumed, rerun):
        a = copy.deepcopy(factory(n, gen, consumed, rerun))
        a["sections"][0]["mutations"].append({"op": "SET", "path": "/scores/probe", "value": {"v": 1}})
        return a
    return f


def _execution_dependent_fingerprint(factory):
    def f(n, gen, consumed, rerun):
        a = copy.deepcopy(factory(n, gen, consumed, rerun))
        if n != 1:
            a["lineage"]["outputFingerprint"] = f"sha256:{n:064x}"
        return a
    return f


def _bad_delete(factory):
    def f(n, gen, consumed, rerun):
        a = copy.deepcopy(factory(n, gen, consumed, rerun))
        a["sections"][0]["mutations"].append({"op": "DELETE", "path": "/probe", "reason": "NOT_IN_ANY_CLOSED_VOCABULARY"})
        return a
    return f


def mutation_cases(spec):
    """[(name, proof function, mutated spec)] — every mutation must make its proof raise AssertionError."""
    r = dataclasses.replace
    cases = [
        ("lifecycle_drift", P.p03_identity_lifecycle_publisher_state, r(spec, lifecycle="PRODUCTION")),
        ("cutover_status_drift", P.p03_identity_lifecycle_publisher_state, r(spec, cutover_status="CUTOVER_COMPLETE")),
        ("workspace_drift", P.p03_identity_lifecycle_publisher_state, r(spec, workspace_id="some-other-workspace")),
        ("authorized_consumers_drift", P.p03_identity_lifecycle_publisher_state, r(spec, authorized_consumers=tuple(spec.authorized_consumers) + ("unknown-consumer",))),
        ("undeclared_extra_consume", P.p06_declared_dependencies_exact, r(spec, consumes=tuple(spec.consumes) + ({"kind": "signal", "signalId": "invented-signal"},))),
        ("undeclared_extra_provider", P.p06_declared_dependencies_exact, r(spec, providers=tuple(spec.providers) + ("invented-provider",))),
        ("wrong_bundle", P.p05_published_contract_derived_from_registry, r(spec, bundle_id="not-a-registered-bundle-v1")),
        ("missing_required_file", P.p01_location_and_shape, r(spec, required_files=tuple(spec.required_files) + ("does/not/exist.txt",))),
        ("missing_unique_module", P.p02_one_production_implementation, r(spec, unique_module_basenames=tuple(spec.unique_module_basenames) + ("no_such_module_anywhere.py",))),
        ("contract_missing_statement", P.p04_operating_contract, r(spec, contract_tokens=tuple(spec.contract_tokens) + ("THIS-SENTENCE-IS-NOT-IN-ANY-CONTRACT",))),
        ("extra_write_site_unaccounted", P.p14_direct_write_sites_pinned, r(spec, allowed_write_sites=frozenset(spec.allowed_write_sites) | {("ghost.py", "ghost", "x.update")})),
        ("write_site_not_in_audit", P.p14_direct_write_sites_pinned, r(spec, allowed_write_sites=frozenset())),
        ("write_primitive_unrecognised", P.p14_direct_write_sites_pinned, r(spec, write_call_suffixes=("no_such_client.update",))),
        ("builder_imports_io", P.p15_artifact_path_cannot_write, r(spec, builder_forbidden_imports=_a_builder_import(spec))),
        ("builder_uses_forbidden_token", P.p15_artifact_path_cannot_write, r(spec, builder_forbidden_tokens=("import",))),
        ("runtime_path_leak", P.p16_runtime_isolation_paths, r(spec, local_path_regex=r"import ")),
        ("runtime_has_non_code_file", P.p17_research_separate_from_runtime, r(spec, allowed_runtime_ext=(".nonexistent",))),
        ("architecture_finding_not_carried", P.p18_architecture_gates_no_new_violations, r(spec, arch_findings=())),
        ("baseline_entry_unexpected", P.p18_architecture_gates_no_new_violations, r(spec, baseline_entry_basenames=("ghost.py",))),
        ("plan_root_not_declared", P.p11_publisher_shadow_only_end_to_end, r(spec, plan_root_prefixes=("zzz-no-such-root/",))),
        ("rejection_code_wrong", P.p12_publisher_rejections, r(spec, extra_rejections=tuple(spec.extra_rejections) + (Rejection("/scores/probe", "NOT_A_REAL_CODE"),))),
        ("artifact_fingerprint_tampered", P.p07_artifact_publisher_valid_and_deterministic, r(spec, artifact_factory=_tamper_fingerprint(spec.artifact_factory))),
        ("artifact_nondeterministic", P.p07_artifact_publisher_valid_and_deterministic, r(spec, artifact_factory=_nondeterministic(spec.artifact_factory))),
        ("validation_status_optimistic", P.p09_lineage_truthful_never_optimistic, r(spec, artifact_factory=_optimistic_validation(spec.artifact_factory))),
        ("release_lineage_invented", P.p09_lineage_truthful_never_optimistic, r(spec, release_lineage=("invented", "invented", "invented"))),
        ("fingerprint_depends_on_execution", P.p08_fingerprint_stability_and_skip, r(spec, artifact_factory=_execution_dependent_fingerprint(spec.artifact_factory))),
        ("brain_not_registered_for_health", P.p10_health_v1_from_engine_truth, r(spec, brain_id="no-such-registered-brain")),
        ("delete_outside_closed_vocabulary", P.p13_typed_deletes_and_null_is_not_delete, r(spec, artifact_factory=_bad_delete(spec.artifact_factory))),
        ("artifact_writes_a_score", P.p19_score_and_lifecycle_unchanged, r(spec, artifact_factory=_score_writer(spec.artifact_factory))),
    ]
    if spec.consumed_absent_when_unknown:
        cases.append(("consumed_emitted_when_unknown", P.p09_lineage_truthful_never_optimistic, r(spec, artifact_factory=_leaky_consumed(spec.artifact_factory))))
    if spec.score_baseline_substring:
        cases.append(("score_baseline_mismatch", P.p19_score_and_lifecycle_unchanged, r(spec, score_baseline_substring="no-such-brain=99.9/10")))
    return cases

