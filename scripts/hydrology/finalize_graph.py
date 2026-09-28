"""Finish the hydrologic arm graph (Clarity Fusion Stage 1): ids, the
arm tree, main-stem regions, gauges, through-water distances, the runtime
graph file, and the before/after membership diff against the lake profile.

Reads build_arm_graph.py's raw outputs and enrich_arms.py's enrichment.

  --raw DIR      build_arm_graph.py --out
  --enrich DIR   enrich_arms.py out_dir
  --out DIR      where the graph, the diff and the reports go

Outputs:
  guntersville.hydrology.json   runtime graph (engine resource)
  guntersville.arm_cells.json   cell -> arm / main-stem region grid on the Water
                                Clarity frame (zlib + base64), for Stage 2
  registry_audit.csv            every old registry tributary: what it was, what
                                the network says, flags
  membership_diff.csv           every shoreline segment: old vs new
  segment_membership.json       the repaired per-segment fields, for the lake
                                profile builder (NOT applied to the app)
"""
import os, sys, json, gzip, math, csv, argparse, collections, base64, zlib, urllib.request
import numpy as np
from scipy.sparse import csgraph
from shapely.geometry import shape, Point, LineString
from shapely.ops import unary_union
import pyproj

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import build_arm_graph as B

GEOD = pyproj.Geod(ellps="WGS84")
DOWNSTREAM_DAM = {"id": "guntersville-dam", "name": "Guntersville Dam", "tva": "GVDA1", "lat": 34.4232, "lon": -86.3930}
UPSTREAM_DAM = {"id": "nickajack-dam", "name": "Nickajack Dam", "tva": "NKJT1", "lat": 35.0035, "lon": -85.6198}
MAINSTEM_ID = "tennessee-river"
MAX_MOUTH_BASIN_KM2 = 5_000      # a "mouth" basin bigger than this is the river's, not the arm's
CORRIDOR_M = 400.0               # main-stem corridor through the water (the old profile's 400 m)


def km(a, b):
    return GEOD.inv(a[1], a[0], b[1], b[0])[2] / 1000


def active_discharge_sites(site_ids):
    """USGS sites (of `site_ids`) reporting 00060 in the last 7 days."""
    out = {}
    ids = sorted(set(site_ids))
    import time
    for k in range(0, len(ids), 40):
        chunk = ",".join(ids[k:k + 40])
        url = f"https://waterservices.usgs.gov/nwis/iv/?format=json&sites={chunk}&parameterCd=00060&period=P7D&siteStatus=all"
        d = None
        for attempt in range(5):
            try:
                with urllib.request.urlopen(url, timeout=120) as r:
                    d = json.loads(r.read())
                break
            except Exception as e:
                time.sleep(5 * (attempt + 1))
        if d is None:
            raise SystemExit(f"USGS IV check failed for {chunk}: gauge association would be incomplete")
        for ts in d["value"]["timeSeries"]:
            v = ts["values"][0]["value"]
            if v:
                sc = ts["sourceInfo"]["siteCode"][0]["value"]
                out[sc] = {"name": ts["sourceInfo"]["siteName"], "last": v[-1]["dateTime"], "cfs": float(v[-1]["value"])}
    return out


def encode_grid(a):
    return base64.b64encode(zlib.compress(a.astype(np.uint8).tobytes(), 9)).decode()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", required=True); ap.add_argument("--enrich", required=True); ap.add_argument("--out", required=True)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    raw = json.load(open(os.path.join(a.raw, "arms_raw.json")))
    arms_raw = {int(k): v for k, v in raw["arms"].items()}
    code_of = {int(k): v for k, v in raw["codes"].items()}
    sid_of_code = {v: k for k, v in code_of.items()}
    enrich = {int(k): v for k, v in json.load(open(os.path.join(a.enrich, "enrichment.json"))).items()}
    label = np.load(os.path.join(a.raw, "label.npy"))
    water = np.load(os.path.join(a.raw, "water.npy"))
    fr = json.load(open(os.path.join(a.raw, "frame.json")))["frame"]
    seg_rows = json.load(open(os.path.join(a.raw, "segment_rows_raw.json")))
    reg = json.load(gzip.open(os.path.join(B.ASSETS, "GuntersvilleTributaries.dataset", "Guntersville.tributaries.json.gz")))
    segs = json.load(gzip.open(os.path.join(B.ASSETS, "GuntersvilleSegments.dataset", "Guntersville.segments.json.gz")))["segments"]
    G = fr["cellGroundM"]

    main_sid = next(s for s, v in arms_raw.items() if v["name"] == B.MAINSTEM_NAME)

    # ── ids: slug of the name; a name two separate systems share gets the
    # mouth's county (and, if still shared, the receiving system) appended.
    by_name = collections.defaultdict(list)
    for s, v in arms_raw.items():
        by_name[v["name"]].append(s)
    ident = {}
    for name, sids in by_name.items():
        if name == B.MAINSTEM_NAME:
            ident[sids[0]] = MAINSTEM_ID; continue
        if len(sids) == 1:
            ident[sids[0]] = B.slug(name); continue
        # county at the mouth; where that is shared too, what it flows into;
        # where even that is shared, the HUC12 watershed it heads in
        def county(s): return B.slug((enrich.get(s, {}).get("mouthCounty") or "").replace(" County", ""))
        def into(s): return "into-" + B.slug(arms_raw[arms_raw[s]["receiving"]]["name"]) if arms_raw[s]["receiving"] in arms_raw else ""
        def huc(s): return B.slug(enrich.get(s, {}).get("huc12Name") or str(s))
        for s in sids:
            t = county(s)
            if [county(x) for x in sids].count(t) > 1:
                t2 = f"{t}-{into(s)}"
                if [f"{county(x)}-{into(x)}" for x in sids].count(t2) > 1:
                    t2 = f"{t}-{huc(s)}"
                t = t2
            ident[s] = f"{B.slug(name)}-{t}"
    assert len(set(ident.values())) == len(ident), "arm ids collide"

    # ── tree: parent = receiving system; top level = the ancestor just below the main stem
    parent = {s: (v["receiving"] if v["receiving"] in arms_raw and v["receiving"] != s else None) for s, v in arms_raw.items()}
    def top_level(s):
        seen = set()
        while parent.get(s) is not None and parent[s] != main_sid and s not in seen:
            seen.add(s); s = parent[s]
        return s

    # ── gauges: active USGS discharge sites upstream on each arm's network
    all_sites = [x["site"] for e in enrich.values() for x in e.get("upstreamSites", [])]
    active = active_discharge_sites(all_sites)
    print(f"{len(set(all_sites))} USGS sites upstream of the arms, {len(active)} report discharge in the last 7 days")

    # ── through-water geometry
    import fill_lake
    idx = fill_lake._index(water)
    A = fill_lake._graph8(water, idx, G)
    import derive_water_surface as dws
    dws.UTM = "EPSG:32616"
    lake = unary_union([shape(f["geometry"]) for f in json.load(open(os.path.join(B.CACHE, "waterbody.geojson")))["features"]])
    frame = dws.Frame(lake, cell=dws.CLARITY_CELL)
    assert frame.width == fr["width"] and frame.height == fr["height"]

    def nearest_water_cell(lon, lat, radius_m=300):
        r, c = B.cell_of(frame, lon, lat)
        rad = int(radius_m / G) + 1
        best = None
        for dr in range(-rad, rad + 1):
            for dc in range(-rad, rad + 1):
                rr, cc = r + dr, c + dc
                if 0 <= rr < frame.height and 0 <= cc < frame.width and water[rr, cc]:
                    d = math.hypot(dr, dc)
                    if best is None or d < best[0]:
                        best = (d, rr, cc)
        return (best[1], best[2]) if best else None

    # distance from each arm's mouth and head, through the water
    mouth_cell, head_cell, d_mouth, d_head = {}, {}, {}, {}
    for s, v in arms_raw.items():
        if v["mouth"]:
            mouth_cell[s] = nearest_water_cell(v["mouth"][0], v["mouth"][1])
        if v["heads"]:
            head_cell[s] = nearest_water_cell(v["heads"][0][0], v["heads"][0][1])
    for s in arms_raw:
        for cells, out in ((mouth_cell, d_mouth), (head_cell, d_head)):
            c = cells.get(s)
            if c is not None:
                out[s] = csgraph.dijkstra(A, directed=False, indices=idx[c], limit=80_000)
    # Through-water distance from any arm mouth (main-stem banks keep a
    # distance-to-tributary this way, as the lake profile has always had one).
    mouth_idx = np.array(sorted({int(idx[c]) for c in mouth_cell.values() if c is not None}))
    d_any_mouth = csgraph.dijkstra(A, directed=False, indices=mouth_idx, min_only=True)
    # Through-water distance to the Tennessee's own channel, and who reaches
    # each cell first among the arms and coves (the channel left out).
    dseed = np.load(os.path.join(a.raw, "dseed.npy"))
    dchan = np.load(os.path.join(a.raw, "dchan.npy"))
    chan = np.load(os.path.join(a.raw, "chan.npy"))
    d_channel = dchan[water]
    # MAIN STEM (the rule consumers get): the corridor within CORRIDOR_M of the
    # channel through the water -- the old profile's 400 m, now measured
    # through water -- plus unnamed coves that drain straight to it. Every
    # other cell belongs to the arm it is reached from first.
    ms_all = water & ((np.nan_to_num(dchan, nan=1e12) <= CORRIDOR_M) | (label == B.COVE) | (label == 0))
    # Sensitivity: the pure nearest-channel split (a cell is main stem when the
    # channel is nearer through the water than any arm's own line).
    ms_nearest = water & ((np.nan_to_num(dchan, nan=1e12) < np.nan_to_num(dseed, nan=1e12)) | (label == B.COVE) | (label == 0))

    # ── main-stem regions: the channel from Nickajack to the dam, cut at every
    # top-level tributary mouth and at least every REGION_KM
    lines, down, up = B.load_network(json.load(open(os.path.join(B.CACHE, "flowlines.geojson")))["features"])
    systems, sys_of = B.systems_of(lines, down, up)
    ms_lines = [i for i in range(len(lines)) if sys_of.get(i) == main_sid and lines[i]["name"] == B.MAINSTEM_NAME]
    ms_geom = unary_union([lines[i]["geom"] for i in ms_lines if lines[i]["geom"].intersects(lake.buffer(0.001))])
    # the main path: walk the channel downstream from Nickajack to the dam
    start = min(ms_lines, key=lambda i: lines[i]["geom"].distance(Point(UPSTREAM_DAM["lon"], UPSTREAM_DAM["lat"])))
    path = [start]; seen = {start}
    while True:
        nxt = [j for j in down[path[-1]] if j in set(ms_lines) and j not in seen]
        if not nxt:
            break
        j = max(nxt, key=lambda k: lines[k]["km"])
        path.append(j); seen.add(j)
    main_path = LineString([c for i in path for c in lines[i]["geom"].coords])
    to_utm = pyproj.Transformer.from_crs("EPSG:4326", "EPSG:32616", always_xy=True)
    from shapely.ops import transform as T
    main_path_m = T(lambda x, y, z=None: to_utm.transform(x, y), main_path)
    L = main_path_m.length
    cuts = {0.0, L}
    top_mouths = {}
    for s, v in arms_raw.items():
        if s == main_sid or parent.get(s) != main_sid or not v["mouth"]:
            continue
        p = T(lambda x, y, z=None: to_utm.transform(x, y), Point(v["mouth"]))
        d = main_path_m.project(p); top_mouths[s] = d; cuts.add(d)
    cuts = sorted(cuts)
    # merge cuts closer than 500 m, then split long pieces
    merged = [cuts[0]]
    for c in cuts[1:]:
        if c - merged[-1] >= 500 or c == L:
            merged.append(c)
    bounds = []
    for x0, x1 in zip(merged[:-1], merged[1:]):
        n = max(1, math.ceil((x1 - x0) / (B.REGION_KM * 1000)))
        for k in range(n):
            bounds.append((x0 + (x1 - x0) * k / n, x0 + (x1 - x0) * (k + 1) / n))
    to_wgs = pyproj.Transformer.from_crs("EPSG:32616", "EPSG:4326", always_xy=True)
    regions = []
    for k, (x0, x1) in enumerate(bounds):
        mid = main_path_m.interpolate((x0 + x1) / 2)
        lon, lat = to_wgs.transform(mid.x, mid.y)
        regions.append({"id": f"ms-{k:02d}", "fromKm": round(x0 / 1000, 2), "toKm": round(x1 / 1000, 2),
                        "center": [round(lat, 5), round(lon, 5)]})
    def region_at(dm):
        for r_ in regions:
            if r_["fromKm"] * 1000 - 1e-6 <= dm <= r_["toKm"] * 1000 + 1e-6:
                return r_["id"]
        return regions[-1]["id"]
    # main-stem cells -> region, through the water: seed each region's piece of the path
    reg_code = np.zeros(water.shape, dtype=np.uint8)
    region_seed_cells, region_seed_codes = [], []
    for k, (x0, x1) in enumerate(bounds):
        steps = max(2, int((x1 - x0) / (G * 0.8)))
        for t in np.linspace(x0, x1, steps):
            p = main_path_m.interpolate(t); lon, lat = to_wgs.transform(p.x, p.y)
            c = nearest_water_cell(lon, lat, radius_m=150)
            if c is not None and chan[c]:
                region_seed_cells.append(idx[c]); region_seed_codes.append(k + 1)
    # each main-stem cell takes the region of the channel piece it reaches
    # first through the water
    _, _, src = csgraph.dijkstra(A, directed=False, indices=np.array(region_seed_cells), min_only=True,
                                 return_predecessors=True)
    code_by_seed = dict(zip(region_seed_cells, region_seed_codes))
    reg_flat = np.array([code_by_seed.get(int(x), 0) if x >= 0 else 0 for x in src], dtype=np.uint8)
    reg_all = np.zeros(water.shape, dtype=np.uint8); reg_all[water] = reg_flat
    reg_code = np.where(ms_all, reg_all, 0).astype(np.uint8)

    # ── arms: everything a consumer needs
    reg_by_name = collections.defaultdict(list)
    for t in reg["tributaries"]:
        reg_by_name[t["name"]].append(t)
    arm_list = []
    for s, v in sorted(arms_raw.items(), key=lambda kv: ident[kv[0]]):
        if s == main_sid:
            continue
        e = enrich.get(s, {})
        # Gauges and the NWM reach come only from an NHDPlus reach that IS this
        # creek (enrich_arms matched the reach's name); otherwise none.
        up_sites = e.get("upstreamSites", []) if e.get("headComid") else []
        gauges = [dict(x, **active[x["site"]]) for x in up_sites if x["site"] in active]
        head = v["heads"][0] if v["heads"] else None
        gauge = min(gauges, key=lambda g: km((g["lat"], g["lon"]), (head[1], head[0]))) if gauges and head else None
        # The reach just above the mouth is this arm's only if NHDPlus names it
        # for this creek, or leaves it unnamed (reservoir reaches often are)
        # with a basin a creek's arm can have: a short arm's probe snaps to the
        # stream it flows into (Slaton Branch got Crow Creek's 623 km2).
        hb, mb = e.get("headBasinKm2"), e.get("mouthBasinKm2")
        mname = e.get("mouthNwmName") or ""
        named_here = bool(mname) and B.slug(mname) == B.slug(v["name"])
        plausible = bool(mb) and (hb is None or mb <= max(3 * hb, hb + 50))
        mouth_ok = bool(mb) and mb < MAX_MOUTH_BASIN_KM2 and (named_here or (not mname and plausible))
        implausible = mouth_ok and hb and mb > 10 * hb and mb - hb > 50
        flags = []
        if mb and not mouth_ok and mname and not named_here:
            flags.append(f"mouthReachIsAnotherStream:{mname}")
        if implausible:
            flags.append("mouthBasinImplausible")
            mouth_ok = False
        if hb is not None and hb < 2 and (v["reservoirKm"] or 0) > 5:
            flags.append("headBasinSuspect")
        if len(by_name[v["name"]]) > 1:
            flags.append("nameSharedWithAnotherSystem")
        nwps = (e.get("nwpsReach") or {}) if e.get("headComid") else {}
        if nwps and nwps.get("name") and B.slug(nwps["name"]) != B.slug(v["name"]):
            flags.append(f"nwmReachNamedOtherwise:{nwps['name']}")
        if not e.get("headComid"):
            flags.append("noNHDPlusComidAtHead")
        if not mouth_ok and not any(f.startswith("mouthReach") or f == "mouthBasinImplausible" for f in flags):
            flags.append("mouthBasinUnresolved")
        if v["reservoirKm"] < 0.2:
            flags.append("tinyReservoirReach")
        tl = top_level(s)
        recv_region = None
        if tl in top_mouths:
            recv_region = region_at(top_mouths[tl])
        cells = int(((label == code_of[s]) & ~ms_all).sum())
        ok_dist = d_mouth.get(s); ok_head = d_head.get(s)
        reservoir_path_km = None
        if ok_dist is not None and s in head_cell and head_cell[s] is not None:
            dm = ok_dist[idx[head_cell[s]]]
            reservoir_path_km = round(float(dm) / 1000, 2) if np.isfinite(dm) else None
        nat_km = e.get("upstreamMainstemKm")
        arm_list.append({
            "id": ident[s], "name": v["name"],
            "parent": (MAINSTEM_ID if parent.get(s) == main_sid else ident.get(parent.get(s))),
            "topLevel": ident[tl], "receivingRegion": recv_region,
            "mouth": [round(v["mouth"][1], 6), round(v["mouth"][0], 6)] if v["mouth"] else None,
            "head": [round(head[1], 6), round(head[0], 6)] if head else None,
            "mouthCounty": e.get("mouthCounty"),
            "reservoirPathKm": reservoir_path_km,
            "naturalChannelKm": nat_km,
            "armClass": ("largeTributaryArm" if (nat_km or 0) >= B.LARGE_ARM_KM else "minorTributary"),
            "nhdReachCodes": v["reachCodes"][:6],
            "nhdplusComidAtHead": e.get("headComid"),
            "drainageKm2AboveHead": e.get("headBasinKm2"),
            "nhdplusComidAtMouth": e.get("mouthComid") if mouth_ok else None,
            "drainageKm2AtMouth": e.get("mouthBasinKm2") if mouth_ok else None,
            "huc12": e.get("huc12"), "huc12Name": e.get("huc12Name"),
            "nwmFeatureId": str(e["headComid"]) if e.get("headComid") and nwps else None,
            "nwmReachName": nwps.get("name"),
            "usgsDischargeSite": gauge["site"] if gauge else None,
            "usgsDischargeSiteName": gauge["name"] if gauge else None,
            "usgsSitesUpstream": [x["site"] for x in up_sites],
            "flowSource": ("measuredUSGS" if gauge else ("modeledNWM" if nwps else "unavailable")),
            "waterCells": cells,
            "flags": flags,
        })
    ids = {x["id"] for x in arm_list}
    assert all(x["parent"] in ids or x["parent"] == MAINSTEM_ID for x in arm_list), "orphan arm"

    # ── graph nodes and edges (downstream)
    nodes = [{"id": UPSTREAM_DAM["id"], "kind": "dam", "name": UPSTREAM_DAM["name"], "tva": UPSTREAM_DAM["tva"],
              "at": [UPSTREAM_DAM["lat"], UPSTREAM_DAM["lon"]]}]
    edges = []
    for r_ in regions:
        nodes.append({"id": r_["id"], "kind": "mainStemRegion", "fromKm": r_["fromKm"], "toKm": r_["toKm"], "at": r_["center"]})
    nodes.append({"id": DOWNSTREAM_DAM["id"], "kind": "dam", "name": DOWNSTREAM_DAM["name"], "tva": DOWNSTREAM_DAM["tva"],
                  "at": [DOWNSTREAM_DAM["lat"], DOWNSTREAM_DAM["lon"]]})
    nodes.append({"id": "wheeler-lake", "kind": "downstream", "name": "Wheeler Lake (below Guntersville Dam)"})
    edges.append([UPSTREAM_DAM["id"], regions[0]["id"]])
    for r0, r1 in zip(regions[:-1], regions[1:]):
        edges.append([r0["id"], r1["id"]])
    edges += [[regions[-1]["id"], DOWNSTREAM_DAM["id"]], [DOWNSTREAM_DAM["id"], "wheeler-lake"]]
    for x in arm_list:
        hid, aid, mid = f"head:{x['id']}", f"arm:{x['id']}", f"mouth:{x['id']}"
        nodes += [{"id": hid, "kind": "armHead", "arm": x["id"], "at": x["head"]},
                  {"id": aid, "kind": "arm", "arm": x["id"]},
                  {"id": mid, "kind": "armMouth", "arm": x["id"], "at": x["mouth"]}]
        edges += [[hid, aid], [aid, mid]]
        edges.append([mid, (f"arm:{x['parent']}" if x["parent"] != MAINSTEM_ID else x["receivingRegion"])])

    # ── per-segment membership, before and after
    code_to_id = {code_of[s]: (MAINSTEM_ID if s == main_sid else ident[s]) for s in arms_raw}
    code_to_id[B.COVE] = MAINSTEM_ID
    region_ids = {k + 1: r_["id"] for k, r_ in enumerate(regions)}
    arm_by_id = {x["id"]: x for x in arm_list}
    reg_names = {t["name"] for t in reg["tributaries"]}
    def registry_level(arm_id):
        # the nearest ancestor-or-self whose name the old registry listed:
        # the level the old tributaryId lived at
        x = arm_by_id.get(arm_id)
        while x and x["name"] not in reg_names and x["parent"] != MAINSTEM_ID:
            x = arm_by_id.get(x["parent"])
        return x["id"] if x and x["name"] in reg_names else (arm_id if arm_id in arm_by_id else None)
    diff_rows, membership = [], []
    old_to_new = collections.Counter()
    for s, row in zip(segs, seg_rows):
        cell = tuple(row["cell"]) if row["cell"] else None
        arm_id = code_to_id.get(int(label[cell])) if cell else None
        if cell and ms_all[cell]:
            arm_id = MAINSTEM_ID
        near_is_ms = bool(cell and ms_nearest[cell])
        is_ms = arm_id == MAINSTEM_ID
        region = region_ids.get(int(reg_code[cell])) if (cell and is_ms) else None
        arm = arm_by_id.get(arm_id)
        top = arm["topLevel"] if arm else None
        rl = registry_level(arm_id) if arm else None
        dm = dh = None
        if arm and cell:
            sid = next(k for k, v in ident.items() if v == arm_id)
            if sid in d_mouth: dm = float(d_mouth[sid][idx[cell]])
            if sid in d_head: dh = float(d_head[sid][idx[cell]])
        dch = float(dchan[cell]) if cell else None
        old = s.get("tributaryId") or ("mainstem" if s["basinClass"] == "mainstem" else "unclassified")
        new_simple = "mainstem" if is_ms else (rl or "unclassified")
        old_name = next((t["name"] for t in reg["tributaries"] if t["id"] == old), old)
        new_name = arm_by_id[rl]["name"] if rl in arm_by_id else new_simple
        if old == new_simple:
            status = "same"
        elif old_name == new_name:
            status = "split:" + new_simple
        else:
            status = "reassigned"
        old_to_new[(old, new_simple)] += 1
        diff_rows.append({"segment": row["segment"], "lat": row["lat"], "lon": row["lon"],
                          "oldTributaryId": s.get("tributaryId") or "", "oldLakeRegion": s["lakeRegion"],
                          "oldBasinClass": s["basinClass"], "oldDistanceToTributaryM": s["distanceToTributaryM"],
                          "oldDistanceToChannelM": s["distanceToChannelM"],
                          "newArm": arm_id or "", "newTributaryId": new_simple if not is_ms else "",
                          "newTopLevel": top or "", "newMainStemRegion": region or "",
                          "newBasinClass": ("mainstem" if is_ms else (arm_by_id[rl]["armClass"] if rl in arm_by_id else "unknown")),
                          "newThroughWaterToMouthM": round(dm, 1) if dm is not None and np.isfinite(dm) else "",
                          "newThroughWaterToHeadM": round(dh, 1) if dh is not None and np.isfinite(dh) else "",
                          "newThroughWaterToChannelM": round(dch, 1) if dch is not None and np.isfinite(dch) else "",
                          "status": status, "nearestChannelVariantIsMainStem": near_is_ms})
        dnm = float(d_any_mouth[idx[cell]]) if cell else None
        membership.append({"segment": row["segment"], "id": s["id"], "arm": arm_id, "tributaryId": None if is_ms else new_simple,
                           "throughWaterToNearestMouthM": round(dnm, 1) if dnm is not None and np.isfinite(dnm) else None,
                           "basinClass": ("mainstem" if is_ms else (arm_by_id[rl]["armClass"] if rl in arm_by_id else "unknown")),
                           "lakeRegion": ("mainstem" if is_ms else (arm_by_id[rl]["name"] if rl in arm_by_id else "unclassified")),
                           "topLevel": top, "mainStemRegion": region,
                           "throughWaterToMouthM": round(dm, 1) if dm is not None and np.isfinite(dm) else None,
                           "throughWaterToHeadM": round(dh, 1) if dh is not None and np.isfinite(dh) else None,
                           "throughWaterToChannelM": round(dch, 1) if dch is not None and np.isfinite(dch) else None})
    with open(os.path.join(a.out, "membership_diff.csv"), "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(diff_rows[0].keys())); w.writeheader(); w.writerows(diff_rows)
    json.dump({"lakeId": B.LAKE_ID, "segments": membership}, open(os.path.join(a.out, "segment_membership.json"), "w"))

    # ── registry audit
    audit = []
    for t in reg["tributaries"]:
        cands = [x for x in arm_list if x["name"] == t["name"]]
        match = min(cands, key=lambda x: km(tuple(t["confluence"]), tuple(x["mouth"]))) if cands and t["confluence"] and all(c["mouth"] for c in cands) else (cands[0] if cands else None)
        row = {"registryId": t["id"], "name": t["name"], "systemsWithThisName": len(cands),
               "oldConfluence": t["confluence"], "oldEmbaymentHead": t["embaymentHead"],
               "oldNaturalChannelKm": t["naturalChannelKm"], "oldReservoirPathKm": t["reservoirPathKm"],
               "oldReachCode": t["reachCode"], "oldUsgsSite": t["usgsSite"], "oldNwmFeatureId": t["nwmFeatureId"],
               "oldSegments": sum(1 for s in segs if s.get("tributaryId") == t["id"])}
        if match:
            row.update({"newArm": match["id"], "newMouth": match["mouth"], "newHead": match["head"],
                        "mouthMovedKm": round(km(tuple(t["confluence"]), tuple(match["mouth"])), 2) if t["confluence"] and match["mouth"] else None,
                        "headMovedKm": round(km(tuple(t["embaymentHead"]), tuple(match["head"])), 2) if t["embaymentHead"] and match["head"] else None,
                        "newNaturalChannelKm": match["naturalChannelKm"], "newReservoirPathKm": match["reservoirPathKm"],
                        "newNhdplusComid": match["nhdplusComidAtHead"], "newHuc12": match["huc12"],
                        "newNwmFeatureId": match["nwmFeatureId"], "newUsgsDischargeSite": match["usgsDischargeSite"],
                        "newSegments": sum(1 for m in membership if m["tributaryId"] == match["id"]),
                        "flags": ";".join(match["flags"])})
            # where the old gauge / NWM id really belong
            if t["usgsSite"] and t["usgsSite"] != match["usgsDischargeSite"]:
                owner = next((x["id"] for x in arm_list if t["usgsSite"] in x["usgsSitesUpstream"]), None)
                row["oldUsgsSiteBelongsTo"] = owner
            if t["nwmFeatureId"] and str(t["nwmFeatureId"]) != str(match["nwmFeatureId"]):
                owner = next((x["id"] for x in arm_list if str(x["nhdplusComidAtHead"]) == str(t["nwmFeatureId"])), None)
                row["oldNwmIdBelongsTo"] = owner or "not an arm head"
        audit.append(row)
    keys = sorted({k for r_ in audit for k in r_}, key=lambda k: list(audit[0].keys()).index(k) if k in audit[0] else 99)
    with open(os.path.join(a.out, "registry_audit.csv"), "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=keys); w.writeheader(); w.writerows(audit)

    # ── runtime graph + cell grid
    arm_index = {x["id"]: k + 1 for k, x in enumerate(arm_list)}
    cell_arm = np.zeros(water.shape, dtype=np.uint8)
    for code, aid in code_to_id.items():
        if aid in arm_index:
            cell_arm[(label == code) & ~ms_all] = arm_index[aid]
    graph = {"lakeId": B.LAKE_ID, "version": 1,
             "sources": {"flowlines": "USGS NHD High Resolution (cached 2026-09-19)",
                         "lakeOutline": "NHD waterbody (Guntersville)",
                         "network": "USGS NLDI / NHDPlus V2", "huc": "USGS WBD", "nwm": "NOAA NWPS reaches",
                         "method": "through-water network allocation (multi-source Dijkstra on the Water Clarity frame)"},
            "mainStem": {"id": MAINSTEM_ID, "name": B.MAINSTEM_NAME, "lengthKm": round(L / 1000, 2),
                         "upstreamDam": UPSTREAM_DAM, "downstreamDam": DOWNSTREAM_DAM, "regions": regions},
            "arms": arm_list, "nodes": nodes, "edges": edges}
    json.dump(graph, open(os.path.join(a.out, "guntersville.hydrology.json"), "w"), indent=1)
    json.dump({"lakeId": B.LAKE_ID, "width": fr["width"], "height": fr["height"], "cornersLonLat": fr["corners"],
               "cellMetresMercator": fr["cell"], "arms": [None] + [x["id"] for x in arm_list],
               "regions": [None] + [r_["id"] for r_ in regions],
               "armGrid": encode_grid(cell_arm), "regionGrid": encode_grid(reg_code),
               "encoding": "zlib(uint8 row-major, top row first), base64; 0 = main stem (armGrid) / none"},
              open(os.path.join(a.out, "guntersville.arm_cells.json"), "w"))

    # ── summary
    st = collections.Counter(r_["status"].split(":")[0] for r_ in diff_rows)
    print("segments:", dict(st))
    print("arms:", len(arm_list), "regions:", len(regions), "nodes:", len(nodes), "edges:", len(edges))
    print("flow sources:", collections.Counter(x["flowSource"] for x in arm_list))
    print("gauged arms:", [(x["id"], x["usgsDischargeSite"]) for x in arm_list if x["usgsDischargeSite"]])
    print("top old->new moves:", [(k, v) for k, v in old_to_new.most_common(40) if k[0] != k[1]][:25])


if __name__ == "__main__":
    main()
