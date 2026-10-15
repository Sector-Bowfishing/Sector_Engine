# Brain package checklist (use at each Brain's migration/certification)

- [ ] `README.md`, `BRAIN_OPERATING_CONTRACT.md` (all 19 headings, bowfisher terminology), `brain.json` present
- [ ] `brain.json` validates against `contracts/schemas/brain.schema.json`; `brainId` unchanged from the live machine id
- [ ] `contracts/` holds each published schema listed in `publishes[]` (or `publishes: []` with `publishesReason`)
- [ ] `runtime/` entrypoint and `tests/` paths in `brain.json` exist
- [ ] providers listed exist in `providers/PROVIDERS.json` and the Brain is an `authorizedConsumer`
- [ ] lake/species identity consumed via registry contracts, not via Lake/Fish Brain
- [ ] `customerIntegrationMode` set deliberately (`none` default); direction is Customer Engine → Brain contract
- [ ] research workspace is a logical id; `research/GAPS.json` + `MANIFEST.json` validate; no data in Git
- [ ] no tracked file ≥ 1 MB without a recorded exception; no absolute path; no runtime read of `docs/`
- [ ] `python3 tools/architecture/report.py` shows no findings for this Brain
- [ ] research artifacts classified GitHub / research workspace / canonical storage (RA-17); nothing copy-and-forget
- [ ] score unchanged by the migration (certification never moves a score)
