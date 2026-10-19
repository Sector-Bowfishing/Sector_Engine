import dataclasses
import json
import os
import sys

import pytest

from brain_cert_kit import BrainCertSpec, ContractSpec, SpecError, describe_contract, make_certification_tests, run_describe_cli, PROOF_IDS
from brain_cert_kit.env import imported_roots, normalise_family, uid, write_sites
from brain_cert_kit.proofs import PROOFS

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))


def _spec(tmp_path, **kw):
    (tmp_path / "brains" / "synth").mkdir(parents=True, exist_ok=True)
    base = dict(brain_id="synth", directory="synth", repo_root=str(tmp_path), lifecycle="CALIBRATION", workspace_id="synth", bundle_id="b", contract_file="c.json",
                registry_schema_id="s", builder_module="runtime/b.py", artifact_factory=lambda *a: {})
    base.update(kw)
    return BrainCertSpec(**base)


def test_proofs_are_uniquely_numbered_and_named():
    ids = [p for p, _, _ in PROOFS]
    assert ids == sorted(set(ids)) and ids == list(PROOF_IDS) and len(ids) == 19
    assert len({slug for _, slug, _ in PROOFS}) == 19


def test_spec_validation_requires_core_truth_and_real_reasons(tmp_path):
    assert _spec(tmp_path).validate()
    with pytest.raises(SpecError):
        _spec(tmp_path, lifecycle="").validate()
    with pytest.raises(SpecError):
        _spec(tmp_path, artifact_factory=None).validate()
    with pytest.raises(SpecError):
        _spec(tmp_path, not_applicable={"P08": "no"}).validate()
    assert _spec(tmp_path, artifact_factory=None, not_applicable={"ARTIFACT": "this Brain has no artifact builder yet"}).validate()
    with pytest.raises(SpecError):
        BrainCertSpec(brain_id="x", directory="missing", repo_root=str(tmp_path), lifecycle="L", workspace_id="w", bundle_id="b", contract_file="c", registry_schema_id="s",
                      builder_module="m", artifact_factory=lambda *a: {}).validate()


def test_spec_is_immutable_data(tmp_path):
    s = _spec(tmp_path)
    with pytest.raises(dataclasses.FrozenInstanceError):
        s.lifecycle = "PRODUCTION"


def test_suite_generates_one_test_per_proof_plus_guards_and_skips_visibly(tmp_path):
    tests = make_certification_tests(_spec(tmp_path, not_applicable={"P08": "justified because there is no changed artifact"}))
    for pid, slug, _ in PROOFS:
        assert f"test_cert_{pid.lower()}_{slug}" in tests
    assert "test_cert_spec_is_valid_and_every_not_applicable_names_a_real_proof" in tests
    with pytest.raises(pytest.skip.Exception) as e:
        tests["test_cert_p08_fingerprint_stability_and_skip"]()
    assert "NOT_APPLICABLE" in str(e.value) and "justified" in str(e.value)
    bad = make_certification_tests(_spec(tmp_path, not_applicable={"P99": "a reason that is long enough"}))
    with pytest.raises(AssertionError):
        bad["test_cert_spec_is_valid_and_every_not_applicable_names_a_real_proof"]()


def test_ast_write_site_scanner(tmp_path):
    f = tmp_path / "m.py"
    f.write_text("import json\nclass W:\n    def patch(self, u):\n        self._db.update(u)\n        self._store.update(u)\n    def other(self):\n        d = {}\n        d.update({})\n        json.dump(1, 2)\n"
                 "def top(rtdb):\n    rtdb.update({})\n")
    assert write_sites(str(f), ("_db.update",)) == {("m.py", "patch", "self._db.update")}
    assert write_sites(str(f), ("rtdb.update",)) == {("m.py", "top", "rtdb.update")}
    assert write_sites(str(f), ("_store.update", "_db.update")) == {("m.py", "patch", "self._db.update"), ("m.py", "patch", "self._store.update")}
    assert write_sites(str(f), ("nothing.update",)) == set()


def test_import_root_scanner_ignores_relative_imports(tmp_path):
    f = tmp_path / "m.py"
    f.write_text("import os.path\nfrom urllib import request\nfrom . import sibling\nfrom .pkg import x\nimport a.b.c\n")
    assert imported_roots(str(f)) == {"os", "urllib", "a"}


def test_small_helpers():
    assert normalise_family("/lakes/{k}/states/{slot}") == "/lakes/{}/states/{}"
    assert uid(1) == uid(1) and uid(1) != uid(2) and len(uid(7)) == 36


def _any_registered_bundle():
    from sector_brain_platform.publisher import default_registry
    reg = default_registry()
    b = next(iter(reg._bundles.values()))
    return b.bundle_id


def test_contract_descriptor_is_deterministic_checkable_and_rejects_unknown_input(tmp_path):
    bid = _any_registered_bundle()
    cs = ContractSpec(contract_dir=str(tmp_path), out_file="x.json", bundle_id=bid, builder="b.py", derived_from="registry", status="SHADOW test",
                      section_fields=("families", "deleteFamilies"), extras={"lit": {"a": 1}, "ver": ("volatile",)})
    d1, d2 = describe_contract(cs), describe_contract(cs)
    assert json.dumps(d1, sort_keys=True) == json.dumps(d2, sort_keys=True) and d1["contractId"] == bid and d1["lit"] == {"a": 1} and "volatileContract" not in d1["sections"][0]
    assert run_describe_cli(cs, ["--check"]) == 1                              # file absent => stale
    assert run_describe_cli(cs, ["--write"]) == 0 and run_describe_cli(cs, ["--check"]) == 0
    (tmp_path / "x.json").write_text("{}")
    assert run_describe_cli(cs, ["--check"]) == 1                              # drift is detected
    with pytest.raises(ValueError):
        ContractSpec(contract_dir=str(tmp_path), out_file="x", bundle_id=bid, builder="b", derived_from="d", status="s", section_fields=("nonsense",))
    with pytest.raises(ValueError):
        ContractSpec(contract_dir=str(tmp_path), out_file="x", bundle_id=bid, builder="b", derived_from="d", status="s", extras={"k": ("registry", "A", "bad-transform")})
    with pytest.raises(ValueError):
        describe_contract(dataclasses.replace(cs, bundle_id="not-registered"))
