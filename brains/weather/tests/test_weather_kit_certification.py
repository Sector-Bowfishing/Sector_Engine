"""Weather structural certification — the SHARED proofs of BRAIN_CERT_KIT_V1 (tools/brain_certification), parametrised by weather_cert_spec.SPEC."""
from brain_cert_kit import make_certification_tests
from weather_cert_spec import SPEC

globals().update(make_certification_tests(SPEC))
