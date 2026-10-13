"""Ingest binding2 candidates (cand/*.jsonl in the SPEC format) into the wave-1 review machinery (binding-review-v1, optional v1.1 extensions in verify11.py).
Each candidate becomes a candidates_all-style row + a probe entry, then verify11.run() applies R1-R9 unchanged. Derived stage candidates (00065 + alt_va) are capped at VERIFIED_FLAG."""
import csv, glob, json, re, collections, math, sys
from common2 import *
import verify as V
import verify11 as V11
from match import load_polys, to_planar, best_sim
from shapely.geometry import Point

TRAP_NAME = re.compile(r"\b(below|blw|tailwater|tailrace|downstream|dnstrm|bl)\b", re.I)
CAP_OPERATOR = {"usace", "usbr", "tva"}


def _datum(v):
    v = (v or "").strip()
    if not v or v.lower() in ("unknown", "local"):
        return ""
    if v.lower().startswith("unknown") and not re.search(r"NGVD|NAVD|MSL ?1912", v):
        return ""
    return v


def geo_score(d, haspoly):
    g = 1.0 if d <= 150 else .9 if d <= 600 else .75 if d <= 1500 else .5 if d <= 3000 else .25 if d <= 6000 else .1
    return g * (1.0 if haspoly else 0.6)


def build(paths=None):
    lakes = {l["id"]: l for l in load_directory()}
    polys = load_polys()
    cands = []
    for p in (paths or sorted(glob.glob(f"{B2}/cand/*.jsonl"))):
        for ln in open(p):
            ln = ln.strip()
            if ln:
                c = json.loads(ln); c["_file"] = os.path.basename(p); cands.append(c)
    rows, probes = [], {}
    for c in cands:
        l = lakes.get(c["lakeId"])
        if not l or c.get("medFt") is None or c.get("lat") is None:
            continue
        prov = "usgs" if c["prov"] in ("usgs2", "usgs") else c["prov"]
        if prov == "usgs" and c.get("derived"):
            prov = "usgs-d"        # derived (00065 + alt_va) series keep their own probe key so they never overwrite a real elevation probe
        V.ORIGIN[prov] = "relay" if (c.get("relay") or c["prov"] == "cwms-lre") else (c.get("origin") or prov)
        if prov in ("usgs", "usgs-d"):
            V.ORIGIN[prov] = "relay" if c.get("relay") else "usgs"
        haspoly = c["lakeId"] in polys
        pj = V11.proj_xy
        if haspoly:
            d = to_planar(polys[c["lakeId"]], l["lat"]).distance(Point(*pj(c["lon"], c["lat"], l["lat"])))
        else:
            d = haversine_m(l["lat"], l["lon"], c["lat"], c["lon"])
        if c.get("lat_note"):
            d = 0.0        # provider publishes whole-lake data without coordinates (Duke Lake View): identity by lake name, position = directory lake point
        sim = best_sim(l, c["stationName"] or "")
        reasons = [f"dist={int(d)}m", f"nameSim={sim}"]
        pts = 40 * geo_score(d, haspoly) + 35 * min(1.0, sim * 1.3) + 8
        if TRAP_NAME.search(c["stationName"] or "") and not re.search(r"\b(lake|res|reservoir)\b[^,]*\bnear\b", c["stationName"] or "", re.I):
            pts -= 30; reasons.append("TRAP:below/tailwater-in-name")
        nm_ = c["stationName"] or ""
        river = re.search(r"\b(river|creek|rv|cr|ck|brook|canal|fork|run|bayou|pass|outlet|diversion|inlet)\b", nm_, re.I)
        lakeword = re.search(r"\b(lake|lk|res|reservoir|pool|pond|dam)\b", nm_, re.I)
        if prov in ("usgs", "usgs-d") and (c.get("stype") or "ST") != "LK" and river and not lakeword:
            pts -= 15; reasons.append("TRAP:river-gauge-name")
        river2 = re.search(r"\b(canyon|wash|draw|above|abv|below|spring|springs|slough|ditch|drain)\b", nm_, re.I)
        if c.get("derived") and prov == "usgs-d" and (c.get("stype") != "LK" and (river or river2 or not lakeword)):
            pts -= 15; reasons.append("TRAP:derived-from-non-lake-site")
        st = c.get("state")
        states = set(l.get("states") or [l["state"]])
        if st and st not in states:
            pts -= 25; reasons.append(f"state-mismatch({st})")
        pts = max(0, min(100, pts))
        fam = c.get("family", "elev")
        if fam == "stage" and c.get("offsetToNGVD29Ft") is not None and c.get("offsetSource"):
            c = dict(c, medFt=round(c["medFt"] + c["offsetToNGVD29Ft"], 3), lastFt=round(c["lastFt"] + c["offsetToNGVD29Ft"], 3), derived=True, vdatum="NGVD29")
            fam = "elev"
        key = f"{prov}|{c['station']}"
        step = c.get("step") or ("1Hour" if (c.get("n30") or 0) > 40 else "1Day")
        probes[key] = dict(prov=prov, station=c["station"], name=c["stationName"], live=c.get("ageH") is not None and c["n30"] > 0, mode=("iv" if step != "1Day" else "dv"), step=step,
                           stats=dict(n=c["n30"], last_t=c["lastObs"], age_h=c["ageH"], last_ft=c["lastFt"], med_ft=c["medFt"]), family=fam, param=c["series"], series=c["series"],
                           vdi=bool(_datum(c.get("vdatum"))), unit="ft")
        row = dict(lakeId=l["id"], lakeName=l["name"], lakeState=l["state"], prov=prov, sid=f"{prov}:{c['station']}:{c['series']}", station=c["station"], series=c["series"], stationName=c["stationName"],
                   stype=c.get("stype") or "", family=fam, unit="ft", datum=_datum(c.get("vdatum")), begin="", end="", count=c.get("n30"), step=step,
                   lat=c["lat"], lon=c["lon"], distM=int(d), nameSim=sim, score=round(pts, 1), reasons=";".join(reasons), extra={"loc": "", "state": st, "src": c["_file"]}, alts=[], capOverride=("DIRECT_OPERATOR_POOL" if (c.get("origin") in CAP_OPERATOR or c.get("operatorPool")) else "DIRECT_LAKE_GAUGE"),
                   derived=bool(c.get("derived")), offsetFt=c.get("offsetToNGVD29Ft"), fullPoolHint=c.get("fullPoolHint"), altVa=c.get("altVa"), lakeWide=bool(c.get("lakeWide") or c["prov"] == "cwms-lre"), greatLakesStation=bool(c["prov"] == "coops" and (c.get("vdatum") or "").startswith("IGLD")), histPath=c.get("histPath"), apiUrl=c.get("apiUrl"), notes=c.get("notes"), cfile=c["_file"])
        rows.append(row)
    return rows, probes, cands


def run(flags, base_probes=None, with_wave1=True):
    rows, probes, cands = build()
    P = dict(json.load(open(f"{B2}/probe_results_v2.json")) if base_probes is None else base_probes)
    P.update(probes)
    from probe import load_cands
    base = load_cands() if with_wave1 else []
    # new rows must not duplicate an existing wave-1 candidate of the same probe key + lake
    seen = {(b["lakeId"], V.probe_key(dict(b, extra=b["extra"] if isinstance(b["extra"], dict) else json.loads(b["extra"])))) for b in base}
    new = [r for r in rows if (r["lakeId"], V.probe_key(r)) not in seen]
    res, lakes = V11.run(flags, cand_rows=base + new, probes=P, extra_claim_rows=[dict(r, score=r["score"]) for r in new])
    # derived stage candidates are capped at FLAG
    derived = {(r["lakeId"], r["prov"], r["station"], r["series"]) for r in rows if r["derived"]}
    for x in res:
        if (x["lakeId"], x["prov"], x["station"], x["series"]) in derived and x["status"] in ("VERIFIED", "VERIFIED_CORROBORATED"):
            x["status"] = "VERIFIED_FLAG"; x["v11"] = (x["v11"] + ",S-derived").strip(",")
    return res, lakes, rows, cands


if __name__ == "__main__":
    flags = {k: 1 for k in ("R1b", "R2b", "R4b", "R5b", "RGL", "R8b", "R2c", "R8c", "RI", "R1c", "R2d")}
    res, lakes, rows, cands = run(flags)
    b = V11.best_per_lake(res)
    print("new candidate rows", len(rows), collections.Counter(r["cfile"] for r in rows))
    print(collections.Counter(v["status"] for v in b.values()))
