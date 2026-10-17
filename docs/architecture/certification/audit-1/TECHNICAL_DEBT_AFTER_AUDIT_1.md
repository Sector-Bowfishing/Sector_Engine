# Technical debt after Architecture Audit #1

Priority: **P0** blocks next Brain / parallel lanes · **P1** fix soon, does not block · **P2** cleanup / scalability · **P3** polish. **P0 count: 0.** Triggers are events, not dates; nothing here is a pre-phase before lane work. Owners are roles (platform lane = the session working `jobs/brain_platform` / Orchestrator; Brain lane = that Brain's session; Michael = decision).

| ID | Item | P | Owner | Trigger | Recommended phase |
|---|---|---|---|---|---|
| D-1 | **Orchestrator runs in-process Brains by directory path** (`_fish_runtime_dir`, `deploy-job.sh` staging, `brain_platform.py` resolver). Fix = runner derived from `brain.json.runtime.{kind,entrypoint}` + staging derived from `brains/*/brain.json`. Not needed for job-kind Brains (Clarity). | **P1** | platform lane | before the *next in-process* Brain is registered (Depth / Vegetation / Sector Intelligence), and before any Orchestrator deploy that must stage a third path | Repo Phase 6/7 platform step; design first, small |
| D-2 | `deploy-job.sh` stages Fish under legacy `jobs/biological-brain` | P2 | platform lane | retires with D-1 | with D-1 |
| D-3 | **ENGINE_READINESS_SCORE means different things per Brain**; no `architectureStatus` field; Wind's stale 3.1 mirror + nested BWIS | P2 | Michael (decision) → platform lane | before an Ops surface ranks/compares Brains by score, or before Sector Intelligence consumes scores | after Brain #3; publish `architectureStatus` (§9 ladder) + reuse `healthV1`; **do not redesign the rubric** |
| D-4 | VERSION-basis freshness has no explicit owner statement (`freshnessBasis`) | P2 | platform lane | Sector Intelligence (consumer of a VERSION Brain) certification, or first Fish consumer going beyond UNKNOWN | map onto existing `stalenessModel` + `ageBasis`; no new vocabulary |
| D-5 | Provisional platform-authored edges for **unregistered** Brains (Depth, Vegetation, Sector Intelligence → …) | P2 | each Brain's lane | when that Brain registers (inv 17 then covers it) | at that Brain's certification |
| D-6 | **Species Registry empty**; Fish carries species identity in its bundle | P2 | platform lane + Fish lane | CERT-8 Species Registry task; Fish research must not widen identity fields meanwhile | after Fish research stabilises identity fields |
| D-7 | **Registration is a hand edit of ~8 platform files** (`registry.py`, `ownership.py`, `keys.py`, `scoring.py`, `jobs.py`, `control_manifest.json`, `ownership_map.json`, `stable_brain_ids.json`) | P2 | platform lane | Brain #5, or the first merge conflict between two parallel Brain lanes | generate from `brain.json` + per-Brain spec module |
| D-7b | **Certification suite and `describe_contract.py` copied per Brain** (Fish ≈ 44 cases; Wind ≈ 24; the two `describe_contract.py` differ only in ids/schemas) | **P1** | platform lane | right after Brain #3 (rule of three) — extract a parametrised `brain-cert-kit` driven by `brain.json`; until then copy Fish's suite | immediately after Clarity structural cert |
| D-8 | Wind has no AST-pinned write-site test (Fish does) | P2 | Wind lane | before Wind's Publisher cutover | with Wind cutover prep |
| D-9 | **No generic lifecycle drift gate** (`brain.json` vs `control_manifest.json` vs artifact lineage) | **P1** | platform lane | before the lifecycle of any registered Brain is changed; or Brain #3 registration, whichever first | extend inv 17 pattern; small, test-only |
| D-10 | Wind `authorizedConsumers` lists `biological-state` though Fish declares `consumes: []` | P3 | Wind lane | next touch of Wind `brain.json` | trivial; needs Wind-lane approval |
| D-11 | `publisher/compat.py` is a Wind-named legacy-path table inside the Publisher | P3 | platform lane | second Brain's cutover plan | move to per-Brain data |
| D-12 | Status vocabulary lacks `STRUCTURALLY_CERTIFIED_V1`; Wind/Fish describe themselves in ad-hoc words | **P1** | Michael | before Brain #3's closeout wording | amend `BRAIN_CERTIFICATION_V1.md` §4 (one table row) |
| D-13 | **Deployed Orchestrator image still carries Fish's 4 legacy edges** (and the old executor path) | P2 | platform lane + Michael | the next deliberate Orchestrator deploy | gate in report §5-G; **not** to be bundled into a Brain lane |
| D-14 | Wind/Fish `docs/` published-label strings (inv 8, 4 baselined findings) | P3 | each Brain lane | with its Publisher cutover (changes published output) | cutover |
| D-15 | Legacy direct-write doors (`run.py --write`, `wind-hourly`) | P2 (by design) | Publisher lane | Publisher production enablement + approved cutover | cutover |
| D-16 | **Exit evidence F** (rules/IAM write-denial) not achieved by either Brain | P1 (program, not factory) | Publisher/security lane + Michael | before anyone says `ARCHITECTURE_CERTIFIED_V1` | separate security phase |
| D-17 | Clarity work spread over ≈ 9 branches, **three local-only** (`feat/clarity-candidate-shadow` 51 commits, `research/clarity-candidate` 111, `campaign/clarity-readiness` 2) — no remote copy | **P1** (data-loss exposure) | Michael | before lane B starts | push to `origin` after Michael's approval (audit did not push them) |
| D-18 | Template + template checklist stale (see below) | P1 | platform lane | before Brain #4 (Brain #3 follows the factory checklist) | docs-only PR |
| D-19 | `describe_contract.py --check` is not in CI | P2 | platform lane | with D-7b | add to `registered-brains` loop |
| D-20 | Legacy research adoption (`Sector_Research_Data/biological-brain`, 13 MB) and pilot graduation (D-1/D-4 in the Fish report) | P3 | Fish lane + Michael | Fish research start | Fish decisions, not factory |

## Template (`brains/_template/`) — exact recommended changes (none applied)
- **T-1 `README.md`**: replace "Phase 1A migrates no Brain; this is the destination shape only" with: Wind and Fish are migrated; reference implementations are `brains/wind` (job) and `brains/fish` (in-process); procedure is `docs/architecture/certification/audit-1/BRAIN_FACTORY_CHECKLIST_V1.md`.
- **T-2 `README.md` table**: add `contracts/<id>-publication-v1.json` (derived; `describe_contract.py --check`), `tests/test_<dir>_certification.py`, `deploy/` only for job Brains.
- **T-3 `brain.template.json`**: `consumes` → `[]` (currently a pre-filled REQUIRED `lakes` registry edge — the shape of the fabricated dependency Fish exposed); add `score.rubricRef`; add a commented in-process/`manual` alternative to `runtime`; show a populated `publishes` example with `pathFamilies` and `schemaRef`.
- **T-4 `BRAIN_PACKAGE_CHECKLIST.md`**: add Publisher registration, deterministic fingerprint, lineage/consumption instrumentation, direct-write audit, healthV1, `stable_brain_ids.json` + `control_manifest.json` entries, score BEFORE/AFTER, SHADOW-only, certification suite (21 proofs), "no unqualified certified".
- **T-5 add** a generic `describe_contract.py` (after D-7b) and a `tests/test_certification.template.py` skeleton.
- **T-6 `research/*.template.json`**: keep (accurate).
- **T-7 `BRAIN_OPERATING_CONTRACT.template.md`**: keep; the real contracts of both Brains pass the same 19-section check (inv 4).
