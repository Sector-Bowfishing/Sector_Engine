"""Wave-2 assembly: cumulative per-lake binding table (verified_bindings_v2.csv) and binding2_summary.json.
Layers (each reported separately so nothing is hidden):
  w1      : wave-1 result (258 core / 57 flagged / 32 stage-only), re-derived here for reproduction
  L1      : binding-review-v1 UNCHANGED (+ wave-1 probe-selection bug fix + new candidates from binding2 scouts / USGS scan)
  L2      : + v1.1 rule extensions R1b, R2b, R4b, R5b, RGL (and documented-offset / gage-height+alt_va derived candidates capped at FLAG)
  L3      : + v1.1-R7h history-envelope promotion FLAG -> core (series' own >=5y history reaches directory full pool within +-8 ft at p99)
"""
import csv, json, collections, os, sys
from common2 import *
import verify as V
import verify11 as V11
import verify2 as W2
import history2 as H
import envelope_promote as EP
from providers import year_completeness, usgs_dv_history

RANK = {"VERIFIED": 0, "VERIFIED_CORROBORATED": 1, "VERIFIED_FLAG": 1, "STAGE_ONLY": 2}
VER = ("VERIFIED", "VERIFIED_FLAG", "VERIFIED_CORROBORATED")
F0 = {k: 0 for k in ("R1b", "R2b", "R4b", "R5b", "RGL", "R8b", "R2c", "R8c", "RI", "R1c", "R2d")}
F1 = {k: 1 for k in F0}


def choose(res, lakes):
    byl = collections.defaultdict(list)
    for x in res:
        byl[x["lakeId"]].append(x)
    out = {}
    for lid, xs in byl.items():
        ok = [x for x in xs if x["status"] in RANK]
        if not ok:
            out[lid] = (None, xs); continue
        ok.sort(key=lambda x: (RANK[x["status"]], 1 if V.ORIGIN.get(x["prov"]) == "relay" else 0, 0 if x["capability"] == "DIRECT_OPERATOR_POOL" else 1, -float(x["matchScore"])))
        b = ok[0]
        agree = set()
        for y in xs:
            if y["status"] in VER and y["family"] == "elev" and b["family"] == "elev" and y is not b:
                oy, ob = V.ORIGIN.get(y["prov"]), V.ORIGIN.get(b["prov"])
                if oy and ob and oy != ob and "relay" not in (oy, ob):
                    gs = [abs(float(y[k]) - float(b[k])) for k in ("medFt", "lastFt") if y[k] not in (None, "") and b[k] not in (None, "")]
                    if gs and min(gs) <= 2.0:
                        agree.add(oy)
        st = b["status"]
        if st == "VERIFIED_FLAG" and agree:
            st = "VERIFIED_CORROBORATED"
        out[lid] = (dict(b, final=st, agree=",".join(sorted(agree))), xs)
    return out


def hist_for(lakeid, b, xs, lakes):
    """best history among the chosen binding and other right-lake candidates (live or history-only) whose level agrees within 3 ft"""
    fam = b["family"]
    cands = [b] + [x for x in xs if x is not b and x["status"] in VER + ("HISTORY_ONLY", "PENDING_CORROBORATION", "PENDING_NO_FULLPOOL")]
    best = (None, None, dict(completeYears=0, firstYear=None, lastDay=None))
    for x in cands:
        if fam == "elev" and x["family"] == "elev" and x is not b:
            gs = [abs(float(x[k]) - float(b[k])) for k in ("medFt", "lastFt") if x[k] not in (None, "") and b[k] not in (None, "")]
            if gs and min(gs) > 3.0:
                continue
        hp = W2_HIST.get((x["lakeId"], x["prov"], x["station"], x["series"]))
        label, d, c = H.best_history(lakeid, x["prov"], x["station"], x["loc"], x["series"], hp)
        off = next((r.get("offsetFt") for r in W2_ROWS if r["lakeId"] == x["lakeId"] and r["prov"] == x["prov"] and r["station"] == x["station"] and r["series"] == x["series"] and r.get("offsetFt") is not None), None)
        if d is not None and off is not None and x["family"] == "elev":
            d = {k: v + float(off) for k, v in d.items()}      # documented stage offset applied to the history leg as well
        if d is None and x["prov"] == "usgs-d":
            alt = next((r.get("altVa") for r in W2_ROWS if r["lakeId"] == x["lakeId"] and r["station"] == x["station"] and r.get("altVa")), None)
            try:
                dd = usgs_dv_history(x["station"], "00065") if alt else None
            except Exception:
                dd = None
            if dd:
                d = {k: v + float(alt) for k, v in dd.items()}; label = f"usgs:{x['station']}:00065+alt:dv"; c = year_completeness(d)
        if d is None and x["prov"] == "usgs" and x["status"] in VER + ("HISTORY_ONLY",) and x["family"] == "elev" and not str(x["series"]).startswith("00065"):
            try:
                dd = usgs_dv_history(x["station"], x["series"])
            except Exception:
                dd = None
            if not dd and x is b:
                try:
                    dd = H.usgs_iv_history(x["station"], x["series"])
                    label = f"usgsiv:{x['station']}:{x['series']}"
                except Exception:
                    dd = None
            if dd:
                d, label = dd, label if label and label.startswith("usgsiv") else f"usgs:{x['station']}:{x['series']}:dv"; c = year_completeness(dd)
        if d is not None and c["completeYears"] > best[2]["completeYears"]:
            best = (label, d, c)
    return best


W2_HIST = {}
W2_ROWS = []


def main():
    global W2_HIST, W2_ROWS
    res0, lakes, rows, cands = W2.run(F0)
    res1, _, _, _ = W2.run(F1)
    W2_ROWS = rows
    W2_HIST = {(r["lakeId"], r["prov"], r["station"], r["series"]): r["histPath"] for r in rows if r.get("histPath")}
    ch0, ch1 = choose(res0, lakes), choose(res1, lakes)
    w1 = {r["lakeId"]: r for r in csv.DictReader(open(f"{BIND}/verified.csv"))}
    nid = {r["lakeId"]: r for r in csv.DictReader(open(f"{BIND}/nid_links.csv"))}
    out = []
    for l in load_directory():
        lid = l["id"]
        w = w1[lid]
        b1, xs1 = ch1.get(lid, (None, []))
        b0, xs0 = ch0.get(lid, (None, []))
        l1final = b1["final"] if b1 else "NONE"
        l0final = b0["final"] if b0 else "NONE"
        # conservative choice: if the lake is bound under the unchanged v1 rules (same or better status class), report THAT binding
        if b0 is not None and b1 is not None and RANK[b0["final"]] <= RANK[b1["final"]]:
            same_src = (b0["prov"], b0["station"]) == (b1["prov"], b1["station"])
            gaps = [abs(float(b0[k]) - float(b1[k])) for k in ("medFt", "lastFt") if b0[k] not in (None, "") and b1[k] not in (None, "")]
            if same_src or (gaps and min(gaps) <= 2.0) or b0["family"] != b1["family"]:
                b1, xs1 = b0, xs0
            else:
                l0final = "FALSE_POSITIVE_V1"
            # the v1 binding contradicts a v1.1-valid source by more than 2 ft (Columbus Lake: USGS lock-and-dam reading 13.5 ft below the CWMS pool): keep the v1.1 one
        rec = dict(lakeId=lid, name=l["name"], state=l["state"], operator=l["operatorName"], hasDam=l["hasDam"], fullPoolFt=l["fullPoolFt"], poolBasis=l["poolBasis"],
                   w1Status=w["bindingStatus"], layer0=l0final, layer1=l1final)
        if b1 is None:
            rec.update(bindingStatus="NONE", capability="none", reason=w["reason"], wave="")
            out.append(rec); continue
        label, d, c = hist_for(lid, b1, xs1, lakes)
        cy = c["completeYears"]
        plan = w["operatorPlan"] if (w["provider"] == b1["prov"] and w["station"] == b1["station"]) else ""
        n = nid.get(lid, {})
        same = w["bindingStatus"] in ("VERIFIED", "VERIFIED_CORROBORATED", "VERIFIED_FLAG")
        if same:
            wave = "w1"
        elif b0 and b0["final"] in RANK and RANK.get(b0["final"], 9) <= 1:
            wave = "w2-v1"
        elif w["bindingStatus"] == "STAGE_ONLY" and b1["final"] in VER and not b1["v11"]:
            wave = "w2-v1"
        else:
            wave = "w2-v1.1"
        # envelope promotion (R7h)
        env = None; final = b1["final"]
        if final == "VERIFIED_FLAG" and d and l["fullPoolFt"] is not None and b1["family"] == "elev":
            env = EP.envelope(d, float(l["fullPoolFt"]))
            if env and -8 <= env["d99"] <= 8:
                final = "VERIFIED_ENVELOPE"
        rec.update(bindingStatus=final, capability=b1["capability"], provider=b1["prov"], station=b1["station"], loc=b1["loc"], series=b1["series"], family=b1["family"], stationName=b1["stationName"],
                   distM=b1["distM"], nameSim=b1["nameSim"], lastObs=b1["lastObs"], ageH=b1["ageH"], medFt=b1["medFt"], deltaFullPoolFt=b1["deltaFullPoolFt"], corroboratedBy=b1["agree"],
                   checks=f"R1,R2,R3,R4,R5,R6,R8,R7={b1['R7_level']}" + (f";v1.1:{b1['v11']}" if b1["v11"] else "") + (";R7h" if final == "VERIFIED_ENVELOPE" else ""),
                   histSeries=label or "", firstYear=c.get("firstYear") or "", lastDay=c.get("lastDay") or "", completeYears=cy,
                   historyClass=("SUFFICIENT" if cy >= 5 else "LIMITED" if cy >= 2 else "INSUFFICIENT" if label else "NONE"), operatorPlan=plan,
                   nidId=(n.get("nidId", "") if n.get("nidScore") and float(n["nidScore"]) >= 70 else ""), reason="", wave=wave, envelopeD99=(env or {}).get("d99", ""))
        out.append(rec)
    out = sibling_pass(out, lakes)
    json.dump(out, open(f"{B2}/assembled_v2.json", "w"))
    return out


def sibling_pass(out, lakes):
    """v1.1-SIB: one physical lake split across directory states (same name, polygons within 3 km, or both without polygon and in the Great Lakes class) inherits the sibling's binding."""
    from match import load_polys, to_planar
    polys = load_polys(); byid = {r["lakeId"]: r for r in out}
    ldir = {l["id"]: l for l in load_directory()}
    BOUND = ("VERIFIED", "VERIFIED_CORROBORATED", "VERIFIED_FLAG", "VERIFIED_ENVELOPE")
    byname = collections.defaultdict(list)
    for r in out:
        byname[r["name"]].append(r)
    for r in out:
        if r["bindingStatus"] in BOUND:
            continue
        sibs = [s for s in byname[r["name"]] if s is not r and s["state"] != r["state"] and s["bindingStatus"] in BOUND]
        for s in sibs:
            pa, pb = polys.get(r["lakeId"]), polys.get(s["lakeId"])
            near = False
            if pa is not None and pb is not None:
                near = to_planar(pa, ldir[r["lakeId"]]["lat"]).distance(to_planar(pb, ldir[r["lakeId"]]["lat"])) < 3000
            if near:
                keep = {k: r[k] for k in ("lakeId", "name", "state", "operator", "hasDam", "fullPoolFt", "poolBasis", "w1Status", "layer0", "layer1")}
                r.clear(); r.update(s); r.update(keep)
                r["wave"] = "w2-v1.1"; r["checks"] = (s["checks"] + ";v1.1:SIB(" + s["lakeId"] + ")"); r["reason"] = ""
                r["layer1"] = r["bindingStatus"]
                break
    return out


def ladder(p):
    return 0 if p < 5 else 2 if p < 10 else 3 if p < 25 else 5 if p < 50 else 7 if p < 75 else 9 if p < 90 else 10


def summarize(out):
    N = len(out)
    def n(f): return sum(1 for r in out if f(r))
    core_w1 = n(lambda r: r["w1Status"] in ("VERIFIED", "VERIFIED_CORROBORATED"))
    S = dict(criteriaVersion="binding-review-v1 (+v1.1 extensions labelled)", lakes=N)
    S["wave1"] = dict(core=core_w1, flagged=n(lambda r: r["w1Status"] == "VERIFIED_FLAG"), stageOnly=n(lambda r: r["w1Status"] == "STAGE_ONLY"), none=n(lambda r: r["w1Status"] == "NONE"))
    cnt = lambda key: collections.Counter(r[key] for r in out)
    S["layers"] = {}
    for key, nm in (("layer0", "L1_v1_rules"), ("layer1", "L2_v1.1_rules")):
        c = cnt(key)
        core = c["VERIFIED"] + c["VERIFIED_CORROBORATED"]
        S["layers"][nm] = dict(core=core, flagged=c["VERIFIED_FLAG"], stageOnly=c["STAGE_ONLY"], none=c["NONE"], pctCore=round(100 * core / N, 1), pctCorePlusFlag=round(100 * (core + c["VERIFIED_FLAG"]) / N, 1))
    c = collections.Counter(r["bindingStatus"] for r in out)
    core = c["VERIFIED"] + c["VERIFIED_CORROBORATED"] + c["VERIFIED_ENVELOPE"]
    S["layers"]["L3_v1.1_plus_R7h"] = dict(core=core, flagged=c["VERIFIED_FLAG"], stageOnly=c["STAGE_ONLY"], none=c["NONE"], pctCore=round(100 * core / N, 1), pctCorePlusFlag=round(100 * (core + c["VERIFIED_FLAG"]) / N, 1))
    for k, v in S["layers"].items():
        v["ladderPointsCore"] = ladder(v["pctCore"]); v["ladderPointsCorePlusFlag"] = ladder(v["pctCorePlusFlag"])
    bound = [r for r in out if r["bindingStatus"] in ("VERIFIED", "VERIFIED_CORROBORATED", "VERIFIED_FLAG", "VERIFIED_ENVELOPE")]
    S["byStatus"] = dict(c)
    S["byWave"] = dict(collections.Counter(r["wave"] for r in bound))
    S["byProvider"] = dict(collections.Counter(r["provider"] for r in bound))
    S["newByProvider"] = dict(collections.Counter(r["provider"] for r in bound if r["wave"] != "w1"))
    S["newByState"] = dict(collections.Counter(r["state"] for r in bound if r["wave"] != "w1"))
    S["historyClassBound"] = dict(collections.Counter(r["historyClass"] for r in bound))
    S["capabilityBound"] = dict(collections.Counter(r["capability"] for r in bound))
    S["noBindingReasons"] = dict(collections.Counter(r["reason"] for r in out if r["bindingStatus"] == "NONE"))
    return S


def write(out, S):
    keys = ["lakeId", "provider", "station", "series", "capability", "bindingStatus", "firstYear", "completeYears", "historyClass", "checks", "corroboratedBy", "nidId", "wave"]
    hdr = ["lake_id", "provider", "station", "series_or_param", "capability_class", "binding_status", "period_of_record_start_year", "complete_years", "history_class", "checks_passed", "corroborated_by", "nid_id", "wave"]
    with open(f"{DOCS}/data/verified_bindings_v2.csv", "w", newline="") as fh:
        w = csv.writer(fh); w.writerow(hdr)
        for r in out:
            if r["bindingStatus"] in ("VERIFIED", "VERIFIED_CORROBORATED", "VERIFIED_FLAG", "VERIFIED_ENVELOPE", "STAGE_ONLY"):
                w.writerow([r.get(k, "") for k in keys])
    json.dump(S, open(f"{DOCS}/data/binding2_summary.json", "w"), indent=1)
    allk = ["lakeId", "name", "state", "operator", "hasDam", "fullPoolFt", "poolBasis", "w1Status", "layer0", "layer1", "bindingStatus", "capability", "provider", "station", "loc", "series", "family", "stationName", "distM", "nameSim", "lastObs", "ageH", "medFt",
            "deltaFullPoolFt", "corroboratedBy", "checks", "histSeries", "firstYear", "lastDay", "completeYears", "historyClass", "operatorPlan", "nidId", "reason", "wave", "envelopeD99"]
    with open(f"{B2}/verified_v2_full.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=allk); w.writeheader(); [w.writerow({k: r.get(k, "") for k in allk}) for r in out]


if __name__ == "__main__":
    out = main()
    S = summarize(out)
    write(out, S)
    print(json.dumps({k: S[k] for k in ("wave1", "layers", "byStatus", "byWave", "newByProvider", "historyClassBound", "noBindingReasons")}, indent=1))
