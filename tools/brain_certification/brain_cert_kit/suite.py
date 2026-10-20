"""Builds the pytest test functions for one Brain from its BrainCertSpec.

    globals().update(make_certification_tests(SPEC))

Each proof becomes `test_cert_<id>_<slug>`; a proof the spec declares not applicable is skipped VISIBLY with its recorded reason."""
from __future__ import annotations

from .env import Env
from .mutations import mutation_cases
from .proofs import PROOFS

PROOF_IDS = tuple(pid for pid, _, _ in PROOFS)


def make_certification_tests(spec) -> dict:
    import pytest
    holder = {}

    def env() -> Env:
        if "e" not in holder:
            holder["e"] = Env(spec)
        return holder["e"]

    def make(pid, slug, fn):
        def test():
            why = spec.not_applicable.get(pid)
            if why:
                pytest.skip(f"NOT_APPLICABLE ({spec.brain_id} {pid}): {why}")
            fn(env())
        test.__name__ = f"test_cert_{pid.lower()}_{slug}"
        test.__qualname__ = test.__name__
        test.__doc__ = f"BRAIN_CERT_KIT_V1 {pid}: {slug.replace('_', ' ')}"
        return test

    out = {}
    for pid, slug, fn in PROOFS:
        t = make(pid, slug, fn)
        out[t.__name__] = t

    def test_cert_spec_is_valid_and_every_not_applicable_names_a_real_proof():
        spec.validate()
        unknown = set(spec.not_applicable) - set(PROOF_IDS) - {"ARTIFACT", "FINGERPRINT_CHANGE"}
        assert not unknown, f"not_applicable names unknown proofs: {sorted(unknown)}"
    out[test_cert_spec_is_valid_and_every_not_applicable_names_a_real_proof.__name__] = test_cert_spec_is_valid_and_every_not_applicable_names_a_real_proof

    # mutation tests: one perturbed truth => the matching shared proof MUST fail (a proof that cannot fail proves nothing)
    pid_of = {fn: pid for pid, _, fn in PROOFS}

    def make_mutation(name, fn, mutated):
        def test():
            if "ARTIFACT" in spec.not_applicable:
                pytest.skip("NOT_APPLICABLE: no artifact factory")
            if pid_of.get(fn) in spec.not_applicable:                     # the proof itself is declared not applicable (skipped visibly), so is its mutation
                pytest.skip(f"NOT_APPLICABLE ({spec.brain_id} {pid_of[fn]}): {spec.not_applicable[pid_of[fn]]}")
            with pytest.raises(AssertionError):
                fn(Env(mutated))
        test.__name__ = f"test_cert_mutation_{name}"
        test.__qualname__ = test.__name__
        test.__doc__ = f"BRAIN_CERT_KIT_V1 mutation: {name.replace('_', ' ')} must be detected"
        return test
    def test_cert_every_proof_has_a_mutation_that_defeats_it():
        if "ARTIFACT" in spec.not_applicable:
            pytest.skip("NOT_APPLICABLE: no artifact factory")
        covered = {fn for _, fn, _ in mutation_cases(spec)}
        missing = [pid for pid, _, fn in PROOFS if fn not in covered]
        assert not missing, f"proofs with no mutation test (a proof that cannot fail proves nothing): {missing}"
    out[test_cert_every_proof_has_a_mutation_that_defeats_it.__name__] = test_cert_every_proof_has_a_mutation_that_defeats_it
    for name, fn, mutated in mutation_cases(spec):
        t = make_mutation(name, fn, mutated)
        out[t.__name__] = t
    return out
