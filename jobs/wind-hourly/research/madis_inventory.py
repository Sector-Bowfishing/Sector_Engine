"""Stage 3D.2 §9: MADIS public-archive station inventory around the four TN-River lakes (research only).

  venv-obs/bin/python research/madis_inventory.py OUT.json FILE.gz ...   # MADIS LDAD mesonet + point/metar hourly netCDF

Files come from https://madis-data.ncep.noaa.gov/madisPublic1/data/archive/ (public subset; restricted providers are absent).
Per station: network/provider, distance to the lake bbox and lake point, obs per hour (cadence), wind/gust availability,
QC descriptor mix (Z,C,S,V,X,Q,G,B), whether a 10 m-reduced speed exists. Classification rule is fixed in
docs/intelligence/wind/stage3d2/WIND_OBSERVATION_NOWCAST_TEST.md §QC before this script was run."""
import gzip, json, math, os, sys, tempfile
from collections import defaultdict
import netCDF4
import numpy as np

LAKES = {"guntersville": ((-86.459, 34.235, -85.559, 35.088), (34.42, -86.23)),
         "wheeler": ((-87.444, 34.34, -86.331, 34.915), (34.66, -87.05)),
         "wilson": ((-87.688, 34.714, -87.321, 34.97), (34.80, -87.52)),
         "pickwick": ((-88.322, 34.677, -87.565, 35.215), (34.95, -88.15))}
RADIUS_KM = 40.0
PRIMARY_NETS = {"ASOS", "ASOS-HFM", "AWOS", "NonFedAWOS", "OTHER-MTR", "METAR"}      # 10 m standard siting, FAA/NWS maintained
SECONDARY_NETS = {"RAWS", "MesoWest/RAWS"}                                                  # 6.1 m standard, agency maintained
DIAGNOSTIC_NETS = {"CRN", "GADOT", "HADS", "NOS-NWLON", "NOS-PORTS"}   # good QC but non-standard height (USCRN wind 1.5 m) or road/gauge siting
REJECT_NETS = {"APRSWXNET", "CWOP", "WXUNDERGROUND", "WEATHERSTEM"}     # citizen / school-rooftop stations: unknown siting and height


def km(a, b, c, d):
    return 6371 * 2 * math.asin(math.sqrt(math.sin(math.radians(c - a) / 2) ** 2 + math.cos(math.radians(a)) * math.cos(math.radians(c)) * math.sin(math.radians(d - b) / 2) ** 2))


def to_bbox(lat, lon, bb):
    return km(lat, lon, min(max(lat, bb[1]), bb[3]), min(max(lon, bb[0]), bb[2]))


def s(x):
    return "".join(c.decode() if isinstance(c, bytes) else str(c) for c in np.ma.filled(x, b"") if c not in (b"", "")).strip()


def read(path):
    with tempfile.NamedTemporaryFile(suffix=".nc") as tmp:
        tmp.write(gzip.open(path).read()); tmp.flush()
        d = netCDF4.Dataset(tmp.name); d.set_auto_mask(True)
        metar = "stationName" in d.variables and "dataProvider" not in d.variables
        n = d.dimensions["recNum"].size
        ids = [s(x) for x in d.variables["stationId" if "stationId" in d.variables else "stationName"][:]]
        prov = ["METAR"] * n if metar else [s(x) for x in d.variables["dataProvider"][:]]
        # MesoWest carries its sub-network as the last token of stationName ("... AL US CRN", "... WEATHERSTEM", "... GADOT")
        names = [s(x) for x in d.variables["stationName"][:]] if "stationName" in d.variables else [""] * n
        sub = [""] * n if metar else [(nm.split()[-1] if p == "MesoWest" and nm else "") for nm, p in zip(names, prov)]
        lat, lon = np.ma.filled(d.variables["latitude"][:], np.nan), np.ma.filled(d.variables["longitude"][:], np.nan)
        ws, wg = np.ma.filled(d.variables["windSpeed"][:].astype(float), np.nan), np.ma.filled(d.variables["windGust"][:].astype(float), np.nan)
        dd = [x.decode() if isinstance(x, bytes) else str(x) for x in np.ma.filled(d.variables["windSpeedDD"][:], b"-")]
        w10 = np.ma.filled(d.variables["windSpeed10"][:].astype(float), np.nan) if "windSpeed10" in d.variables else np.full(n, np.nan)
        t = np.ma.filled(d.variables["timeObs" if metar else "observationTime"][:].astype(float), np.nan)
        if metar:   # autoStationType: A01/A02 automated (ASOS/AWOS); blank = manual/other
            sub = [s(x) for x in d.variables["autoStationType"][:]]
        hour = getattr(d, "startTime", os.path.basename(path))
        d.close()
    return [dict(id=ids[i], prov=prov[i], sub=sub[i], lat=float(lat[i]), lon=float(lon[i]), ws=ws[i], wg=wg[i], dd=dd[i], w10=w10[i],
                 t=t[i], hour=hour, metar=metar) for i in range(n)]


def klass(net, has_wind=True):
    if not has_wind:
        return "REJECT"     # reports no wind in the sampled hours
    for group, k in ((PRIMARY_NETS, "PRIMARY"), (SECONDARY_NETS, "SECONDARY"), (DIAGNOSTIC_NETS, "DIAGNOSTIC"), (REJECT_NETS, "REJECT")):
        if net in group or net.split("/")[0] in group or net.split("/")[-1] in group:
            return k
    return "DIAGNOSTIC"     # unknown network: never anchor-grade until its siting is documented


def main(out, files):
    st = defaultdict(lambda: {"obs": 0, "hours": set(), "wind": 0, "gust": 0, "dd": defaultdict(int), "w10": 0, "times": set()})
    meta = {}
    for f in files:
        for r in read(f):
            if not np.isfinite(r["lat"]) or not (33.6 < r["lat"] < 35.9 and -89.0 < r["lon"] < -85.0):
                continue
            near = {lk: round(to_bbox(r["lat"], r["lon"], bb), 1) for lk, (bb, _) in LAKES.items()}
            if min(near.values()) > RADIUS_KM:
                continue
            net = r["prov"] + (f"/{r['sub']}" if r["sub"] and r["prov"] in ("MesoWest", "METAR") else "")
            k = (r["id"], net); x = st[k]
            meta[k] = {"lat": r["lat"], "lon": r["lon"], "toBboxKm": near,
                       "toLakePointKm": {lk: round(km(r["lat"], r["lon"], *p), 1) for lk, (_, p) in LAKES.items()}}
            if r["t"] in x["times"]:
                continue
            x["times"].add(r["t"]); x["obs"] += 1; x["hours"].add(r["hour"])
            x["wind"] += bool(np.isfinite(r["ws"])); x["gust"] += bool(np.isfinite(r["wg"])); x["w10"] += bool(np.isfinite(r["w10"]))
            if np.isfinite(r["ws"]):
                x["dd"][r["dd"]] += 1
    rows = []
    for (sid, net), x in st.items():
        m = meta[(sid, net)]; nh = max(len(x["hours"]), 1)
        good = sum(v for k, v in x["dd"].items() if k in "CSVG"); bad = sum(v for k, v in x["dd"].items() if k in "XQB")
        rows.append({"station": sid, "network": net, "class": klass(net, x["wind"] > 0), **m, "nearestLake": min(m["toBboxKm"], key=m["toBboxKm"].get),
                     "obsPerHour": round(x["obs"] / nh, 1), "windAvailable": x["wind"] > 0, "gustAvailable": x["gust"] > 0,
                     "windShare": round(x["wind"] / x["obs"], 2), "gustShare": round(x["gust"] / x["obs"], 2),
                     "qcDescriptors": dict(x["dd"]), "qcPassShare": round(good / max(x["wind"], 1), 2), "qcFailShare": round(bad / max(x["wind"], 1), 2),
                     "has10mReduced": x["w10"] > 0})
    rows.sort(key=lambda r: (r["nearestLake"], {"PRIMARY": 0, "SECONDARY": 1, "DIAGNOSTIC": 2, "REJECT": 3}[r["class"]], min(r["toBboxKm"].values())))
    json.dump({"files": [os.path.basename(f) for f in files], "radiusKm": RADIUS_KM, "stations": rows}, open(out, "w"), indent=1)
    from collections import Counter
    print(len(rows), Counter(r["class"] for r in rows), Counter(r["network"] for r in rows).most_common(20))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2:])
