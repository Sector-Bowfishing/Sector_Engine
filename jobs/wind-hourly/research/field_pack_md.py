"""Render docs/brains/wind/WIND_BANK_PAIR_FIELD_PACK.md from data/field_pairs_candidates.json (deterministic).
  python research/field_pack_md.py CANDIDATES.json OUT.md"""
import json, sys
R = json.load(open(sys.argv[1]))
CARD = {0: 'N', 45: 'NE', 90: 'E', 135: 'SE', 180: 'S', 225: 'SW', 270: 'W', 315: 'NW'}
def bk(b): return f"{b['bankId']} ({b['anchor'][0]:.4f}, {b['anchor'][1]:.4f})"
def row(p, n):
    A, B = p['A'], p['B']; a, b = A['at12'], B['at12']; th = p['windFromDeg_forAasExposed']; rev = ''
    if 'reverse12' in A:
        rev = f"; reversed ({CARD.get(p['windFromDeg_reversed'])}) A {A['reverse12']['label']}, B {B['reverse12']['label']} ({B['reverse12']['effectiveFetchM']/1000:.1f} km)"
    ratio = a['predictedHm0In'] / max(b['predictedHm0In'], 0.1)
    return (f"| {n} | {p['type'].replace('_', ' ').title()} | **A** {bk(a)} · **B** {bk(b)} | from **{CARD.get(th, th)}** ({th}°) | A {a['label']}{' + HIGH FETCH' if a['highFetch'] else ''}, {a['effectiveFetchM']/1000:.1f} km, ~{a['predictedHm0In']} in · "
            f"B {b['label']}, {b['effectiveFetchM']} m, ~{b['predictedHm0In']} in{rev} | {a['effectiveFetchM']/max(b['effectiveFetchM'], 1):.0f}× fetch, {ratio:.1f}× wave | {p['distanceM']/1000:.1f} km |")
out = '''# Bank-pair field pack (candidate pairs from the pilot and contrast lakes)

Purpose: obtain the **physical truth** Wind lacks (BWIS B3 + D2; certification dims 6/7) with observations a tester can do in about a minute per bank (`WIND_FIELD_OBSERVATION_PROTOCOL.md`; programme `WIND_FIELD_PROGRAM_PLAN.md`). Pairs were selected by geometry alone (`jobs/wind-hourly/research/field_pairs.py`; no forecasts, no H2): all 99 candidates are in `data/field_pairs_candidates.json` (sha256 pinned by the v2 pre-registration). **ESTIMATED lakes (Hartwell, Toledo Bend) use the published Lake Registry v1 polygons** (an earlier draft built from older engine polygons placed most banks > 300 m from the registry shoreline and was discarded before any session). **Access and safety are not verified** — check public ramps, hazards and permission before any visit; coordinates are shoreline anchors, not launch points.

## Independence warning
Guntersville, Wheeler, Wilson and Pickwick are four reaches of the Tennessee River system with similar wind climate and fetch geometry; **they count as one environment** for generalisation (and the same 8 METAR stations back all four). Lake Hartwell (SC/GA, ESTIMATED geometry), Mille Lacs (open natural lake), Lake McConaughy (plains reservoir), Toledo Bend (large southern reservoir, ESTIMATED) and Lake Maurepas (shallow coastal) are added for independence and to test the ESTIMATED tier. Smith Mountain Lake VA (dendritic, max p90 fetch 0.75 km) is a useful *negative control* (everything should read protected/low) but has no strong pairs.

## Pair types
- **Mirror pair:** opposite shores of one open-water run. Wind from θ → A (downwind shore) DIRECT/HIGH FETCH, B (upwind shore) PROTECTED. **Reverse the wind and the roles swap**, so the same two banks test the model in both directions.
- **Cove vs point:** ≤ 1.5 km apart, one exposed point, one true cove (the "is this cove sheltered?" question).
- **Subtle ordering:** two exposed banks ≤ 3 km apart, predicted waves 1.25–2.5× different (tests fetch *ordering*, not just land vs water).
ESTIMATED lakes publish only EXPOSED / PROTECTED; the DIRECT/CROSS words below are internal for those two lakes.

## Conditions that make a session count (all pairs)
- Wind from the stated direction ±25°, **8–15 mph sustained** (a forecast ≥ 5 mph with the NBM breezy-risk flag is ideal), steady ≥ 3 h; evening or night (7 pm–1 am local) preferred, **afternoons are the practical volume** (`WIND_FIELD_PROGRAM_PLAN.md`).
- Visit both banks within **60 minutes** (same device, same height, 60-s average).
- Skip: < 5 mph (direction unreliable), thunderstorms, wind shifting > 45° during the session.

## What to record (per bank)
Water: calm / light / choppy / rough · bank: EXPOSED / PROTECTED / UNSURE (optional DIRECT/CROSS on audited lakes) · boat control: easy / noticeable / difficult · wind direction and speed (handheld if available) · confidence 1–3 · one photo looking upwind. **The observer does not see the model's prediction** until after submitting.

## What would falsify the model (proposed; the canonical scorer owns real thresholds; see `WIND_BANK_VALIDATION_V2_PREREG.md`)
- Predicted-rougher bank observed **rougher by at least one step** = concordant; equal = half; calmer = discordant. After **≥ 20 qualifying sessions on ≥ 2 independent lakes** concordance < 0.70 ⇒ not supported as a bank ranking.
- **False-PROTECTED:** a PROTECTED call recorded choppy/rough (or boat control difficult) with wind ≥ 8 mph from the stated direction in more than **1 in 10** such calls (≥ 15 calls) ⇒ ESTIMATED labels stay withheld.
- ESTIMATED and AUDITED lakes are scored separately. Evidence Addendum v1 volumes for certification credit: ≥ 40 holdout pairs, ≥ 2 lakes, ≥ 3 quadrants; concordance ≥ 80% earns full credit.
'''
for L in R:
    out += f"\n## {L['lake']} — {L['kind']} · geometry {L['tier']} ({L['geometryConfidence']})\n\n| # | Type | Banks (shoreline anchor lat, lon) | Best separating wind | Predicted at 12 mph | Contrast | Distance |\n|---|---|---|---|---|---|---|\n"
    pairs = L['pairs']; pick = []; seen = set()
    for p in [p for p in pairs if p['type'] == 'MIRROR']:
        if p['axis'] not in seen and len(seen) < 2:
            seen.add(p['axis']); pick.append(p)
    pick += [p for p in pairs if p['type'] == 'COVE_vs_POINT'][:1] + [p for p in pairs if p['type'] == 'SUBTLE_ORDERING'][:1]
    for i, p in enumerate(pick, 1): out += row(p, i) + "\n"
    out += f"\n{L['banksUsable']} usable banks; strong-fetch threshold {L['hiFetchThresholdM']:.0f} m. " + ("**Validates the ESTIMATED tier** — priority for field time.\n" if L['tier'] == 'ESTIMATED' else "Audited geometry (modeled exposure, no field truth).\n")
out += '''
## Suggested first programme
Guntersville (home water, 20 pairs) + Lake Hartwell (ESTIMATED, 16–20 pairs, ≥ 8 mandatory) satisfy ≥ 40 pairs / ≥ 2 independent lakes; add a third system (Mille Lacs, McConaughy, Toledo Bend) via a local tester when available. Single-bank tester records feed the agreement matrix but only paired sessions count toward concordance.
'''
open(sys.argv[2], 'w').write(out); print(len(out) // 1000, 'KB')
