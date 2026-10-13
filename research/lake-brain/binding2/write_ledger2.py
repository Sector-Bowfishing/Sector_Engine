"""Write ledger/gaps.jsonl (source / blocker / action / dataset / score rows) and append MANIFEST rows for binding2 data. Sources come from the scout notes + this thread's own tests."""
import glob, hashlib, json, os, collections
from common2 import *

REPO = "/Users/mcather/Desktop/Development/Sector_Engine"
S = json.load(open(f"{DOCS}/data/binding2_summary.json"))
T = "2026-10-13"
rows = []
n = 0
DEC = {"WORKS": "ACCEPTED", "PARTIAL": "ACCEPTED", "STALE": "DEAD_END", "NO_DATA": "DEAD_END", "NO_API": "DEAD_END", "PORTAL_ONLY": "LEAD", "REQUIRES_LOGIN": "DEAD_END", "BLOCKED": "DEAD_END"}
for f in sorted(glob.glob(f"{B2}/notes/*.json")):
    if "series_check" in f:
        continue
    area = os.path.basename(f)[:-5]
    for r in json.load(open(f)):
        n += 1
        res = r.get("result")
        dec = DEC.get(res, "LEAD")
        if res == "PARTIAL" and not r.get("lakesUnlocked"):
            dec = "LEAD"
        rows.append(dict(kind="source", id=f"S-gaps-{n:03d}", question="Q-gaps", name=r.get("source"), org=r.get("org"), url=r.get("url"), accessed=T,
                         dataType="lake pool/stage level", geoCoverage=", ".join((r.get("scope") or [])[:6]) + (" ..." if len(r.get("scope") or []) > 6 else ""),
                         lakeCoverage=f"{len(r.get('lakesUnlocked') or [])} lakes with live candidate", timeCoverage=str(r.get("history")), cadence="", machineReadable=(r.get("access") in ("api", "bulk")),
                         access=r.get("access") or "portal", license=r.get("license") or "", authority=r.get("authority") or 7, supports="binding", scoreDimensions=["coverage", "historyQuality"], decision=dec,
                         reason=f"[{res}] {(r.get('evidence') or '')[:400]}", localPath=f"binding2/notes/{area}.json", checksum="", notes=(r.get("notes") or "")[:400] + f" | tested: {(r.get('tested') or '')[:200]}"))
own = [
 ("USGS NWIS iv bounding-box scan for 00062/62614/62615/62616/72020/72022/00065 (binding2/usgs_scan.py)", "USGS", "https://waterservices.usgs.gov/nwis/iv/", "WORKS", 1, "ACCEPTED", "364 lakes scanned (274 unbound + flagged + stage-only); 829 candidate series on 261 lakes. Shows that wave-1 probe selection preferred 00065 over a live elevation parameter at 30 sites."),
 ("USGS gage height + site altitude (alt_va) as derived elevation", "USGS", "https://waterservices.usgs.gov/nwis/site/?siteOutput=expanded", "PARTIAL", 1, "LEAD", "Calibration on 58 sites that report both: 45 within 0.5 ft, 53 within 2 ft; failures are sites with alt_va 0.0 or river gauges. Used only as FLAG tier derived candidates (LK sites)."),
 ("IEM HADS raw DCP archive (mesonet.agron.iastate.edu/cgi-bin/request/hads.py) as NWPS history", "Iowa Environmental Mesonet / NWS", "https://mesonet.agron.iastate.edu/cgi-bin/request/hads.py", "PARTIAL", 2, "ACCEPTED", "HP/HG lake-level columns exist from 2012 for 35 of 50 wave-1 NWPS lake gauges (first value 2016 for 9, 2022 for 3, none for 2): up to 13 complete years; completeness depends on DCP transmit interval."),
 ("NWPS as DIRECT_LAKE_GAUGE (acceptability test)", "NOAA/NWS", "https://api.water.noaa.gov/nwps/v1/gauges", "PARTIAL", 1, "ACCEPTED", "NWPS HP gauges relay USACE/USGS/state/operator data (dataAttribution field names the origin). Acceptable as a live relay and for HADS history, never as independent corroboration; local-stage gauges (Catawba chain 97-100 ft, Lake of the Woods 59 ft, Vermilion 56.8 ft) are not absolute elevations."),
]
for nm, org, url, res, auth, dec, why in own:
    n += 1
    rows.append(dict(kind="source", id=f"S-gaps-{n:03d}", question="Q-gaps", name=nm, org=org, url=url, accessed=T, dataType="level series", geoCoverage="US", lakeCoverage="", timeCoverage="", cadence="", machineReadable=True, access="api", license="public data", authority=auth,
                     supports="binding", scoreDimensions=["coverage", "historyQuality"], decision=dec, reason=f"[{res}] {why}", localPath="binding2/", checksum="", notes=""))
blk = [
 dict(kind="blocker", id="B-gaps-001", question="Q-gaps", missing="Public level data for ~70 natural lakes in AK, HI, ME, VT, NH (dam-less), CT, RI, DE, SD, MI inland, CA/NV playas", why="No gauge, volunteer manual reads, or discontinued gauges (see remaining_unbound.json)", scoreDimension="coverage", impact="caps fleet coverage near 75-80% even with every available public source", attempted=["USGS bbox scan", "NWPS", "state portals", "operator pages"], proxy="outlet-stream stage, satellite water extent, nearest bound lake (PROXY only, not DIRECT_*)", michaelAction=False, priority="medium", status="OPEN"),
 dict(kind="blocker", id="B-gaps-002", question="Q-gaps", missing="Terms of use / permission for undocumented but public operator endpoints (Duke Energy Lake View API, SRP Watershed JSON, Brookfield Safe Waters pages, utahlake.gov, CNPPID, WPS)", why="Endpoints are used by the operators' own public web apps but are not documented APIs; they can change or be rate-limited", scoreDimension="sourceAuthority", impact="8 Duke lakes + ~12 operator lakes depend on them", attempted=["unauthenticated GET only, polite rate"], proxy="NWPS relay or USGS where available", michaelAction=True, priority="medium", status="OPEN"),
 dict(kind="blocker", id="B-gaps-003", question="Q-gaps", missing="Reviewed (human) adoption of v1.1 rule extensions", why="v1.1 rules (R1b R2b R2c R4b R5b R8b R8c RGL RI R1c, R7h, S-derived) are labelled and reported separately; they are not part of the pre-registered binding-review-v1", scoreDimension="coverage", impact=f"difference between {S['layers']['L1_v1_rules']['pctCore']}% (v1 rules) and {S['layers']['L3_v1.1_plus_R7h']['pctCore']}% (v1.1 + R7h) core coverage", attempted=["ablation per rule"], proxy="v1-only list is in verified_bindings_v2.csv (wave column)", michaelAction=True, priority="high", status="OPEN"),
 dict(kind="blocker", id="B-gaps-004", question="Q-gaps", missing="Datum offsets for local-stage gauges (Duke chain, Henrys/Payette, Lake of the Woods NWPS)", why="Provider publishes local stage and a full-pond elevation; offset is documented but not independently surveyed", scoreDimension="trendQuality", impact="flagged tier only", attempted=["Duke Elevation field", "NWPS gauge zero", "USGS alt_va"], proxy="flagged derived elevation", michaelAction=False, priority="low", status="WORKED_AROUND"),
 dict(kind="blocker", id="B-gaps-005", question="Q-gaps", missing="Access to Nebraska DWEE AQUARIUS (Lake McConaughy/Ogallala/Sherman) and SFWMD DBHYDRO (login)", why="Click-through disclaimer / credentials; not bypassed", scoreDimension="coverage", impact="2-3 lakes (mirrors exist via NWPS/CWMS)", attempted=["landing page", "publish API 401"], proxy="NWPS KNGN1, CNPPID page, CWMS SAJ", michaelAction=False, priority="low", status="WORKED_AROUND"),
 dict(kind="blocker", id="B-gaps-006", question="Q-gaps", missing="Directory fullPoolFt errors discovered while verifying (Spirit Lake IA 1447 vs ~1401, Storm Lake IA 1437 vs ~1399, West Grand Lake ME 259 vs ~296, Clear Lake IA 1204 vs ~1227, Lake Geneva WI 879 vs ~864, Henrys Lake and Payette Lake in local stage)", why="R7 compares to directory fullPoolFt", scoreDimension="coverage", impact="blocks promotion of a few lakes", attempted=["history envelope check"], proxy="none", michaelAction=True, priority="low", status="OPEN"),
]
act = [
 dict(kind="action", id="M-G01", what="Decide whether the v1.1 rule extensions (listed in LAKE_BRAIN_BINDING_GAPS_RESEARCH.md section 3) may be used for the reviewed-binding batch; if not, adopt only rows with wave = w1 or w2-v1 in verified_bindings_v2.csv", impact=f"+{round(S['layers']['L3_v1.1_plus_R7h']['pctCore'] - S['layers']['L1_v1_rules']['pctCore'], 1)} percentage points of core coverage ({S['layers']['L1_v1_rules']['pctCore']}% v1 vs {S['layers']['L3_v1.1_plus_R7h']['pctCore']}% v1.1+R7h)", priority="high", relatedBlocker="B-gaps-003"),
 dict(kind="action", id="M-G02", what="Confirm acceptable use of the Duke Energy Lake View endpoint and the other public operator endpoints (or ask the operators for a supported feed); Duke has the largest single block (8 lakes, bowfishing-relevant Catawba/Keowee chain)", impact="8 flagged Duke lakes + ~12 operator lakes", priority="medium", relatedBlocker="B-gaps-002"),
 dict(kind="action", id="M-G03", what="Review the directory fullPoolFt values listed in B-gaps-006 and the 'directory fp suspects' table in the research doc", impact="removes false R7 failures; a few lakes become promotable", priority="low", relatedBlocker="B-gaps-006"),
]
ds = []
def dataset(path, ret, rebuild, note):
    p = f"{DATA}/{path}"
    if os.path.isdir(p):
        b = sum(os.path.getsize(os.path.join(d, x)) for d, _, fs in os.walk(p) for x in fs)
        ds.append(dict(kind="dataset", path=path, bytes=b, sha256="", track="binding2", retention=ret, rebuild=rebuild, note=note))
    elif os.path.exists(p):
        ds.append(dict(kind="dataset", path=path, bytes=os.path.getsize(p), sha256=hashlib.sha256(open(p, "rb").read()).hexdigest(), track="binding2", retention=ret, rebuild=rebuild, note=note))
dataset("binding2/unbound_profile.json", "KEEP", "python research/lake-brain/binding2/profile_unbound.py", "274 unbound lakes with bowfishing tier")
dataset("binding2/verified_v2_full.csv", "KEEP", "python research/lake-brain/binding2/assemble_v2.py", "cumulative per-lake binding table (all 621 lakes, layers)")
dataset("binding2/assembled_v2.json", "REBUILDABLE", "python research/lake-brain/binding2/assemble_v2.py", "assembled records")
dataset("binding2/remaining_unbound.json", "KEEP", "python research/lake-brain/binding2/remaining.py", "remaining unbound lakes with reason")
dataset("binding2/ablation.json", "KEEP", "python research/lake-brain/binding2/ablation.py", "v1.1 rule ablation")
dataset("binding2/envelope.json", "REBUILDABLE", "python research/lake-brain/binding2/envelope_promote.py", "wave-1 flagged lakes history envelope")
dataset("binding2/usgs_stage_calibration.json", "KEEP", "python research/lake-brain/binding2/usgs_stage_calibration.py", "gage height + alt_va calibration")
dataset("binding2/stage_plus_alt.json", "KEEP", "python research/lake-brain/binding2/stage_plus_alt.py", "wave-1 stage-only lakes with derived elevation")
dataset("binding2/hads_probe.json", "KEEP", "python research/lake-brain/binding2/hads_probe.py", "IEM HADS first-year probe for NWPS lake gauges")
dataset("binding2/probe_results_v2.json", "REBUILDABLE", "python research/lake-brain/binding2/reprobe_usgs.py", "wave-1 probe results with USGS parameter-selection fix")
for d, note in (("cand", "scout + scan candidate series"), ("history", "daily history series (scouts, HADS, USGS dv)"), ("notes", "source evaluation records incl. dead ends"), ("raw", "scout raw captures"), ("probe", "cached probes")):
    dataset(f"binding2/{d}/", "REBUILDABLE", "python research/lake-brain/binding2/src_*.py usgs_scan.py hads_history.py", note)
score = [dict(kind="score", step="binding-wave2-gaps", previous=S["wave1"]["core"] / S["lakes"] * 100, candidate=S["layers"]["L3_v1.1_plus_R7h"]["pctCore"], dimensions={k: v for k, v in S["layers"].items()},
              evidence="binding2_summary.json", confidence="medium: machine-verified; v1.1 rules and R7h are not pre-registered", remaining=f"human review adoption; {S['layers']['L3_v1.1_plus_R7h']['none']} lakes without a binding (see doc)")]
with open(f"{DOCS}/ledger/gaps.jsonl", "w") as f:
    for r in rows + blk + act + ds + score:
        f.write(json.dumps(r) + "\n")
man = f"{DATA}/MANIFEST.jsonl"
have = set(json.loads(l).get("path") for l in open(man))
with open(man, "a") as f:
    for r in ds:
        if r["path"] not in have:
            f.write(json.dumps(r) + "\n")
print(len(rows), len(blk), len(act), len(ds))

# enrich the committed summary with ablation / control / fate
ab = json.load(open(f"{B2}/ablation.json")); ct = json.load(open(f"{B2}/r7h_control.json")); sc = json.load(open(f"{B2}/state_cov.json"))
S["ablation"] = {k: {a: b for a, b in v.items() if a not in ("lost", "lakes")} for k, v in ab.items()}
S["r7hNegativeControl"] = {k: v for k, v in ct.items() if k != "per"}
S["stateCoverage"] = sc["state"]; S["operatorFamilyCoverage"] = sc["opfam"]
S["rules"] = {"v1": "binding-review-v1 R1-R9 unchanged", "v1.1": ["R1b", "R2b", "R2c", "R2d", "R4b", "R5b", "R8b", "R8c", "RGL", "RI", "R1c", "S-derived", "SIB"], "R7h": "history envelope p99 within +-8 ft of directory full pool, >=5 complete years"}
json.dump(S, open(f"{DOCS}/data/binding2_summary.json", "w"), indent=1)
