# tools/brain_certification — BRAIN_CERT_KIT_V1

The shared structural-certification kit of the Brain Factory (D-7b). It encodes **how** a Brain is certified, never **what** a Brain knows. Design, parameters, the 19 proofs and the adoption guide for the next Brain: `docs/architecture/certification/brain-cert-kit/BRAIN_CERT_KIT_V1.md`. Duplication inventory and migration report next to it.

```bash
python -m pytest -q tools/brain_certification        # the kit's own tests (synthetic Brain; no real Brain involved)
cd brains/<dir> && python -m pytest -q               # a Brain's suite (its tests/*_kit_certification.py runs the shared proofs)
```
Test-only; never vendored into a deploy image. Import root for a Brain: add `../../tools/brain_certification` to its `pytest.ini` `pythonpath`.
