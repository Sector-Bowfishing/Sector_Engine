"""Fish structural certification — the SHARED proofs of BRAIN_CERT_KIT_V1 (tools/brain_certification), parametrised by fish_cert_spec.SPEC.
Domain-specific proofs (species identity, release lineage, typed species deletes, the science golden, staged-layout run) are in test_fish_certification.py."""
from brain_cert_kit import make_certification_tests
from fish_cert_spec import SPEC

globals().update(make_certification_tests(SPEC))
