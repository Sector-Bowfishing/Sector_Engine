"""Wind structural certification — the SHARED proofs of BRAIN_CERT_KIT_V1 (tools/brain_certification), parametrised by wind_cert_spec.SPEC.
Wind's Gate-P / equivalence / snapshot-projection tests stay in test_publish_artifact.py; its package, staging and import-boundary gates stay in
verification/integration/test_wind_package.py. This module needs the whole repository (platform registries, schemas, control manifest); the clean-copy gate excludes it."""
from brain_cert_kit import make_certification_tests
from wind_cert_spec import SPEC

globals().update(make_certification_tests(SPEC))
