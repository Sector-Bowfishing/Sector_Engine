"""Stage 20 task builders (value-blind).
  prelim   the 12-19 Dec 2024 tandem pairs of tandem20_pairs.json whose L1C exist on the Google bucket (S2A N0511 + the
           PRELIMINARY S2C N9905/N9906): per (S2A item, S2C item) one ACOLITE run each on S2A and S2C, plus S2C re-calibrated
           to nominal (emulate_nominal). Crops as in the research (points within +-0.07/0.09 of the first).
  ops      nominal operational pairs: S2C (2025 N0511; 2026 N0512) and an S2A/S2B pass at the same site within 2 days, both
           <= 20% cloud, Apr-Oct; per site and year the closest pair (then lowest cloud); a deterministic sample of sites.
Elevation per crop: USGS EPQS (US lakes) or Copernicus GLO-30 (elsewhere), as Stage 14. Writes tasks20_<kind>.json.
  python build20.py prelim|ops [N_SITES_PER_YEAR]"""
import json, os, sys, math, time, hashlib, collections, urllib.request, datetime as dt, concurrent.futures as cf
S = os.environ["CLARITY_RESEARCH_ROOT"]
sys.path[:0] = [f"{S}/stage11/tools", f"{S}/stage6"]
import safe as SAFE, extract as E6
sites = {s["site"]: s for s in json.load(open(f"{S}/stage20/sites20.json"))}
EP = f"{S}/stage20/elevations20.json"; EL = json.load(open(EP)) if os.path.exists(EP) else {}


def epqs(la, lo):
    for i in range(4):
        try:
            with urllib.request.urlopen(f"https://epqs.nationalmap.gov/v1/json?x={lo}&y={la}&wkid=4326&units=Meters&includeDate=false", timeout=30) as r:
                v = float(json.load(r).get("value")); return v if v > -100 else None
        except Exception: time.sleep(2 * (i + 1))
    return None


def glo30(lat, lon):
    import rasterio
    la, lo = math.floor(lat), math.floor(lon)
    t = f"Copernicus_DSM_COG_10_{'N' if la >= 0 else 'S'}{abs(la):02d}_00_{'E' if lo >= 0 else 'W'}{abs(lo):03d}_00_DEM"
    try:
        with rasterio.open(f"/vsicurl/https://copernicus-dem-30m.s3.amazonaws.com/{t}/{t}.tif") as ds:
            v = float(next(ds.sample([(lon, lat)]))[0]); return v if v > -100 else None
    except Exception: return None


def elev(la, lo, us):
    k = f"{la},{lo}"
    if k not in EL: EL[k] = epqs(la, lo) if us else glo30(la, lo)
    return EL[k]


def crops(points):
    out, left = [], list(points)
    while left:
        c = left[0]; inside = [p for p in left if abs(p[0] - c[0]) < 0.07 and abs(p[1] - c[1]) < 0.09]
        out.append({"lat": c[0], "lon": c[1], "points": [list(p) for p in inside]}); left = [p for p in left if p not in inside]
    return out


def finish(T, kind):
    jobs = [c for t in T for c in t["crops"]]
    with cf.ThreadPoolExecutor(8) as ex:
        for c, v in zip(jobs, ex.map(lambda c: elev(c["lat"], c["lon"], not str(c["points"][0][2]).split("|")[0].startswith("G:")), jobs)): c["elev"] = v
    json.dump(EL, open(EP, "w")); json.dump(T, open(f"{S}/stage20/tasks20_{kind}.json", "w"))
    print(kind, len(T), "runs,", len({t["l1c"] for t in T}), "L1C,", len(jobs), "crop runs,", sum(len(c["points"]) for c in jobs), "points;", sum(1 for c in jobs if c["elev"] is None), "without elevation")


if sys.argv[1] == "prelim":
    P = [p for p in json.load(open(f"{S}/stage20/tandem20_pairs.json")) if "20241212" <= p["s2c"].split("_")[2][:8] <= "20241219"]
    grp = collections.defaultdict(list)
    for p in P: grp[(p["s2a"], p["s2c"])].append(p["site"])
    T = []
    for (a, c), ss in sorted(grp.items()):
        la, lc = SAFE.l1c_for(a), SAFE.l1c_for(c)
        if not (la and lc): print("no L1C for", a, c); continue
        pts = [(sites[s]["lat"], sites[s]["lon"], f"{s}|{a}|{c}") for s in ss]
        cr = crops(pts)
        T += [{"run": f"A_{la}", "l1c": la, "crops": cr}, {"run": f"C_{lc}", "l1c": lc, "crops": cr}, {"run": f"E_{lc}", "l1c": lc, "crops": cr, "emulate_nominal": True}]
    finish(T, "prelim")
else:
    N = int(sys.argv[2]) if len(sys.argv) > 2 else 80
    rank = lambda s, y: hashlib.md5(f"{s}|{y}".encode()).hexdigest()
    T, meta = [], []
    for year, rng in ((2025, ("2025-04-01", "2025-10-31")), (2026, ("2026-04-01", "2026-09-30"))):
        order = sorted(sites, key=lambda s: rank(s, year))
        def find(sname):
            s = sites[sname]
            try:
                f = E6.post(E6.ES_SEARCH, {"collections": ["sentinel-2-c1-l2a"], "intersects": {"type": "Point", "coordinates": [s["lon"], s["lat"]]},
                                           "datetime": f"{rng[0]}T00:00:00Z/{rng[1]}T23:59:59Z", "limit": 300, "query": {"eo:cloud_cover": {"lte": 20}}}).get("features", [])
            except Exception: return sname, None
            C = [i for i in f if i["properties"]["platform"] == "sentinel-2c"]; AB = [i for i in f if i["properties"]["platform"] in ("sentinel-2a", "sentinel-2b")]
            day = lambda i: dt.date.fromisoformat(i["properties"]["datetime"][:10])
            best = None
            for c in C:
                for o in AB:
                    gap = abs((day(c) - day(o)).days)
                    if 1 <= gap <= 2:
                        k = (gap, c["properties"]["eo:cloud_cover"] + o["properties"]["eo:cloud_cover"], c["id"], o["id"])
                        if best is None or k < best[0]: best = (k, c, o, gap)
            return sname, best
        got = []
        with cf.ThreadPoolExecutor(8) as ex:
            for sname, best in ex.map(find, order[: N * 3]):
                if best and len(got) < N: got.append((sname, best))
        for sname, (k, c, o, gap) in got:
            lc, lo = SAFE.l1c_for(c["id"]), SAFE.l1c_for(o["id"])
            if not (lc and lo): continue
            s = sites[sname]; pt = [[s["lat"], s["lon"], f"{sname}|{o['id']}|{c['id']}"]]
            cr = crops([tuple(pt[0])])
            T += [{"run": f"O{year}_{lo}_{sname}", "l1c": lo, "crops": cr}, {"run": f"S{year}_{lc}_{sname}", "l1c": lc, "crops": cr}]
            meta.append({"year": year, "site": sname, "s2c": c["id"], "other": o["id"], "gap_days": gap, "l1c_c": lc, "l1c_o": lo})
        print(year, len(got), "pairs", flush=True)
    json.dump(meta, open(f"{S}/stage20/ops20_pairs.json", "w"))
    finish(T, "ops")
