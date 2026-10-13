"""Fleet geometry from the PUBLISHED Lake Registry v1 (gs://sector-lake-registry, public): download analysis polygons, compute the polygon-fetch
profile per lake (same method as the ESTIMATED tier), and cross-check every AUDITED table against the registry polygon (area/identity).
  python research/registry_fleet.py INDEX.json OUT_DIR [--workers 4]"""
import gzip, json, math, os, sys, urllib.request
from concurrent.futures import ThreadPoolExecutor
from multiprocessing import Pool
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np

def fetch_poly(args):
    lake_key, url, out = args
    p = os.path.join(out, "geom", lake_key + ".geojson")
    if os.path.exists(p):
        return lake_key, True
    try:
        raw = urllib.request.urlopen(urllib.request.Request(url, headers={"Accept-Encoding": "identity", "User-Agent": "SectorWind research"}), timeout=60).read()
        try:
            raw = gzip.decompress(raw)
        except OSError:
            pass
        os.makedirs(os.path.dirname(p), exist_ok=True); open(p, "wb").write(raw)
        return lake_key, True
    except Exception as e:
        return lake_key, False

def profile(args):
    lake_id, lake_key, area, out = args
    from shapely.geometry import shape
    from sector_wind.brain import estimate as ES
    from scipy import ndimage
    try:
        j = json.load(open(os.path.join(out, "geom", lake_key + ".geojson")))
        g = j["features"][0]["geometry"] if j.get("type") == "FeatureCollection" else (j["geometry"] if j.get("type") == "Feature" else j)
        geom = ES.clean_geometry(shape(g))
        if geom is None:
            return {"id": lake_id, "areaKm2": area, "ok": False, "why": "unusable geometry"}
        mask, res, ref = ES.rasterize(geom)
        edge = mask & ~ndimage.binary_erosion(mask, iterations=1)
        ys, xs = np.nonzero(edge)
        if len(xs) < 20:
            return {"id": lake_id, "areaKm2": area, "ok": False, "why": "fewer than 20 shoreline cells", "res": res}
        st = max(1, len(xs) // 400); xs, ys = xs[::st].astype(float), ys[::st].astype(float)
        F = np.zeros((len(xs), 16))
        for j2, b in enumerate(range(16)):
            F[:, j2] = np.mean([ES.ray_distances(mask, res, xs, ys, (22.5 * b + o) % 360) for o in range(-12, 13, 6)], axis=0)
        return {"id": lake_id, "areaKm2": area, "ok": True, "nBanks": int(len(xs)), "res": float(res), "medianFetchByDir": np.median(F, axis=0).round(0).tolist(),
                "p90FetchByDir": np.percentile(F, 90, axis=0).round(0).tolist(), "maxFetchM": float(F.max())}
    except Exception as e:
        return {"id": lake_id, "areaKm2": area, "ok": False, "why": repr(e)[:120]}

if __name__ == "__main__":
    idx = json.load(open(sys.argv[1])); out = sys.argv[2]; os.makedirs(out, exist_ok=True)
    workers = int(sys.argv[sys.argv.index("--workers") + 1]) if "--workers" in sys.argv else 4
    lakes = [l for l in idx["lakes"] if l.get("geometry")]
    with ThreadPoolExecutor(8) as ex:
        got = dict(ex.map(fetch_poly, [(l["lakeKey"], l["geometry"]["analysisUrl"], out) for l in lakes]))
    print("downloaded", sum(got.values()), "of", len(lakes), flush=True)
    jobs = [(l["lakeId"], l["lakeKey"], l["areaKm2"], out) for l in lakes if got.get(l["lakeKey"])]
    res = []
    with Pool(workers) as pool:
        for i, r in enumerate(pool.imap(profile, jobs, chunksize=2)):
            res.append(r)
            if i % 50 == 0: print(i, r["id"], r.get("ok"), flush=True)
    json.dump(res, open(os.path.join(out, "registry_fleet_fetch.json"), "w"))
    print("done", len(res), sum(r["ok"] for r in res))
