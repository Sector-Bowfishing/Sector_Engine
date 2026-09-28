"""Hydrologic arm graph and tributary membership for one lake, by water
connectivity (Clarity Fusion Stage 1).

The old lake profile gave a shoreline segment to a tributary by NAME and
STRAIGHT-LINE distance: every NHD flowline called "Town Creek" was merged into
one line, and a bank within 6 km of any part of it (including the creek's
channel on land) became Town Creek's. Two different Town Creeks, 36 km apart,
shared one identity and one gauge.

Here membership follows the water:

  1. NHD HR flowlines become a directed network (they are digitized
     downstream; endpoints are shared at junctions).
  2. A "system" is a connected run of same-named flowlines. Two separate
     creeks with the same name are two systems. An unnamed flowline belongs to
     the named system it drains into.
  3. Each system's flowlines inside the lake are burned onto the lake's water
     lattice (the Water Clarity frame, ~30 m cells) as seeds, and every water
     cell takes the system it reaches first THROUGH THE WATER (multi-source
     Dijkstra, 8-neighbour, metres). A cove across a peninsula is reached
     through its own arm, never across the land.
  4. A system's mouth is where its last flowline hands the water to another
     system; its head is where its channel enters the lake. The main stem
     (Tennessee River) is cut into regions between tributary mouths.

Outputs (in --out):
  <lake>.hydrology.json      the runtime graph (nodes, edges, arms, segment
                             membership, cell-label grid on the clarity frame)
  <lake>.arm_labels.png      the cell-label grid as an image (for review)
  membership_diff.csv        every segment: old vs new tributary

usage: geo/bin/python build_arm_graph.py --out DIR
"""
import os, sys, json, gzip, math, argparse, collections, base64, zlib
import numpy as np
from scipy import sparse
from scipy.sparse import csgraph
from shapely.geometry import shape, Point, LineString, mapping
from shapely.ops import unary_union
import pyproj
import rasterio.features

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "jobs", "lake-surface"))
import derive_water_surface as dws
import fill_lake

IOS = os.path.expanduser("~/Desktop/Development/iOS/Sector-mapbox")
CACHE = os.path.join(IOS, ".fishintel-cache", "guntersville")
ASSETS = os.path.join(IOS, "Sector", "Assets.xcassets", "FishIntel")
LAKE_ID = "Guntersville|AL"
MAINSTEM_NAME = "Tennessee River"
SNAP_M = 150.0            # a shoreline anchor's water cell must be this close
REGION_KM = 5.0           # main-stem regions no longer than this along the channel
LARGE_ARM_KM = 15.0       # natural channel length dividing large from minor (as before)
UPSTREAM_DAM = (35.0035, -85.6198)   # Nickajack Dam: where Guntersville's main stem begins
COVE = 32000              # label code: an unnamed cove draining straight to the main stem

TO_M = pyproj.Transformer.from_crs("EPSG:4326", "EPSG:3857", always_xy=True)


def slug(s):
    return "".join(c if c.isalnum() else "-" for c in s.lower()).strip("-").replace("--", "-")


def key(xy):
    return (round(xy[0], 7), round(xy[1], 7))


# ─────────────────────────────── network ─────────────────────────────────────

def load_network(flowlines):
    """Directed flowline network: each flowline goes from its first to its
    last vertex. Returns (lines, down, up) where down[i] / up[i] are the
    flowlines that start where i ends / end where i starts."""
    lines = []
    for f in flowlines:
        c = f["geometry"]["coordinates"]
        p = f["properties"]
        lines.append({"i": len(lines), "name": p.get("gnis_name") or "", "ftype": p["ftype"],
                      "reach": p.get("reachcode") or "", "pid": p["permanent_identifier"],
                      "km": p.get("lengthkm") or 0.0, "geom": LineString(c),
                      "a": key(c[0]), "b": key(c[-1])})
    starts = collections.defaultdict(list); ends = collections.defaultdict(list)
    for l in lines:
        starts[l["a"]].append(l["i"]); ends[l["b"]].append(l["i"])
    down = {l["i"]: [j for j in starts[l["b"]] if j != l["i"]] for l in lines}
    up = {l["i"]: [j for j in ends[l["a"]] if j != l["i"]] for l in lines}
    return lines, down, up


def up_of_point(lines, node):
    return [l["i"] for l in lines if l["b"] == node]


def systems_of(lines, down, up):
    """Connected runs of same-named flowlines -> system ids. Unnamed lines
    take the system of the first named line downstream of them."""
    name_of = {l["i"]: l["name"] for l in lines}
    sys_of = {}
    systems = []
    for l in lines:
        if not l["name"] or l["i"] in sys_of:
            continue
        sid = len(systems)
        stack = [l["i"]]; members = []
        while stack:
            i = stack.pop()
            if i in sys_of:
                continue
            sys_of[i] = sid; members.append(i)
            for j in down[i] + up[i]:
                if name_of[j] == l["name"] and j not in sys_of:
                    stack.append(j)
        systems.append({"sid": sid, "name": l["name"], "lines": members})
    # Unnamed lines. One that CARRIES a named creek's water (downstream of it,
    # through other unnamed lines) is that creek's continuation: NHD often
    # runs a creek's flow path on through a wide arm as unnamed connectors
    # down to the river, and giving those to the river made the lower arm a
    # river cove. Where two creeks' water meets in an unnamed line, the one
    # with the longer path above it keeps it. An unnamed line no named creek
    # drains through is a feeder: it belongs to the first named system
    # downstream of it.
    length_above = {}
    def above(i, seen=()):
        if i in length_above:
            return length_above[i]
        best = 0.0
        for j in up[i]:
            if j not in seen:
                best = max(best, above(j, seen + (i,)))
        length_above[i] = best + lines[i]["km"]
        return length_above[i]
    sys.setrecursionlimit(1_000_000)
    carry = {}                       # unnamed line -> (named length above, sid)
    for sid, sy in enumerate(systems):
        mine = max((above(k) for k in sy["lines"]), default=0.0)
        frontier = [j for i in sy["lines"] for j in down[i] if not name_of[j]]
        while frontier:
            nxt = []
            for j in frontier:
                best = carry.get(j)
                if best is not None and (best[1] == sid or best[0] >= mine):
                    continue
                carry[j] = (mine, sid)
                nxt += [k for k in down[j] if not name_of[k]]
            frontier = nxt
    role = {}
    for l in lines:
        if l["name"]:
            role[l["i"]] = "named"
    for j, (_, sid) in carry.items():
        sys_of[j] = sid; systems[sid]["lines"].append(j); role[j] = "continuation"
    for l in lines:
        if l["name"] or l["i"] in sys_of:
            continue
        seen = {l["i"]}; frontier = [l["i"]]; found = None
        while frontier and found is None:
            nxt = []
            for i in frontier:
                for j in down[i]:
                    if j in seen:
                        continue
                    seen.add(j)
                    if j in sys_of:
                        found = sys_of[j]; break
                    nxt.append(j)
                if found is not None:
                    break
            frontier = nxt
        if found is not None:
            sys_of[l["i"]] = found
            systems[found]["lines"].append(l["i"]); role[l["i"]] = "feeder"
    for sy in systems:
        sy["role"] = role
    return systems, sys_of


def longest_paths(system, lines, down, up):
    """Longest upstream length (km) ending at each member line, within the
    system (NHD braids are a DAG; a cycle, if any, is broken by visit order)."""
    members = set(system["lines"])
    memo = {}
    def L(i, stack=()):
        if i in memo:
            return memo[i]
        if i in stack:
            return 0.0
        best = 0.0
        for j in up[i]:
            if j in members:
                best = max(best, L(j, stack + (i,)))
        memo[i] = best + lines[i]["km"]
        return memo[i]
    sys.setrecursionlimit(100000)
    for i in system["lines"]:
        L(i)
    return memo


def outlet_of(system, lines, down, up, sys_of, lp):
    """The system's mouth: the downstream end of the member line that ends
    the system's LONGEST path and hands its water to another system (or runs
    off the map). A braid that touches another system halfway down is not
    the mouth. Returns (node, receiving sid or None, line index)."""
    members = set(system["lines"])
    exits = [i for i in system["lines"] if not down[i] or any(j not in members for j in down[i])]
    if not exits:
        return None, None, None
    i = max(exits, key=lambda k: lp[k])
    recv = [sys_of.get(j) for j in down[i] if j not in members]
    return lines[i]["b"], (recv[0] if recv else None), i


# ─────────────────────────────── lattice ─────────────────────────────────────

def burn(frame, geoms_values, all_touched=True):
    shapes = [(mapping(shp_to_merc(g)), v) for g, v in geoms_values]
    return rasterio.features.rasterize(shapes, out_shape=(frame.height, frame.width),
                                       transform=frame.transform, fill=0, all_touched=all_touched,
                                       dtype="int32")


def shp_to_merc(g):
    from shapely.ops import transform
    return transform(lambda x, y, z=None: TO_M.transform(x, y), g)


def cell_of(frame, lon, lat):
    x, y = TO_M.transform(lon, lat)
    c, r = ~frame.transform * (x, y)
    return int(r), int(c)


# ─────────────────────────────── build ───────────────────────────────────────

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)

    lake = unary_union([shape(f["geometry"]) for f in json.load(open(os.path.join(CACHE, "waterbody.geojson")))["features"]])
    fl = json.load(open(os.path.join(CACHE, "flowlines.geojson")))["features"]
    reg = json.load(gzip.open(os.path.join(ASSETS, "GuntersvilleTributaries.dataset", "Guntersville.tributaries.json.gz")))
    segs = json.load(gzip.open(os.path.join(ASSETS, "GuntersvilleSegments.dataset", "Guntersville.segments.json.gz")))["segments"]

    lines, down, up = load_network(fl)
    systems, sys_of = systems_of(lines, down, up)
    lake_b = lake.buffer(0.0005)
    in_lake = {l["i"] for l in lines if l["ftype"] == 558 and l["geom"].intersects(lake_b)}
    main_sids = {s["sid"] for s in systems if s["name"] == MAINSTEM_NAME}
    # systems that carry water inside the lake
    lake_sys = sorted({sys_of[i] for i in in_lake if i in sys_of})
    print(f"{len(lines)} flowlines, {len(systems)} named systems, {len(lake_sys)} carry water in the lake "
          f"({len(main_sids)} main-stem system(s))")
    # Same-named systems in the lake: the name-union defect, surfaced.
    by_name = collections.defaultdict(list)
    for sid in lake_sys:
        by_name[systems[sid]["name"]].append(sid)
    dup = {n: s for n, s in by_name.items() if len(s) > 1}
    print("names carried by more than one separate system in the lake:", {n: len(s) for n, s in dup.items()})

    # ── frame and water lattice (the Water Clarity frame, so cells line up)
    dws.UTM = "EPSG:32616"
    frame = dws.Frame(lake, cell=dws.CLARITY_CELL)
    masks = dws.lake_masks(lake, frame)
    G = frame.cell_ground_m()
    # The centre burn only: an all-touched burn would join the two sides of a
    # peninsula narrower than a cell. Pieces the centre burn cuts off are
    # rejoined through touched cells (fill_lake._bridges), as the clarity
    # fill does.
    lake_c = masks["lake"]

    # ── seeds: each lake system's in-lake flowlines, burned on the water
    code_of = {sid: k + 1 for k, sid in enumerate(lake_sys)}
    seeds = burn(frame, [(lines[i]["geom"], code_of[sys_of[i]]) for i in in_lake if i in sys_of])
    # Every piece the centre burn cut off is rejoined to the lake's main body
    # (the piece the river channel runs through). A narrow upper arm keeps its
    # own creek line, so "pieces without a seed" would leave it an island.
    chan0 = burn(frame, [(lines[i]["geom"], 1) for i in in_lake
                         if sys_of.get(i) in main_sids and lines[i]["name"] == MAINSTEM_NAME])
    lab0, _ = __import__("scipy.ndimage", fromlist=["label"]).label(lake_c)
    anchored = np.isin(lab0, np.unique(lab0[(chan0 > 0) & lake_c])) & lake_c
    bridges = fill_lake._bridges(lake_c, masks["lake_touch"].astype(bool), anchored) \
        if (lake_c & ~anchored).any() else np.zeros(lake_c.shape, bool)
    water = lake_c | bridges
    idx = fill_lake._index(water)
    A = fill_lake._graph8(water, idx, G)
    print(f"frame {frame.width}x{frame.height}, {int(water.sum()):,} water cells "
          f"({int(bridges.sum())} bridge cells), {G:.1f} m")
    seeds[~water] = 0
    # The main stem's CHANNEL is its named lines. Unnamed lines that drain
    # straight to the main stem are coves: they seed their own water (code
    # COVE) instead of stretching the channel into every unnamed cove.
    main_code = code_of[min(main_sids)] if main_sids else None
    chan = burn(frame, [(lines[i]["geom"], 1) for i in in_lake
                        if sys_of.get(i) in main_sids and lines[i]["name"] == MAINSTEM_NAME])
    cove = burn(frame, [(lines[i]["geom"], 1) for i in in_lake
                        if sys_of.get(i) in main_sids and not lines[i]["name"]])
    seeds[(seeds == main_code)] = 0
    seeds[(cove > 0) & water & (seeds == 0)] = COVE
    def allocate(seed_grid):
        cells = idx[seed_grid > 0]; codes = seed_grid[seed_grid > 0]
        dist, _, sources = csgraph.dijkstra(A, directed=False, indices=cells, min_only=True,
                                            return_predecessors=True)
        at = dict(zip(cells.tolist(), codes.tolist()))
        lab = np.zeros(water.shape, dtype=np.int32)
        lab[water] = np.array([at.get(int(x), 0) if x >= 0 else 0 for x in sources], dtype=np.int32)
        dd = np.full(water.shape, np.nan, dtype=np.float32); dd[water] = dist
        return lab, dd
    # arms and coves, the channel left out: who reaches each cell first
    label, dseed = allocate(seeds)
    # the channel alone: how far each cell is from the river, through the water
    chan_seed = np.where((chan > 0) & water, main_code, 0).astype(np.int32)
    _, dchan = allocate(chan_seed)
    print(f"allocated {int((label > 0).sum()):,} of {int(water.sum()):,} water cells to arms/coves; "
          f"{int(((chan > 0) & water).sum()):,} channel cells")
    np.save(os.path.join(a.out, "dchan.npy"), dchan)
    np.save(os.path.join(a.out, "seeds.npy"), seeds)
    np.save(os.path.join(a.out, "chan.npy"), (chan > 0) & water)

    # ── arms: mouths, heads, receiving system, lengths
    sid_of_code = {v: k for k, v in code_of.items()}
    arms = {}
    for sid in lake_sys:
        s = systems[sid]
        lp = longest_paths(s, lines, down, up)
        mouth, recv, mline = outlet_of(s, lines, down, up, sys_of, lp)
        lake_lines = [i for i in s["lines"] if i in in_lake]
        natural = [i for i in s["lines"] if lines[i]["ftype"] == 460]
        # main natural channel: the longest run of natural lines ending at a head
        nat_set = set(natural)
        def nat_len(i, seen=()):
            best = 0.0
            for j in up[i]:
                if j in nat_set and j not in seen:
                    best = max(best, nat_len(j, seen + (j,)))
            return best + (lines[i]["km"] if i in nat_set else 0.0)
        # head: the upstream end of an in-lake line whose upstream neighbour
        # is a natural channel of the same system (channel meets reservoir)
        # Heads: where the system's water ENTERS THE LAKE OUTLINE. NHD carries
        # some creeks as artificial paths through wide valley floors for tens
        # of km above the reservoir (Town Creek, South Sauty), so a line's type
        # cannot say where the lake begins; the lake's own outline can. An
        # entry is an in-lake line none of whose upstream lines is in the lake;
        # the head is its first vertex inside the outline.
        strict = [i for i in s["lines"] if lines[i]["geom"].intersects(lake)]
        sset = set(strict)
        heads = []
        for i in strict:
            if any(j in sset for j in up[i]):
                continue
            pt = next((c for c in lines[i]["geom"].coords if lake.contains(Point(c))),
                      lines[i]["geom"].intersection(lake).representative_point().coords[0])
            heads.append((key(pt), lp[i] - lines[i]["km"]))
        # the main head: the one with the longest channel above it. The main
        # stem's head is the upstream dam, whatever the braids say.
        heads.sort(key=lambda h: -h[1])
        if sid in main_sids:
            nk = UPSTREAM_DAM
            best = min(((lines[i]["geom"].distance(Point(nk[1], nk[0])), i) for i in strict))
            p0 = lines[best[1]]["geom"].interpolate(lines[best[1]]["geom"].project(Point(nk[1], nk[0])))
            heads = [(key(p0.coords[0]), 0.0)] + heads
        # A probe ~300 m up the channel above the main head, for NLDI (a query
        # at the head itself snaps to the reservoir line).
        # Probes up the main channel above the main head (~300 m, 1 km, 2 km,
        # 4 km), for NLDI: a query at the head itself snaps to the reservoir
        # line, and a small creek's first NHDPlus reach can sit well up it.
        probes = []
        if heads and sid not in main_sids:
            hp = Point(heads[0][0])
            li = min(s["lines"], key=lambda i: lines[i]["geom"].distance(hp))
            for want in (0.003, 0.01, 0.02, 0.04):
                cur, d = li, lines[li]["geom"].project(hp)
                need = want
                while cur is not None and need > d:
                    need -= d
                    feeders = [j for j in up[cur] if sys_of.get(j) == sid]
                    if not feeders:
                        cur = None; break
                    cur = max(feeders, key=lambda j: lp.get(j, 0.0))
                    d = lines[cur]["geom"].length
                if cur is not None:
                    probes.append(lines[cur]["geom"].interpolate(d - need).coords[0])
        probe = probes[0] if probes else None
        arms[sid] = {"sid": sid, "name": s["name"], "mouth": mouth, "receiving": recv,
                     "heads": [h[0] for h in heads], "mainChannelKmInCache": round(heads[0][1], 2) if heads else 0.0,
                     "probe": probe, "probes": probes,
                     "mouthProbe": (lines[mline]["geom"].interpolate(max(0.0, lines[mline]["geom"].length - 0.003)).coords[0]
                                    if mline is not None else None),
                     "reservoirKm": round(sum(lines[i]["km"] for i in lake_lines), 2),
                     "naturalKmInCache": round(sum(lines[i]["km"] for i in natural), 2),
                     "reachCodes": sorted({lines[i]["reach"] for i in lake_lines if lines[i]["reach"]})}
    json.dump({"arms": {str(k): {kk: vv for kk, vv in v.items()} for k, v in arms.items()},
               "codes": {str(k): v for k, v in code_of.items()}},
              open(os.path.join(a.out, "arms_raw.json"), "w"), indent=1, default=list)

    # ── old vs new, per segment
    old_by_seg = {}
    rows = []
    reg_by_id = {t["id"]: t for t in reg["tributaries"]}
    for s in segs:
        r, c = cell_of(frame, s["anchor"][1], s["anchor"][0])
        # nearest water cell within SNAP_M (straight line is safe at this range:
        # the anchor sits on the water's own edge)
        best = None
        rad = int(SNAP_M / G) + 1
        for dr in range(-rad, rad + 1):
            for dc in range(-rad, rad + 1):
                rr, cc = r + dr, c + dc
                if 0 <= rr < frame.height and 0 <= cc < frame.width and label[rr, cc] > 0:
                    d = math.hypot(dr, dc) * G
                    if d <= SNAP_M and (best is None or d < best[0]):
                        best = (d, rr, cc)
        new_sid = sid_of_code.get(int(label[best[1], best[2]])) if best else None
        rows.append({"segment": f"{s['ring']}:{s['indexInRing']}", "lat": s["anchor"][0], "lon": s["anchor"][1],
                     "oldTributary": s.get("tributaryId") or "", "oldRegion": s["lakeRegion"],
                     "oldBasin": s["basinClass"], "newSystem": new_sid,
                     "newName": systems[new_sid]["name"] if new_sid is not None else "",
                     "cell": [best[1], best[2]] if best else None})
    json.dump(rows, open(os.path.join(a.out, "segment_rows_raw.json"), "w"))
    np.save(os.path.join(a.out, "label.npy"), label)
    np.save(os.path.join(a.out, "dseed.npy"), dseed)
    np.save(os.path.join(a.out, "water.npy"), water)
    json.dump({"frame": {"width": frame.width, "height": frame.height, "cell": frame.cell,
                         "corners": frame.corners(), "cellGroundM": G, "bounds": list(frame.bounds)}},
              open(os.path.join(a.out, "frame.json"), "w"))
    print("wrote raw outputs to", a.out)


if __name__ == "__main__":
    main()
