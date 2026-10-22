"""water-temp structural certification — the SHARED proofs of BRAIN_CERT_KIT_V1 (tools/brain_certification), parametrised by water_temp_cert_spec.SPEC.
Domain science, the write-set fixture and the runner's behaviour are in the Swift tests (tests/swift)."""
from brain_cert_kit import make_certification_tests
from water_temp_cert_spec import SPEC

globals().update(make_certification_tests(SPEC))
