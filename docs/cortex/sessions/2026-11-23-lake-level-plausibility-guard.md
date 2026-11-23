# Lake Brain level plausibility guard (Lake Tahoe decimal slip) — Session Record

```text
Standards: Rehtac Cortex 3.1.6 @ a785035 (extracted read-only with git archive; the loader reports "uncommitted" because the extract has no .git), pack sector/engine
Repository: Sector-Bowfishing/sector_engine · Branch: fix/lake-level-plausibility-guard-2026-11-23 (new worktree off origin/main) · Start commit: f5460aac · Date: 2026-11-23
```

## 1. Scope
- **Request and mode:** guided implementation (urgent fix). Sector_Ops #51 comment 7091893754: Lake Tahoe's newest USACE manual reading, 6,226,054 ft (true ~6,226.05 ft), was published as the current level; the archived history holds ~12 older slips (e.g. 622.83 ft, 62,223.31 ft, 2014–2016). Add a per-lake plausibility guard for live readings and history baselines, tests, a fixture sweep; no binding or knowledge-release change.
- **Inspected:** `LakeLevelClassifier.swift`, `LakeLevelBaseline.swift` (`spikeDays`, #218), `LakeLevelValidity.swift`, `LakeBrainRunner.swift` (`evaluateLake`, `historyLiveMismatch`), `LakeBrainProfiles.swift` (issues), `LakeLevelFeeds.swift` types, Tahoe's binding (`bindings.proposed.v1.json`: CWMS SPK daily MANUAL primary, NWPS THLC1 hourly fallback), the Lake Swift tests that build series, the run golden, `docs/brains/LAKE_BRAIN_INTEGRATION.md` §6–7.
- **Not accessible:** the CWMS API (egress proxy refused `cwms-data.usace.army.mil`), so Tahoe's real history was not re-read; the slip values come from the Mac mini report. No Swift toolchain in this container: Swift suites run in CI only.

## 2. Findings
| ID | Status | Finding | Evidence |
|---|---|---|---|
| P1 | FAIL → fixed | Live readings were accepted with no plausibility check; `select` took the newest reading of the first fresh source | `LakeLevelClassifier.select` / `evaluate` at f5460aac |
| P2 | FAIL → fixed | The #218 neighbour filter cannot judge the newest history day (no later neighbours) or a run/gap of slips (needs ≥ 4 neighbours), so slips reach the baseline | `LakeBaselineBuilder.spikeDays` (`spikeMinNeighbours`) |
| P3 | PASS | The fixture sweep finds no bound lake whose committed current reading the guard would reject (§4) | sweep output in the PR |

## 3. Changes
| Correction | Class | Files | Commit |
|---|---|---|---|
| `LakeLevelPlausibility` (rules 0–2), classifier filtering + flags, runner reference + warnings, profile issue, baseline exclusion into `excludedSpikeDays`, docs | Safe (requested) | `brains/lake/runtime/LakeBrain/{LakeLevelPlausibility,LakeLevelClassifier,LakeLevelBaseline,LakeBrainRunner,LakeBrainProfiles}.swift`, `LAKE_BRAIN_INTEGRATION.md`, `rules_v2.py` docstring | 46af638e |
| Tests | Safe | `brains/lake/tests/swift/LakeLevelPlausibilityTests.swift` | 46af638e |
| Certification + engineering-status digests | Record | `docs/cortex/engineering-status/**` | this branch |

**Rule chosen (reversible choices, stated):** band = p01–p99 of the lake's own daily history (+ directory full pool when it agrees) ± max(that range, 50 ft); full pool ± 50 ft without history; re-centred on the series median when fewer than half of the series is inside (another datum, the `historyLiveMismatch` lakes); step > 10 ft (= `spikeToleranceFt`) + 2 ft/h × gap; absolute −300…14,505 ft backstop. The shown value falls back by the existing selection (last valid reading within the source's stale rule, else the next bound source). Flags: `implausibleReading:<src>@<t>=<raw>` (≤ 5 + count), `implausibleLatestRejected:<src>`, `allReadingsImplausible`.

**Known limits:** a ÷10 slip of a lake below ~60 ft elevation can sit inside the 50 ft band (the step rule still catches it on hourly series); a series whose readings are all wrong but plausible-looking reads as another datum; a real record-low excursion shorter than 1 % of the record and more than (range + 50 ft) beyond p01 would be left out of the baseline (never out of the live value, which is judged by the series).

## 4. Verification
| Command | Result |
|---|---|
| `python3 -m pytest -q` in `brains/lake` | 81 passed, 2 skipped |
| `python3 -m pytest -q` in `tools/architecture` (after the digest sequence) | 196 passed |
| `python3 tools/architecture/report.py --legacy --baseline` | NEW findings 0 (the new file does not import SectorEngine) |
| `collect_certification.py` → `build_engineering_status.py --write` → `--check` | failing: none; OK |
| Fixture sweep (Python mirror of the rules, scratch only): 287 bound lakes' committed probe values (`bindings.*.json` last/min/max/median), 102 batch-2 live checks (value vs 30-day median), every provider fixture series, the run golden | 0 rejections of real readings. Rejected only the fixtures' deliberate trap rows the parsers already drop (CDEC −9999, CO-OPS flagged 590.0). 2 lakes (El Vado, Navajo) are > 50 ft from full pool: re-centred, not rejected. Max 30-day span 27.3 ft; max fixture rate 1.0 ft/h |
| Swift Lake suites | CI (`swift-tests.yml`), see the PR |

## 5. Standing checks
- `data-check`: unchanged findings (no RTDB path added). `lake-audit`: LB-04…LB-07 statuses unchanged (PARTIAL / STRUCTURAL_MET). `worktree-check`: one merged worktree (`se_wt_wind`) removable; not removed (owner batch). Security: no secrets, IAM or rules touched.

## 6. Decisions / approvals
- None required for this change. Merge is not done in this session (instruction). Whether Tahoe should be held until this ships is the owner's question on #51.
