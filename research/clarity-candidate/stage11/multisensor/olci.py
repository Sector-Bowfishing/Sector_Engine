"""Stage 11 Part F (PREREGISTRATION_STAGE11.md section 8): Sentinel-3 OLCI WFR L2 at corpus rows with >= 600 m of water
in every direction (S2 dist_nonwater_m >= 600), same day or +-1 day. Planetary Computer (anonymous SAS), HDF5 range
reads. Nearest 300 m pixel (tie-point grid, then the full-resolution coordinates), 3x3 window, WQSF recommended
NN-product flags clear. Reads TSM_NN, CHL_NN, KD490_M07 and the Oa08 (665 nm) reflectance. Writes olci.json."""
import json, sys, math, time, os, urllib.request, concurrent.futures as cf, datetime as dt
import numpy as np, rasterio
S = __import__("os").environ["CLARITY_RESEARCH_ROOT"] + ""
PC = "https://planetarycomputer.microsoft.com/api/stac/v1/search"
COLL = "sentinel-3-olci-wfr-l2-netcdf"
_tok = {"t": None, "exp": 0}
# NN products (TSM_NN, CHL_NN): the standard quality flags. LAND is set on inland water too, so it only counts
# when INLAND_WATER is not set. Baseline reflectance (Oa06/08/11) additionally needs no AC failure or negative Rw.
BAD_NN = ("INVALID", "CLOUD", "CLOUD_AMBIGUOUS", "CLOUD_MARGIN", "SNOW_ICE", "SUSPECT", "HISOLZEN", "SATURATED",
          "MEGLINT", "HIGHGLINT", "WHITECAPS", "OCNN_FAIL")
BAD_RW = BAD_NN + ("AC_FAIL", "HIGHRW", "RWNEG_O2", "RWNEG_O3", "RWNEG_O4", "RWNEG_O5", "RWNEG_O6", "RWNEG_O7", "RWNEG_O8")


def token():
    if time.time() > _tok["exp"] - 300:
        d = json.loads(urllib.request.urlopen(f"https://planetarycomputer.microsoft.com/api/sas/v1/token/{COLL}", timeout=60).read())
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


def h5(href, var):
    return rasterio.open(f'HDF5:"/vsicurl/{href}?{token()}"://{var}')


def scaled(src, arr):
    sc, off, nd = src.scales[0] or 1.0, src.offsets[0] or 0.0, src.nodatavals[0]
    a = arr.astype("float64") * sc + off
    if nd is not None:
        a[arr == nd] = np.nan
    return a


def locate(item, lat, lon):
    a = item["assets"]
    with h5(a["tie-geo-coordinates"]["href"], "latitude") as s1, h5(a["tie-geo-coordinates"]["href"], "longitude") as s2:
        tla, tlo = scaled(s1, s1.read(1)), scaled(s2, s2.read(1))
    with h5(a["geo-coordinates"]["href"], "latitude") as g:
        H, W = g.height, g.width
    d = (tla - lat) ** 2 + ((tlo - lon) * math.cos(math.radians(lat))) ** 2
    ti, tj = np.unravel_index(np.nanargmin(d), d.shape)
    if d[ti, tj] > 0.05 ** 2:
        return None
    r0 = int(round(ti * (H - 1) / max(1, tla.shape[0] - 1))); c0 = int(round(tj * (W - 1) / max(1, tla.shape[1] - 1)))
    half = 40
    ra, ca = max(0, r0 - half), max(0, c0 - half)
    win = rasterio.windows.Window(ca, ra, min(W, c0 + half) - ca, min(H, r0 + half) - ra)
    with h5(a["geo-coordinates"]["href"], "latitude") as g1, h5(a["geo-coordinates"]["href"], "longitude") as g2:
        la, lo = scaled(g1, g1.read(1, window=win)), scaled(g2, g2.read(1, window=win))
    d = (la - lat) ** 2 + ((lo - lon) * math.cos(math.radians(lat))) ** 2
    i, j = np.unravel_index(np.nanargmin(d), d.shape)
    if math.sqrt(d[i, j]) * 111000 > 250:
        return None
    return ra + i, ca + j, H, W


def flag_mask(src, arr, bad_names):
    t = src.tags(1)
    names = t.get("flag_meanings", "").split()
    masks = [int(float(m)) for m in t.get("flag_masks", "").split()]
    f = dict(zip(names, masks)); v = arr.astype("uint64")
    bad = 0
    for n in bad_names:
        bad |= f.get(n, 0)
    ok = (v & np.uint64(bad)) == 0
    land = (v & np.uint64(f.get("LAND", 0))) != 0
    inland = (v & np.uint64(f.get("INLAND_WATER", 0))) != 0
    return ok & (~land | inland)


def one(x):
    d = dt.date.fromisoformat(x["date"])
    body = {"collections": [COLL], "intersects": {"type": "Point", "coordinates": [x["lon"], x["lat"]]},
            "datetime": f"{(d - dt.timedelta(days=1)).isoformat()}T00:00:00Z/{(d + dt.timedelta(days=1)).isoformat()}T23:59:59Z", "limit": 12}
    try:
        its = post(body).get("features", [])
    except Exception as e:
        return x["id"], {"error": "search " + str(e)[:80]}
    out = []
    t0 = dt.datetime.fromisoformat(x["date"] + "T16:00:00+00:00")
    its.sort(key=lambda it: abs((dt.datetime.fromisoformat(it["properties"]["datetime"].replace("Z", "+00:00")) - t0).total_seconds()))
    for it in its:
        if any(p.get("tsm_log10") is not None for p in out):
            break
        try:
            loc = locate(it, x["lat"], x["lon"])
            if loc is None:
                continue
            r, c, H, W = loc
            if not (1 <= r < H - 1 and 1 <= c < W - 1):
                continue
            win = rasterio.windows.Window(c - 1, r - 1, 3, 3)
            a = it["assets"]
            with h5(a["wqsf"]["href"], "WQSF") as s:
                fl = s.read(1, window=win)
                ok_nn, ok_rw = flag_mask(s, fl, BAD_NN), flag_mask(s, fl, BAD_RW)
            rec = {"item": it["id"], "platform": it["properties"]["platform"], "datetime": it["properties"]["datetime"],
                   "valid_nn": int(ok_nn.sum()), "valid_rw": int(ok_rw.sum())}
            for key, var, name, ok in (("tsm-nn", "TSM_NN", "tsm_log10", ok_nn), ("chl-nn", "CHL_NN", "chl_nn_log10", ok_nn),
                                       ("trsp", "KD490_M07", "kd490_log10", ok_rw)):
                if ok.sum() < 5:
                    rec[name] = None; continue
                with h5(a[key]["href"], var) as s:
                    v = scaled(s, s.read(1, window=win))
                vv = v[ok & np.isfinite(v)]
                rec[name] = float(np.median(vv)) if vv.size else None
            out.append(rec)
        except Exception as e:
            out.append({"item": it["id"], "error": str(e)[:100]})
    return x["id"], {"passes": out}


if __name__ == "__main__":
    rows = [x for x in json.load(open(f"{S}/stage11/corpus/corpus.json")) if (x.get("dist_nonwater_m") or 0) >= 600]
    path = f"{S}/stage11/multisensor/olci.json"
    done = json.load(open(path)) if os.path.exists(path) else {}
    todo = [x for x in rows if x["id"] not in done]
    print("rows with >= 600 m of water:", len(rows), "to do:", len(todo), flush=True)
    with cf.ThreadPoolExecutor(8) as ex:
        futs = [ex.submit(one, x) for x in todo]
        for i, fu in enumerate(cf.as_completed(futs)):
            k, v = fu.result(); done[k] = v
            if i % 10 == 0:
                json.dump(done, open(path, "w")); print(i, len(todo), flush=True)
    json.dump(done, open(path, "w"))
    n = sum(1 for v in done.values() if any(p.get("tsm_log10") is not None for p in v.get("passes", [])))
    print("rows", len(done), "with a valid OLCI read", n)
