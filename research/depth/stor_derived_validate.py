"""Can depth shares be derived from an Elev;Stor rating when no Elev;Area rating exists? area(z) = dS/dz. Validation on lakes that have BOTH ratings: shares from the storage
derivative vs shares from the area rating (the truth for this question). Output docs/brains/depth/data/stor_derived_validation.json. Read-only GETs (cached)."""
import json, os, urllib.parse
import numpy as np
from datum_pair_common import get_json, CWMS
HERE = os.path.dirname(os.path.abspath(__file__))
D = f"{HERE}/../../jobs/depth-brain/depth_brain/data"
cur = json.load(open(f"{D}/stage_area_curves.json"))["lakes"]
cands = {c["lakeId"]: c for c in json.load(open(f"{D}/candidates.json"))["candidates"]}
norm = lambda x: "".join(ch for ch in x.lower() if ch.isalnum())
specs_cache = {}


def specs(office):
    if office in specs_cache:
        return specs_cache[office]
    out, page = [], None
    for _ in range(30):
        p = {"office": office, "rating-id-mask": "*Elev;Stor*", "page-size": 500}
        if page: p["page"] = page
        r = get_json(f"{CWMS}/ratings/spec", p, headers={"Accept": "application/json;version=2"}, retries=1)
        d = (r or {}).get("data")
        if not d or "specs" not in d: break
        out += [s["rating-id"] for s in d["specs"]]
        page = d.get("next-page")
        if not page: break
    specs_cache[office] = out
    return out


def fetch(office, rid):
    r = get_json(f"{CWMS}/ratings/{urllib.parse.quote(rid, safe='')}", {"office": office}, headers={"Accept": "application/json;version=2"}, retries=1)
    d = (r or {}).get("data")
    if not d: return None
    sr = d["simple-rating"]; sr = sr if isinstance(sr, list) else [sr]
    b = max(sr, key=lambda x: x["effective-date"])
    pts = b["rating-points"]["point"]
    e = np.array([float(p["ind"]) for p in pts]); s = np.array([float(p["dep"]) for p in pts]); o = np.argsort(e)
    return e[o], s[o], b["effective-date"][:10], b.get("units-id")


def area_from_storage(e, s):
    """-> (elevation midpoints, area acres) from finite differences; the caller decides whether the step is fine enough."""
    de = np.diff(e); keep = de > 1e-9
    mid = ((e[1:] + e[:-1]) / 2)[keep]; a = (np.diff(s)[keep] / de[keep])
    return mid, a


def shares(zs, az, P, edges=(3.0, 6.0, 10.0)):
    aP = float(np.interp(P, zs, az))
    return {x: (aP - float(np.interp(P - x, zs, az))) / aP for x in edges if P - x >= zs[0]}


def main():
    res = {}
    for lid, v in cur.items():
        if v["matchedBy"] == "tsc-table":
            continue
        c = cands[lid]; off = v["office"]; loc = v["seriesLocation"] or ""
        hits = [i for i in specs(off) if norm(i.split(".Elev")[0].split("-")[0]) == norm((v["ratingId"].split(".Elev")[0]).split("-")[0])]
        if not hits:
            continue
        got = fetch(off, hits[0])
        if not got: continue
        e, s, eff, units = got
        if not units or "ac-ft" not in units.lower().replace("acre-ft", "ac-ft").replace(" ", ""):
            res[lid] = {"skip": f"units {units}"}; continue
        zs, az = area_from_storage(e, s)
        step = float(np.median(np.diff(e)))
        P = v["poolFt"]
        if not (zs[0] <= P - 3 and P <= zs[-1]):
            res[lid] = {"skip": "pool not inside storage rating"}; continue
        truth = shares(np.array(v["elevFt"]), np.array(v["areaAc"]), P)
        est = shares(zs, az, P)
        d = {x: round(est[x] - truth[x], 4) for x in est if x in truth}
        res[lid] = {"storRating": hits[0], "stepFt": round(step, 3), "effective": eff, "diff": d}
        print(lid, res[lid]["stepFt"], d, flush=True)
    json.dump({"schema": "depth-stor-derived-validation-v1", "lakes": res}, open(f"{HERE}/../../docs/brains/depth/data/stor_derived_validation.json", "w"), indent=1)


main()
