"""Phase 5: choose per-lake binding (live + history), compute class/history summary, write verified.csv + docs summary files."""
import csv, collections, json, os, re
from common import *

DOCS = "/Users/mcather/Desktop/Development/Sector_Engine/docs/research/lake-brain/data"
os.makedirs(DOCS, exist_ok=True)
RANK = {"VERIFIED": 0, "VERIFIED_CORROBORATED": 1, "VERIFIED_FLAG": 1, "STAGE_ONLY": 2}
COUNT_STRICT = ("VERIFIED", "VERIFIED_CORROBORATED", "VERIFIED_FLAG")   # strict = core + flagged; core excludes uncorroborated flagged


def f(x):
    try:
        return float(x)
    except Exception:
        return None


def main():
    lakes = load_directory()
    rows = list(csv.DictReader(open(f"{BIND}/candidates.csv")))
    hist = json.load(open(f"{BIND}/history_results.json"))
    probes = json.load(open(f"{BIND}/probe_results.json"))
    nid = {r["lakeId"]: r for r in csv.DictReader(open(f"{BIND}/nid_links.csv"))}
    guides = json.load(open(f"{BIND}/cwms_guides.json")) if os.path.exists(f"{BIND}/cwms_guides.json") else {}
    byl = collections.defaultdict(list)
    for r in rows:
        byl[r["lakeId"]].append(r)
    site_hist = {}
    for k, v in hist.items():
        p = k.split("|")
        if v.get("best") and (p[1], p[2], p[3]) not in site_hist:
            site_hist[(p[1], p[2], p[3])] = v["best"]
    out = []
    for l in lakes:
        xs = [x for x in byl.get(l["id"], []) if x["status"] in RANK]
        rec = dict(lakeId=l["id"], name=l["name"], state=l["state"], operator=l["operatorName"], hasDam=l["hasDam"], fullPoolFt=l["fullPoolFt"], poolBasis=l["poolBasis"])
        if not xs:
            pend = [x for x in byl.get(l["id"], []) if x["status"].startswith("PENDING")]
            conf = [x for x in byl.get(l["id"], []) if x["status"] == "CONFLICT"]
            rec.update(bindingStatus="NONE", capability="none", reason=("independent-sources-disagree" if conf else "pending:" + pend[0]["status"] if pend else ("candidates-rejected" if byl.get(l["id"]) else "no-candidate")))
            out.append(rec); continue
        xs.sort(key=lambda x: (RANK[x["status"]], 0 if x["capability"] == "DIRECT_OPERATOR_POOL" else 1, -float(x["matchScore"])))
        b = xs[0]
        # best history among all passing candidates (levels must agree with the live binding within 3 ft; stage series skip the level test)
        bh = None
        for x in xs:
            h = hist.get(f"{x['lakeId']}|{x['prov']}|{x['station']}|{x['loc']}", {}).get("best") or site_hist.get((x["prov"], x["station"], x["loc"]))
            if not h:
                continue
            if x["family"] == "elev" and b["family"] == "elev" and f(x["medFt"]) is not None and f(b["medFt"]) is not None and abs(f(x["medFt"]) - f(b["medFt"])) > 3.0:
                continue
            if bh is None or h["completeYears"] > bh[0]["completeYears"]:
                bh = (h, x)
        h, hx = bh if bh else ({}, None)
        ORIG = {"usgs": "usgs", "cwms": "usace", "a2w": "usace", "rise": "usbr", "tva": "tva", "coops": "noaa"}
        agree = set()
        for y in byl[l["id"]]:
            if y["status"] in ("VERIFIED", "VERIFIED_FLAG", "VERIFIED_CORROBORATED") and y["prov"] in ORIG and b["prov"] in ORIG and ORIG[y["prov"]] != ORIG[b["prov"]] and y["family"] == "elev" and b["family"] == "elev":
                gs = [abs(float(y[k]) - float(b[k])) for k in ("medFt", "lastFt") if f(y[k]) is not None and f(b[k]) is not None]
                if gs and min(gs) <= 2.0:
                    agree.add(ORIG[y["prov"]])
        n = nid.get(l["id"], {})
        status = b["status"]
        if status == "VERIFIED_FLAG" and agree:
            status = "VERIFIED_CORROBORATED"      # flagged level class but an independent origin agrees within 2 ft
        pr = probes.get(b["probeKey"], {})
        plan = []
        if b["prov"] == "a2w" and pr.get("levels"):
            plan = [k.split("|")[0] for k, v in pr["levels"].items() if v is not None and any(t in k for t in ("Top of Normal", "Top of Flood", "Bottom of Flood", "Bottom of Normal", "Rule Curve", "Top of Conservation"))]
        if b["prov"] == "tva":
            plan = ["TVA operating guide (guide curve + operating zone)"]
        if b["prov"] == "cwms" and guides.get(f"{b['station']}|{b['loc'].split('-')[0]}"):
            plan = ["CWMS " + p for p in guides[f"{b['station']}|{b['loc'].split('-')[0]}"][:4]]
        cy = h.get("completeYears", 0)
        rec.update(bindingStatus=status, capability=b["capability"], provider=b["prov"], station=b["station"], loc=b["loc"], series=b["series"], family=b["family"],
                   stationName=b["stationName"], distM=b["distM"], nameSim=b["nameSim"], lastObs=b["lastObs"], ageH=b["ageH"], medFt=b["medFt"], deltaFullPoolFt=b["deltaFullPoolFt"],
                   corroboratedBy=",".join(sorted(agree)), checks="R1,R2,R3,R4,R5,R6,R8,R7=" + b["R7_level"],
                   histSeries=h.get("series", ""), firstYear=h.get("firstYear", ""), lastDay=h.get("lastDay", ""), completeYears=cy, historyClass=("SUFFICIENT" if cy >= 5 else "LIMITED" if cy >= 2 else "INSUFFICIENT" if h else "NONE"),
                   operatorPlan="; ".join(plan), nidId=n.get("nidId", "") if f(n.get("nidScore", 0)) and f(n.get("nidScore")) >= 70 and f(n.get("nidSim") or 0) and f(n.get("nidSim")) >= 0.4 else "", reason="")
        out.append(rec)
    keys = ["lakeId", "name", "state", "operator", "hasDam", "fullPoolFt", "poolBasis", "bindingStatus", "capability", "provider", "station", "loc", "series", "family", "stationName", "distM", "nameSim", "lastObs", "ageH", "medFt", "deltaFullPoolFt", "corroboratedBy", "checks",
            "histSeries", "firstYear", "lastDay", "completeYears", "historyClass", "operatorPlan", "nidId", "reason"]
    with open(f"{BIND}/verified.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=keys); w.writeheader(); [w.writerow({k: r.get(k, "") for k in keys}) for r in out]
    # compact committed csv: only bound lakes
    ck = ["lakeId", "provider", "station", "series", "capability", "bindingStatus", "firstYear", "completeYears", "historyClass", "checks", "corroboratedBy", "nidId"]
    with open(f"{DOCS}/verified_bindings.csv", "w", newline="") as fh:
        w = csv.writer(fh); w.writerow(["lake_id", "provider", "station", "series_or_param", "capability_class", "binding_status", "period_of_record_start_year", "complete_years", "history_class", "checks_passed", "corroborated_by", "nid_id"])
        for r in out:
            if r["bindingStatus"] in RANK:
                w.writerow([r.get(k, "") for k in ck])
    S = summarize(out)
    json.dump(S, open(f"{DOCS}/binding_summary.json", "w"), indent=1)
    print(json.dumps(S, indent=1))


def ladder(p):
    return 0 if p < 5 else 2 if p < 10 else 3 if p < 25 else 5 if p < 50 else 7 if p < 75 else 9 if p < 90 else 10


def summarize(out):
    N = len(out)
    strict = [r for r in out if r["bindingStatus"] in COUNT_STRICT]
    stage = [r for r in out if r["bindingStatus"] == "STAGE_ONLY"]
    core = [r for r in out if r["bindingStatus"] in ("VERIFIED", "VERIFIED_CORROBORATED")]
    flag = [r for r in out if r["bindingStatus"] == "VERIFIED_FLAG"]
    S = dict(criteriaVersion="binding-review-v1", lakes=N, strictVerified=len(strict), stageOnly=len(stage), total=len(strict) + len(stage))
    S["core"] = len(core); S["flagged"] = len(flag); S["pctCore"] = round(100 * len(core) / N, 1)
    S["coreByCapability"] = dict(collections.Counter(r["capability"] for r in core))
    S["flaggedByCapability"] = dict(collections.Counter(r["capability"] for r in flag))
    S["coreHistory"] = dict(collections.Counter(r["historyClass"] for r in core))
    S["flaggedHistory"] = dict(collections.Counter(r["historyClass"] for r in flag))
    S["coreCapabilityByHistory"] = {f"{c}|{h}": n for (c, h), n in collections.Counter((r["capability"], r["historyClass"]) for r in core).items()}
    S["strictCapabilityByHistory"] = {f"{c}|{h}": n for (c, h), n in collections.Counter((r["capability"], r["historyClass"]) for r in strict).items()}
    S["pctStrict"] = round(100 * len(strict) / N, 1); S["pctWithStage"] = round(100 * (len(strict) + len(stage)) / N, 1)
    S["ladderPointsStrict"] = ladder(S["pctStrict"]); S["ladderPointsWithStage"] = ladder(S["pctWithStage"])
    S["byCapability"] = dict(collections.Counter(r["capability"] for r in strict + stage))
    S["byCapabilityStrict"] = dict(collections.Counter(r["capability"] for r in strict))
    S["byProvider"] = dict(collections.Counter(r["provider"] for r in strict + stage))
    S["byStatus"] = dict(collections.Counter(r["bindingStatus"] for r in out))
    S["historyClass"] = dict(collections.Counter(r["historyClass"] for r in strict + stage))
    S["historyClassStrict"] = dict(collections.Counter(r["historyClass"] for r in strict))
    S["capabilityByHistory"] = {f"{c}|{h}": n for (c, h), n in collections.Counter((r["capability"], r["historyClass"]) for r in strict + stage).items()}
    S["strictWith5yHistory"] = sum(1 for r in strict if r["historyClass"] == "SUFFICIENT")
    S["strictWith5yHistoryAndOperatorPlan"] = sum(1 for r in strict if r["historyClass"] == "SUFFICIENT" and r["operatorPlan"])
    S["operatorPlanEvidence"] = sum(1 for r in strict + stage if r["operatorPlan"])
    S["noBindingReasons"] = dict(collections.Counter(r.get("reason", "") for r in out if r["bindingStatus"] == "NONE"))
    hd = [r for r in out if str(r["hasDam"]) == "True"]
    S["hasDamLakes"] = len(hd); S["hasDamVerified"] = sum(1 for r in hd if r["bindingStatus"] in COUNT_STRICT)
    S["nidResolvedStrong"] = sum(1 for r in out if r.get("nidId"))
    S["byOperatorGroup"] = {}
    for r in out:
        g = re.sub(r"\s*\(.*", "", r["operator"] or "none")
        d = S["byOperatorGroup"].setdefault(g, [0, 0]); d[0] += 1; d[1] += 1 if r["bindingStatus"] in COUNT_STRICT else 0
    S["byOperatorGroup"] = {k: v for k, v in sorted(S["byOperatorGroup"].items(), key=lambda kv: -kv[1][0])[:25]}
    return S


if __name__ == "__main__":
    main()
