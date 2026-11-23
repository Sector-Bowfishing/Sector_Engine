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

> **Superseded (2026-11-23):** the rule below is the first version (commit 46af638e). The shipped behaviour is the one in §7–§10 and in `docs/brains/LAKE_BRAIN_INTEGRATION.md` §7 (rules 0, D, 1, 2; anchor; `levelUnverified`; flags without raw values; rejections as run warnings).

**Rule chosen in the first version (reversible choices, stated):** band = p01–p99 of the lake's own daily history (+ directory full pool when it agrees) ± max(that range, 50 ft); full pool ± 50 ft without history; re-centred on the series median when fewer than half of the series is inside (another datum, the `historyLiveMismatch` lakes); step > 10 ft (= `spikeToleranceFt`) + 2 ft/h × gap; absolute −300…14,505 ft backstop. The shown value falls back by the existing selection (last valid reading within the source's stale rule, else the next bound source). Flags: `implausibleReading:<src>@<t>=<raw>` (≤ 5 + count), `implausibleLatestRejected:<src>`, `allReadingsImplausible`.

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

## 7. Review fixes (PR #249 review at bfc85b78)
| Finding | Fix |
|---|---|
| MEDIUM re-centring by majority vote let n=1 and slipped-majority series through | Re-centre only when the newest reading is outside and ≥ 6 outside readings span ≥ 24 h within one band width; new rule D rejects ×10 / ÷10 decade slips against the recorded range ±15 % regardless of the band |
| MEDIUM ÷10 slip at low-elevation lakes | Rule D (Okeechobee-like 15 → 1.5 rejected; a real 2 ft drop kept) |
| MEDIUM full-pool-only band rejected a real drawdown past fp−50 | Continuity: an out-of-band reading within 1 ft + 2 ft/h of its accepted neighbour is accepted (4-day drawdown publishes 546 ft) |
| LOW baseline without full pool | `LakeBaselineBuilder.build(..., fullPoolFt:)`, passed by the runner |
| LOW rejections counted as errors | `LakeBrainLakeResult.warnings` / `LakeBrainRunResult.warnings` (job prints `~`); not in `archiveErrors`, so `errorCount`/`latestError` unchanged |
| LOW unsorted newest | `implausibleLatestRejected` uses the newest raw reading by time |
| LOW raw value in the published flag | Flag is `implausibleReading:<src>@<time>`; raw value only in the run warning. New `qualityFlags` / `activeIssues` string values extend the published state contract; schema unchanged |

Re-sweep with the revised rules (Python mirror): 288 bound lakes, 102 batch-2 checks, 47 provider fixture series: 0 real readings rejected; only the fixtures' trap rows (CDEC −9999, CO-OPS flagged 590.0, USGS −999999). No bound lake's live value is a decade of its full pool. El Vado and Navajo (> 50 ft below full pool) have 51 / 63 years of history, which sets their band.

## 8. Round-2 review fixes (PR #249 review at afbaf709)
| Finding | Fix |
|---|---|
| MEDIUM rule D ran on proxies and no-reference series (self-median fallback) and would reject real 10× river rises | D only against a real lake reference (history range or full pool); no self-median fallback; proxies get no reference |
| MEDIUM no-history lakes (21 with `historyClass` NONE in the committed binding tables read here; the reviewer counted 26) could go UNAVAILABLE up to 24 h after an outage with a real level > 50 ft from full pool | Anchor = last published OBSERVED value (≤ 7 days, passes 0 and D, inside a history band if any); out-of-band readings within the step limit of it are accepted. No in-band reading and no anchor: the internally consistent series is published with `levelUnverified:<src>` (profile issue `level-unverified`), never blanked |
| LOW datum-change window | Same: with no old-datum reading left, the new series is published flagged; rejected only when it is a decade slip |
| LOW digit transposition | Documented as a known limit (header and integration doc) |

Re-sweep (Python mirror, revised rules): 288 bound lakes, 102 batch-2 checks, 47 fixture series: 0 real readings rejected (only the trap rows). El Vado and Navajo would be `levelUnverified` only in a hypothetical run without their history and without an anchor; their 51 / 63 years of history set the band.

## 9. Round-3 review fixes (PR #249 review at 3025e68)
- The PR was dirty after #241: merged origin/main (engineering-status conflict resolved by taking main and re-running the digest sequence), commit 7f83d79c.
| Finding | Fix |
|---|---|
| HIGH an unverified value anchored the next run and was then published unflagged | `LakeBrainRunner.anchor` refuses states flagged `levelUnverified*`, `implausible*`, `allReadingsImplausible`; "unverified" therefore carries forward until the band, history or a verified anchor confirms it (test: run 1 → flagged, run 2 fed run 1's state → still flagged) |
| MEDIUM history lake, only new-datum readings (< 6 or < 24 h) with a valid in-band anchor → UNAVAILABLE | If the walk accepts nothing but ≥ 2 readings agree within the step rule, they are published `levelUnverified`; a lone reading stays rejected. Test passes the old-datum anchor and asserts published + flagged |
| LOW no history, no full pool, < 3 readings → published unflagged | `levelUnverified` |
| LOW rule D vs a full pool alone could reject a gauge ~10× off | Flag only (kept, `levelUnverified`) unless an anchor confirms the slip; history-backed D still rejects |

Sweep: the revisions add no rejection path without an anchor (the committed probe data carries none), so the round-2 result stands: 0 real readings rejected.

## 10. Round-4 review fixes (PR #249 review at 4301508)
| Finding | Fix |
|---|---|
| MEDIUM at a no-history lake a re-centred band made a consistent wrong-datum / wrong-unit feed look verified, published unflagged and anchoring | `bandDecision` reports re-centring; re-centred without a history range (full pool only) → `levelUnverified`. Test: 30 h of 26 ft and of a metres feed (~182.6) at full pool 600: both published flagged in run 1 and run 2, neither anchors |
| LOW anchor refused for an `implausibleReading` about an older slip | Refused only when the published CURRENT value was flagged: `levelUnverified`, `implausibleLatestRejected`, `allReadingsImplausible` (test) |
| LOW §3 out of date | Marked superseded, pointing here |

**Run golden (`brains/lake/tests/golden/lake_run_updates.json`) changes, deliberately:** its FakeFeeds lakes have no history and a flat 593.8 ft; three of them have a directory full pool more than 50 ft away (Pickwick 414, Wilson 507.7, Hartwell 660), so their band is re-centred on a full-pool-only reference and they are now honestly `levelUnverified:<src>` with a `level-unverified` profile issue (`issueCount` 1). No Swift toolchain here: the golden was edited surgically (flag first in `qualityFlags`, issue object in sorted-key order) and is verified by `LakePublicationFixtureTests` in CI. Python consumers of the golden: `jobs/brain_platform` 1011 passed, `brains/lake` 81 passed.
