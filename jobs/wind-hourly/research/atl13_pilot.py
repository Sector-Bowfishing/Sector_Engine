"""Stage 3C Track C pilot: ATL13 V007 over the four development lakes during the NBM v5.0 corpus window.

  python research/atl13_pilot.py download     # raw .h5 (Earthdata login via ~/.netrc), immutable cache
  python research/atl13_pilot.py extract OUT  # QC'd SWH points inside the development-lake NHD polygons

QC v1.1 (corrected 2026-10-07 BEFORE any SWH was compared with Sector): v1 required qf_cloud == 0 and qf_ice == 0,
but both are fill (127) on every V007 segment here, and snow_ice_atl09 == 0, stricter than NSIDC's guidance
(values 2/3 = caution). v1.1: snow_ice_atl09 in {0, 1}; cloud_flag_asr_atl09 == 0 (clear); qf_bckgrd <= 2;
qf_iwp >= 6 (full deconvolution); finite significant_wave_ht; inside the lake polygon; not the first/last
in-lake segment of a crossing."""
import json, os, sys, urllib.parse, urllib.request
import numpy as np
RAW = os.path.expanduser("~/Library/Caches/sector-wind/wind-validation/icesat2/raw")
GEOM = os.path.expanduser("~/Library/Caches/sector-wind/fetch-build/nhd")


def granule_urls():
    q = urllib.parse.urlencode({"short_name": "ATL13", "version": "007", "bounding_box": "-88.32,34.23,-85.56,35.22",
                                "temporal": "2026-05-06T00:00:00Z,2026-10-07T00:00:00Z", "page_size": 200})
    e = json.load(urllib.request.urlopen("https://cmr.earthdata.nasa.gov/search/granules.json?" + q, timeout=120))["feed"]["entry"]
    return [next(a["href"] for a in x["links"] if a["href"].endswith(".h5") and a["href"].startswith("https")) for x in e]


def download():
    import requests
    os.makedirs(RAW, exist_ok=True)
    s = requests.Session()   # credentials come from the user's existing ~/.netrc (urs.earthdata.nasa.gov)
    for u in granule_urls():
        p = os.path.join(RAW, u.rsplit("/", 1)[1])
        if os.path.exists(p):
            continue
        r = s.get(u, stream=True, timeout=600); r.raise_for_status()
        with open(p + ".part", "wb") as f:
            for ch in r.iter_content(1 << 20):
                f.write(ch)
        os.replace(p + ".part", p); os.chmod(p, 0o444); print("got", os.path.basename(p), flush=True)


def lake_polys():
    from shapely.geometry import shape
    from shapely.ops import unary_union
    from shapely.prepared import prep
    out = {}
    for lk in ("guntersville", "wheeler", "wilson", "pickwick"):
        j = json.load(open(os.path.join(GEOM, f"{lk}.geojson")))
        g = unary_union([shape(f["geometry"]) for f in j["features"]])
        out[lk] = (g, prep(g))
    return out


def extract(outp):
    import h5py
    from shapely.geometry import Point
    polys = lake_polys(); pts = []; seen = {"segments": 0, "inLake": 0}
    for fn in sorted(os.listdir(RAW)):
        if not fn.endswith(".h5"):
            continue
        with h5py.File(os.path.join(RAW, fn), "r") as h:
            for beam in [k for k in h.keys() if k.startswith("gt")]:
                g = h[beam]
                if "segment_lat" not in g:
                    continue
                lat, lon = g["segment_lat"][:], g["segment_lon"][:]
                swh = g["significant_wave_ht"][:] if "significant_wave_ht" in g else None
                if swh is None:
                    continue
                t0 = h["ancillary_data/atlas_sdp_gps_epoch"][0] if "ancillary_data/atlas_sdp_gps_epoch" in h else None
                dt = g["delta_time"][:]
                def fld(name):
                    return g[name][:] if name in g else None
                qf = {k: fld(k) for k in ("snow_ice_atl09", "cloud_flag_asr_atl09", "qf_bckgrd", "qf_iwp")}
                seen["segments"] += len(lat)
                for i in range(len(lat)):
                    p = Point(lon[i], lat[i]); lake = next((k for k, (_, pp) in polys.items() if pp.contains(p)), None)
                    if not lake:
                        continue
                    seen["inLake"] += 1
                    ok = (np.isfinite(swh[i]) and swh[i] < 1e30 and all(qf[k] is not None for k in qf)
                          and qf["snow_ice_atl09"][i] in (0, 1) and qf["cloud_flag_asr_atl09"][i] == 0
                          and qf["qf_bckgrd"][i] <= 2 and qf["qf_iwp"][i] >= 6)
                    pts.append({"file": fn, "beam": beam, "lake": lake, "lat": float(lat[i]), "lon": float(lon[i]),
                                "deltaTime": float(dt[i]), "swh": float(swh[i]) if np.isfinite(swh[i]) else None,
                                "qcPass": bool(ok), **{k: (int(v[i]) if v is not None else None) for k, v in qf.items()}})
    # drop first/last in-lake segment of each crossing (land-edge leakage)
    by = {}
    for q in pts:
        by.setdefault((q["file"], q["beam"], q["lake"]), []).append(q)
    for v in by.values():
        v.sort(key=lambda q: q["deltaTime"])
        for q in (v[0], v[-1]):
            q["qcPass"] = False; q["edge"] = True
    json.dump({"seen": seen, "points": pts}, open(outp, "w"))
    good = [q for q in pts if q["qcPass"]]
    print(json.dumps({**seen, "inLakeSegments": len(pts), "qcPass": len(good), "crossings": len(by),
                      "crossingsWithQcPass": len({(q['file'], q['beam'], q['lake']) for q in good}),
                      "byLake": {lk: sum(q['lake'] == lk for q in good) for lk in polys}}, indent=1))


if __name__ == "__main__":
    download() if sys.argv[1] == "download" else extract(sys.argv[2])
