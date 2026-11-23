# Session record: Weather Brain retrospective validation, pre-registration and runner (2026-11-23)

Standards: Rehtac Cortex 3.1.6 @ a785035 (extracted read-only with `git archive`; the loader reports "uncommitted (no-git)" for an extracted tree), pack sector/engine

## Request
Research task (caller request in this session, under the owner's direction to strengthen Brains, Sector_Ops #51 comment 7093610553): let the disabled Weather Brain earn validation now instead of waiting 30–60 prospective days. Pre-register, before fetching any data, a retrospective version of `WEATHER_BRAIN_PLAN.md` §5 (5.1 fidelity, 5.2 representativeness WX-001, 5.3 change signal WX-002) mapped to the draft rubric's validation states (PR #241, `weather-score-v1.json`, DRAFT); hash and commit it first; build a read-only runner with fixture tests; draft (not post) a Mac mini request. Publish nothing, write nothing live.

Branch `research/weather-retro-validation-2026-11-23` from `origin/main` `5db0679`, worktree `/home/claude/sector_engine_wxretro` (cloud container).

## What was read (observed)
| Item | Evidence |
|---|---|
| §5 criteria, marks, windows, minimum samples | `docs/brains/WEATHER_BRAIN_PLAN.md` §5.1–§5.3 |
| Rubric validation states (VALIDATED / PARTIAL / NOT_VALIDATED; INSUFFICIENT is never PASS) | PR #241 `docs/brains/scoring/drafts/weather-score-v1.json` `validationStatusMeaning` (open, not adopted) |
| Station selection: NWS list order, first 3 | `brains/weather/runtime/sector_weather/publish.py` `resolve_point` |
| Per-instant value pick, offset, trend | `reading.py` `assemble`, `tendency` |
| Change rules and thresholds v1 | `signal.py` `evaluate`; `runtime/knowledge/weather-change-thresholds-v1.json` |
| Observation request window (13 h) | `client.py` `LiveSource.observations`, `contract.py` `OBS_LOOKBACK_HOURS` |

## Changes
| Commit | What |
|---|---|
| `c8d2e526` | Protocol `WX-RETRO-2026-11-23` and its sha256 sidecar, committed **before** the runner and before any data was fetched (`6e08d42ed7e808a7a9775e885f865233e7ba2bb2279e4fbb8e0171634ed37ab8`) |
| next | Runner `tools/research/weather_retro_validation.py` (imports the Brain's own `assemble`, `evaluate`, `tendency`, `decode_*`; no second copy of the logic), 17 offline tests, plan amendment §5.4, Weather research README and GAPS evidence lines, draft Mini request, this record, closeout, Cortex gap CG-3.1-26 |

Choices made (reversible, standing approval 6), all fixed in the protocol before data:
- Past window ending 2026-11-19 (4 days before registration, archives settled): 5.1 14 days, 5.2 30 days, 5.3 60 days, evaluation every hour at HH:10Z.
- Archive: IEM ASOS routine + special METARs (the NWS API's feed), mapped to the Brain's `Obs`; wxcodes mapped to NWS text wording so the Brain's own `weather_code` decides "precipitation present".
- Substitution check R-SUB added: the archive must reproduce the NWS API's last 7 days (coverage ≥ 0.95, temperature/pressure/precip agreement ≥ 0.99 at one quantum); otherwise no criterion may be reported PASS.
- Grid not replayed (no archive): RAIN_EXPECTED and WATCH shares are not graded; CHANGE (observed events only) is.
- Fronts: WPC CODSUS, 0.1° bulletins only, COLD/WARM/OCFNT within 50 mi; no substitute source if unavailable (NOT_GRADED).
- 5.3 minimum sample added (30 truth and 30 Brain events per kind, 10 lakes); POD primary population = truth events when the Brain's rule was evaluable (strict POD reported too).
- Rubric mapping proposed only: retrospective PASS is evidence; it never writes `/validation/weather`. Owner decides whether it stands in for prospective 5.2/5.3.

## Verification
- `python3 -I tools/research/weather_retro_validation.py verify`: OK, sha256 as registered.
- `python3 -m pytest -q tools/research`: 109 passed, 2 failed. The 2 failures (`test_cleanup_removes_read_only_campaign_files_but_nothing_else`, `test_read_only_sources_folder_is_never_modified`) are **pre-existing** (recorded in `2026-11-23-water-temp-protected-truth.md`: this container runs as root, so read-only permission checks do not hold). The 17 new tests pass.
- `brains/weather` pytest: 116 passed (unchanged; no runtime file touched). `jobs/brain-scores`: 37 passed.
- Timing: one lake, 60 days of synthetic hourly reports, all criteria: 0.17 s, so the full directory grades in minutes.
- `research-check --repo .`: 85 findings on the branch and on `origin/main` (unchanged); none in the new files. `research-check --gaps brains/weather/research/GAPS.json`: 0. `research-check --closeout`: 0.
- `data-check --repo .`: unchanged output size (548 lines); the runner reads no Firebase path.
- `mission-audit --brain weather`: 5 findings, all pre-existing (`UNREGISTERED_BRAIN` weather/moon/generation, CG-W-1; legacy fish layout) plus `UNKNOWN_BRAIN` for the proposed work, which is the same unregistered-Brain gap.
- Security: no secrets, no machine paths; fixtures are the Brain's recorded NWS files or labelled SYNTHETIC (SEC-02); the runner refuses any host outside the protocol's three and non-https URLs (test), and writes only under `--out`.

## Data fetched
None, by design: the protocol was hashed first and the run belongs to the Mac mini.

## Decisions for Michael (batched)
1. Post the draft Mini request on Sector_Ops #51: `docs/brains/weather-retro-validation/MINI_REQUEST_DRAFT.md`.
2. After results: may retrospective R-5.2 / R-5.3 PASS (with R-SUB PASS) stand in for the prospective 5.2 / 5.3 windows (protocol `resultStates.rubricMapping`)? Recommendation: yes for 5.3 and 5.2 as PARTIAL evidence, keep prospective 5.1 (published values) and a prospective WX-001 window as the confirmation before VALIDATED.
3. Research folder for Weather: Cortex has none (CG-3.1-26); the draft uses `weather-brain` (the name the Weather research README already gives).
4. (Resolved) Worktrees `se_wt_validation` and `sector_engine_wt_wtpt` (REMOVABLE_MERGED, other sessions) were removed by the coordinator: merged and clean.

## Not done (gated or out of scope)
No data fetched, no Firebase read or write, no Brain runtime, knowledge release, manifest, execution-control, rubric or score change, nothing published, no merge.

## Closeout
[`2026-11-23-weather-retro-validation.closeout.md`](2026-11-23-weather-retro-validation.closeout.md) (stored here because the cloud container has no research home; CG-3.1-22).

## Operating contract
Gaps WX-001, WX-002; bowfisher decision: whether the Pressure and Air Temperature tiles describe the lake and whether Lake/Water Temp refresh when the weather turns; score before/after UNSCORED / UNSCORED (draft rubric, Brain never published); field validation needed: none; not changed: live systems, schedulers, customer `/conditions`, Brain logic, thresholds.

## Review round 1 (coordinator)
- Cortex gap id renumbered CG-3.1-24 → CG-3.1-26 (PR #244 holds CG-3.1-24, PR #245 CG-3.1-25); every citation updated. Protocol bytes and sha256 unchanged. Engineering-status digest regenerated.

## Review round 2 (independent review of 93f7aeb0: NOT CLEAN), re-registered as v2 before any data
Merged `origin/main` (no force-push). Still nothing fetched, so the protocol was re-registered rather than amended after data:
**`WX-RETRO-2026-11-23.2`**, sha256 `01eac7bc56033154dcf64ee365826a0da1c4d33cd921cec7ec76e79df48eb58c`, committed alone in `b8e284f3`. v1 (`6e08d42e…`) is kept byte-for-byte, marked SUPERSEDED in `docs/brains/weather-retro-validation/README.md`, and the runner no longer loads it.

| Finding | Fix (protocol v2 + runner + test) |
|---|---|
| HIGH CODSUS: a `000` separator after a front block made the previous bulletin ineligible | Separators (`000`, WMO heading, PIL, title, SOH/ETX) end the bulletin in progress; per VALID time the latest WMO issuance wins whatever the order (IEM also asked `order=asc`). Two-product test |
| HIGH R-SUB too narrow | Every 5.3 input: temperature, dew point, pressure, wind speed, wind direction (both ≥ 5 mph), precipitation, present-weather presence (code agreement reported only); null-versus-value agreement per field; ≥ 1000 pairs per metric; per-station coverage floor (≥ 20 reports and < 0.90 matched → FLAGGED, lake excluded as SUBSTITUTION_STATION); truth (candidate) stations included; per-criterion gates (`gates()`): any gating metric not PASS → no PASS for that criterion |
| HIGH POD population | Graded POD = all truth events (misses with no Brain data count); evaluable-only POD is a labelled secondary. Truth-onset definition and 2 h merge labelled `amendmentAdditions` |
| MEDIUM fixtures inside windows | Disclosed in `dataExaminedBeforeRegistration`; `excludedSpans` drops Guntersville and Champlain 2026-11-06 07:00Z→11-07 00:00Z (instants, values, pairs, events); counts reported |
| MEDIUM 5.1 label | Now R-5.1R "replay self-consistency check", not the plan's 5.1, never a stand-in |
| MEDIUM wx mapping | Earliest row across all tokens wins (`BR -RA` → Light Rain); VCTS, VCSH, VCFG rows |
| MEDIUM unjudgeable fronts | Brain fronts with no eligible analysis within ±3 h left out of FAR and counted |
| LOW separation | Independent station ≥ 3 mi from every Brain station; distance to lake and to nearest Brain station recorded |
| LOW UA / redirects / bytecode | One User-Agent (`SECTOR_WEATHER_USER_AGENT` or `Sector-WeatherRetroValidation/0.2 …`) for all hosts, stated in the protocol; redirects refused; Mini runs with `PYTHONDONTWRITEBYTECODE=1`, `python3 -I` |

Gap renumbered CG-3.1-24 → CG-3.1-26 (collision with #244 / #245). Verification: 26 runner tests pass; `tools/research` 118 passed, 2 pre-existing failures (root permission); `verify` OK for v2 and v1; engineering-status digest regenerated and `--check` OK; Mini draft updated to v2.
