"""Stage 11 Part F, OLCI (same rules as olci.py; faster I/O): every granule (+-1 day) of every row with >= 600 m of
water is downloaded once (geo_coordinates, wqsf, tsm_nn, chl_nn, trsp), read locally with h5py for all the rows it
covers, and deleted. Nearest 300 m pixel within 250 m, 3x3 window, WQSF flags as olci.py (NN products: standard
quality flags; LAND counts only without INLAND_WATER). Per row the closest-in-time valid pass is kept. Writes olci.json."""
import json, os, sys, time, math, shutil, tempfile, urllib.request, concurrent.futures as cf, datetime as dt, collections
import numpy as np, h5py
S = __import__("os").environ["CLARITY_RESEARCH_ROOT"] + ""
sys.path.insert(0, f"{S}/stage11/multisensor")
import olci as O
TMP = f"{S}/stage11/multisensor/olci_tmp"; os.makedirs(TMP, exist_ok=True)


def get(href, dst):
    for i in range(4):
        try:
            with urllib.request.urlopen(href + "?" + O.token(), timeout=600) as r, open(dst, "wb") as f:
                shutil.copyfileobj(r, f, 1 << 20)
            return dst
        except Exception:
            if i == 3: raise
            time.sleep(5)


def var(path, name):
    with h5py.File(path, "r") as f:
        v = f[name]; a = v[()]
        at = {k: (v.attrs[k].decode() if isinstance(v.attrs[k], bytes) else v.attrs[k]) for k in v.attrs}
    return a, at


def scaled(a, at):
    x = a.astype("float64")
    fill = at.get("_FillValue")
    if fill is not None:
        x[a == np.array(fill).item()] = np.nan
    return x * float(np.array(at.get("scale_factor", 1.0)).item()) + float(np.array(at.get("add_offset", 0.0)).item())


def masks(fl, at):
    names = str(at["flag_meanings"]).split(); ms = [int(m) for m in np.array(at["flag_masks"]).ravel()]
    f = dict(zip(names, ms)); v = fl.astype("uint64")
    def ok(bad):
        b = 0
        for n in bad: b |= f.get(n, 0)
        land = (v & np.uint64(f.get("LAND", 0))) != 0; inland = (v & np.uint64(f.get("INLAND_WATER", 0))) != 0
        return ((v & np.uint64(b)) == 0) & (~land | inland)
    return ok(O.BAD_NN), ok(O.BAD_RW)


def process_item(it, rows):
    a = it["assets"]; d = tempfile.mkdtemp(dir=TMP); out = {}
    try:
        g = get(a["geo-coordinates"]["href"], f"{d}/geo.nc")
        la, lat_at = var(g, "latitude"); lo, lon_at = var(g, "longitude")
        la, lo = scaled(la, lat_at), scaled(lo, lon_at)
        H, W = la.shape; pix = {}
        for x in rows:
            dd = (la - x["lat"]) ** 2 + ((lo - x["lon"]) * math.cos(math.radians(x["lat"]))) ** 2
            i, j = np.unravel_index(np.nanargmin(dd), dd.shape)
            if math.sqrt(dd[i, j]) * 111000 <= 250 and 1 <= i < H - 1 and 1 <= j < W - 1:
                pix[x["id"]] = (i, j)
        del la, lo
        if not pix:
            return out
        wq, wat = var(get(a["wqsf"]["href"], f"{d}/wqsf.nc"), "WQSF")
        nn = {k: masks(wq[i - 1:i + 2, j - 1:j + 2], wat) for k, (i, j) in pix.items()}
        del wq
        need = [k for k, (m1, m2) in nn.items() if m1.sum() >= 5]
        vals = collections.defaultdict(dict)
        if need:
            for key, fname, vname, which in (("tsm-nn", "tsm.nc", "TSM_NN", 0), ("chl-nn", "chl.nc", "CHL_NN", 0), ("trsp", "trsp.nc", "KD490_M07", 1)):
                arr, at = var(get(a[key]["href"], f"{d}/{fname}"), vname)
                for k in need:
                    i, j = pix[k]; m = nn[k][which]
                    v = scaled(arr[i - 1:i + 2, j - 1:j + 2], at)
                    vv = v[m & np.isfinite(v)]
                    vals[k][vname] = float(np.median(vv)) if vv.size >= 5 else None
                del arr
                os.remove(f"{d}/{fname}")
        for k in pix:
            out[k] = {"item": it["id"], "platform": it["properties"]["platform"], "datetime": it["properties"]["datetime"],
                      "valid_nn": int(nn[k][0].sum()), "valid_rw": int(nn[k][1].sum()),
                      "tsm_log10": vals[k].get("TSM_NN"), "chl_nn_log10": vals[k].get("CHL_NN"), "kd490_log10": vals[k].get("KD490_M07")}
        return out
    finally:
        shutil.rmtree(d, ignore_errors=True)


if __name__ == "__main__":
    rows = [x for x in json.load(open(f"{S}/stage11/corpus/corpus.json")) if (x.get("dist_nonwater_m") or 0) >= 600 and x["date"] <= "2025-12-31"]
    print("rows", len(rows), flush=True)
    items, by_item = {}, collections.defaultdict(list)
    def search(x):
        d0 = dt.date.fromisoformat(x["date"])
        body = {"collections": [O.COLL], "intersects": {"type": "Point", "coordinates": [x["lon"], x["lat"]]},
                "datetime": f"{(d0 - dt.timedelta(days=1)).isoformat()}T00:00:00Z/{(d0 + dt.timedelta(days=1)).isoformat()}T23:59:59Z", "limit": 12}
        try:
            return x, O.post(body).get("features", [])
        except Exception:
            return x, []
    with cf.ThreadPoolExecutor(8) as ex:
        for x, its in ex.map(search, rows):
            for it in its:
                if (it["properties"].get("eo:cloud_cover") or 0) > 90:
                    continue
                items[it["id"]] = it; by_item[it["id"]].append(x)
    print("granules", len(items), flush=True)
    path = f"{S}/stage11/multisensor/olci.json"
    res = collections.defaultdict(lambda: {"passes": []})
    with cf.ThreadPoolExecutor(5) as ex:
        futs = {ex.submit(process_item, items[k], v): k for k, v in by_item.items()}
        for n, fu in enumerate(cf.as_completed(futs)):
            try:
                for rid, rec in fu.result().items():
                    res[rid]["passes"].append(rec)
            except Exception as e:
                pass
            if n % 10 == 0:
                json.dump(res, open(path, "w")); print(n, len(futs), flush=True)
    for x in rows:
        res.setdefault(x["id"], {"passes": []})
    json.dump(res, open(path, "w"))
    print("rows", len(res), "with a valid OLCI read", sum(1 for v in res.values() if any(p.get("tsm_log10") is not None for p in v["passes"])))
