"""Generate the documents of the 2026-10-14 long-run campaign from committed data (no network):
  DEPTH_RECLAMATION_DATUM_CHAIN.md   (RISE storage-consistency and allocation-diagram frame results)
  DEPTH_OFFICIAL_SCORE_DECISION.md   (score v2 proposal: dimensions, indicative values, scenarios, decisions)
  DEPTH_RECLAMATION_DATUM_REQUEST.md (the NARROWED request: only what public data could not settle)"""
import datetime as dt, json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.join(HERE, "..", ".."); sys.path.insert(0, f"{ROOT}/jobs/depth-brain"); sys.path.insert(0, f"{ROOT}/jobs/brain_platform")
from depth_brain import maturity as M, score_v2_proposal as S, score_v1_proposal as S1  # noqa: E402
D = f"{ROOT}/docs/brains/depth"
MAN = json.load(open(f"{ROOT}/jobs/depth-brain/depth_brain/data/candidates.json")); CL = json.load(open(f"{ROOT}/jobs/depth-brain/depth_brain/data/claim_levels.json"))
C = {c["lakeId"]: c for c in MAN["candidates"]}
ST = json.load(open(f"{D}/data/rise_storage_link.json"))["results"]; DG = json.load(open(f"{D}/data/rise_diagram_link.json"))["results"]; FR = json.load(open(f"{D}/data/reclamation_pool_frame.json"))["results"]
fm = M.fleet_metrics(MAN); ev = M.evaluate(MAN)
P = f"{ROOT}/jobs/depth-brain/depth_brain/data/proposals"
N_NEW = len(json.load(open(f"{P}/datum_pairings_5.json"))['lakes']) + len(json.load(open(f"{P}/datum_pairings_6.json"))['lakes'])
N_RISE_KNOWN = sum(1 for c in MAN['candidates'] if c['levelSource'].get('provider') == 'rise' and c['datum']['status'] != 'UNKNOWN')
NOW = dt.datetime(2026, 10, 14, tzinfo=dt.timezone.utc)

# ---------------------------------------------------------------- chain doc
rows_st = "".join(f"| {k.split('|')[0]} | {v.get('tableForm','-')} | {v['table'].rsplit('.',1)[0]} | {v['n']} | {v['bestOffsetFt']:+.2f} | {v['relRmsAtBest']} | {'**yes**' if v['passes'] else 'no'} | {C[k]['datum']['status'] if k in C else '-'} |\n" for k, v in ST.items() if 'error' not in v)
rows_dg = ""
for k, v in DG.items():
    use = [p for p in v['pairs'] if 'dEFt' in p]
    rows_dg += f"| {k.split('|')[0]}{' (control)' if v['control'] else ''} | {v['revised'] or '-'} | {', '.join(f'{p['printedElevFt']} ft: {p['dEFt']:+.3f}' for p in use) or 'no printed capacity inside the observed RISE range'} | {'**yes**' if v['passes'] else 'no'} | {C[k]['datum']['status'] if k in C else '-'} |\n"
doc = f"""# Reclamation datum chain: what public data settled (2026-10-14)

Research only. Scripts: `research/depth/{{tsc_tables_parse,tsc_equations_parse,rise_storage_link,resaloc_pairs,reclamation_pool_frame,rise_diagram_link,rise_link_proposals,rise_diagram_proposals}}.py`; data `docs/brains/depth/data/{{rise_storage_link,rise_diagram_link,reclamation_pool_frame}}.json`. Earlier position (`DEPTH_RISE_DATUM_RULES.md`): the datum documents exist but one link is undocumented, that the RISE daily elevation is the gage record the survey and allocation pages describe; it needed Reclamation's confirmation. **That link can be tested with Reclamation's own data**, because RISE also publishes daily storage, which Reclamation computes from the elevation through its capacity table.

## Test 1: storage consistency against the survey table
RISE daily elevation reproduces RISE daily storage through the TSC area-capacity table when both are in one frame; a frame offset d shows as `storage(E) = table(E + d)`. d is fitted on a 0.01 ft grid over -3..+3 ft over the last ~400 days. **Rule:** pass when |best d| <= 0.10 ft and the relative RMS at the best d <= 0.005 (the numeric limits were set after the first six fits were read; the cases below that fail would also fail a stricter limit except Jamestown).

| Reservoir | Table form | Table | Days | Best d (ft) | Rel. RMS | Pass | Datum status now |
|---|---|---|---|---|---|---|---|
{rows_st}
Failures are not evidence of a different datum: Flaming Gorge and Fresno (2010 table) fit a table about 1.2 / 0.27 ft away, which means RISE storage comes from a different table version; Blue Mesa's RISE storage differs by about a third (it is not total storage); Jamestown is within 0.04 ft but at 0.7% RMS. None of them is promoted.

## Test 2: allocation-diagram frame (no table needed)
Great Plains allocation diagrams print `Elev. E (C Acre-Feet)` pairs, and **the Depth reference pool is itself one of the printed elevations** (the pool source is that diagram). Where RISE's (elevation, storage) cloud passes through a printed capacity, the RISE elevation at that capacity should equal E. dE below is that difference on the most recent 60 nearby days (and only days after the diagram's revision). **Rule:** at least one printed pair inside the observed range, every such pair within 0.10 ft. Controls (Calamus, Tschida, Patterson, whose frame the survey tables already settled) reproduce to <= 0.003 ft.

| Reservoir | Diagram revised | dE at printed pairs inside the RISE range | Pass | Datum status now |
|---|---|---|---|---|
{rows_dg}
Pairs outside the observed range are not extrapolated: Box Butte, Buffalo Bill, Glendo, Horsetooth, Granby and Ruedi have not been at any printed capacity since their diagram was revised. That re-runs by itself whenever they refill (no new data source needed).

## Pool figure in the table frame
Where the diagram prints elevation/capacity pairs and the survey table is parsed, the table's capacity at those elevations equals the printed capacity exactly (Calamus 2244.0 ft = 119,469 af; Swanson 2752.0 ft = 110,175 af; Tschida 2064.5 ft = 65,091 af; Patterson 2420.0 ft = 8,479 af). So the pool figure Depth uses is on the table's frame, whatever that frame is called.

## Result and what it means
* Reclamation rows now defensible from public data: **{N_NEW} lakes** (plus Cheney via an independent USGS 62614 pairing and the same storage fit). Their datum is a Reclamation **project vertical frame**: shift only, never converted, never named NGVD29/NAVD88 (`SAME_SOURCE`, sigma 0.1 ft).
* The request to Reclamation (`DEPTH_RECLAMATION_DATUM_REQUEST.md`) is narrowed to what this could not settle.
* Method limits: it proves RISE elevation and the pool share a frame to about 0.1 ft; it does not say the frame equals NGVD29. Tier-A survey statements already say that for most of these project datums. Results are time-dependent (drought leaves some printed pairs out of range).
"""
open(f"{D}/DEPTH_RECLAMATION_DATUM_CHAIN.md", "w").write(doc)

# ---------------------------------------------------------------- request doc (narrowed)
unres = [k for k, c in C.items() if c["levelSource"].get("provider") == "rise" and c["datum"]["status"] == "UNKNOWN" and c["reference"].get("basis") == "fullPool"]
tier = lambda k: "A" if k in {"Blue Mesa Reservoir|CO", "Box Butte Reservoir|NE", "Caballo Lake|NM", "Flaming Gorge Reservoir|UT", "Flaming Gorge Reservoir|WY", "Fontenelle Reservoir|WY", "Jamestown Reservoir|ND"} else "B/C"
why = {"Blue Mesa Reservoir|CO": "RISE daily storage is not total storage (fit off by a third), the 2019 tables cannot be used for a frame check", "Box Butte Reservoir|NE": "no printed capacity reached since the diagram was revised (reservoir low)",
       "Caballo Lake|NM": "no table or diagram capacity available publicly", "Flaming Gorge Reservoir|UT": "RISE storage matches a table 1.2 ft away from the 2019 table; which table does RISE use?", "Flaming Gorge Reservoir|WY": "same series as UT",
       "Fontenelle Reservoir|WY": "no table available publicly", "Jamestown Reservoir|ND": "within 0.04 ft of the 2009 table but 0.145 ft off the 2015 diagram at 1431 ft; which is current?"}
lines = "".join(f"| {k.replace('|', ' (') + ')'} | RISE item {C[k]['levelSource']['series']} | {C[k]['reference']['poolFt']} | {why.get(k) or ('no printed capacity of its allocation diagram has been reached since the diagram was revised (re-runs when the reservoir refills)' if k in DG and not DG[k]['passes'] else 'no Reclamation allocation diagram or public capacity table for this pool figure')} |\n" for k in sorted(unres, key=lambda x: (tier(x) != 'A', x))[:24])
req = f"""# Reclamation datum confirmation request - NARROWED (Michael-ready; NOT SENT)

**Update 2026-10-14 (long-run campaign).** The original request (19 RISE rows) is superseded. Public Reclamation data settled **{N_RISE_KNOWN} RISE lakes** (16 of them from this work, Cheney through an independent USGS gauge) without waiting for Reclamation (storage consistency against the TSC survey tables, allocation-diagram frame check; `DEPTH_RECLAMATION_DATUM_CHAIN.md`). What remains is below, with the specific reason each stayed open. Sending is still Michael's call; this version is shorter and every question is specific.

## Reservoirs still open (RISE series, pool Depth uses, why open)
| Reservoir | Series | Pool (ft) | Why public data did not settle it |
|---|---|---|---|
{lines}
## Email text (placeholders [YOUR NAME] [CONTACT])

> Subject: Vertical frame of RISE daily reservoir elevation series for a short list of reservoirs
> Hello - Sector is a bowfishing conditions app. We compare each reservoir's current RISE "Lake/Reservoir Elevation" (parameter 2, daily) with its normal pool to tell anglers how far the water has moved. For most Reclamation reservoirs we could confirm from RISE storage and the Technical Service Center tables that RISE elevation and the allocation pages share one vertical frame. For the reservoirs in the attached table we could not (reasons listed). For each:
> 1. Is the RISE daily elevation the dam water-surface gage record in the reservoir's current TSC survey / area-capacity report, in the same project datum as the allocation elevations?
> 2. Which capacity table does RISE storage use today (survey year), and has the gage or datum been re-adjusted (dates, offsets)?
> 3. Where we list a mismatch (Flaming Gorge, Jamestown), which source is current?
> We will not convert between datums without an official offset, we will credit Reclamation, and we use only derived numbers. A one-line reply per reservoir is enough. Thank you - [YOUR NAME], [CONTACT]

## If confirmation arrives
Add the confirmed reservoirs as lake-scoped `operator-doc` proposals (`SAME_SOURCE`, project frame, sigma 0.1), `promote-proposals --apply`, `refresh`, `report --log`, regenerate docs, tests. Nothing is promoted before that.
"""
open(f"{D}/DEPTH_RECLAMATION_DATUM_REQUEST.md", "w").write(req)

# ---------------------------------------------------------------- score decision doc
def run(**kw):
    f = S.facts_from_manifest(MAN, CL, **kw); r = S.score_depth_proposal(f, NOW); return f, r
f0, today = run(live_states=5)
_, lake_live = run(live_states=f0["shiftPossible"], orchestration="RUNNING")
_, field = run(live_states=f0["shiftPossible"], orchestration="RUNNING", field_validation="PASSED", interpretation_claims_published=True)
# what coverage the policy needs
need = int(0.75 * f0["addressable"]) + 1
v1 = S1.score_depth_proposal(S1.facts_from_manifest(MAN, live_states=5), NOW)
dims = "".join(f"| {k} | {w} | {'yes' if k in S.CRITICAL else ''} | {today['scoreBreakdown'][k].get('value', 'UNKNOWN')} | {today['scoreBreakdown'][k]['evidence']} |\n" for k, w in S.WEIGHTS.items())
sc = lambda r: f"{r['value']} (uncapped {r['uncapped']}); critical below 7.5: {', '.join(r['criticalBelow7_5']) or 'none'}; production policy {'MET' if r['meetsProductionPolicy'] else 'not met'}"
sd = f"""# Official Depth score: one consolidated decision (proposal; NOT ratified, NOT applied)

Generated by `research/depth/campaign_docs.py` from the committed manifest and claim file. Code: `jobs/depth-brain/depth_brain/score_v2_proposal.py` (not imported by the publisher, never writes `/scores/depth`; Depth has **no official score**, `scoreStatus` stays NOT_ESTABLISHED). Tests: `tests/test_score_v2.py`. It supersedes `DEPTH_SCORE_V1_PROPOSAL.md` and answers `DEPTH_RUBRIC_MISMATCH_PROPOSAL.md`.

## What it measures
The running Brain, on the claims Depth actually makes (known depth evidence, level shift, effective shallow implications, dry/flooded bounds, confidence/provenance). It deliberately has **no** dimension for absolute depth, flats, drop-offs, channels, bathymetry or GLOBathy coverage (a test fails if one appears and extra facts about them are ignored). Same primitives as Lake/Wind/Biological: weights sum to 100, UNKNOWN contributes 0, gates cap and never add.

| Dimension | Weight | Critical (proposed) | Value today (indicative) | Evidence |
|---|---|---|---|---|
{dims}
Gates: coverage < 10% of the addressable fleet caps at 3.0; datum conflict 2.0; health FAILED/UNKNOWN 2.0; interpretation classes published without a passed field validation 5.0.

## What changed from v1 (each is a decision below)
1. **Coverage = lakes with a defensible profiled shift path**, the way Lake Brain's score counts profiled lakes rather than published states. Live states are scored under operational reliability, so a Lake Brain publication gap does not read as a Depth defect. (v1 capped everything at 3.0 until 10% of lakes had a live Depth state.)
2. **Validation is split.** `derivationValidity` (formula, inputs, provider verification, desk validation) is scorable today from the claim file. `interpretationValidity` (field/prospective) is the only dimension that needs field data and is **critical**, so the 8.0 / 7.5 production policy cannot pass before field validation, but nothing else is waiting on it.
3. **Datum correctness is quality, not coverage** (share of shift-defensible lakes whose datum is verified; inferred counts half). Coverage is its own dimension.
4. **The two out-of-mission research-rubric dimensions are replaced** by `depthShareEvidence` (shift-defensible lakes with an authoritative depth-share source: tier A/B contours or an operator elevation-area rating/survey table) and `shallowZoneActivation` (those whose effective zones are active).

## What it would say (indicative only)
| Situation | Result |
|---|---|
| Today (5 live states, no orchestration, no field validation) | **{sc(today)}** |
| Lake Brain publishes states for all {f0['shiftPossible']} defensible lakes and orchestration is registered and running | {sc(lake_live)} |
| ... and the interpretation classes are field-validated and published | {sc(field)} |
| For comparison: v1 proposal today | {v1['value']} (uncapped {v1['uncapped']}) |

The production policy (overall >= 8.0, every critical dimension >= 7.5) additionally needs **fleet coverage >= 75% of the addressable pool-basis fleet** (ladder 9): at least {need} of {f0['addressable']} lakes, against {f0['shiftPossible']} today. The {f0['addressable'] - f0['shiftPossible']} lakes still blocked are blocked by operator documents Depth cannot create, and by the absence of a level binding for lakes whose level Lake Brain owns (`DEPTH_DATUM_UNLOCK_QUEUE.md`).

## Decisions for Michael
| # | Decision | Recommendation |
|---|---|---|
| 1 | Ratify `depth-brain-score-v2` (replacing v1) and register Depth with the platform scorer in shadow | Yes. It rewards only what Depth claims; the numbers above move only with real work |
| 2 | Coverage definition: defensible profiled lakes (v2) vs published states (v1) | Profiled, to match Lake Brain's precedent |
| 3 | Is `fleetCoverage` critical? (as proposed it makes 75% coverage a production requirement) | Yes while Depth is the only source of the shift; revisit if demand-weighting is adopted |
| 4 | Inferred operator-system datum (TVA) counts 0.5 / 0.75 / 0 | 0.5 until TVA names the datum |
| 5 | Replace the research rubric's absolute-depth and relative-morphology dimensions as listed in `DEPTH_RUBRIC_MISMATCH_PROPOSAL.md` | Yes, folded into v2 (items 3-4 above) |
| 6 | Licence classification for `USACE_CWMS` and `USBR_TSC` (federal works; terms pages could not be fetched, so ASSUMED) | Confirm; rating-derived shares are customer-ineligible until then if you prefer the conservative reading |

Until a decision is made, nothing changes: research maturity stays on the old rubric ({ev['overall']}, `official:false`) and is reported separately.
"""
open(f"{D}/DEPTH_OFFICIAL_SCORE_DECISION.md", "w").write(sd)
print("ok", today["value"], lake_live["value"], field["value"], v1["value"], need)
