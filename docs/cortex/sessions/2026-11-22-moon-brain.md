# Session record: Moon and Night Light Brain (registered disabled)

Standards: Rehtac Cortex 3.1.2 @ ecaef70 (clean), pack sector/engine. The briefing was run by hand from the local Cortex checkout because `CORTEX_HOME` is unset. The repository pin a785035 is not in that checkout. Date: 2026-11-22. Branch: `feat/moon-night-light-brain-2026-11-22` off main 0fc0682a. Owner decision: chat 2026-11-22 19:37Z, recorded on Sector_Ops #51 ("build it, everything approved"). Work stayed within the standing approvals: branch, commit, push, PR.

## Scope
A new Brain, `brains/moon` (`brainId` `moon`). For all 621 directory lakes it computes moon phase, illumination, moonrise/moonset, sunset and civil/nautical/astronomical twilight, plus an on-water darkness class (DARKNESS_RULE_V1). It is registered **disabled**: control manifest PARKED, executionTarget none, absent from the execution control, no live writer, customer publication off. Plan: `docs/brains/MOON_BRAIN_PLAN.md`.

Not done, and needing the owner: enabling execution, a live writer, any customer surface, IAM, and rules.

## Done
- Package: brain.json (CALIBRATION), operating contract, `contracts/moon-night-light-v1.json` (state schema, weather input, darkness rule), `contracts/moon-publication-v1.json` (derived from the Publisher registry), runtime (stdlib only), research CHARTER/GAPS, and 262 tests including Brain Cert Kit V1.
- Reuse: the ephemeris is a port of `Astronomy.swift` (sector-moon-v1) and passes all 52 spec vectors. Event times use the USNO / Meeus standard altitudes. They are cross-checked against USNO values retrieved 2026-11-22 (worst case 40 s; tolerance ±2 min).
- Registrations: control manifest, `keys.py`, `BrainPlatform.swift`, `stable_brain_ids.json`, Publisher registry (moon specs and bundle), `control.py` SHADOW_BRAINS, `cutover_order.json` (blocked), and the identity-split and publisher-security plan documents (plans only; no IAM change). Engineering-status inputs and the certification were regenerated.
- Hand-kept Brain lists in the tests were extended by `moon`, each with its reason.

## Findings
- The Engine's `moonRiseSet` scans the UTC day, so at US longitudes it can report the previous evening's moonrise. The 2026-08-03 Langston "9:59 PM" value in iOS `specs/conditions-engine.md` is that case. The Brain uses a local-solar-noon span. The Engine was not changed (MOON_BRAIN_PLAN §7.5).
- The Weather Brain branch `feat/weather-brain-2026-11-22` did not exist on origin. The cloud input is defined provisionally (`moon-weather-cloud-input-v0`, OPTIONAL).
- `data-check`: the Moon families are UNMAPPED_FILE (Moon is not a Cortex component). There are 2 UNREGISTERED_PATH hits on docstring text in `publish.py`, the same wording Vegetation carries. Recorded as CG-3.1-19.
- `tools/research` has 2 failures that predate this branch (read-only folder tests: `test_cleanup_removes_read_only_campaign_files_but_nothing_else`, `test_read_only_sources_folder_is_never_modified`). They fail identically on main in this container (root user). Not touched.

## Cortex gaps
CG-3.1-19 (`docs/cortex/CORTEX_GAPS.md`): add Moon as a target Brain and register its families.
