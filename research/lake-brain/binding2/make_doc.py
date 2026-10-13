"""Generate docs/research/lake-brain/LAKE_BRAIN_BINDING_GAPS_RESEARCH.md from the computed JSON/CSV (numbers come from files, prose is here)."""
import csv, collections, glob, json, os
from common2 import *

S = json.load(open(f"{DOCS}/data/binding2_summary.json"))
out = json.load(open(f"{B2}/assembled_v2.json"))
prof = {p["lakeId"]: p for p in json.load(open(f"{B2}/unbound_profile.json"))}
rem = json.load(open(f"{B2}/remaining_unbound.json"))
abl = json.load(open(f"{B2}/ablation.json")) if os.path.exists(f"{B2}/ablation.json") else {}
ctrl = json.load(open(f"{B2}/r7h_control.json"))
cal = json.load(open(f"{B2}/usgs_stage_calibration.json"))
sc = json.load(open(f"{B2}/state_cov.json"))
hp = json.load(open(f"{B2}/hads_probe.json"))
C = collections.Counter
CORE = ("VERIFIED", "VERIFIED_CORROBORATED", "VERIFIED_ENVELOPE")
BOUND = CORE + ("VERIFIED_FLAG",)
N = S["lakes"]
L1, L2, L3 = S["layers"]["L1_v1_rules"], S["layers"]["L2_v1.1_rules"], S["layers"]["L3_v1.1_plus_R7h"]
W1 = S["wave1"]
new = [r for r in out if r["w1Status"] in ("NONE", "STAGE_ONLY") and r["bindingStatus"] in BOUND]
newcore = [r for r in new if r["bindingStatus"] in CORE]
flag_w1 = [r for r in out if r["w1Status"] == "VERIFIED_FLAG"]
fate = C()
for r in flag_w1:
    fate["history envelope (R7h)" if r["bindingStatus"] == "VERIFIED_ENVELOPE" else "promoted by a second independent origin / strong series" if r["bindingStatus"] in ("VERIFIED", "VERIFIED_CORROBORATED") else "still flagged"] += 1
v1only = [r for r in out if r["bindingStatus"] in BOUND and r["wave"] in ("w1", "w2-v1")]


def dn(lid):
    n, st = lid.rsplit('|', 1)
    return f'{n} ({st})'


def pct(x):
    return f"{100 * x / N:.1f}%"


def md(rows, head):
    s = "| " + " | ".join(head) + " |\n|" + "|".join("---" for _ in head) + "|\n"
    for r in rows:
        s += "| " + " | ".join(str(x) for x in r) + " |\n"
    return s


doc = []
A = doc.append
A(f"""# Lake Brain: filling the level-source gaps (wave 2 of binding)

Thread `gaps`, Lake Brain deep-research campaign, 2026-10-13. Research only: GET-only against public endpoints, no deploy, no write to any RTDB or bucket, no rubric edit, no push.
Method and code: `research/lake-brain/binding2/` (wave-1 machinery in `research/lake-brain/binding/` is imported, not copied). Bulk data (candidate series, daily history, raw captures) lives outside Git in `Sector_Research_Data/lake-brain/binding2/`.
Committed results: `data/verified_bindings_v2.csv` (cumulative table with a `wave` column), `data/binding2_summary.json`, `ledger/gaps.jsonl`.

## 1. Result in one table

Wave 1 machine-verified {W1['core']} core + {W1['flagged']} flagged of {N} directory lakes ({pct(W1['core'])} / {pct(W1['core'] + W1['flagged'])}). Wave 2 profiled the 274 unbound lakes, used four regional scouts (southeast, northeast, Midwest + Great Lakes, West) to test source families in parallel, ran a systematic USGS live scan, re-ran the wave-1 review machinery on every new candidate, and audited wave 1.
Three layers are reported separately because they rest on different rule sets. Only L1 uses the pre-registered `binding-review-v1` unchanged.

| Layer | Rules | Core | Flagged | Stage-only | No binding | Core % | Core + flagged % | Ladder points (core / core+flagged) |
|---|---|---|---|---|---|---|---|---|
| wave 1 (reproduced) | binding-review-v1 | {W1['core']} | {W1['flagged']} | {W1['stageOnly']} | {W1['none']} | {pct(W1['core'])} | {pct(W1['core'] + W1['flagged'])} | 5 / 7 |
| **L1** | v1 unchanged + wave-1 probe bug fix + new sources | {L1['core']} | {L1['flagged']} | {L1['stageOnly']} | {L1['none']} | {L1['pctCore']}% | {L1['pctCorePlusFlag']}% | {L1['ladderPointsCore']} / {L1['ladderPointsCorePlusFlag']} |
| **L2** | + v1.1 rule extensions (section 5) | {L2['core']} | {L2['flagged']} | {L2['stageOnly']} | {L2['none']} | {L2['pctCore']}% | {L2['pctCorePlusFlag']}% | {L2['ladderPointsCore']} / {L2['ladderPointsCorePlusFlag']} |
| **L3** | + v1.1-R7h history-envelope promotion | **{L3['core']}** | {L3['flagged']} | {L3['stageOnly']} | {L3['none']} | **{L3['pctCore']}%** | {L3['pctCorePlusFlag']}% | {L3['ladderPointsCore']} / {L3['ladderPointsCorePlusFlag']} |

Reading it honestly: with the pre-registered rules alone the fleet moves from {pct(W1['core'])} to {L1['pctCore']}% core (the 50% ladder step is not reached). The 50% step (7 points instead of 5) is reached only with the labelled v1.1 extensions plus R7h, i.e. with rules that were written after seeing wave-1 failures. All of it is machine-verified, not human-reviewed; per the rubric nothing counts until a human adopts it (blockers B-binding-001 and B-gaps-003, actions M-B02 and M-G01). Each lake's `wave` value in `verified_bindings_v2.csv` (`w1`, `w2-v1`, `w2-v1.1`) lets the reviewer take only the rows that rest on the strict rules.

Newly bound lakes (previously no binding or stage-only): **{len(new)}** ({len(newcore)} core in L3, {len(new) - len(newcore)} flagged). History of all {len([r for r in out if r['bindingStatus'] in BOUND])} bound lakes: {S['historyClassBound'].get('SUFFICIENT', 0)} with >= 5 complete years, {S['historyClassBound'].get('LIMITED', 0)} with 2-4, {S['historyClassBound'].get('NONE', 0) + S['historyClassBound'].get('INSUFFICIENT', 0)} with none or under 2.
""")

# ---------------------------------------------------------------- 2 profile
byst = C(p["state"] for p in prof.values()); byop = C(p["opfam"] for p in prof.values()); tiers = C(p["bowTier"] for p in prof.values())
now_unb = {r["lakeId"] for r in out if r["bindingStatus"] not in BOUND}
tt = []
for t in ("A", "B", "C"):
    ids = [k for k, p in prof.items() if p["bowTier"] == t]
    tt.append((t, len(ids), sum(1 for k in ids if k not in now_unb), sum(1 for k in ids if k in now_unb)))
A(f"""## 2. The 274 unbound lakes and how they were ranked

Profile table: `binding2/unbound_profile.json` (state, operator, `hasDam`, `poolBasis`, area, `apiLevel`, `usgsGage`, wave-1 reason, bowfishing tier). By wave-1 reason: 171 `no-candidate`, 96 `candidates-rejected`, 7 pending. By `poolBasis`: 146 natural-surface, 115 full-pool, 13 unknown; {sum(1 for p in prof.values() if p['hasDam'] == 'True')} have a dam. Median area {sorted(float(p['areaKm2'] or 0) for p in prof.values())[len(prof)//2]:.1f} km2 (only 45 are larger than 50 km2). By operator family: {', '.join(f'{k} {v}' for k, v in byop.most_common())} (`NONE` = natural lakes with no operator). Largest state groups: {', '.join(f'{k} {v}' for k, v in byst.most_common(12))}.

There is no popularity field in the directory, so the bowfishing relevance tier is a documented heuristic (`profile_unbound.py`): size class (0-4) + state bowfishing prevalence (1-3: warm-water carp/gar states 3, Mountain West and mid-Atlantic 2, AK/HI/New England 1) + regulated pool (+1) + warm-water lake (+1); tier A >= 8, B 6-7, C otherwise. It encodes judgement, not data, and it only decided where scouts spent effort first.

| Tier | Unbound lakes (wave-1 list) | Bound now (L3 incl. flagged) | Still unbound |
|---|---|---|---|
""" + "\n".join(f"| {t} | {n} | {b} | {u} |" for t, n, b, u in tt) + "\n")

# ---------------------------------------------------------------- 3 providers
prov_names = {"usgs": "USGS NWIS (live scan, absolute elevation parameters)", "usgs-d": "USGS NWIS gage height + gage-datum altitude (derived, flagged class)", "sjrwmd": "SJRWMD WISKI static store (FL)", "duke": "Duke Energy Lake View API (documented stage offset, flagged class)",
              "nhdes": "NH DES Dam Bureau real-time platform", "coops": "NOAA CO-OPS Great Lakes IGLD85 stations", "cwms-lre": "USACE Detroit Great Lakes lake-wide means (relay of NOAA)", "eccc": "Water Survey of Canada / LWCB (Lake of the Woods)",
              "usbr-pnhm": "USBR Pacific Northwest Hydromet (live copy of lagging RISE series)", "cdec": "California CDEC (DWR)", "srp": "SRP Watershed Connection JSON", "cwms": "USACE CWMS (re-pointed / dam-named series)", "a2w": "USACE Access2Water (re-pointed)",
              "cwms-nwdp": "USACE CWMS NWDP (Grand Coulee forebay)", "cwms-saw": "USACE CWMS SAW (Kerr)", "cwms-sam": "USACE CWMS SAM", "cwms-saj": "USACE CWMS SAJ", "cwms-mvp": "USACE CWMS MVP", "rise": "USBR RISE (state-split sibling)", "nwps": "NOAA NWPS relay", "nipsco": "NIPSCO hydro page", "nppd": "NPPD", "cnppid": "CNPPID",
              "aep": "AEP Smith Mountain plant-levels", "nwrfc": "NWRFC XML (NWS)", "njwsa": "NJ Water Supply Authority", "mncsg": "MN DNR Cooperative Stream Gaging", "alliant": "Alliant Energy hydro page", "wps-hydro": "WPS/WRPCO hydro page", "cwlp": "CWLP", "twdb": "TWDB"}
pc = collections.defaultdict(lambda: dict(n=0, core=0, h5=0, lakes=[]))
for r in new:
    d = pc[r["provider"]]; d["n"] += 1; d["core"] += r["bindingStatus"] in CORE; d["h5"] += r["historyClass"] == "SUFFICIENT"; d["lakes"].append(dn(r["lakeId"]))
rows = [(prov_names.get(k, k), v["n"], v["core"], v["h5"], ", ".join(sorted(v["lakes"])[:7]) + (" ..." if len(v["lakes"]) > 7 else "")) for k, v in sorted(pc.items(), key=lambda kv: -kv[1]["n"])]
A("""## 3. Which sources unlocked lakes

Source families tested in parallel by four scouts (southeast, northeast, Midwest + Great Lakes, West) plus this thread's USGS scan. Every scout record, including dead ends, is in `ledger/gaps.jsonl` (`S-gaps-*`) and `binding2/notes/*.json`. Table: lakes newly bound at L3 by the provider that ended up as the binding (a lake counts once; `History >= 5y` is the final history leg, which may come from another provider).

""" + md(rows, ["Provider (binding)", "New lakes", "of which core", "history >= 5y", "Examples"]) + f"""
General methods that unlocked many lakes at once, in order of yield:
1. **Fix the wave-1 matching rules, not the sources** (section 4 and 5): probe-parameter bug, state split, dam-named gauges, sibling lakes.
2. **NOAA CO-OPS Great Lakes** (13 directory entries in one stroke; stations carry 45-126 years of IGLD85 daily means). The lake-wide rule RGL is what makes the town-named harbour stations eligible.
3. **State/district platforms with an index**: NH DES (`nhdes.rtiamanzi.org/api`, hourly, history back to 2010, covers about 20 NH lakes beyond the directory), SJRWMD's static WISKI store (7 lakes of the Harris chain / Ocklawaha / St. Johns, 5-30 years), Duke Energy Lake View (43 Duke lakes; 8 in the directory).
4. **USBR PN Hydromet and CDEC** as live copies of USBR/DWR series that RISE lags by 9-13 days (the original reason for the R6 rejections of Cascade, Crescent, Potholes, Banks, Berryessa).
5. **USGS bounding-box scan** (one request per lake) found the rest: 829 candidate series on 261 lakes, but only {pc['usgs']['n'] + pc['usgs-d']['n']} lakes end up on USGS because most nearby sites are river/outlet gauges, discontinued, or local stage.

Providers that did **not** help (all recorded in the ledger): SFWMD DBHYDRO (login), mass.gov/des.nh.gov documents/NJDWSC (HTTP 403 to automated clients; not bypassed), FirstLight/Great River Hydro/Baltimore DPW/WSSC/MDC/PA DCNR/DE DNREC/VT/ME/RI state programs (phone line, percent-full PDFs, flows only), Nebraska DWEE AQUARIUS (click-through disclaimer; not bypassed), Dominion (no observed level), Utah DWRi/OWRD/Upper Colorado hydrodata (unreachable or 403), Xcel Chippewa Flowage (404).
""")

# ---------------------------------------------------------------- 4 wave-1 corrections
A(f"""## 4. Wave-1 audit: what was wrong

| # | Finding | Evidence | Effect |
|---|---|---|---|
| 1 | **Probe-parameter bug.** `probe_usgs` kept the parameter with the latest timestamp and broke ties by sample count, so sites reporting both an absolute lake elevation (62614/62615/00062) and gage height (00065) were recorded as 00065. | 78 USGS probes chose 00065; 30 of them have a live elevation parameter (`reprobe_usgs.py`, `probe_results_v2.json`). | 14 lakes were `STAGE_ONLY` only because of this (Winnebago, Mendota, Monona, Geneva, Devils, Stump, Higgins, Gogebic, Geist, Greenwood, Quinault, Francis Case, Eufaula, Clear Lake CA). They now bind (4 core, 8 flagged, 12 core via R7h in L3 across the 32 stage-only lakes; 8 stay stage-only). |
| 2 | **State rule rejected cross-state reservoirs.** Kerr (NC entry, station in VA), Thurmond (SC and GA entries), Youghiogheny (MD entry, station in PA), Flaming Gorge (WY). | R4 `state-mismatch` with name similarity 1.0 and the gauge on the dam. | R4b waiver (v1.1). |
| 3 | **Uniqueness rule (R5) blocked sibling entries** of one physical lake: Thurmond SC/GA, Eufaula/W.F. George AL/GA, East Lake Tohopekaliga vs Lake Tohopekaliga. | the same series was claimed by the sibling entry. | R5b (v1.1). |
| 4 | **Identity by name failed for dam-named pools**: Grand Coulee Dam (Lake Roosevelt), Jamie Whitten L&D (Bay Springs), Stennis L&D (Columbus Lake), Garrison Dam (Sakakawea), Libby, Big Bend, Fort Randall. | station inside the polygon, level in the strong window, NID dam name matches. | R2b/R2c (v1.1). |
| 5 | **Geometry rule R1 (1.5 km) rejected dam gauges** of large reservoirs: Logan Martin (1.6 km, two agreeing sources), Longview (3.0 km, four agreeing sources), Smith Mountain (2.3 km). | CWMS/A2W project coordinates sit 1.6-3.2 km from the polygon edge. | R1b (v1.1, strong level + name sim >= 0.75 only). |
| 6 | **Datum rule R8 is a label test.** Operators whose feed carries no datum label (USBR PN Hydromet, CDEC, SRP, utahlake.gov, NWRFC, AEP, CNPPID) failed it although the level sat at the full pool. | R7 strong or the provider publishes its own full pool within 3 ft of the directory's. | R8b/R8c (v1.1). |
| 7 | **TWDB history bookkeeping miss**: Amistad and Falcon recorded `NONE`; the history files exist in lower case. | TWDB CSV exists: Amistad 57 complete years, Falcon 72. | history fixed (history2.py). |
| 8 | **Lake St. Clair (CO-OPS) had no history leg.** | CO-OPS daily means 1990-2025 pulled (`coops_history.py`). | history fixed. |
| 9 | **Great Lakes and Great Salt Lake were unbound** because the five Great Lakes have no polygons (wave-1 blocker B-binding-005). | every CO-OPS harbour station passes level and state; only the position rule fails. | RGL (v1.1). |
| 10 | **R9 limit (not an error).** Lake Francis Case: USGS Chamberlain (upper pool) 1350.2 ft and CWMS Fort Randall forebay 1353.2 ft differ by 3-5 ft, 80 miles apart on a river-run reservoir; the 2 ft agreement band would call them `CONFLICT`. Bound on the Chamberlain USGS gauge (a lake gauge, 26 complete years). | both are right; a single "lake level" does not exist on a long reservoir with a pool slope. | recorded; the Fort Randall forebay is the better dam-pool series if the product wants the forebay |

Checks that came out clean: **Eagle Lake MS** (the "Muddy Bayou control structure" binding): the station name is literally "Eagle Lake Side" (landside = lake side, 75.17 ft vs full pool 76.9) and NWPS `MBGM6` "above Muddy Bayou C/S Eagle Lake Side" agrees (75.02); the other side is Steele Bayou (69.65) and was rejected. **Access2Water tailwater cases:** a station-name/operator-level audit of all 315 wave-1 bindings (`wave1_audit.py`) found no additional tailwater series; the flagged names (`Powell` contains "well", `Outlet`, `Control Structure`, `Pump`) are innocent or are the Eagle Lake case above. The audit's delta-to-full-pool flags (about 50 lakes) are legitimate drawdown or flood-pool in western, Tennessee/Cumberland and Corps flood-control reservoirs, not mis-matches (their own multi-year history reaches the full pool).

Directory data-quality finding (not a binding error): the `fullPoolFt` of several lakes disagrees with every gauge reading for the lake. Spirit Lake IA 1447 ft (gauge ~1401), Storm Lake IA 1437 (~1399), Clear Lake IA 1204 (~1227), Lake Geneva WI 879 (~864), West Grand Lake ME 259 (gauge 296.7, NAVD88, 15 years), Alamo AZ and Bluewater NM (history never within 10 ft of the stored pool). These lakes stay flagged or unbound because R7 compares to the stored value. Action M-G03.
""")

# ---------------------------------------------------------------- 5 rules
rule_desc = [("R1b", "dam-gauge geometry", "polygon distance <= 5 km, linked NID dam within 4 km of the gauge, name similarity >= 0.75, strong R7 only"),
             ("R2b", "identity via dam", "an NID dam within 1.5 km of the gauge and within 6 km of the polygon with a similar name, or an Access2Water NIDID equal to the lake's linked dam; strong R7 only"),
             ("R2c", "inside + dam token", "gauge inside the polygon sharing a >= 5-letter token with the linked dam name; strong R7 only"),
             ("R2d", "inside + operator pool", "USACE/USBR pool series inside the polygon with strong or weak R7 (Lake Pepin)"),
             ("R4b", "state waiver", "gauge inside the polygon or dam-confirmed"),
             ("R5b", "sibling waiver", "same linked NID dam or polygons within 3 km"),
             ("R8b", "datum label waiver", "absolute elevation (not derived) with strong R7"),
             ("R8c", "datum via published pool", "provider's own full-pool elevation within 3 ft of the directory's"),
             ("RGL", "Great Lakes / big polygon-less lakes", "Great Lakes, Green Bay, Lake of the Woods, Great Salt Lake: gauge within 80 km (150 km for IGLD85 CO-OPS stations) or a lake-wide series; level within 6 ft of the directory's"),
             ("RI", "identity widening", "inside the polygon with name similarity >= 0.5, or within 1.5 km with similarity >= 0.6 on a polygon >= 20 km2 (needed for the flagged tier)"),
             ("R1c", "big-lake gauge", "USGS LK / state or operator lake page named for the lake within 5 km of a polygon >= 20 km2 (Houghton Lake)")]
rows = []
for k, nm, ds in rule_desc:
    on = abl.get(f"only_{k}", {}); off = abl.get(f"minus_{k}", {})
    rows.append((k, nm, ds, on.get("gain", "?"), off.get("marginal", "?"), ", ".join(x.split("|")[0] for x in (off.get("lost") or on.get("lakes") or [])[:6])))
A("""## 5. Proposed v1.1 rules and what they are worth

None of these weakens R6 (liveness), R7 (level window) or R9 (cross-origin agreement). They are labelled v1.1, counted separately (layers L1 vs L2/L3 above) and listed per lake in the `checks_passed` column. Counts are lakes bound (core + flagged class, before R7h) found by the ablation in `ablation.py`: "alone" = gain when only that rule is added to v1; "marginal" = loss when only that rule is removed from the full set.

""" + md(rows, ["Rule", "Name", "Definition", "Gain alone", "Marginal in full set", "Lakes"]) + f"""
**S-derived (derived elevation, capped at the flagged tier).** USGS gage height (00065) + site gage-datum altitude (`alt_va`, with a named vertical datum) from LK-type sites, or a provider-documented stage offset (Duke: gauge zero = published `Elevation` minus 100 ft; NWPS lists 660 ft for Norman, Duke's USACE-matched Jocassee offset 1010.01 ft over 1010 days). Calibration on the USGS sites that report both a published elevation and gage height live now ({len(cal)} sites, 58 with a usable `alt_va`): 45 of 58 within 0.5 ft and 53 of 58 within 2 ft; the misses are sites with `alt_va` = 0.0 or river gauges, which the rule excludes (site type LK, or a lake-named non-river site). Of the 32 wave-1 stage-only lakes, 17 USGS sites give a derived elevation within 8 ft of the directory pool (`stage_plus_alt.json`); 14 of those turned out to have a published elevation parameter all along (finding 1).

**R7h (history envelope).** A flagged lake (deep drawdown or low-confidence full pool, which is why R7 only allows it as flagged) is promoted to core when its own daily history (>= 5 complete years) has a 99th percentile within +-8 ft of the directory full pool. This is not a second origin; it removes the specific doubt behind the flag (is this series really the lake's pool?). Negative control (`r7h_control.py`): for each of the {ctrl['nPromoted']} promoted lakes, the share of the other {ctrl['nSeries'] - 1} bound lakes' series that would also pass against its full pool is a median {ctrl['medianChanceRate']*100:.1f}% and a maximum {ctrl['maxChanceRate']*100:.1f}% (Great Lakes at 577 ft, where many Michigan/Ohio lakes sit); since identity checks also constrain position, the conditional false-pass rate is lower. R7h cannot rescue a wrong directory pool: it fails for Spirit, Storm, Clear IA, Geneva.

**Fate of the 57 wave-1 flagged lakes** (can any be promoted by a second independent source?): {'; '.join(f'{k} {v}' for k, v in fate.items())}. A second independent origin is rare: western USBR reservoirs have no USGS/USACE elevation series at the dam, so only Red Lake MN (USGS agrees within 2 ft) was corroborated by a second origin. The other promotions come from R7h. The {fate.get("still flagged", 0)} still flagged ({", ".join(r["lakeId"].split("|")[0] for r in flag_w1 if r["bindingStatus"] == "VERIFIED_FLAG")}) have short or no history, or a series that never reaches the stored pool (Alamo, Isabella, Catahoula, Bluewater, Walker). Of the 32 wave-1 stage-only lakes, 24 now bind (see finding 1 and the S-derived rule) and 8 remain stage-only.
""")

# ---------------------------------------------------------------- 6 NWPS
nw = [v for v in hp.values()]
yrs = C(v["firstYear"] for v in nw)
A(f"""## 6. NWPS gauges as DIRECT_LAKE_GAUGE, and what history exists

**Acceptability.** NWPS `HP` lake gauges are a relay: the `dataAttribution` field names the owner (USACE, USGS, MN DNR, Duke, TVA...). They are acceptable as a live DIRECT_LAKE_GAUGE source for lakes with no other feed (wave 1 bound 50 lakes this way; the wave-2 additions are Gaston, Smith Mountain, Thurmond GA, Liberty, Youghiogheny), because the level is the operator's, measured on the lake. They are never independent corroboration, and they are not always elevations: the Catawba chain (97-100 ft), Lake of the Woods (59 ft), Vermilion (56.8 ft) and the Idaho reservoirs are local stage, which only the documented-offset route (S-derived) can use. Two further traps: some NWPS gauges transmit twice a day (liveness is then ~20 h, which R6 accepts for daily feeds), and the anonymous listing endpoint allows only 10 requests per 5 minutes.

**History via the IEM HADS archive** (`mesonet.agron.iastate.edu/cgi-bin/request/hads.py`, NWS raw DCP data): probed for the 50 wave-1 NWPS lake gauges by sampling one 3-day window in 2004, 2008, 2012, 2016, 2019, 2022 (`hads_probe.py`). First year with data: 2012 for {yrs.get(2012, 0)}, 2016 for {yrs.get(2016, 0)}, 2022 for {yrs.get(2022, 0)}, 2008 for {yrs.get(2008, 0)}; none for {yrs.get(None, 0)}. So HADS gives a maximum of about 13 calendar years (2013-2025) and nothing before 2012 (the TVA pool stream starts 2022-10-27, as the baselines thread found). `hads_history.py` converts 5-15-minute data to daily means (UTC date); gauges that transmit only once or twice a day were re-pulled with a 1-observation minimum. Resulting NWPS-chosen bindings with >= 5 complete years: see `history_class` in the verified file. USACE RVD AFOS text products are TVA/Huntsville-specific and did not help the others.
""")

# ---------------------------------------------------------------- 7 coverage by state
def row(s):
    d = sc["state"][s]
    return (s, d["n"], f"{d['w1core']}+{d['w1flag']}", f"{d['core']}+{d['flag']}")
A("""## 7. Coverage where wave 1 was weakest

Bound as core + flagged (wave 1 -> L3):

""" + md([row(s) for s in ("AK", "CT", "HI", "NH", "ME", "WI", "DE", "RI", "VT", "MA", "MD", "NJ", "PA", "FL", "SC", "MI", "MN")], ["State", "Lakes", "wave 1", "L3"]) + """
By operator family (core + flagged, wave 1 -> L3): """ + "; ".join(f"{k} {v['n']} lakes {v['w1core']}+{v['w1flag']} -> {v['core']}+{v['flag']}" for k, v in sc["opfam"].items()) + ".\n")

# ---------------------------------------------------------------- 8 remaining
cls = C(r["cls"] for r in rem)
cur = {
 "Lake Maurepas|LA": "only the Pass Manchac strait gauge (tidal, gauge datum -0.18 ft NAVD88, 3 years); stage-only. PROXY only",
 "Sabine Lake|LA": "CO-OPS Port Arthur tide gauge 239 m from the polygon (tidal estuary level, 10 years); pending - not a lake pool",
 "White Lake|LA": "CRMS marsh gauge last reported 2026-07-29 (stale). Proxy: none",
 "Grand Lake|LA": "Catfish Point control-structure stage intermittent, last 2026-10-05 (190 h). Proxy: structure stage",
 "Quabbin Reservoir|MA": "MWRA/DCR publish monthly elevations only (517.64 ft on 10/01). Proxy: monthly value",
 "Houghton Lake|MI": "USGS 442400084472801 62615 live with 43 years; see section 1 for the current status",
 "Chippewa Flowage|WI": "Xcel hydro page 404; no machine-readable level",
 "Otter Tail Lake|MN": "MN DNR volunteer reads only (last 2026-04-29)",
 "Pymatuning Reservoir|PA": "USGS record stopped 2026-06-04; PA DCNR publishes nothing",
 "Lake Thompson|SD": "no gauge; nearest live SD lake level is Poinsett (NWPS PONS2)",
 "Lake Anna|VA": "Dominion publishes no observed level; USGS sites are water-quality only",
 "Lake Murray (OK)|OK": "OWRB lake-level page not reachable; nothing published",
 "Lake Springfield|IL": "CWLP stick reading at the pump station, weekly web table (R3 pump-station name, not daily)",
 "Salton Sea|CA": "USGS 10254005 stopped; no replacement", "Sevier Lake|UT": "terminal playa, usually dry; USGS 10218500 is a different water body",
 "Pyramid Lake|NV": "USGS 10336500 last observation 274 h old, non-recording", "Utah Lake|UT": "utahlake.gov POST endpoint (90 days of history) fails the datum label only when the full-pool hint is missing; see verified file",
 "Mono|CA": "1-2 manual readings per year", "Malheur Lake|OR": "USGS record ends 1989", "Moosehead Lake|ME": "Brookfield Safe Waters publishes the current value only (1026.12 ft, no history, no API)",
 "Flagstaff Lake|ME": "Brookfield current value only", "Mooselookmeguntic Lake|ME": "Brookfield current value only", "Lake Wallenpaupack|PA": "Brookfield current value only (1174.54 ft)",
 "Candlewood Lake|CT": "FirstLight phone line only", "Conowingo Reservoir|MD": "Constellation/MDE percent-full only",
 "Eleven Mile Reservoir|CO": "Denver Water percent-full PDF only", "Washoe Lake|NV": "USGS gauges discontinued", "Holter Lake|MT": "only tailwater stage is public",
 "Lake Pepin|MN": "see verified file (inside-polygon USACE pool gauge)", "Skaneateles Lake|NY": "USGS record ended 1995; city publishes yearly PDFs",
 "Torch Lake|MI": "no gauge; Mullett Lake (USGS) is 45 km away - PROXY only", "Burt Lake|MI": "Mullett Lake (sibling by outlet) is a PROXY, not DIRECT", "Lake Charlevoix|MI": "no gauge",
 "Elk Lake|MI": "USGS record ended", "Big Stone Lake|SD": "NWPS BSLM5 twice-daily, 188 h old (R6) and in MN; history-only", "Riffe Lake|WA": "NWRFC MSRW1 (10 days) and the stopped USGS 14234800; Tacoma Power publishes nothing machine-readable",
 "Lake Vermilion|MN": "NWPS LVOM5 and MN DNR gauge 73050001 read local stage (56.8 ft, no documented offset); MN DNR LakeFinder has monthly volunteer reads. Stage-only",
 "Yellowstone Lake|WY": "no lake gauge; the USGS site on the Yellowstone River at the outlet is a river gauge (rejected)",
 "Big Green Lake|WI": "USGS 434840089000001 is a local-stage lake gauge (6.7 ft, gauge altitude 790.13 ft NAVD88 gives 796.8 ft, plausible) but name similarity is only 0.42; stays unbound",
 "Georgetown Lake|MT": "USGS 12325000 live 6428.85 ft NAVD88 but the directory has no full pool (county report ~6429.5): cannot pass R7; one value in the directory would bind it",
 "Eagle Nest Lake|NM": "USGS 07205500 live 8159.9 ft NGVD29 but the directory has no full pool: cannot pass R7",
 "Lake Freeman|IN": "NIPSCO Oakdale hydro page reads 610.37 ft (FERC target 610.35) but the plant is 1.8 km from the polygon (R1)",
 "Lake Macbride|IA": "USGS 05453500 stopped", "Big Creek Lake|IA": "USACE MVR stage with unconfirmed datum", "Lake Ogallala|NE": "no feed (the Kingsley Dam gauge is McConaughy's pool)", "Nelson Lake|ND": "no gauge",
 "Timothy Lake|OR": "operator publishes nothing machine-readable", "Lake Arthur|PA": "USGS 03106280 last observation 7 days old (R6), PA DCNR publishes nothing", "Wachusett Reservoir|MA": "MWRA monthly elevations only",
 "Loch Raven Reservoir|MD": "Baltimore DPW percent-full only", "Prettyboy Reservoir|MD": "Baltimore DPW percent-full only", "Lake Washington|MS": "no gauge (USGS site is a groundwater well)", "Moon Lake|MS": "no gauge",
 "Waubay Lake|SD": "no gauge", "Bitter Lake|SD": "no gauge", "Enemy Swim Lake|SD": "no gauge", "Lac Courte Oreilles|WI": "no gauge", "Cranberry Lake|NY": "no gauge", "Lake Bemidji|MN": "MN DNR volunteer reads only",
 "Lake Metigoshe|ND": "USGS 05123000 stopped", "Sangchris Lake|IL": "no public level", "Lake of Egypt|IL": "no public level", "Rice Lake|IL": "no public level", "Sherman Reservoir|NE": "Nebraska DWEE AQUARIUS needs a click-through; not bypassed", "Chesuncook Lake|ME": "no public level (Brookfield publishes ponds near it but not this one)", "Lake Waccamaw|NC": "no stage gauge (a groundwater well only)", "Eagle Lake|CA": "monthly manual reading in local news only", "Lake Wawasee|IN": "USGS sites silent for 60-90 days on every parameter", "West Grand Lake|ME": "USGS 01018900 and NWPS WGLM1 are live at 296.7 ft but the directory pool (259 ft) is wrong by 37 ft: R7 fails; fixing the directory value would bind it",
 "Dillon Reservoir|CO": "CO DWR telemetry live (16 y) but no datum label and name similarity 0.58; left unbound", "Lake George|FL": "SJRWMD gauges are stream-side stations (Middle Rd) not named for the lake", "Chicot|AR": "MVK pumping-plant gauges 7 km from the polygon",
 "False River|LA": "MVN stage with no vertical-datum info (8 years)", "Lake Chesdin|VA": "ARWA homepage prints feet below normal pool, no absolute level",
}
A(f"""## 8. Lakes still without a DIRECT binding

L3 leaves {L3['none']} lakes with no binding and {L3['stageOnly']} stage-only. Counts by what blocks them: {'; '.join(f'{k} {v}' for k, v in cls.most_common())}. Full table with the best attempted source and the scout's evidence: `binding2/remaining_unbound.json`; per-lake dead-end records in `ledger/gaps.jsonl`.

**Lakes with no public level data (evidence in the ledger).** Alaska (all 12): no lake gauge in USGS or NWPS (two inactive NWPS gauges at Aleknagik and Lake Nerka); outlet-stream gauges exist (Kenai River below Skilak outlet, Kasilof, Kvichak at Igiugig) but are stream stage/discharge, i.e. PROXY only. Hawaii (all 9): no lake gauge anywhere. Connecticut (12): FirstLight phone line only; USGS has river gauges only. New Hampshire is the success story (6 lakes bound through NH DES). Delaware ponds: DNREC publishes nothing. Rhode Island salt ponds: tidal. The satellite route (Hydroweb, DAHITI, G-REALM) is limited to large lakes and was not tested; at best it gives a PROXY (water-extent or altimetry height with metre-scale error), which per the rubric cannot count as DIRECT_*.

**Bowfishing-relevant lakes still open (tier A and B, largest first).**

""" + md([(r["tier"], dn(r["lakeId"]), round(float(r["areaKm2"] or 0)), r["status"].replace("STAGE_ONLY", "stage-only").replace("NONE", "none"), cur.get(r["lakeId"], r["cls"])) for r in sorted([x for x in rem if x["tier"] in ("A", "B")], key=lambda x: (x["tier"], -float(x["areaKm2"] or 0)))], ["Tier", "Lake", "km2", "status", "Reason / proxy"]))

tierA_new = sorted(dn(r["lakeId"]) for r in new if prof.get(r["lakeId"], {}).get("bowTier") == "A")
A("**Tier-A lakes newly bound in wave 2:** " + ", ".join(tierA_new) + ".\n")

A("""
## 9. Blockers and actions

- **B-gaps-003 / M-G01 (high):** decide whether the labelled v1.1 rules and R7h may be used for the reviewed-binding batch. Without them core coverage is the L1 figure.
- **B-gaps-002 / M-G02 (medium):** permission for undocumented-but-public operator endpoints (Duke Lake View is the largest block, 8 lakes; also SRP, Brookfield Safe Waters, utahlake.gov, CNPPID, WPS, NIPSCO, Alliant).
- **B-gaps-006 / M-G03 (low):** review the directory full pools listed in section 4.
- **B-gaps-001 (medium, no action possible):** about 70 lakes have no public level source at all.
- **M-B02 (carried over, high):** human review of the machine-verified ledger.

## 10. Honest limits

- Everything is machine-verified on a single-day liveness snapshot (2026-10-13); a seasonal outage turns a lake `REJECT`. Weekly re-probing (wave-1 section 6) still applies.
- The v1.1 rules and R7h were designed after seeing wave-1 and wave-2 failures, so their error rate is not measured by a hold-out. The rule ablation and the negative control bound the damage but do not replace review. Spot-check: of the {len(new)} newly bound lakes, the station names and levels were read by hand against dam names and domain knowledge; three classes of false positive were found and removed during the work (river gauges whose gage height + altitude coincidentally sits near the lake, outlet/pass/canyon gauges, and a pump-station reading).
- Derived (S-derived) elevations depend on a gauge-datum altitude or a provider-documented offset; Duke's offsets agree with NWPS metadata and the USACE series for two lakes but were not independently surveyed. They stay in the flagged tier unless R7h or a second origin promotes them.
- Several operator feeds are undocumented web-app endpoints (authority 7 in the ledger) and can change without notice. History for those is mostly 2-4 years.
- Satellite altimetry (DAHITI, Hydroweb, G-REALM) was not tested; it would be PROXY only.
- The bowfishing tier is a heuristic. Wave-2 effort followed it, but the verification itself is lake-blind.

## 11. Reproduce

```
python research/lake-brain/binding2/profile_unbound.py      # unbound profile + tier
python research/lake-brain/binding2/reprobe_usgs.py         # wave-1 probe fix
python research/lake-brain/binding2/usgs_scan.py            # live USGS scan -> cand/usgs_scan.jsonl
python research/lake-brain/binding2/src_se.py | src_ne.py | src_mw.py | src_west.py   # scouts -> cand/*.jsonl, history/
python research/lake-brain/binding2/hads_probe.py; hads_history.py; hads_extra.py; coops_history.py
python research/lake-brain/binding2/assemble_v2.py          # verify (verify2/verify11 -> wave-1 verify.evaluate), history, R7h, summary, verified_bindings_v2.csv
python research/lake-brain/binding2/ablation.py; r7h_control.py; remaining.py; state_cov.py; make_doc.py; write_ledger2.py
```
""")
open(f"{DOCS}/LAKE_BRAIN_BINDING_GAPS_RESEARCH.md", "w").write("\n".join(doc))
print("doc written", len("\n".join(doc)))
