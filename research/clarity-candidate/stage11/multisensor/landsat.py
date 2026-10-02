"""Stage 11 Part F (PREREGISTRATION_STAGE11.md section 8): Landsat 8/9 Collection 2 L2 surface reflectance at every
corpus row, same day as the agency record or +-1 day. Planetary Computer STAC (anonymous SAS token). 3x3 pixels (90 m)
at the station; QA_PIXEL water (bit 7) and no cloud / shadow / cirrus / dilated cloud (bits 1-4). Dogliotti FNU with the
production coefficients on SR_B4 (655 nm). Writes landsat.json."""
import json, sys, math, time, urllib.request, concurrent.futures as cf, datetime as dt, os
import numpy as np, rasterio, pyproj
S = __import__("os").environ["CLARITY_RESEARCH_ROOT"] + ""
sys.path.insert(0, os.path.expanduser(__import__("os").environ["CLARITY_RESEARCH_ROOT"] + "/vendor/Sector_Engine-fusion/jobs/lake-surface"))
import derive_water_surface as dws
PC = "https://planetarycomputer.microsoft.com/api/stac/v1/search"
_tok = {"t": None, "exp": 0}


def token():
    if time.time() > _tok["exp"] - 300:
        d = json.loads(urllib.request.urlopen("https://planetarycomputer.microsoft.com/api/sas/v1/token/landsat-c2-l2", timeout=60).read())
        _tok["t"] = d["token"]; _tok["exp"] = time.time() + 3000
    return _tok["t"]


def post(body, tries=5):
    for i in range(tries):
        try:
            req = urllib.request.Request(PC, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
            return json.loads(urllib.request.urlopen(req, timeout=90).read())
        except Exception:
            if i == tries - 1:
                raise
            time.sleep(3 * (i + 1))


def read_px(href, lat, lon, half=1):
    with rasterio.open(href + ("&" if "?" in href else "?") + token()) as src:
        x, y = pyproj.Transformer.from_crs("EPSG:4326", src.crs, always_xy=True).transform(lon, lat)
        c, r = ~src.transform * (x, y)
        c, r = int(c), int(r)
        if not (half <= c < src.width - half and half <= r < src.height - half):
            return None
        return src.read(1, window=rasterio.windows.Window(c - half, r - half, 2 * half + 1, 2 * half + 1))


def one(x):
    d = dt.date.fromisoformat(x["date"])
    body = {"collections": ["landsat-c2-l2"], "intersects": {"type": "Point", "coordinates": [x["lon"], x["lat"]]},
            "datetime": f"{(d - dt.timedelta(days=1)).isoformat()}T00:00:00Z/{(d + dt.timedelta(days=1)).isoformat()}T23:59:59Z",
            "query": {"platform": {"in": ["landsat-8", "landsat-9"]}, "eo:cloud_cover": {"lt": 60}}, "limit": 10}
    try:
        its = post(body).get("features", [])
    except Exception as e:
        return x["id"], {"error": "search " + str(e)[:80]}
    out = []
    for it in its:
        try:
            qa = read_px(it["assets"]["qa_pixel"]["href"], x["lat"], x["lon"])
            if qa is None:
                continue
            water = ((qa >> 7) & 1) == 1
            bad = (((qa >> 1) & 1) | ((qa >> 2) & 1) | ((qa >> 3) & 1) | ((qa >> 4) & 1)) == 1
            ok = water & ~bad
            if ok.sum() < 5:
                out.append({"item": it["id"], "valid": int(ok.sum())}); continue
            rec = {"item": it["id"], "platform": it["properties"]["platform"], "datetime": it["properties"]["datetime"],
                   "sun_elev": it["properties"].get("view:sun_elevation"), "valid": int(ok.sum())}
            for b, k in (("blue", "SR_B2"), ("green", "SR_B3"), ("red", "SR_B4"), ("nir08", "SR_B5"), ("swir16", "SR_B6")):
                key = {"SR_B2": "blue", "SR_B3": "green", "SR_B4": "red", "SR_B5": "nir08", "SR_B6": "swir16"}[k]
                v = read_px(it["assets"][key]["href"], x["lat"], x["lon"]).astype("float32") * 0.0000275 - 0.2
                rec[b] = float(np.median(v[ok]))
            r = max(rec["red"], 0.0)
            rec["fnu"] = float(dws.TURB_SATURATED_FNU if r >= dws.TURB_SATURATED else dws.TURB_A * r / max(1e-6, 1 - r / dws.TURB_C))
            out.append(rec)
        except Exception as e:
            out.append({"item": it["id"], "error": str(e)[:80]})
    return x["id"], {"passes": out}


if __name__ == "__main__":
    rows = json.load(open(f"{S}/stage11/corpus/corpus_base.json"))
    path = f"{S}/stage11/multisensor/landsat.json"
    done = json.load(open(path)) if os.path.exists(path) else {}
    todo = [x for x in rows if x["id"] not in done]
    with cf.ThreadPoolExecutor(8) as ex:
        for i, (k, v) in enumerate(ex.map(one, todo)):
            done[k] = v
            if i % 100 == 0:
                json.dump(done, open(path, "w")); print(i, len(todo), flush=True)
    json.dump(done, open(path, "w"))
    n = sum(1 for v in done.values() if any(p.get("fnu") is not None for p in v.get("passes", [])))
    print("rows", len(done), "with a valid Landsat 8/9 read (+-1 day)", n)
