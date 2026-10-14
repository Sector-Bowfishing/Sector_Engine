"""TVA link test: TVA `observed-data-48-hours` ReservoirElevation vs independent USGS lake-elevation series (62614 NGVD29 / 62615 NAVD88 / 72020 NGVD29; 00062 and 00065 never)
near the dam, hourly at identical instants. Names the TVA reservoir datum only if an independent series agrees to the gate in proposals.py. Read-only GETs."""
import json, math, os, re, urllib.request
import pandas as pd
from datum_pair_common import usgs_series, offset_stats

R3 = os.path.expanduser("~/Desktop/Development/Sector_Research_Data/depth-brain/datum3/tva/")
CAT = os.path.expanduser("~/Desktop/Development/Sector_Research_Data/lake-brain/binding/catalog_usgs_cwms.jsonl")
OUT = os.path.join(os.path.dirname(__file__), "../../docs/brains/depth/data/tva_link_test.json")
LOCS = {"Guntersville": "GVDA1", "Wheeler": "WHLA1", "Wilson": "WLSA1", "Pickwick": "PICT1", "Chickamauga": "CKDT1", "Fort Loudoun": "FLDT1", "Nickajack": "NKJT1", "Watts Bar": "WBOT1",
        "Kentucky": "KYDK2", "Fontana": "FONN7", "Hiwassee": "HIWN7", "Cherokee": "CRKT1", "Douglas": "DUGT1", "Norris": "NRST1", "Tims Ford": "TMFT1", "South Holston": "SHDT1"}
PARAMS = {"62614": "NGVD29", "72020": "NGVD29", "62615": "NAVD88"}
TZ = {"CDT": -5, "CST": -6, "EDT": -4, "EST": -5}


def km(a, b):
    R = 6371.0; p1, p2 = math.radians(a[0]), math.radians(b[0]); dl = math.radians(b[1] - a[1]); dp = p2 - p1
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R * math.asin(math.sqrt(h))


def tva_series(loc):
    req = urllib.request.Request(f"https://www.tva.com/RestApi/observed-data-48-hours/{loc}", headers={"Accept": "application/json"})
    rows = json.loads(urllib.request.urlopen(req, timeout=60).read())
    out = []
    for r in rows:
        m = re.match(r"(Midnight|Noon|\d+ [AP]M) ([CE][DS]T)", r["Time"])
        if not m or not r.get("ReservoirElevation"):
            continue
        t = {"Midnight": "12 AM", "Noon": "12 PM"}.get(m.group(1), m.group(1))
        ts = pd.to_datetime(r["Day"] + " " + t, format="%m/%d/%Y %I %p") - pd.Timedelta(hours=TZ[m.group(2)])
        out.append((ts.tz_localize("UTC"), float(r["ReservoirElevation"].replace(",", ""))))
    s = pd.Series([v for _, v in out], index=[t for t, _ in out]).sort_index()
    return s[~s.index.duplicated()]


def main():
    locs = {l["LocationID"]: l for l in json.load(open(R3 + "locations.json"))}
    cat = [json.loads(l) for l in open(CAT)]
    cat = [r for r in cat if r["prov"] == "usgs" and r.get("family") == "elev" and r["param"] in PARAMS and r.get("lat") is not None and (r.get("end") or "") >= "2026-09-01"]
    res = {}
    for lake, lid in LOCS.items():
        l = locs[lid]; pt = (l["Lat"], l["Long"])
        ts = tva_series(lid)
        near = sorted([(km(pt, (r["lat"], r["lon"])), r) for r in cat], key=lambda x: x[0])
        near = [(d, r) for d, r in near if d <= 12]
        rec = {"lake": lake, "tvaLocation": lid, "tvaRows": int(len(ts)), "candidates": [{"site": r["station"], "name": r["name"], "param": r["param"], "km": round(d, 2), "step": r["step"]} for d, r in near], "pairs": []}
        end = pd.Timestamp.now(tz="UTC").normalize() + pd.Timedelta(days=1); begin = end - pd.Timedelta(days=5)
        seen = set()
        for d, r in near:
            if (r["station"], r["param"]) in seen:
                continue
            seen.add((r["station"], r["param"]))
            us, _, urls = usgs_series(r["station"], r["param"], begin, end, "iv")
            if us is None or not len(us):
                continue
            j = pd.merge_asof(ts.rename("tva").reset_index().rename(columns={"index": "t"}).sort_values("t"), us.rename("usgs").reset_index().rename(columns={"index": "t"}).sort_values("t"),
                              on="t", direction="nearest", tolerance=pd.Timedelta(minutes=30)).dropna().set_index("t")
            if len(j) >= 10:
                rec["pairs"].append({"site": r["station"], "name": r["name"], "param": r["param"], "paramDatum": PARAMS[r["param"]], "km": round(d, 2), "usgsMinusTva": offset_stats(j["usgs"] - j["tva"]), "urls": urls[:1]})
        res[lake] = rec
        print(lake, len(rec["candidates"]), [(p["param"], p["km"], p["usgsMinusTva"]["meanFt"], p["usgsMinusTva"]["sdFt"], p["usgsMinusTva"]["n"]) for p in rec["pairs"]], flush=True)
    json.dump({"schema": "depth-tva-link-test-v1", "generatedAt": pd.Timestamp.now(tz="UTC").strftime("%Y-%m-%dT%H:%MZ"), "results": res}, open(OUT, "w"), indent=1)


main()
