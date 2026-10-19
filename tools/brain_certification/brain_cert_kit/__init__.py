"""BRAIN_CERT_KIT_V1 — the shared structural-certification machinery of the Brain Factory (D-7b).

It encodes HOW a Brain is structurally certified (location, identity, ownership, input declarations, artifact contract, lineage, health, Publisher SHADOW
compatibility, direct-write isolation, runtime/research separation, architecture gates, score/lifecycle truth) and NEVER what a Brain knows. A Brain supplies
a declarative `BrainCertSpec` (plus a small artifact factory); domain science, goldens and domain freshness stay in the Brain's own tests.

    from brain_cert_kit import BrainCertSpec, make_certification_tests
    globals().update(make_certification_tests(SPEC))            # in brains/<dir>/tests/test_<brain>_certification.py

Import root: add `../../tools/brain_certification` to the Brain's pytest.ini `pythonpath` (next to `../../jobs/brain_platform`). Test-only: never vendored into a deploy image.
"""
from .contract import ContractSpec, describe_contract, run_describe_cli
from .spec import BrainCertSpec, Rejection, SpecError
from .suite import make_certification_tests, PROOF_IDS

KIT_VERSION = "BRAIN_CERT_KIT_V1"
__all__ = ["BrainCertSpec", "ContractSpec", "Rejection", "SpecError", "describe_contract", "run_describe_cli", "make_certification_tests", "PROOF_IDS", "KIT_VERSION"]
