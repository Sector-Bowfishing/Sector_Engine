"""RISE link test (read-only GETs; cached outside git). For each bound USBR RISE elevation series, find independent USGS lake-elevation series
(62614 NGVD29 / 62615 NAVD88 / 72020 NGVD29 / 00062 site datum; never 00065) near the RISE location and compare at the RISE timestamps over 365 days.
Question answered: is the RISE daily elevation the same physical gage record as an independent gauge, and on which scale? It does NOT by itself name RISE's datum.
Output: docs/brains/depth/data/rise_link_test.json (small)."""
import json, math, os, sys
import pandas as pd
from datum_pair_common import get_json, usgs_series, offset_stats

R3 = os.path.expanduser("~/Desktop/Development/Sector_Research_Data/depth-brain/datum3/rise/")
CAT = os.path.expanduser("~/Desktop/Development/Sector_Research_Data/lake-brain/binding/catalog_usgs_cwms.jsonl")
OUT = os.path.join(os.path.dirname(__file__), "../../docs/brains/depth/data/rise_link_test.json")
PARAMS = {"62614": "NGVD29", "72020": "NGVD29", "62615": "NAVD88", "00062": None}
MAX_KM = 6.0


def km(a, b):
    R = 6371.0; p1, p2 = math.radians(a[0]), math.radians(b[0]); dl = math.radians(b[1] - a[1]); dp = p2 - p1
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R * math.asin(math.sqrt(h))


def rise_series(sid, after):
    out, page = [], 1
    while True:
        r = get_json("https://data.usbr.gov/rise/api/result", {"itemId": sid, "dateTime[after]": after, "itemsPerPage": 500, "page": page}, headers={"Accept": "application/vnd.api+json"})
        d = r.get("data") if isinstance(r, dict) else None
        if not d or "data" not in d:
            break
        out += [(x["attributes"]["dateTime"], x["attributes"]["result"]) for x in d["data"] if x["attributes"]["result"] is not None]
        if len(d["data"]) < 500:
            break
        page += 1
    s = pd.Series([v for _, v in out], index=pd.to_datetime([t for t, _ in out], utc=True)).sort_index()
    return s[~s.index.duplicated()]


def main():
    items = {i["sid"]: i for i in json.load(open(R3 + "rise_items.json"))}
    locs = json.load(open(R3 + "rise_records_locations.json"))
    cat = [json.loads(l) for l in open(CAT)]
    cat = [r for r in cat if r["prov"] == "usgs" and r.get("family") == "elev" and r["param"] in PARAMS and r.get("lat") is not None and (r.get("end") or "") >= "2026-06-01"]
    end = pd.Timestamp.now(tz="UTC").normalize(); begin = end - pd.Timedelta(days=365)
    res = {}
    for sid, it in items.items():
        if sid in res:
            continue
        loc = (locs.get(sid) or {}).get("loc") or {}
        c = (loc.get("locationCoordinates") or {}).get("coordinates")
        if not c:
            continue
        pt = (c[1], c[0])
        near = sorted([(km(pt, (r["lat"], r["lon"])), r) for r in cat], key=lambda x: x[0])
        near = [(d, r) for d, r in near if d <= MAX_KM]
        rec = {"lake": it["lake"], "riseItem": sid, "riseLocation": it.get("locName"), "candidates": [], "pairs": []}
        if near:
            rs = rise_series(sid, begin.strftime("%Y-%m-%d"))
            rec["riseRows"] = int(len(rs))
            seen = set()
            for d, r in near:
                key = (r["station"], r["param"])
                rec["candidates"].append({"site": r["station"], "name": r["name"], "param": r["param"], "km": round(d, 2), "step": r["step"], "end": r["end"]})
                if key in seen or len(rs) < 20:
                    continue
                seen.add(key)
                us, _, urls = usgs_series(r["station"], r["param"], begin, end, "iv")
                if us is None or not len(us):
                    continue
                j = pd.merge_asof(rs.rename("rise").reset_index().rename(columns={"index": "t"}).sort_values("t"),
                                  us.rename("usgs").reset_index().rename(columns={"index": "t"}).sort_values("t"), on="t", direction="nearest", tolerance=pd.Timedelta(minutes=45)).dropna().set_index("t")
                if len(j) < 20:
                    rec["pairs"].append({"site": r["station"], "param": r["param"], "n": int(len(j)), "note": "fewer than 20 matched instants"}); continue
                st = offset_stats(j["usgs"] - j["rise"])
                rec["pairs"].append({"site": r["station"], "name": r["name"], "param": r["param"], "paramDatum": PARAMS[r["param"]], "km": round(d, 2), "usgsMinusRise": st, "urls": urls[:2]})
        res[sid] = rec
        print(it["lake"], sid, len(rec["candidates"]), [(p.get("param"), (p.get("usgsMinusRise") or {}).get("meanFt"), (p.get("usgsMinusRise") or {}).get("sdFt")) for p in rec["pairs"]], flush=True)
    json.dump({"schema": "depth-rise-link-test-v1", "generatedAt": pd.Timestamp.now(tz="UTC").strftime("%Y-%m-%dT%H:%MZ"), "maxKm": MAX_KM, "results": res}, open(OUT, "w"), indent=1)


def build_proposals():
    """Promotable pairings from the link test: the RISE series equals an independent USGS series whose parameter definition names NGVD29/NAVD88 (|mean|<=0.35, SD<=0.25, n>=20), AND the lake's reference pool
    is verified on that same datum in candidates.json. Anything else stays UNKNOWN."""
    res = json.load(open(OUT))["results"]
    cands = {c["lakeId"]: c for c in json.load(open(os.path.join(os.path.dirname(__file__), "../../jobs/depth-brain/depth_brain/data/candidates.json")))["candidates"]}
    lakes = {}
    for sid, r in res.items():
        c = cands.get(r["lake"])
        for p in r["pairs"]:
            st = p.get("usgsMinusRise") or {}
            ref = (c or {}).get("reference") or {}
            if not (c and st.get("n", 0) >= 20 and abs(st["meanFt"]) <= 0.35 and st["sdFt"] <= 0.25 and p.get("paramDatum") and ref.get("datumVerified") and ref.get("datum") == p["paramDatum"]):
                continue
            sig = round(max(0.15, abs(st["meanFt"]), min(2 * st["sdFt"], 1.0)), 2)
            lakes[r["lake"]] = {
                "decision": "SAME_DATUM", "group": "RISE-link", "levelDatum": p["paramDatum"], "referenceDatum": ref["datum"], "method": "hartwell-pairing", "confidence": "medium", "sigmaFt": sig, "offsetStats": st,
                "summary": f"RISE item {sid} equals USGS {p['site']} {p['param']} ({p['paramDatum']} by USGS parameter definition) to {st['meanFt']:+.3f} ft (SD {st['sdFt']}, n {st['n']}, quarters {st['quarterMeanRangeFt']}); the pool is verified {ref['datum']} ({ref.get('datumRule')}).",
                "evidence": [{"url": u, "says": "USGS iv series used in the pairing"} for u in p["urls"]] + [
                    {"url": "https://api.waterdata.usgs.gov/ogcapi/v0/collections/parameter-codes/items/" + p["param"], "says": "USGS parameter definition names the datum of this series"},
                    {"url": f"https://data.usbr.gov/rise/api/result?itemId={sid}", "says": "RISE daily elevation series compared with the USGS series at the RISE timestamps"}],
                "caveat": "Independence of the USGS gauge from Reclamation's own sensor is not documented; agreement SD 0.12 ft with outliers to -1.2 ft indicates separate processing. Only one RISE lake has a lake-elevation gauge within 6 km."}
    out = os.path.join(os.path.dirname(__file__), "../../jobs/depth-brain/depth_brain/data/proposals/datum_pairings_3.json")
    json.dump({"schema": "depth-datum-proposals-v1", "generatedAt": pd.Timestamp.now(tz="UTC").strftime("%Y-%m-%d"), "sigmaRule": "max(0.15, |mean|, min(2*SD, 1.0))", "lakes": lakes}, open(out, "w"), indent=1)
    print("proposals", list(lakes))


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "proposals":
        build_proposals()
    else:
        main()
