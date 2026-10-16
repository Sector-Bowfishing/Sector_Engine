# Large and generated data policy (Repository Architecture V1, RA-15)

**Rule:** a tracked file ≥ 1 MB (1,048,576 bytes) requires an explicit recorded exception. Report-only until its owning migration phase: `python3 tools/architecture/report.py` (invariant 15); exceptions are recorded in `tools/architecture/large_file_exceptions.json`.

An exception entry records: `path`, `reason`, and, for generated or source-controlled runtime data, `source`, `generator`, `version`, `provenance`, and `rebuild` instructions (how to regenerate it byte-for-byte or why it cannot be).

Preferred alternatives, in order: (1) build the artifact at build time from a small source; (2) store it as a canonical versioned release and track only a manifest (URI/version/hash) in Git; (3) record an exception.

Raw research data never belongs in Git (invariant 16): `brains/<dir>/research/` holds `GAPS.json`, `MANIFEST.json`, a README and small reproducible tools only.

**Phase 1A scope:** the policy and the report exist. No existing large file was deleted, moved or "fixed"; no exception was recorded. Baseline findings are listed in `PHASE_1A_IMPLEMENTATION.md`.
