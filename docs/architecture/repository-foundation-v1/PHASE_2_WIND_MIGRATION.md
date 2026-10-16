# Repository Phase 2 — Wind Brain physical migration (implementation record)

**Status: `WIND_REPOSITORY_PHASE_2_COMPLETE`** (2026-10-16), branch `migrate/wind-brain-v1` (based on foundation `988d6745`, local until approved). Wind record: `docs/architecture/certification/wind/WIND_REPOSITORY_MIGRATION_V1.md`.

What changed in the repository foundation itself:
- **First registered Brain.** `brains/wind/brain.json` exists; `report.py` scans 1 Brain (all 16 invariants evaluated; inv 8 reports the two carried Wind label entries). No other `brain.json` was created (gate: `test_real_repo_registers_only_migrated_brains`).
- **Provider catalog.** `providers/PROVIDERS.json` registers only Wind's three Brain-exclusive sources; nothing else adopted.
- **CI.** `python-jobs-tests.yml` gains `registered-brains`: for each `brains/*/brain.json` it installs `runtime/requirements.txt` + `research/tools/requirements.txt` and runs the Brain's suite from its canonical location, then the Wind package gates with dependency gates mandatory (`SECTOR_REQUIRE_WIND_DEPS=1`). The legacy wind-hourly step is gone (no legacy copy left to test). Not yet run on GitHub.
- **Verification.** `verification/integration/test_wind_package.py` (9 gates: identity, contract, contract-vs-Publisher-registry, runtime/research boundary + Mac paths, reachability, single implementation, exact staged image context, image-layout import, clean-copy production tests).
- **Architecture tooling.** Customer-endpoint detector (inv 11) now matches only the endpoints `/conditions` / `/lakes` (RTDB `/lakes/{k}/…` paths were false positives); `--write-baseline` preserves curated annotations; ownership map gains `brains/wind`; vacuous-PASS note only when 0 Brains.
- **Baseline.** 21 entries: `jobs/wind-hourly/.../writer.py` RESOLVED by the move; `brains/wind/.../writer.py` (carried) and `profile.py` (newly detected by the stricter Brain-runtime scan) recorded as Wind published provenance labels with a retirement condition. 0 NEW.
- **Score baseline** unchanged (no score file moved).

Deviations from the Phase 2 prompt / target: no `artifact/`, `scoring/`, `validation/` directories (not triggered yet; see the Wind record §2); research tools stay in Git under `research/tools/` (per-script classification deferred to Wind certification); research default paths not repointed (approval + collector); `SECTOR_WIND_RESEARCH_ROOT` not introduced; platform package still imported from its legacy location `jobs/brain_platform`.
