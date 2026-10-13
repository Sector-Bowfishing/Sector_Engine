#!/usr/bin/env python3
"""Step 3: independent-series pairing (the Hartwell pattern). For each USACE-served lake with a CWMS level series, find USGS NWIS lake/reservoir
water-surface-elevation series (parameters 62614=NGVD29, 62615=NAVD88, 72020=NGVD29, 00062=per-site datum; NEVER 00065) within 3 km of the CWMS
location, pull the overlapping window, compare at the SAME instants (USGS iv vs CWMS values at identical UTC timestamps; both stamped in UTC) and quantify
the offset (usgs - cwms): n, mean, sd, min, max, first/second-half means and per-quarter mean range. Also records the CWMS-vs-NGVD29/NAVD88 expectation.
Read-only. Output: <cache>/usgs_pairs.json  and docs/brains/depth/data/datum_pairings_usgs.csv
Run: venv python -I research/depth/datum_pair_usgs.py [--only 'Lake|ST,...']"""
import csv, datetime as dt, json, math, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from datum_pair_common import *

REPO = os.path.expanduser("~/Desktop/Development/Sector_Engine-depth-adoption")
CAT = os.path.expanduser("~/Desktop/Development/Sector_Research_Data/lake-brain/binding/catalog_usgs_cwms.jsonl")
PARAMS = {"62614": "NGVD29", "72020": "NGVD29", "62615": "NAVD88", "00062": None}
WINDOW_DAYS = 365
MAX_KM = 3.0


def km(a, b):
    R = 6371.0; p1, p2 = math.radians(a[0]), math.radians(b[0]); dl = math.radians(b[1] - a[1]); dp = p2 - p1
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R * math.asin(math.sqrt(h))


def load_catalog():
    rows = []
    for l in open(CAT):
        r = json.loads(l)
        if r["prov"] == "usgs" and r.get("family") == "elev" and r["param"] in PARAMS and r.get("lat") is not None and (r.get("end") or "") >= "2026-06-01":
            rows.append(r)
    return rows


def compare(cw, us, tol_min=3):
    """Same-instant join: for each CWMS timestamp take the USGS iv value at exactly that UTC instant (tolerance tol_min minutes)."""
    cw = cw[~cw.index.duplicated()]; us = us[~us.index.duplicated()]
    cw = cw.copy(); us = us.copy(); cw.index = cw.index.astype("datetime64[ns, UTC]"); us.index = us.index.astype("datetime64[ns, UTC]")
    j = pd.merge_asof(cw.rename("cwms").reset_index().rename(columns={"index": "t"}).sort_values("t"), us.rename("usgs").reset_index().rename(columns={"index": "t"}).sort_values("t"),
                      on="t", direction="nearest", tolerance=pd.Timedelta(minutes=tol_min)).dropna()
    j = j.set_index("t")
    return j


def main(only=None):
    pairs = json.load(open(f"{ROOT}/cwms_pairs.json"))
    cat = load_catalog()
    end = pd.Timestamp.now(tz="UTC").normalize(); begin = end - pd.Timedelta(days=WINDOW_DAYS)
    out = {}
    for lid, v in pairs.items():
        if only and lid not in only:
            continue
        s = v["series"]; loc = v.get("seriesLocation") or {}
        if not s.get("cwmsOffice") or loc.get("lat") is None:
            continue
        pt = (loc["lat"], loc["lon"])
        cands = sorted([(km(pt, (r["lat"], r["lon"])), r) for r in cat], key=lambda x: x[0])
        cands = [(d, r) for d, r in cands if d <= MAX_KM]
        version = s["tsid"].split(".")[-1]
        # TRAP: a CWMS series whose version names USGS (Raw-USGS, USGS-raw, USGS-rev) is the USGS gauge feed itself, so pairing it with that gauge is circular, not independent
        res = {"lake": lid, "cwmsTsid": s["tsid"], "cwmsOffice": s["cwmsOffice"], "candidates": [], "pairs": [], "cwmsVersion": version, "circularIfUsgsGauge": "usgs" in version.lower()}
        for d, r in cands:
            res["candidates"].append({"site": r["station"], "name": r["name"], "param": r["param"], "km": round(d, 2), "step": r["step"], "end": r["end"]})
        if cands:
            cw, meta, curls = cwms_series(s["cwmsOffice"], s["tsid"], begin.strftime("%Y-%m-%dT%H:%M:%SZ"), end.strftime("%Y-%m-%dT%H:%M:%SZ"))
            res["cwmsFetch"] = {"n": 0 if cw is None else int(len(cw)), "verticalDatumInfo": (meta or {}).get("vertical-datum-info"), "interval": (meta or {}).get("interval"), "urls": curls[:3]}
            if cw is not None and len(cw):
                seen = set()
                for d, r in cands:
                    key = (r["station"], r["param"])
                    if key in seen or r["step"] != "iv":
                        continue
                    seen.add(key)
                    us, _, uurls = usgs_series(r["station"], r["param"], begin, end, "iv")
                    if us is None or not len(us):
                        res["pairs"].append({"site": r["station"], "param": r["param"], "error": "no iv data"}); continue
                    j = compare(cw, us)
                    if len(j) < 20:
                        res["pairs"].append({"site": r["station"], "param": r["param"], "n": int(len(j)), "note": "too few same-instant values", "usgsN": int(len(us))}); continue
                    stat = offset_stats(j["usgs"] - j["cwms"])
                    res["pairs"].append({"site": r["station"], "siteName": r["name"], "param": r["param"], "paramDatum": PARAMS[r["param"]], "km": round(d, 2), "stats": stat, "usgsN": int(len(us)),
                                         "usgsUrl": uurls[0] if uurls else None})
        out[lid] = res
        print(lid, [(p.get("site"), p.get("param"), p.get("stats", {}).get("n"), p.get("stats", {}).get("meanFt"), p.get("stats", {}).get("sdFt")) for p in res["pairs"]], flush=True)
    json.dump(out, open(f"{ROOT}/usgs_pairs.json", "w"), indent=1)


if __name__ == "__main__":
    only = None
    if "--only" in sys.argv:
        only = set(sys.argv[sys.argv.index("--only") + 1].split(","))
    main(only)
