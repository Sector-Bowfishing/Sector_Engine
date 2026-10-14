# Brain Spec — template

Copy to `docs/brains/<brain>/BRAIN_SPEC.md`. One page. Delete a row only if it truly does not apply, and say so. Specialists fill the science; the platform fixes the vocabulary.

| | |
|---|---|
| **Brain id / slot / snapshot field** | `brainId`, `/lakes/{k}/states/{slot}`, snapshot field (must appear in `BRAIN_PLATFORM_CONTRACT.md` §2) |
| **Question it answers** | one sentence, customer-comprehensible |
| **Owner / lane / branch** | |
| **Lifecycle** | one of `RESEARCH PROFILED SHADOW CALIBRATION PRODUCTION_READY PRODUCTION` (+ legacy `status` while migrating) |
| **Execution type** | one of `PROVIDER_INGESTION DEPENDENCY_DRIVEN PROSPECTIVE_VALIDATION MAINTENANCE MANUAL_SHADOW`; if a recurring schedule exists, which of A/B/C/D justifies it |
| **Staleness model** | `TIME` (+ `staleAfterHours`) / `VERSION` / `FINGERPRINT` |
| **Fingerprint ingredients** | material inputs; confirm volatile fields excluded |
| **Canonical runtime state** | node, state schema id, compact (no research artifacts as runtime inputs) |
| **Dependencies** | per dependency: id, REQUIRED/OPTIONAL, min claim maturity, stateVersion, freshness authority (owner's, or documented stricter rule), fallback |
| **Claim table** | per claim: id, **level (1/2/3)**, **maturity**, evidence, limits |
| **Score** | rubric id/version; what is `underlyingScore`, `canonicalScore`; critical dimensions (production needs each ≥ 7.5) ; source of the score (computed by platform from published facts, or generated artifact with its generator command) |
| **Validation** | gate(s), pre-registered (yes/no), truth type, status |
| **Field validation** | block fields registered in `field_validation.BLOCKS` |
| **Customer path** | what the customer runtime reads, size, and confirmation it does no heavy compute |
| **Ops summary** | which `brain-control-v1` fields it fills (omit meaningless ones) |
| **Unknown policy** | which fields can be UNKNOWN/NOT_OBSERVABLE/WITHHELD and how they are published |
| **Cost** | scheduler jobs, Cloud Run jobs, RTDB writes/run, storage, egress; scale-to-zero? |
| **Runner safety** | any thread/process pool: worker count clamped ≥ 1 (`bounded_workers`); empty work list is a successful no-op |
| **Stop conditions** | when further research is not warranted without new truth |
| **Handoffs** | folder + `HANDOFF_INDEX.md` pointer |
