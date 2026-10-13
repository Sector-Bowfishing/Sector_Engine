#!/usr/bin/env python3
"""Add tier-2 regulator evidence (TWDB conservation/dead pool; NWPS normalThreshold) to the strict USACE/TVA table and write the committed outputs:
docs/research/lake-brain/data/plan_flood_evidence.csv and plan_summary.json."""
import csv, json, re, math, collections
from common import *
import plan_evidence as pe

base = list(csv.DictReader(open(f"{PLAN}/plan_flood_evidence_base.csv")))
D, poly, V, nid = pe.load_lakes()
twdb = json.load(open(f"{DATA}/binding/raw/twdb/recent-conditions.json"))
nwps = json.load(open(f"{PLAN}/raw/nwps_meta.json"))
tw_by = {}
for k, t in twdb.items():
    c = (t.get("gauge_location") or {}).get("coordinates") or [None, None]
    tw_by[k] = {"name": t.get("full_name") or k, "lat": c[1], "lon": c[0], "cons": t.get("conservation_pool_elevation"), "dead": t.get("dead_pool_elevation"), "floodLake": t.get("flood_control_lake")}

def twdb_match(lid):
    lake = D[lid]
    if lake["state"] != "TX": return None
    best = None
    for k, t in tw_by.items():
        nm = pe.name_match(lake["name"], t["name"])
        dk = pe.km((lake["lat"], lake["lon"]), (t["lat"], t["lon"])) if t["lat"] else 99
        if nm >= 0.6 and dk <= 25:
            if best is None or nm > best[0]: best = (nm, k, t, dk)
    return best

rows = []
for r in base:
    lid = r["lakeId"]; v = V[lid]
    r = dict(r)
    r["tier2Flood"] = ""; r["tier2Zone"] = ""; r["tier2Source"] = ""; r["tier2ConsPoolFt"] = ""; r["tier2DeadPoolFt"] = ""
    m = twdb_match(lid)
    if m and m[2]["cons"]:
        t = m[2]
        # wrong-lake guard: conservation pool within 100 ft of the observed median / directory pool
        ref = [float(x) for x in (v.get("medFt"), D[lid].get("fullPoolFt")) if x]
        ok = any(abs(float(t["cons"]) - x) <= 100 for x in ref)
        if ok:
            r["tier2Flood"] = True; r["tier2Source"] = f"TWDB:{m[1]}"; r["tier2ConsPoolFt"] = t["cons"]
            if t["dead"]:
                r["tier2Zone"] = True; r["tier2DeadPoolFt"] = t["dead"]
    if v["provider"] == "nwps" and v["station"] in nwps:
        nt = (nwps[v["station"]].get("normalThreshold") or {}).get("value")
        if nt and float(nt) > 0:
            ref = [float(x) for x in (v.get("medFt"), D[lid].get("fullPoolFt")) if x]
            if any(abs(float(nt) - x) <= 25 for x in ref):
                r["tier2Flood"] = r["tier2Flood"] or "nwps-normal-only"; r["tier2Source"] = (r["tier2Source"] + "+" if r["tier2Source"] else "") + f"NWPS:{v['station']}"; r["tier2ConsPoolFt"] = r["tier2ConsPoolFt"] or nt
    rows.append(r)

T = lambda x: str(x) == "True"
for r in rows:
    r["planStrict"] = T(r["planStrict"]); r["planInclusive"] = T(r["planInclusive"]); r["floodStrict"] = T(r["floodStrict"])
    r["flood_all_tiers"] = r["floodStrict"] or bool(r["tier2Flood"] is True)
    r["flood_all_tiers_incl_nwps"] = r["floodStrict"] or bool(r["tier2Flood"])
    r["plan_all_tiers"] = r["planInclusive"] or bool(r["tier2Zone"] is True and r["tier2Flood"] is True)

cols = ["lakeId", "name", "state", "bindingStatus", "provider", "operator", "planSource", "matchedProject", "matchBasis", "matchTier", "distKm", "verifiedMatch", "levelPlausible",
        "swingFt", "guide", "guideTopConSeasonal", "regSchedule", "zoneTop", "zoneBottom", "zone", "flood", "floodSeasonal", "planStrict", "planInclusive", "floodStrict", "levelLabels",
        "tier2Source", "tier2Flood", "tier2Zone", "tier2ConsPoolFt", "tier2DeadPoolFt", "plan_all_tiers", "flood_all_tiers", "flood_all_tiers_incl_nwps", "priorOperatorPlanText"]
with open(f"{DOCS_DATA}/plan_flood_evidence.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore"); w.writeheader(); [w.writerow(r) for r in rows]

core = [r for r in rows if r["bindingStatus"] in ("VERIFIED", "VERIFIED_CORROBORATED")]
def cnt(rs, f): return sum(1 for r in rs if f(r))
def summ(rs):
    n = len(rs)
    return {"lakes": n, "verifiedMatch": cnt(rs, lambda r: T(r["verifiedMatch"])), "guide": cnt(rs, lambda r: T(r["guide"])), "guideTopConSeasonal": cnt(rs, lambda r: T(r["guideTopConSeasonal"])),
            "regSchedule": cnt(rs, lambda r: T(r["regSchedule"])), "zone": cnt(rs, lambda r: T(r["zone"])), "flood": cnt(rs, lambda r: T(r["flood"])),
            "planStrict": cnt(rs, lambda r: r["planStrict"]), "planInclusive": cnt(rs, lambda r: r["planInclusive"]), "floodStrict": cnt(rs, lambda r: r["floodStrict"]),
            "tier2FloodTWDB": cnt(rs, lambda r: r["tier2Flood"] is True), "tier2FloodNwpsNormalOnly": cnt(rs, lambda r: r["tier2Flood"] == "nwps-normal-only"),
            "flood_all_tiers": cnt(rs, lambda r: r["flood_all_tiers"]), "flood_all_tiers_incl_nwps": cnt(rs, lambda r: r["flood_all_tiers_incl_nwps"]), "plan_all_tiers": cnt(rs, lambda r: r["plan_all_tiers"]),
            "priorTextAny": cnt(rs, lambda r: bool(r["priorOperatorPlanText"])),
            "matchTierStrong": cnt(rs, lambda r: r["matchTier"] == "strong"), "matchTierWeak": cnt(rs, lambda r: r["matchTier"] == "weak"),
            "seasonalFlood": cnt(rs, lambda r: T(r["floodSeasonal"]) and r["floodStrict"]),
            "swingGE2ft": cnt(rs, lambda r: r["swingFt"] != "" and float(r["swingFt"]) >= 2), "swingGE5ft": cnt(rs, lambda r: r["swingFt"] != "" and float(r["swingFt"]) >= 5), "swingGE10ft": cnt(rs, lambda r: r["swingFt"] != "" and float(r["swingFt"]) >= 10)}
S = {"core": summ(core), "coreAndFlagged": summ(rows),
     "byProvider": {p: summ([r for r in core if r["provider"] == p]) for p in sorted({r["provider"] for r in core})}}
json.dump(S, open(f"{DOCS_DATA}/plan_summary.json", "w"), indent=1)
print(json.dumps({k: S[k] for k in ("core", "coreAndFlagged")}, indent=1))
