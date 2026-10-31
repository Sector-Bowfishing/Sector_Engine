# Fish / Biological split: M04 and the M01–M03 plan: Session Record

```text
Standards: Rehtac Cortex 3.1.1 @ 3ac7e81 (clean), pack sector/engine (repository pin d5c8380, identical tree)
Repository: Sector-Bowfishing/Sector_Engine · Branch: cortex/fish-biological-m04-2026-10-31 · Start commit: ca669772 (origin/main) · Date: 2026-10-31
```

## 1. Scope
Overnight run (Sector_Ops issue 24, step 5), safe parts only: Cortex M04 (two charters; the Water Temp wording) and a step-by-step M01–M03 plan that lists exactly what D-1 and D-3 (Sector_Ops 20) must decide. No package, registry, contract or data change. Inspected: `brains/fish/` (brain.json, research charter, runtime listing, operating contract), the charters of the other Brains, `cutover_order.json`, `data_ownership.json`, Cortex `brain-architecture.json` (authorizedInputs) and the tools that read charters.

## 2. Findings
| ID | Finding | Status | Evidence |
|---|---|---|---|
| FB-1 | One combined charter for two target Brains | FAIL (M04) | `brains/fish/research/CHARTER.json` brainId `biological-state` |
| FB-2 | Water Temp charter says Fish owns fish behaviour | FAIL (M04) | `brains/water-temperature/research/CHARTER.json` mustNotPredict |
| FB-3 | M04 as written needs M02's directory (Cortex gap CG-3.1-3) | gap | see CORTEX_GAPS |
| FB-4 | Sector_Ops 20 describes D-1/D-3 as blocking "cutover step 2 (biological-state)", which predates the corrected order | stale tracker text | `cutover_order.json` deferred Fish steps |

## 3. Changes
| Correction | Class | Files |
|---|---|---|
| Target charters (partition of the combined charter, unchanged statuses) | safe docs (M04) | `docs/architecture/production/fish-biological-split/{fish-knowledge,fish-behavior}.CHARTER.json` |
| Combined charter: `targetBrain` per prediction and input; `splitInto` | safe (additive) | `brains/fish/research/CHARTER.json` |
| Water Temp wording | safe docs (M04) | `brains/water-temperature/research/CHARTER.json` |
| Partition test | safe | `brains/fish/tests/test_target_charters.py` |
| M01–M03 plan + decisions D-1, D-3, /sources, S-1 | docs | `docs/architecture/production/fish-biological-split/M01_M03_SPLIT_PLAN_V1.md` |
| Cortex gap CG-3.1-3 | record | `docs/cortex/CORTEX_GAPS.md` |

## 3a. Standing checks
- Mission (BA-07): `mission-audit --repo .`: 1 finding, `LEGACY_COMBINED` (expected until M02), no `WRONG_OWNER`. `--brain fish-knowledge|fish-behavior --text <each prediction>`: 0 findings; the control is `WRONG_OWNER`.
- Research (RS-25): `research-check --charter .`: 0 findings.
- Memory, data, security: not triggered (no runtime, data path or access change).

## 4. Verification
Fish 404 passed (400 before + 4 new); Water Temp 53 passed; Kit V1 re-collected for all Brains; engineering status regenerated; the full suite set is unchanged otherwise.

## 5–9
Decisions: D-1, D-3, /sources, S-1 (plan document, last table). Next step: owner answers on Sector_Ops 20 using that table; then M01 as its own approved PR.
