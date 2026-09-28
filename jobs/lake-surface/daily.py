"""Daily lake-surface job: fresh Water Clarity for every lake.

For each directory lake with an outline, find Sentinel-2 L2A passes newer than
the last one published; if there is one, build the lake's clarity field from
the newest usable pass (derive_water_surface.build_clarity, UTM set per lake)
and publish it:

  lakes/<slug>/clarity/<date>.png | .measured.png | .distance.png | .json
  lakes/<slug>/clarity/latest.json   the newest pass: date, files, summary
  lakes/<slug>/clarity/history.json  one summary per published pass
  lakes/<slug>/clarity/<date>.cells.bin, arms/<date>.json
                                     lakes with a Current Clarity regions index
                                     only (Stage 4): the engine's per-cell input
  index.json                         every lake's latest pass date + summary

A lake with no new usable pass is left as it is. --pass-dates rebuilds the
named days' passes instead (a history backfill): each day's scene files and
history entry are published, and latest.json moves only to a newer day. Storage is a local folder
(OUT_DIR) or a Cloud Storage bucket (BUCKET); the job runs as N parallel tasks
(CLOUD_RUN_TASK_INDEX / CLOUD_RUN_TASK_COUNT), each taking every Nth lake, and
LAKE_WORKERS lakes at a time inside a task (the work is mostly waiting on
Sentinel-2 reads).

usage: python daily.py [--lakes id1,id2] [--until YYYY-MM-DD] [--force] [--pass-dates D1,D2]
env:   OUT_DIR or BUCKET; POLYGONS (default polygons.geojson.gz); LAKES_URL;
       LAKE_WORKERS (default 4); MEM_BUDGET_GB (default 14)
"""
import os, sys, io, gzip, json, time, re, argparse, datetime as dt, traceback, tempfile, threading
import concurrent.futures as cf
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from shapely.geometry import shape
import derive_water_surface as dws

LAKES_URL = os.environ.get("LAKES_URL", "https://sector-engine-e43utajroa-uc.a.run.app/lakes")
POLYGONS = os.environ.get("POLYGONS", os.path.join(os.path.dirname(os.path.abspath(__file__)), "polygons.geojson.gz"))
LOOKBACK_DAYS = 14          # passes older than this are not "fresh"
GRID_FACTOR = 6             # the engine's point-lookup grid: 6 x 36 m cells (~216 m mercator)
_build_lock = threading.Lock()   # build_clarity sets dws.UTM, a module global
_publish_lock = threading.Lock() # latest.json / history.json are read, changed and written
# Memory. Most of a build's peak is reading one Sentinel-2 tile's window at
# 10 m (~100 bytes a pixel), which grows with the lake's ground area up to a
# whole tile (110 km square) and does not shrink with a coarser frame; the
# frame's own arrays add a little per million cells. Measured: Guntersville
# (6,000 km2 frame) 4.6 GB, Kentucky Lake (10,000 km2) 6.5 GB. Lakes share a
# task's MEM_BUDGET_GB; a frame too big for it is coarsened, and a lake still
# over it builds alone.
MEM_BASE_GB = 1.0
MEM_PER_1000KM2_GB = 0.55
MEM_TILE_KM2 = 12_100
MEM_PER_MCELL_GB = 0.2
MEM_BUDGET_GB = float(os.environ.get("MEM_BUDGET_GB", "14"))
REPLACE_WITHIN = 0.8        # a sparser new pass must read this share of what the published one read
REPLACE_DAYS = 10           # ...unless the published pass is older than this


class MemoryBudget:
    """Gigabytes shared by the lakes building at once in a task."""

    def __init__(self, gb):
        self.free, self.cv = gb, threading.Condition()

    def take(self, gb):
        with self.cv:
            self.cv.wait_for(lambda: self.free >= gb)
            self.free -= gb

    def give(self, gb):
        with self.cv:
            self.free += gb
            self.cv.notify_all()


_budget = MemoryBudget(MEM_BUDGET_GB)


def frame_for(lake):
    """The lake's clarity frame, coarsened for the few lakes whose 36 m frame
    would not fit the budget, and the memory its build is expected to need."""
    cell = dws.CLARITY_CELL
    while True:
        frame = dws.Frame(lake, cell=cell)
        cells = frame.width * frame.height
        km2 = cells * frame.cell_ground_m() ** 2 / 1e6
        gb = (MEM_BASE_GB + MEM_PER_1000KM2_GB * min(km2, MEM_TILE_KM2) / 1000
              + MEM_PER_MCELL_GB * cells / 1e6)
        if gb <= MEM_BUDGET_GB or cell >= 8 * dws.CLARITY_CELL:
            return frame, min(gb, MEM_BUDGET_GB)
        cell *= 2


def slug(lake_id):
    return re.sub(r"[^A-Za-z0-9]+", "_", lake_id).strip("_")


class Store:
    """A local folder, or a Cloud Storage bucket."""

    def __init__(self):
        self.bucket_name = os.environ.get("BUCKET")
        self.root = os.environ.get("OUT_DIR", "out")
        if self.bucket_name:
            from google.cloud import storage
            self.bucket = storage.Client().bucket(self.bucket_name)

    def read_json(self, key):
        try:
            if self.bucket_name:
                return json.loads(self.bucket.blob(key).download_as_bytes())
            return json.load(open(os.path.join(self.root, key)))
        except Exception:
            return None

    def write(self, key, data, content_type, cache="public, max-age=600"):
        if self.bucket_name:
            b = self.bucket.blob(key)
            b.cache_control = cache
            b.upload_from_string(data, content_type=content_type)
        else:
            path = os.path.join(self.root, key)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            open(path, "wb").write(data)

    def write_json(self, key, obj, cache="public, max-age=600"):
        self.write(key, json.dumps(obj, separators=(",", ":")).encode(), "application/json", cache)


def utm_epsg(lake):
    c = lake.centroid
    zone = int((c.x + 180) // 6) + 1
    return f"EPSG:{(32600 if c.y >= 0 else 32700) + zone}"


def newest_pass_date(bbox, until):
    """The newest Sentinel-2 pass date over the lake in the lookback window."""
    got = dws.passes(dws.ES_SEARCH, dws.S2_COLLECTION, bbox, until, max_cloud=40)
    fresh = [d for (d, _), _ in got
             if (until.date() - dt.date.fromisoformat(d)).days <= LOOKBACK_DAYS]
    return max(fresh) if fresh else None


def point_grid(out, meta):
    """A coarse copy of the field for the engine's point lookups (the engine
    runs on Linux, where decoding a PNG is not on hand): per GRID_FACTOR x
    GRID_FACTOR block, the median encoded value of the valued cells (0 = none)
    and the most common measured code, base64 uint8, row-major from the top."""
    import base64
    import numpy as np
    from PIL import Image
    q = np.asarray(Image.open(out + ".png"), dtype=np.uint8)
    src = np.asarray(Image.open(out + ".measured.png"), dtype=np.uint8)
    f = GRID_FACTOR
    h, w = (q.shape[0] + f - 1) // f, (q.shape[1] + f - 1) // f
    pad = lambda a: np.pad(a, ((0, h * f - a.shape[0]), (0, w * f - a.shape[1])))
    qb = pad(q).reshape(h, f, w, f).transpose(0, 2, 1, 3).reshape(h, w, f * f).astype(float)
    sb = pad(src).reshape(h, f, w, f).transpose(0, 2, 1, 3).reshape(h, w, f * f)
    qb[qb == 0] = np.nan
    with np.errstate(all="ignore"):
        med = np.nanmedian(qb, axis=2)
    val = np.where(np.isnan(med), 0, np.round(med)).astype(np.uint8)
    # measured share per block: 255 where most valued cells were measured
    valued = ~np.isnan(qb)
    meas = ((sb == 255) & valued).sum(axis=2)
    code = np.where(val == 0, 0, np.where(meas * 2 >= np.maximum(1, valued.sum(axis=2)), 255, 1)).astype(np.uint8)
    left, top = meta["coordinates"][0]
    return {"lakeId": meta["lakeId"], "pass": meta["pass"]["date"], "projection": "EPSG:3857",
            "cellMetresMercator": meta["cellMetresMercator"] * f, "width": int(w), "height": int(h),
            "cornersLonLat": meta["coordinates"], "encoding": meta["encoding"],
            "values": base64.b64encode(val.tobytes()).decode(), "measured": base64.b64encode(code.tobytes()).decode()}


REGIONS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "regions")


def current_cells_files(out, date, lake_id, store, key):
    """Clarity Fusion Stage 4: for a lake with a Current Clarity regions index
    (regions/<slug>.current_regions.bin and .arm_cells.json, copied in by
    deploy-job.sh), the scene's cells file and its per-arm anchors — what the
    engine's Current Clarity reads. Nothing for any other lake."""
    prefix = os.path.join(REGIONS_DIR, slug(lake_id))
    if not os.path.exists(prefix + ".current_regions.bin"):
        return {}
    import current_cells, arm_anchor
    d, name = os.path.dirname(out), os.path.basename(out)
    current_cells.scene(d, name, prefix + ".current_regions", out + ".cells.bin")
    store.write(f"{key}/{date}.cells.bin", open(out + ".cells.bin", "rb").read(), "application/octet-stream",
                cache="public, max-age=31536000")
    arms = arm_anchor.anchors(d, name, prefix + ".arm_cells.json")
    store.write_json(f"{key}/arms/{date}.json", arms, cache="public, max-age=31536000")
    return {"cells": f"{key}/{date}.cells.bin", "arms": f"{key}/arms/{date}.json"}


def summary(meta):
    s = meta.get("measuredStatsFNU") or {}
    return {"date": meta["pass"]["date"], "platform": meta["pass"]["platform"],
            "time": meta["pass"].get("time"), "measuredPct": meta.get("measuredPct"),
            "openWaterReadPct": meta.get("openWaterReadPct"),
            "grassPct": meta.get("grassPct"), "fnuP25": s.get("p25"), "fnuP50": s.get("p50"),
            "fnuP75": s.get("p75")}


def process(lake_id, geom_json, store, until, force, day=None):
    """day: rebuild that day's pass only (a history backfill), whatever is published."""
    key = f"lakes/{slug(lake_id)}/clarity"
    latest = store.read_json(f"{key}/latest.json") or {}
    lake = shape(geom_json)
    bbox = list(lake.bounds)
    held = latest.get("summary") or {}
    if day:
        # Only that day's passes are candidates, and the job's own choice among them.
        until = dt.datetime.fromisoformat(day + "T23:59:59")
        after, floor = (dt.date.fromisoformat(day) - dt.timedelta(days=1)).isoformat(), 0.0
    else:
        newest = newest_pass_date(bbox, until)
        if newest is None:
            return lake_id, "no pass in the window", latest.get("summary")
        if not force and held.get("date", "") >= newest:
            return lake_id, "up to date", held or None
        # Only passes newer than the published one are read; a sparser one
        # replaces it only if it reads nearly as much, or the published is old.
        after, floor = (None, 0.0) if force or not held else (held["date"], 0.0)
        if after and held.get("openWaterReadPct") and \
                (until.date() - dt.date.fromisoformat(held["date"])).days <= REPLACE_DAYS:
            floor = REPLACE_WITHIN * held["openWaterReadPct"] / 100
    with tempfile.TemporaryDirectory() as tmp:
        out = os.path.join(tmp, "c")
        with _build_lock:
            dws.UTM = utm_epsg(lake)
            frame, gb = frame_for(lake)
            masks = dws.lake_masks(lake, frame)
        _budget.take(gb)
        try:
            dws.build_clarity(frame, masks, bbox, until, out, after=after, floor=floor)
        finally:
            _budget.give(gb)
        meta = json.load(open(out + ".json"))
        meta.update({"lakeId": lake_id, "projection": dws.WEB_MERCATOR, "coordinates": frame.corners(),
                     "pixelWidth": frame.width, "pixelHeight": frame.height,
                     "cellMetresMercator": frame.cell, "generatedOn": dt.date.today().isoformat()})
        date = meta["pass"]["date"]
        if not force and not day and latest.get("summary", {}).get("date", "") >= date:
            return lake_id, f"newest usable pass {date} already published", latest.get("summary")
        files = {}
        for suffix, name in ((".png", "clarity"), (".measured.png", "measured"), (".distance.png", "distance")):
            fk = f"{key}/{date}{suffix}"
            store.write(fk, open(out + suffix, "rb").read(), "image/png", cache="public, max-age=31536000")
            files[name] = fk
        meta["measured"]["file"] = os.path.basename(files["measured"])
        meta["measured"]["distanceFile"] = os.path.basename(files["distance"])
        store.write_json(f"{key}/{date}.json", meta, cache="public, max-age=31536000")
        files["meta"] = f"{key}/{date}.json"
        store.write_json(f"{key}/{date}.grid.json", point_grid(out, meta), cache="public, max-age=31536000")
        files["grid"] = f"{key}/{date}.grid.json"
        files.update(current_cells_files(out, date, lake_id, store, key))
        s = summary(meta)
        with _publish_lock:
            held = (store.read_json(f"{key}/latest.json") or {}).get("summary") or {}
            if not day or date >= held.get("date", ""):
                store.write_json(f"{key}/latest.json", {"lakeId": lake_id, "summary": s, "files": files,
                                                        "publishedAt": dt.datetime.utcnow().isoformat() + "Z"})
            hist = store.read_json(f"{key}/history.json") or {"lakeId": lake_id, "passes": []}
            hist["passes"] = [p for p in hist["passes"] if p["date"] != date] + [s]
            hist["passes"].sort(key=lambda p: p["date"])
            store.write_json(f"{key}/history.json", hist)
    return lake_id, f"published {date}", s


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--lakes", default=None)
    ap.add_argument("--until", default=None)
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--pass-dates", default=None, help="rebuild these days' passes (YYYY-MM-DD,...)")
    a = ap.parse_args()
    until = dt.datetime.fromisoformat(a.until) if a.until else dt.datetime.utcnow()
    with (gzip.open if POLYGONS.endswith(".gz") else open)(POLYGONS, "rt") as fh:
        polys = {f["properties"]["id"]: f["geometry"] for f in json.load(fh)["features"]
                 if f.get("geometry")}
    ids = every = sorted(polys)
    if a.lakes:
        want = set(a.lakes.split(","))
        ids = [i for i in ids if i in want]
    n = int(os.environ.get("CLOUD_RUN_TASK_COUNT", "1"))
    k = int(os.environ.get("CLOUD_RUN_TASK_INDEX", "0"))
    days = a.pass_dates.split(",") if a.pass_dates else [None]
    mine = [(i, d) for i in ids for d in days][k::n]
    store = Store()
    workers = int(os.environ.get("LAKE_WORKERS", "4"))
    print(f"task {k + 1}/{n}: {len(mine)} builds, {workers} at a time, until {until.date()}", flush=True)
    results = {}
    t0 = time.time()
    with cf.ThreadPoolExecutor(workers) as ex:
        futs = {ex.submit(process, i, polys[i], store, until, a.force, d): (i, d) for i, d in mine}
        for f in cf.as_completed(futs):
            i, d = futs[f]
            try:
                lid, status, s = f.result()
            except SystemExit as e:
                lid, status, s = i, f"no usable pass: {e}", None
            except Exception as e:
                lid, status, s = i, f"error: {e}", None
                traceback.print_exc()
            results[lid if d is None else f"{lid} {d}"] = {"status": status, "summary": s}
            print(f"  {lid}{'' if d is None else ' ' + d}: {status}", flush=True)
    store.write_json(f"runs/{until.date()}-task{k}.json", {"until": until.isoformat(), "seconds": round(time.time() - t0),
                                                           "results": results})
    # The index is rebuilt from every lake's latest.json by task 0 (cheap reads),
    # all of them even when --lakes ran only a few.
    if k == 0:
        index = {}
        for i in every:
            l = store.read_json(f"lakes/{slug(i)}/clarity/latest.json")
            if l:
                index[i] = {"slug": slug(i), **l["summary"]}
        store.write_json("index.json", {"generatedAt": dt.datetime.utcnow().isoformat() + "Z", "lakes": index})
    print(f"done in {time.time() - t0:.0f}s", flush=True)


if __name__ == "__main__":
    main()
