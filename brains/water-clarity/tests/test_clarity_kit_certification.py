"""Water Clarity structural certification — the SHARED proofs of BRAIN_CERT_KIT_V1 (tools/brain_certification), parametrised by clarity_cert_spec.SPEC.
Domain-specific proofs (input truth, domain freshness, science golden, write-set classification, engine-miss path) are in test_clarity_certification.py."""
from brain_cert_kit import make_certification_tests
from clarity_cert_spec import SPEC

globals().update(make_certification_tests(SPEC))
