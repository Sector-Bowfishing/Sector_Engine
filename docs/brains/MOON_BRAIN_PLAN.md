# Moon and Night Light Brain — plan

**Decision.** Owner, chat 2026-11-22 19:37Z, recorded on Sector_Ops #51: build it, everything approved. This document is the plan and the record of what was built. The package is `brains/moon` (`brainId` `moon`).

**Runtime effect of merging: none.** The Brain is registered in the control manifest as `PARKED` with `executionTarget.kind: none`, it is absent from the execution control (`/control/executionControlV1`; absent means disabled), it has no live writer, and `run.py --write` refuses. Customer publication is off.

## 1. What it answers

For each of the 621 lakes in the lake registry, for tonight:

| Output | Definition |
|---|---|
| Moon phase name, phase fraction, waxing | sector-moon-v1 (`contracts/moon/moon-v1.json`), at local solar midnight |
| Illumination fraction | sector-moon-v1 (true Sun–Moon elongation), at local solar midnight |
| Moonrise, moonset | Moon's upper limb on the horizon with 34′ refraction: geocentric altitude of the centre = 0.7275 × parallax − 0°34′ (Meeus ch. 15, USNO) |
| Sunset, sunrise | Sun's centre at −0°50′ |
| Civil, nautical, astronomical dusk and dawn | Sun's centre at −6°, −12°, −18° |
| Fishing window | astronomical dusk (else sunset + 80 min) to the next sunrise — the Engine's and the app's window |
| Moonlight across the window | mean of max(0, sin(moon altitude)) every 15 min — the Engine's `moonAltitudeFraction` |
| On-water darkness class | DARKNESS_RULE_V1 (§3) |

"Tonight" for date D runs from local solar noon on D to local solar noon on D+1 (`D 12:00 UTC − lon/15 h`). Every instant is UTC. An event that does not happen in that span (polar day, polar night, a day without a moonrise) is `null` with a `sunState` reason. It is never interpolated.

## 2. What was reused, and why the event finder is new

**Reused.** The Engine already computes moon data. Step 0 of the conditions consolidation froze it as `contracts/moon/moon-v1.json` (specId `sector-moon-v1`, 52 vectors; reference `Sources/SectorEngine/Engine/Astronomy.swift`, identical to the iOS copy apart from one extension). The iOS moon tile (`specs/weather-metric-detail.md` §9) and the darkness factor (`specs/conditions-engine.md`) are the behavioural source of truth. `ephemeris.py` is a line-for-line port of that file, and `tests/test_moon_spec_vectors.py` runs all 52 vectors at the spec's tolerances. A change to the moon math goes to the spec and every copy.

**New.** The Engine's `sunEvents` and `moonRiseSet` are fine for a tile but do not meet a ±2 min USNO check:
- `sunEvents` computes the Sun once, at the request instant, and solves the hour angle from that single position.
- `moonRiseSet` puts the Moon's *centre* at 0° topocentric, with no refraction or semidiameter. That is about 0.8° from the USNO definition, which is several minutes of time.
- `moonRiseSet` scans the **UTC** day, so at US longitudes it can return the previous evening's moonrise. This explains the "9:59 PM moonrise" in the 2026-08-03 Langston measurement in `specs/conditions-engine.md`. The Brain's noon-to-noon span gives 10:22 PM CDT for that night.

`events.py` keeps the same ephemeris. It applies the USNO standard altitudes, samples every 10 min, and bisects each crossing to 1 s, recomputing positions at every trial instant. Sidereal time uses Meeus eq. 12.4, which is about 1 s from Schlyter's L+180. The Engine is not changed by this PR. Whether the Engine should adopt the same event definitions is a separate decision (§7).

## 3. DARKNESS_RULE_V1, stated before scoring

This is the machine-readable rule in `contracts/moon-night-light-v1.json` → `darknessRule`. The constants are the Engine's `DarknessFactor` and `ConditionsConfig.Darkness`, so the Brain and the app classify a night the same way.

```
I = illumination at local solar midnight              P = moon presence across the fishing window
C = clamp((cloudPct − 50) / 50, 0, 1) × (1 − 0.8 × 0.3)      (0.3 = Engine default city glow; no per-lake skyglow input)
A = I × P × (1 − C)
DARK  A < 0.15   |   MOSTLY_DARK  < 0.35   |   SOME_MOONLIGHT  < 0.60   |   BRIGHT_MOON  ≥ 0.60   |   NO_NIGHT  Sun never sets
```

- **Cloud missing, partial or invalid → MOON_ONLY.** The class uses A = I × P (the clear-sky upper bound). The state says so in `statement` and names the reason. No cloud value is assumed: the Engine's `cloud ?? 0` default is not copied.
- `moonOnly` is reported on every night, so a consumer can always see the cloud's effect.
- The labels are the Engine's ("97% moon · bright — moon up"). The copy makes no fish-behaviour claim, per the iOS "Copy accuracy (moon)" rules. A test enforces this.
- Cloud use: the mean of the hourly values within ±30 min of the window. At least 75 % of the window's hours must have a value.

## 4. Weather Brain input

The Weather Brain is being built in parallel on `feat/weather-brain-2026-11-22`. That branch did not exist on origin when this PR was built (checked at the start and again before the final commit), so the Brain defines what it needs as an **optional, provisional** input: `moon-weather-cloud-input-v0`, an hourly list of `{at, cloudCoverPct}` per lake. It is not declared in `brain.json` `consumes`, because a `kind: brain` entry needs a registered brainId. Gap MOON-INP-001 tracks it. When the Weather Brain contract exists: map it to this input, add the `consumes` entry, and add a mapping test.

## 5. Package and registrations

| Where | What |
|---|---|
| `brains/moon/` | `brain.json` (CALIBRATION, customerPublication NOT_ELIGIBLE, INTERNAL only), operating contract, README, `contracts/` (state contract + Publisher declaration), `runtime/`, `tests/`, `research/` (CHARTER, GAPS) |
| `runtime/knowledge/` | Packaged knowledge release: a projection of the Engine lake directory (lakeId, name, state, lat, lon), approval NOT_RECORDED. A test fails if it drifts from `LakeDirectory.swift`. A tampered or missing release refuses the run |
| `control_manifest.json` | `moon`: PARKED, executionTarget none, schedule MANUAL, triggers MANUAL/ADMIN, costClass NONE, customerPublication false |
| Execution control | Not added. A Brain absent from `brains` is disabled (fail closed). Only the owner CLI writes it |
| `control.py` | `moon` in SHADOW_BRAINS/SHADOW_SLOTS: visible, never in a roll-up or the Engine score |
| `keys.py`, `BrainPlatform.swift`, `stable_brain_ids.json` | slot `moon`, snapshot field `moonNightLight` |
| `publisher/registry.py` | `moon-lake-state-v1`, `moon-registry-v1`, bundle `moon-publication-v1` (describes the dry-run write set so the Brain can be certified; authorizes no writer) |
| `cutover_order.json` | `moon` blocked (no cutover plan) |
| `platform/security/*` | Plan documents only: `moon` current identity NONE, target `brain-job` (like Depth and Vegetation). The publisher plan is regenerated from the model. No IAM is changed |
| Engineering status | Memory-standing row and status layers for `moon`; certification re-collected |

## 6. Verification

- `cd brains/moon && python -m pytest -q`: 262 tests. That covers the moon-spec vectors; the USNO cross-check (10 place-days of rise/set and civil twilight, 12 nautical/astronomical table rows including one "Sun never below −12°" case, 20 principal phases); the night window (including the 2026-08-03 "window ends before it starts" regression and polar day/night); DARKNESS_RULE_V1; the lake directory; run entry; the dry-run write set against the contract schema; and Brain Cert Kit V1 (all proofs and mutations).
- USNO tolerances: rise/set and twilight ±2 min (observed worst case 40 s against the minute-rounded USNO values), principal phases ±20 min (observed worst case 17 min, from the Schlyter ephemeris), illumination at a principal phase within 0.003.
- The full 621-lake directory computes in about 4 s on one CPU. On 2026-11-22 (a 97 % waxing moon, no cloud input), every lake is MOON_ONLY: 470 SOME_MOONLIGHT, 150 BRIGHT_MOON, 1 MOSTLY_DARK (Teshekpuk, AK, polar night).

## 7. Not done here (owner decisions or later work)

1. **Enable execution**: add `moon` to the execution control, give it an executor and a writer, and make it ACTIVE. These are gated owner decisions.
2. **Weather Brain mapping** (MOON-INP-001), once that Brain's contract exists.
3. **Validate DARKNESS_RULE_V1** against measured on-water illuminance (MOON-VAL-001).
4. **Per-lake skyglow** (MOON-INP-002).
5. **Engine event definitions**: whether the Engine and the apps should adopt the USNO altitudes and the noon-to-noon span for the moonrise/sunset they display. That would be a `moon-v2` spec change across iOS, Android and Web.
6. **Cortex**: Moon is not one of the Cortex target Brains, and its families are not in the Cortex data registry (CG-3.1-19). Cortex is read-only here.
