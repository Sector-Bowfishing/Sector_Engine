# PRODUCTION_EXIT_GATE_V1 — reusable production Publisher exit gate

**Status:** definition + evaluator only. Nothing here executes against production. Implementation: `tools/brain_certification/brain_cert_kit/exit_gate.py`; tests: `tools/brain_certification/tests/test_exit_gate.py`.
**Why separate from the 19 structural proofs:** the structural kit runs offline in CI for every Brain and must stay hermetic. This gate contains LIVE checks (real readback, forced failure, write-denial) that only a reviewed cutover runbook can execute. The kit therefore ships the gate as **data + a pure evaluator + a cutover guard**, not as live tests.

## Contract
* Evidence record: `brains/<dir>/contracts/production-exit-evidence.json` = `{"standard":"production-exit-gate-v1","brainId":"…","checks":{"X01":{"status":"PASS|FAIL|NOT_RUN","evidenceRef":"…","mode":"OFFLINE|LIVE"},…}}`. Raw security detail stays private; `evidenceRef` points at a private record, the repo stores pass/fail.
* `evaluate()` is PASS only if all 16 checks are PASS with a non-empty `evidenceRef`, modes match the definition, the `brainId` matches and nothing unknown is present.
* `cutover_guard(brain_dir)`: `publisherRequired.cutoverStatus` must be `SHADOW`, `CUTOVER_IN_PROGRESS` or `CUTOVER_COMPLETE`; **`CUTOVER_COMPLETE` requires a PASSing record**. A test pins that Wind, Fish and Water Clarity are `SHADOW` and have no evidence file (no one can claim cutover early).

## The checks
| ID | Check | Mode | Maps to |
|---|---|---|---|
| X01 | artifact accepted | OFFLINE | G |
| X02 | correct Brain identity | OFFLINE | G |
| X03 | correct schema (unregistered/mismatched rejected) | OFFLINE | G |
| X04 | path ownership (plan inside declared families; cross-domain rejected) | OFFLINE | G, F |
| X05 | deterministic fingerprint | OFFLINE | G |
| X06 | unchanged artifact SKIPs, zero live writes | OFFLINE | G |
| X07 | changed artifact publishes; readback shows change | LIVE | G |
| X08 | unrelated Brain paths untouched (before/after export diff) | LIVE | G, I |
| X09 | atomic write; forced mid-write failure leaves prior state intact | LIVE | G |
| X10 | publication metadata correct | LIVE | G |
| X11 | health remains correct (healthV1 not blanked / not wrongly HEALTHY) | LIVE | I |
| X12 | score ownership and value unchanged (same scoreType/scoreVersion) | LIVE | H |
| X13 | rollback restores pre-cutover state | LIVE | G |
| X14 | legacy writer cannot re-enter (zero RTDB write sites on Publisher-owned paths; brain.json status and AST pin agree) | OFFLINE | F |
| X15 | authoritative readback equals publication | LIVE | G |
| X16 | write denial: specialist, Ops, cross-domain denied; Publisher allowed (rules AND IAM) | LIVE | **F** |

OFFLINE checks can be run today against the SHADOW Publisher (most are already covered by the 19 kit proofs; X14 is the AST pin + invariant 10). LIVE checks need P1-P6/P12 and the security gate. Scope note: rollback and atomicity (X09, X13) cover Publisher-owned RTDB paths only; Brain-owned GCS storage is outside the Publisher by design.
