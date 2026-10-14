"""CWMS storage-consistency frame check: the CWMS `Stor` series is computed from the `Elev` series through the project's `Elev;Stor` rating (native datum stated on the rating). If the Elev
series (A2W/CWMS tag LOCAL or blank) sits in the rating's frame, rating(Elev(t) + d) reproduces Stor(t) with d ~ 0. Same rule as the RISE storage fit:
|best d| <= 0.10 ft and relative RMS <= 0.005. Controls: lakes whose LOCAL == NGVD29 is already proven by a paired USGS series (Clinton, Kanopolis...). Output docs/brains/depth/data/cwms_stor_link.json"""
import json, os, sys, urllib.parse
import numpy as np
import pandas as pd
from datum_pair_common import cwms_series, get_json, CWMS

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "../../docs/brains/depth/data/cwms_stor_link.json")
PAIRS = json.load(open(os.path.expanduser("~/Desktop/Development/Sector_Research_Data/depth-brain/datum2/cwms_pairs.json")))
LAKES = ["Clinton Lake|KS", "Kanopolis Lake|KS", "Melvern Lake|KS", "Wilson Lake|KS", "Rathbun Lake|IA", "Longview Lake|MO", "Pomme de Terre Lake|MO", "Smithville Lake|MO", "Perry Lake|KS", "Tuttle Creek Lake|KS", "Milford Lake|KS", "Pomona Lake|KS"]


def specs(office):
    out, page = [], None
    for _ in range(30):
        p = {"office": office, "rating-id-mask": "*Elev;Stor*", "page-size": 500}
        if page:
            p["page"] = page
        r = get_json(f"{CWMS}/ratings/spec", p, headers={"Accept": "application/json;version=2"}, retries=1)
        d = (r or {}).get("data")
        if not d or "specs" not in d:
            break
        out += [s["rating-id"] for s in d["specs"]]
        page = d.get("next-page")
        if not page:
            break
    return out


def rating(office, rid):
    r = get_json(f"{CWMS}/ratings/{urllib.parse.quote(rid, safe='')}", {"office": office}, headers={"Accept": "application/json;version=2"}, retries=1)
    d = (r or {}).get("data")
    sr = d["simple-rating"]; sr = sr if isinstance(sr, list) else [sr]
    b = max(sr, key=lambda x: x["effective-date"])
    pts = b["rating-points"]["point"]
    e = np.array([float(p["ind"]) for p in pts]); s = np.array([float(p["dep"]) for p in pts]); o = np.argsort(e)
    return e[o], s[o], b["effective-date"][:10], (b.get("vertical-datum-info") or {}).get("native-datum"), b.get("units-id")


def main():
    res, cache = {}, {}
    end = pd.Timestamp.now(tz="UTC").normalize(); begin = end - pd.Timedelta(days=365)
    for lid in LAKES:
        v = PAIRS.get(lid); s = (v or {}).get("series") or {}
        off, tsid = s.get("cwmsOffice"), s.get("tsid") or ""
        loc = tsid.split(".")[0]
        if not off:
            continue
        cache.setdefault(off, specs(off))
        norm = lambda x: "".join(ch for ch in x.lower() if ch.isalnum())
        hits = [i for i in cache[off] if norm(i.split(".Elev")[0].split("-")[0]) == norm(loc.split("-")[0])]
        stor_ts = ".".join([loc] + ["Stor"] + tsid.split(".")[2:])
        if not hits:
            res[lid] = {"error": "no Elev;Stor rating at the series location", "tsid": tsid}; continue
        e, st, eff, vd, units = rating(off, hits[0])
        el, _, _ = cwms_series(off, tsid, begin.strftime("%Y-%m-%dT%H:%M:%SZ"), end.strftime("%Y-%m-%dT%H:%M:%SZ"), unit="ft")
        sv, _, _ = cwms_series(off, stor_ts, begin.strftime("%Y-%m-%dT%H:%M:%SZ"), end.strftime("%Y-%m-%dT%H:%M:%SZ"), unit="ac-ft")
        if el is None or sv is None or not len(el) or not len(sv):
            res[lid] = {"error": "series fetch failed", "tsid": tsid, "storTsid": stor_ts, "rating": hits[0]}; continue
        j = pd.concat([el.rename("e"), sv.rename("s")], axis=1).dropna()
        j = j[(j.e >= e.min() + 0.5) & (j.e <= e.max() - 0.5) & (j.s > 0)]
        if len(j) < 100:
            res[lid] = {"error": f"only {len(j)} joined hours in the rating range", "rating": hits[0]}; continue
        ds = np.arange(-3.0, 3.0001, 0.01); S = j.s.values
        rms = [float(np.sqrt(np.mean((np.interp(j.e.values + d, e, st) - S) ** 2))) for d in ds]
        k = int(np.argmin(rms))
        r = {"rating": hits[0], "ratingEffective": eff, "ratingNativeDatum": vd, "ratingUnits": units, "tsid": tsid, "storTsid": stor_ts, "n": int(len(j)), "bestOffsetFt": round(float(ds[k]), 2),
             "relRmsAtBest": round(rms[k] / float(np.mean(S)), 5), "relRmsAtZero": round(rms[int(np.argmin(np.abs(ds)))] / float(np.mean(S)), 5)}
        r["passes"] = abs(r["bestOffsetFt"]) <= 0.10 and r["relRmsAtBest"] <= 0.005
        res[lid] = r
        print(lid, {x: r[x] for x in ("ratingNativeDatum", "n", "bestOffsetFt", "relRmsAtBest", "passes")}, flush=True)
    json.dump({"schema": "depth-cwms-stor-link-v1", "generatedAt": pd.Timestamp.now(tz="UTC").strftime("%Y-%m-%dT%H:%MZ"), "results": res}, open(OUT, "w"), indent=1)


main()
