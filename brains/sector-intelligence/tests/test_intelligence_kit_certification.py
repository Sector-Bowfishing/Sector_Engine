"""Sector Intelligence structural certification — the SHARED proofs of BRAIN_CERT_KIT_V1 (tools/brain_certification), parametrised by
intelligence_cert_spec.SPEC. Synthesis-specific behaviour (dependency truth, degrade/abstain, pilot evaluation) is in the Brain's other tests."""
from brain_cert_kit import make_certification_tests
from intelligence_cert_spec import SPEC

globals().update(make_certification_tests(SPEC))
